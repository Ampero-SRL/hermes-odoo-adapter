"""
Tests for HanelHostComClient — telegram building, parsing, state
transitions, and the "skip call when tray already at pickup" optimization.

Runs without a physical MP controller by patching the TCP transport:
- ``_send`` is captured into a list so we can assert outbound telegrams.
- Inbound telegrams are injected directly via ``_handle_telegram``.

Run:
    cd hermes_odoo_adapter
    python3 -m pytest tests/test_hanel_hostcom.py -v
    # or standalone:
    python3 tests/test_hanel_hostcom.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow running without installing the package
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from hermes_odoo_adapter.warehouse.hanel_hostcom import (  # noqa: E402
    HanelHostComClient,
    _Job,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_client(**overrides) -> HanelHostComClient:
    """Build a client with capture-only _send (no real TCP)."""
    kwargs = dict(
        host="127.0.0.1",
        port=2200,
        elevator_num=1,
        pickup_point=1,
        sku_tray_map={"EL-SAFETY-RELAY": 1, "EL-CONTACTOR": 8},
        default_tray=8,
    )
    kwargs.update(overrides)
    client = HanelHostComClient(**kwargs)

    # Fake a "connected" state so send_pick_order doesn't bail early.
    client._writer = object()  # sentinel, never touched because _send is patched
    client._sent: list[str] = []

    async def capture_send(telegram: str) -> None:
        client._sent.append(telegram)

    client._send = capture_send  # type: ignore
    return client


def feed(client: HanelHostComClient, line: str) -> None:
    """Inject an inbound telegram as if the reader loop had received it."""
    client._handle_telegram(line)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_request_telegram_format() -> None:
    client = make_client()
    result = await client.send_pick_order("job-A", "EL-CONTACTOR", 1)
    assert result.success, result.error
    assert len(client._sent) == 1
    tx = client._sent[0]
    # Header: *G0011:2301$U XR$001$ ; body: macro=get_shelf$PM1=8$PM14=1$\r\n
    assert tx.startswith("*G0011:2301$U XR$001$"), tx
    assert "macro=get_shelf$" in tx
    assert "PM1=8$" in tx
    assert "PM14=1$" in tx
    assert tx.endswith("\r\n")
    print("  ✓ request telegram:", tx.rstrip())


async def test_sku_to_tray_mapping_override() -> None:
    client = make_client()
    # EL-SAFETY-RELAY is mapped to tray 1 (override), not default 8
    await client.send_pick_order("job-S", "EL-SAFETY-RELAY", 2)
    tx = client._sent[0]
    assert "PM1=1$" in tx, tx
    print("  ✓ mapped SKU → tray 1:", tx.rstrip())


async def test_sku_default_tray() -> None:
    client = make_client()
    # Unknown SKU falls back to default_tray=8
    await client.send_pick_order("job-X", "UNKNOWN-SKU", 1)
    tx = client._sent[0]
    assert "PM1=8$" in tx, tx
    print("  ✓ unknown SKU → default tray 8")


async def test_status_accepted_then_response_ready() -> None:
    client = make_client()
    await client.send_pick_order("job-A", "EL-CONTACTOR", 1)
    job = client._jobs_by_id["job-A"]
    assert job.status in ("submitted", "presenting")

    # MP replies: accepted
    feed(client, f"*G2301:0011$V XS${job.seq}$E00$")
    assert job.status == "presenting"

    # Info: motion started
    feed(client, f"*G2301:0011$V XI${job.seq}$ER=01&L=1&E=1$")
    # Info: waiting for RETURN
    feed(client, f"*G2301:0011$V XI${job.seq}$ER=02&L=1&E=1$")
    assert job.status == "presenting"

    # Final response: success, T=8 means tray 8 is now at pickup
    feed(client, f"*G2301:0011$V XA${job.seq}$ER=00&L=1&E=1&T=8&U=1_000&I=0&J=0$")
    assert job.status == "ready", job.status
    assert client._current_tray == 8

    status = await client.get_pick_status("job-A")
    assert status.tray_ready is True
    assert status.slot == "TRAY-8"
    print("  ✓ lifecycle: submitted → presenting → ready (current_tray=8)")


async def test_status_rejected() -> None:
    client = make_client()
    await client.send_pick_order("job-B", "EL-CONTACTOR", 1)
    job = client._jobs_by_id["job-B"]
    feed(client, f"*G2301:0011$V XS${job.seq}$E02$")  # another cmd in progress
    assert job.status == "failed"
    assert "E02" in job.error
    print("  ✓ rejected status E02 → job failed:", job.error)


async def test_response_aborted() -> None:
    client = make_client()
    await client.send_pick_order("job-C", "EL-CONTACTOR", 1)
    job = client._jobs_by_id["job-C"]
    feed(client, f"*G2301:0011$V XS${job.seq}$E00$")
    feed(client, f"*G2301:0011$V XA${job.seq}$ER=99&L=1&E=1&T=0$")
    assert job.status == "failed"
    assert "ER=99" in job.error
    print("  ✓ response ER=99 → job failed:", job.error)


async def test_skip_when_tray_already_at_pickup() -> None:
    client = make_client()
    # Simulate state after a prior successful get_shelf
    client._current_tray = 8

    result = await client.send_pick_order("job-D", "EL-CONTACTOR", 1)
    assert result.success
    # No telegram should have been sent
    assert client._sent == [], f"unexpected send: {client._sent}"

    status = await client.get_pick_status("job-D")
    assert status.tray_ready is True
    assert status.slot == "TRAY-8"
    print("  ✓ current_tray==target → no TCP call, immediate ready")


async def test_skip_only_when_exact_match() -> None:
    client = make_client()
    # Tray 1 is at pickup, but we want tray 8 — must still send the call
    client._current_tray = 1

    result = await client.send_pick_order("job-E", "EL-CONTACTOR", 1)
    assert result.success
    assert len(client._sent) == 1
    assert "PM1=8$" in client._sent[0]
    print("  ✓ current_tray=1, target=8 → call still issued")


async def test_sequence_number_wraparound() -> None:
    client = make_client()
    client._seq_counter = 998
    # 999
    s1 = client._next_seq()
    # wraps to 000
    s2 = client._next_seq()
    assert s1 == "999"
    assert s2 == "000"
    print("  ✓ sequence wraparound 999 → 000")


async def test_unknown_sequence_ignored() -> None:
    client = make_client()
    # Inject a telegram with a seq we never sent — must not crash
    feed(client, "*G2301:0011$V XA$777$ER=00&T=8$")
    print("  ✓ unknown seq gracefully ignored")


async def test_multiple_jobs_tracked_independently() -> None:
    client = make_client()
    await client.send_pick_order("job-1", "EL-CONTACTOR", 1)
    # Force a second call by pretending no tray is at pickup
    await client.send_pick_order("job-2", "EL-SAFETY-RELAY", 1)
    j1 = client._jobs_by_id["job-1"]
    j2 = client._jobs_by_id["job-2"]
    assert j1.seq != j2.seq
    assert j1.tray == 8
    assert j2.tray == 1
    # Complete job-2 first
    feed(client, f"*G2301:0011$V XS${j2.seq}$E00$")
    feed(client, f"*G2301:0011$V XA${j2.seq}$ER=00&T=1$")
    assert j2.status == "ready"
    assert j1.status in ("submitted", "presenting")  # still in flight
    print("  ✓ independent tracking: job-2 ready, job-1 still in flight")


async def test_get_state_summary_shape() -> None:
    """Backend must expose the fields /readyz and /diagnostics depend on."""
    client = make_client()
    summary = client.get_state_summary()
    expected = {
        "backend", "current_tray", "pending_jobs", "last_pickup_refresh",
        "mp_host", "mp_port", "elevator_num", "pickup_point",
        "default_tray", "connected",
    }
    missing = expected - set(summary.keys())
    assert not missing, f"get_state_summary missing keys: {missing}"
    assert summary["backend"] == "hanel_hostcom"
    assert summary["mp_host"] == "127.0.0.1"
    assert summary["mp_port"] == 2200
    assert summary["elevator_num"] == 1
    assert summary["pickup_point"] == 1
    assert summary["default_tray"] == 8
    assert summary["current_tray"] is None           # no refresh yet
    assert summary["last_pickup_refresh"] is None    # ditto
    assert summary["pending_jobs"] == 0
    assert summary["connected"] is True              # fake _writer sentinel
    print("  ✓ get_state_summary exposes all required fields")


async def test_cancel_forgets_job() -> None:
    client = make_client()
    await client.send_pick_order("job-X", "EL-CONTACTOR", 1)
    assert "job-X" in client._jobs_by_id
    ok = await client.cancel_pick("job-X")
    assert ok
    assert "job-X" not in client._jobs_by_id
    print("  ✓ cancel_pick removes job from registry")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


ALL_TESTS = [
    test_request_telegram_format,
    test_sku_to_tray_mapping_override,
    test_sku_default_tray,
    test_status_accepted_then_response_ready,
    test_status_rejected,
    test_response_aborted,
    test_skip_when_tray_already_at_pickup,
    test_skip_only_when_exact_match,
    test_sequence_number_wraparound,
    test_unknown_sequence_ignored,
    test_multiple_jobs_tracked_independently,
    test_get_state_summary_shape,
    test_cancel_forgets_job,
]


async def _main() -> int:
    failed = 0
    for t in ALL_TESTS:
        name = t.__name__
        try:
            await t()
            print(f"PASS  {name}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {name}: {exc}")
        except Exception as exc:
            failed += 1
            print(f"ERROR {name}: {type(exc).__name__}: {exc}")
    print()
    print(f"{len(ALL_TESTS) - failed}/{len(ALL_TESTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
