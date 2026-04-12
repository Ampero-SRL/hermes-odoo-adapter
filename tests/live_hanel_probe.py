#!/usr/bin/env python3
"""
Live HOST-COM integration probe — talks to a real Hanel MP 12N.

This is NOT a unit test. It opens a TCP connection to the MP on port
2200 and walks through the full ASRS flow the orchestrator will use,
without requiring Docker, ROS2, Odoo, or any robot. Useful for:

  1. Verifying the MP is reachable and speaks HOST-COM on this machine.
  2. Watching the actual telegrams fly (every byte is logged).
  3. Proving the "skip if tray already at pickup" optimization works.
  4. Rehearsing the RETURN-key auto-press timing.

Usage
-----
    HANEL_HOST=192.168.x.x python3 tests/live_hanel_probe.py [TRAY]

    TRAY        target tray number (default: 8)

    HANEL_HOST           MP IP address                    (required)
    HANEL_PORT           MP TCP port                      (default 2200)
    HANEL_ELEVATOR       elevator number 1-99             (default 1)
    HANEL_PICKUP         pickup point number 1-8          (default 1)
    PROBE_MODE           read_status | get_shelf | cycle  (default cycle)
                         - read_status : query state only, no motion
                         - get_shelf   : fetch target tray
                         - cycle       : read_status → get_shelf → skip-test

Flow
----
The probe is intentionally verbose. It logs every outbound and inbound
telegram, the state transitions of each job, and the final value of
``_current_tray`` so you can verify the state-tracking logic with your
own eyes against the physical Hanel panel display.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from hermes_odoo_adapter.warehouse.hanel_hostcom import (  # noqa: E402
    HanelHostComClient,
)


LOG_FMT = "%(asctime)s.%(msecs)03d %(levelname)-5s %(message)s"
logging.basicConfig(level=logging.DEBUG, format=LOG_FMT, datefmt="%H:%M:%S")
log = logging.getLogger("probe")


def env(key: str, default: str) -> str:
    return os.environ.get(key, default).strip()


async def wait_for_job(client: HanelHostComClient, job_id: str,
                       timeout: float = 120.0) -> None:
    """Poll client.get_pick_status like the mission controller would."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        status = await client.get_pick_status(job_id)
        log.info("  poll: status=%-10s slot=%-10s ready=%s",
                 status.status, status.slot, status.tray_ready)
        if status.tray_ready:
            return
        if status.status == "failed":
            raise RuntimeError(f"job {job_id} failed")
        await asyncio.sleep(2.0)
    raise TimeoutError(f"job {job_id} did not become ready within {timeout}s")


async def main() -> int:
    host = env("HANEL_HOST", "")
    if not host:
        log.error("HANEL_HOST environment variable is required")
        log.error("  example: HANEL_HOST=192.168.1.50 python3 %s", sys.argv[0])
        return 2

    port = int(env("HANEL_PORT", "2200"))
    elevator = int(env("HANEL_ELEVATOR", "1"))
    pickup = int(env("HANEL_PICKUP", "1"))
    tray = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    mode = env("PROBE_MODE", "cycle")

    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info("HOST-COM probe")
    log.info("  MP          : %s:%d", host, port)
    log.info("  elevator    : %d", elevator)
    log.info("  pickup point: %d", pickup)
    log.info("  target tray : %d", tray)
    log.info("  mode        : %s", mode)
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    client = HanelHostComClient(
        host=host,
        port=port,
        elevator_num=elevator,
        pickup_point=pickup,
        sku_tray_map={"PROBE-SKU": tray},
        default_tray=tray,
        connect_timeout=5.0,
    )

    try:
        log.info("connecting …")
        await client.connect()
    except Exception as exc:
        log.error("CONNECT FAILED: %s", exc)
        log.error("Check: (1) MP is powered on, (2) network route from this")
        log.error("machine to %s is open, (3) port 2200 is not firewalled.", host)
        return 1

    try:
        # ---------- Phase 1: read_status --------------------------------
        if mode in ("read_status", "cycle"):
            log.info("")
            log.info("━━━ Phase 1: read_status (query current pickup state) ━━━")
            current = await client.refresh_pickup_state(timeout=5.0)
            if current is None:
                log.warning("no response from read_status — MP may be busy")
            else:
                log.info("✓ MP reports tray %d at pickup point", current)

        if mode == "read_status":
            return 0

        # ---------- Phase 2: get_shelf for target tray ------------------
        log.info("")
        log.info("━━━ Phase 2: get_shelf PM1=%d ━━━", tray)
        if client._current_tray == tray:
            log.info("NOTE: tray %d is already at pickup — the call will be", tray)
            log.info("      short-circuited and no elevator motion will occur.")
            log.info("      To exercise real motion, first extract the tray")
            log.info("      manually or send store_shelf.")

        result = await client.send_pick_order(
            job_id="probe-001", sku="PROBE-SKU", quantity=1,
        )
        log.info("send_pick_order returned: success=%s err=%s",
                 result.success, result.error)
        if not result.success:
            return 1

        log.info("")
        log.info("━━━ Phase 2b: poll until ready ━━━")
        log.info("(operator / auto-press bot must press GREEN RETURN on panel)")
        try:
            await wait_for_job(client, "probe-001", timeout=120.0)
            log.info("✓ TRAY %d IS AT THE PICKUP POINT", tray)
            log.info("  client._current_tray = %s", client._current_tray)
        except TimeoutError as exc:
            log.error("TIMEOUT: %s", exc)
            return 1
        except RuntimeError as exc:
            log.error("FAILED: %s", exc)
            return 1

        if mode != "cycle":
            return 0

        # ---------- Phase 3: skip optimization check --------------------
        log.info("")
        log.info("━━━ Phase 3: re-call get_shelf for the same tray ━━━")
        log.info("(should short-circuit — ZERO telegrams on the wire)")
        result2 = await client.send_pick_order(
            job_id="probe-002", sku="PROBE-SKU", quantity=1,
        )
        status2 = await client.get_pick_status("probe-002")
        log.info("send_pick_order returned: success=%s", result2.success)
        log.info("status: %s (ready=%s)", status2.status, status2.tray_ready)
        if status2.tray_ready:
            log.info("✓ skip optimization works as designed")
        else:
            log.error("✗ skip did NOT trigger — state tracking may be broken")
            return 1

        return 0
    finally:
        log.info("")
        log.info("closing …")
        await client.close()


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
