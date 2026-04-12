"""
Hänel MP 12N — HOST-COM telegram client.

This is NOT the SOAP ``/ws/com?wsdl`` interface (that is HOST-WEB/JWS).
HOST-COM is a raw TCP telegram protocol on port 2200 where the MP
controller is the server and the host is the TCP client. See the
Hänel manual ``b-12nll.HOST-COM.it.pdf`` Section 10 for full details.

Telegram format (all ASCII, terminated by CRLF)::

    Request:  *Gxxxy:2301$U XR$zzz$macro=<name>$PM1=<v>$PM2=<v>...$<CRLF>
    Status:   *G2301:xxxy$V XS$zzz$E<nn>$<CRLF>       (E00 = accepted)
    Info:     *G2301:xxxy$V XI$zzz$ER=<nn>&L=<l>&E=<e>...$<CRLF>  (optional)
    Response: *G2301:xxxy$V XA$zzz$ER=<nn>&...$<CRLF>  (ER=00 success)

- ``xxx`` = elevator number (3 digits), ``y`` = pickup point (1 digit)
- ``zzz`` = host sequence 000–999, wraps; used to correlate request / status / info / response

Mapping to the :class:`WarehouseClient` API
-------------------------------------------

HOST-COM has no concept of article master data or inventory — trays are
operator-managed. The client therefore relies on a static
``SKU → tray_number`` map supplied via configuration. For the HERMES
demo every component lives on tray 8, but the map lets us also pull a
different tray (e.g. tray 1) for a specific SKU to demonstrate that
the orchestrator picks the right tray per request.

``push_article`` and ``read_all_inventory`` are intentional no-ops —
HOST-COM does not expose those concepts.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from .base import ArticleInfo, PickResult, PickStatus, WarehouseClient

logger = logging.getLogger(__name__)


CRLF = "\r\n"


class HanelHostComError(Exception):
    """Raised when the MP returns a non-E00 status telegram."""


_STATUS_ERRORS = {
    "E00": "accepted",
    "E01": "first-connection-after-power-on (re-send)",
    "E02": "another command still in progress",
    "E03": "syntax error in telegram header",
    "E04": "remote-operation host-id mismatch",
    "E05": "controller not ready (press RETURN on panel)",
}


@dataclass
class _Job:
    seq: str                      # 3-digit zzz sequence used in request
    sku: str
    tray: int
    quantity: int
    status: str = "submitted"     # submitted | presenting | ready | failed
    slot: str = ""
    error: str = ""
    response_event: asyncio.Event = field(default_factory=asyncio.Event)


class HanelHostComClient(WarehouseClient):
    """Async HOST-COM telegram client over a persistent TCP connection."""

    def __init__(
        self,
        host: str,
        port: int = 2200,
        elevator_num: int = 1,
        pickup_point: int = 1,
        sku_tray_map: Optional[dict[str, int]] = None,
        default_tray: int = 8,
        connect_timeout: float = 5.0,
    ) -> None:
        self._host = host
        self._port = port
        self._elevator_num = int(elevator_num)
        self._pickup_point = int(pickup_point)
        self._sku_tray_map = {k.upper(): int(v) for k, v in (sku_tray_map or {}).items()}
        self._default_tray = int(default_tray)
        self._connect_timeout = connect_timeout

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()  # serialise request/status handshake
        self._seq_counter = 0
        self._jobs_by_seq: dict[str, _Job] = {}
        self._jobs_by_id: dict[str, _Job] = {}  # job_id (user-facing) → _Job
        # Tray number currently at the pickup point (0 = none, None = unknown).
        # Extracted from the ``T=<t>`` field of read_status / get_shelf responses.
        self._current_tray: Optional[int] = None
        # Unix timestamp of the last successful read_status (for health).
        self._last_pickup_refresh: Optional[float] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=self._connect_timeout,
            )
        except Exception as exc:
            logger.error("HanelHostCom: cannot connect to %s:%d — %s",
                         self._host, self._port, exc)
            raise
        self._reader_task = asyncio.create_task(self._reader_loop())
        logger.info("HanelHostCom connected to %s:%d (elevator=%d, pickup=%d)",
                    self._host, self._port, self._elevator_num, self._pickup_point)
        # Absorb the "first connection after power-on" E01 rejection by
        # firing a throwaway read_status. If the MP was already awake and
        # replies E00/ER=00, great; if it replies E01, the next real
        # macro sent by the user will succeed immediately.
        await self._handshake()

    async def _handshake(self) -> None:
        try:
            async with self._lock:
                seq = self._next_seq()
                job = _Job(seq=seq, sku="", tray=0, quantity=0)
                self._jobs_by_seq[seq] = job
                await self._send(self._build_request(seq, "read_status"))
                try:
                    await asyncio.wait_for(job.response_event.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass
                self._jobs_by_seq.pop(seq, None)
                if job.error == "E01":
                    logger.info("HanelHostCom: handshake absorbed E01 — MP now ready")
                else:
                    logger.info("HanelHostCom: handshake OK (status=%s)", job.status)
        except Exception as exc:
            logger.warning("HanelHostCom handshake failed: %s", exc)

    async def close(self) -> None:
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):
                pass
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        self._reader = None
        self._writer = None
        logger.info("HanelHostCom closed")

    async def _post_pick_cleanup(self) -> None:
        """After a successful get_shelf, clear the grid display and hand
        control of the MP panel back to the operator.

        Both macros are fired without blocking on their responses:
        ``delete_comp_display`` returns immediately, ``base_services``
        only returns when the operator exits the base menu (could be
        minutes later). We track neither — the next real macro call
        will just fail with E02 if the operator hasn't finished, and
        the retry logic in ``send_pick_order`` handles that.
        """
        try:
            await asyncio.sleep(0.2)  # let the response event settle first
            await self._fire_and_forget("delete_comp_display")
            await asyncio.sleep(0.1)
            # base_services with NO parameters produces an empty menu
            # where no key is active — exactly the "stuck screen" bug
            # from the first live run. Per manual p.92, each PMn must
            # be set to 1 to enable the corresponding menu key:
            #   PM1=add_shelf, PM2=remove_shelf, PM3=manual_retrieve,
            #   PM4=manual_store, PM5=optimisation, PM6=remove_block,
            #   PM21=info_services, PM22=system_services,
            #   PM23=doors, PM24=tray_transport
            await self._fire_and_forget(
                "base_services",
                PM1=1, PM2=1, PM3=1, PM4=1, PM5=1, PM6=1,
                PM21=1, PM22=1, PM23=1, PM24=1,
            )
            logger.info("HanelHostCom: post-pick cleanup fired "
                        "(delete_comp_display + base_services) — panel released")
        except Exception as exc:
            logger.warning("HanelHostCom: post-pick cleanup failed: %s", exc)

    async def _fire_and_forget(self, macro: str, **params: object) -> None:
        """Send a macro without registering/awaiting its response.

        We still allocate a sequence number so the (eventual) status
        and response telegrams won't match any tracked job and will be
        logged-and-ignored by :meth:`_handle_telegram`.
        """
        if self._writer is None:
            return
        async with self._lock:
            seq = self._next_seq()
            await self._send(self._build_request(seq, macro, **params))

    async def refresh_pickup_state(self, timeout: float = 3.0) -> Optional[int]:
        """Send ``read_status`` and wait for the response to learn which
        tray (if any) is currently at the pickup point.

        Returns the tray number (0 = none at pickup), or ``None`` on timeout.
        """
        if self._writer is None:
            return None
        async with self._lock:
            seq = self._next_seq()
            job = _Job(seq=seq, sku="", tray=0, quantity=0)
            self._jobs_by_seq[seq] = job
            telegram = self._build_request(seq, "read_status")
            try:
                await self._send(telegram)
                await asyncio.wait_for(job.response_event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning("HanelHostCom: read_status timed out")
                return None
            finally:
                self._jobs_by_seq.pop(seq, None)
        self._last_pickup_refresh = time.time()
        return self._current_tray

    def get_state_summary(self) -> dict:
        """Expose HOST-COM session state for /readyz and /diagnostics."""
        return {
            "backend": "hanel_hostcom",
            "current_tray": self._current_tray,
            "pending_jobs": len(self._jobs_by_id),
            "last_pickup_refresh": self._last_pickup_refresh,
            "mp_host": self._host,
            "mp_port": self._port,
            "elevator_num": self._elevator_num,
            "pickup_point": self._pickup_point,
            "default_tray": self._default_tray,
            "connected": self._writer is not None,
        }

    async def health_check(self) -> bool:
        """Ping the MP by sending a ``read_status`` macro."""
        if self._writer is None:
            return False
        try:
            seq = self._next_seq()
            telegram = self._build_request(seq, "read_status")
            await self._send(telegram)
            # We don't need to wait for the full response — the TCP
            # write succeeding on a live socket is a sufficient ping.
            return True
        except Exception as exc:
            logger.warning("HanelHostCom health_check failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Pick orders
    # ------------------------------------------------------------------

    async def send_pick_order(
        self, job_id: str, sku: str, quantity: int
    ) -> PickResult:
        """Dispatch ``get_shelf`` for the tray mapped to ``sku``."""
        if self._writer is None:
            return PickResult(success=False, job_id=job_id, error="not connected")

        tray = self._sku_tray_map.get(sku.upper(), self._default_tray)
        logger.info("HanelHostCom: SKU %s → tray %d (qty=%d, job=%s)",
                    sku, tray, quantity, job_id)

        # Short-circuit: if the target tray is already at the pickup point,
        # there's nothing to move. We still register a synthetic "ready"
        # job so the mission controller's polling loop terminates cleanly.
        if self._current_tray == tray:
            logger.info(
                "HanelHostCom: tray %d already at pickup — skipping get_shelf",
                tray,
            )
            job = _Job(seq="---", sku=sku, tray=tray, quantity=quantity,
                       status="ready", slot=f"TRAY-{tray}")
            job.response_event.set()
            self._jobs_by_id[job_id] = job
            return PickResult(success=True, job_id=job_id)

        # Up to 5 attempts — handles two transient cases:
        #   - E01: fresh power-cycle makes the first telegram get "first
        #     connection after power-on" (resend immediately)
        #   - E02: "another command in progress" — usually because a
        #     previous base_services is still active on the panel.
        #     Wait a bit and retry; total budget ~8 s.
        for attempt in range(1, 6):
            async with self._lock:
                seq = self._next_seq()
                job = _Job(seq=seq, sku=sku, tray=tray, quantity=quantity)
                self._jobs_by_seq[seq] = job
                self._jobs_by_id[job_id] = job

                # get_shelf: present the tray at the pickup for in-place
                # access by the cobot. We intentionally do NOT use
                # remove_shelf — that one blocks until the operator
                # physically extracts the tray from the cabinet and
                # aborts with ER=99 on timeout when nothing is removed.
                # The storage-position grid that get_shelf paints on the
                # MP display is cleared right after arrival via
                # delete_comp_display (see _handle_response).
                telegram = self._build_request(
                    seq, "get_shelf", PM1=tray, PM14=1,
                )
                try:
                    await self._send(telegram)
                except Exception as exc:
                    self._jobs_by_seq.pop(seq, None)
                    self._jobs_by_id.pop(job_id, None)
                    return PickResult(success=False, job_id=job_id, error=str(exc))

                # Wait briefly for the status telegram (E00 = accepted).
                try:
                    await asyncio.wait_for(self._wait_status(seq), timeout=3.0)
                except asyncio.TimeoutError:
                    logger.warning("HanelHostCom: no status telegram for seq=%s", seq)
                    # Not fatal — some MPs only answer with the response.

            if job.error == "E01" and attempt < 5:
                logger.info("HanelHostCom: retrying get_shelf after E01 handshake")
                self._jobs_by_id.pop(job_id, None)
                continue
            if "E02" in job.error and attempt < 5:
                logger.info(
                    "HanelHostCom: E02 — another command pending, "
                    "retrying get_shelf in 2s (attempt %d/5)", attempt,
                )
                self._jobs_by_id.pop(job_id, None)
                await asyncio.sleep(2.0)
                continue
            break

        if job.status == "failed":
            self._jobs_by_id.pop(job_id, None)
            return PickResult(success=False, job_id=job_id, error=job.error)

        return PickResult(success=True, job_id=job_id)

    async def get_pick_status(self, job_id: str) -> PickStatus:
        job = self._jobs_by_id.get(job_id)
        if job is None:
            return PickStatus(status="failed")
        return PickStatus(
            status=job.status,
            slot=job.slot or f"TRAY-{job.tray}",
            tray_ready=(job.status == "ready"),
        )

    async def cancel_pick(self, job_id: str) -> bool:
        """HOST-COM has no direct cancel; we just forget the job locally."""
        job = self._jobs_by_id.pop(job_id, None)
        if job is not None:
            self._jobs_by_seq.pop(job.seq, None)
            logger.info("HanelHostCom: job %s (tray %d) cancelled locally",
                        job_id, job.tray)
        return True

    # ------------------------------------------------------------------
    # Article / inventory (unsupported by HOST-COM)
    # ------------------------------------------------------------------

    async def push_article(self, sku: str, name: str) -> bool:
        logger.debug("HanelHostCom: push_article is a no-op (HOST-COM has no APD)")
        return True

    async def read_all_inventory(self) -> list[ArticleInfo]:
        logger.debug("HanelHostCom: read_all_inventory is a no-op (HOST-COM has no AMD)")
        return []

    # ------------------------------------------------------------------
    # Telegram building / parsing
    # ------------------------------------------------------------------

    def _next_seq(self) -> str:
        self._seq_counter = (self._seq_counter + 1) % 1000
        return f"{self._seq_counter:03d}"

    def _header(self, seq: str) -> str:
        # *G<xxx><y>:2301$U XR$<zzz>$
        xxxy = f"{self._elevator_num:03d}{self._pickup_point:1d}"
        return f"*G{xxxy}:2301$U XR${seq}$"

    def _build_request(self, seq: str, macro: str, **params: object) -> str:
        parts = [self._header(seq), f"macro={macro}$"]
        for key, value in params.items():
            parts.append(f"{key}={value}$")
        return "".join(parts) + CRLF

    async def _send(self, telegram: str) -> None:
        assert self._writer is not None
        logger.debug("HanelHostCom TX: %s", telegram.rstrip())
        self._writer.write(telegram.encode("ascii", errors="replace"))
        await self._writer.drain()

    async def _wait_status(self, seq: str) -> None:
        """Briefly wait for an E00/E0x status telegram on ``seq``."""
        # Poll the job state — the reader loop sets it on receipt.
        for _ in range(30):  # ~3s
            job = self._jobs_by_seq.get(seq)
            if job is None:
                return
            if job.status != "submitted":
                return
            await asyncio.sleep(0.1)

    async def _reader_loop(self) -> None:
        """Continuously read telegrams from the MP and dispatch them."""
        assert self._reader is not None
        buffer = b""
        try:
            while True:
                chunk = await self._reader.read(4096)
                if not chunk:
                    logger.warning("HanelHostCom: connection closed by MP")
                    return
                buffer += chunk
                # Telegrams are CRLF-terminated; split and keep tail
                while True:
                    idx = buffer.find(b"\r\n")
                    if idx < 0:
                        break
                    line = buffer[:idx].decode("ascii", errors="replace")
                    buffer = buffer[idx + 2:]
                    if line:
                        self._handle_telegram(line)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("HanelHostCom reader loop error: %s", exc)

    _TELEGRAM_RE = re.compile(
        r"^\*G2301:(?P<xxxy>\d{4})\$V\s+X(?P<kind>[SIA])\$(?P<seq>\d{3})\$(?P<body>.*)$"
    )

    def _handle_telegram(self, line: str) -> None:
        logger.debug("HanelHostCom RX: %s", line)
        m = self._TELEGRAM_RE.match(line)
        if not m:
            logger.warning("HanelHostCom: unparseable telegram: %r", line)
            return

        kind = m.group("kind")    # S=status, I=info, A=response
        seq = m.group("seq")
        body = m.group("body").rstrip("$")
        job = self._jobs_by_seq.get(seq)
        if job is None:
            logger.debug("HanelHostCom: telegram for unknown seq=%s", seq)
            return

        if kind == "S":
            self._handle_status(job, body)
        elif kind == "I":
            self._handle_info(job, body)
        elif kind == "A":
            self._handle_response(job, body)

    def _handle_status(self, job: _Job, body: str) -> None:
        # Body looks like "E00" or "E03" etc.
        code_match = re.match(r"E(\d{2})", body)
        code = f"E{code_match.group(1)}" if code_match else body
        if code == "E00":
            job.status = "presenting"
            logger.info("HanelHostCom: job seq=%s accepted (tray %d)", job.seq, job.tray)
        elif code == "E01":
            # First telegram after MP power-on is always rejected with
            # E01 per manual p.74: "Reinviare macro". The retry is
            # orchestrated by the caller via job.error='E01' sentinel.
            logger.info("HanelHostCom: E01 (first-connection handshake) — will retry")
            job.status = "failed"
            job.error = "E01"
            job.response_event.set()
        else:
            reason = _STATUS_ERRORS.get(code, f"unknown status {code}")
            job.status = "failed"
            job.error = f"MP rejected macro: {code} ({reason})"
            logger.error("HanelHostCom: %s", job.error)
            job.response_event.set()

    def _handle_info(self, job: _Job, body: str) -> None:
        # Info telegrams describe progress (ER=01 started, ER=08 insert-tray, etc.)
        er_match = re.search(r"ER=(\d{2})", body)
        if not er_match:
            return
        er = int(er_match.group(1))
        info_labels = {
            1: "elevator-motion-started",
            2: "awaiting-RETURN-press",
            3: "elevator-error",
            4: "elevator-busy-other-pickup",
            5: "command-blocked-other-pickup",
            6: "close-door",
            7: "open-door",
            8: "insert-tray",
            9: "extract-tray",
            10: "user-instructions",
        }
        logger.info("HanelHostCom: job seq=%s info ER=%02d (%s)",
                    job.seq, er, info_labels.get(er, "unknown"))
        if er == 2:
            # Operator (or auto-press bot) must press RETURN on the panel.
            job.status = "presenting"

    def _handle_response(self, job: _Job, body: str) -> None:
        er_match = re.search(r"ER=(\d{2})", body)
        er = int(er_match.group(1)) if er_match else 99

        # Both read_status and get_shelf responses carry T=<tray-at-pickup>.
        t_match = re.search(r"T=(\d+)", body)
        if t_match:
            self._current_tray = int(t_match.group(1))
            logger.debug("HanelHostCom: pickup tray now = %d",
                         self._current_tray)

        if er == 0:
            job.status = "ready"
            job.slot = f"TRAY-{job.tray}"
            # Only overwrite _current_tray from job.tray on an actual
            # get_shelf (tray > 0). For synthetic read_status jobs
            # (tray=0) we trust whatever T=<t> the response already gave
            # us above.
            if job.tray > 0:
                self._current_tray = job.tray
                logger.info("HanelHostCom: job seq=%s COMPLETE — tray %d presented",
                            job.seq, job.tray)
                # Fire post-pick cleanup in the background:
                #   1. delete_comp_display — clear the storage-position
                #      grid that get_shelf paints on the MP display
                #   2. base_services — open the base-functions menu so
                #      the operator can use the panel locally again
                # Both are fire-and-forget; we don't block tray_ready on
                # them. The cleanup runs AFTER the response event is
                # set, so the mission controller's poll loop unblocks
                # immediately.
                asyncio.create_task(self._post_pick_cleanup())
            else:
                logger.info("HanelHostCom: job seq=%s read_status OK — pickup=%s",
                            job.seq, self._current_tray)
        else:
            job.status = "failed"
            job.error = f"macro aborted ER={er:02d}"
            logger.error("HanelHostCom: job seq=%s ABORTED (ER=%02d)",
                         job.seq, er)
        job.response_event.set()
