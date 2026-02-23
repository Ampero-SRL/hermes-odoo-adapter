"""
Null warehouse client for development and testing.

Returns mock success responses with configurable delay, replacing the
need for a WireMock container.
"""
from __future__ import annotations

import asyncio
import logging
import uuid

from .base import ArticleInfo, PickResult, PickStatus, WarehouseClient

logger = logging.getLogger(__name__)


class NullWarehouseClient(WarehouseClient):
    """
    Stub warehouse backend that simulates a warehouse with no real I/O.

    All operations succeed immediately (after an optional ``delay`` seconds)
    and are logged for debugging.
    """

    def __init__(self, delay: float = 0.5) -> None:
        self._delay = delay
        self._pending_jobs: dict[str, dict] = {}

    async def connect(self) -> None:
        logger.info("NullWarehouseClient connected (dev/test mode)")

    async def close(self) -> None:
        logger.info("NullWarehouseClient closed")

    async def health_check(self) -> bool:
        return True

    async def send_pick_order(
        self, job_id: str, sku: str, quantity: int
    ) -> PickResult:
        await asyncio.sleep(self._delay)
        effective_id = job_id or f"null-{uuid.uuid4().hex[:8]}"
        self._pending_jobs[effective_id] = {"sku": sku, "quantity": quantity}
        logger.info(
            "[NULL] Pick order submitted: job=%s sku=%s qty=%d",
            effective_id, sku, quantity,
        )
        return PickResult(success=True, job_id=effective_id)

    async def get_pick_status(self, job_id: str) -> PickStatus:
        await asyncio.sleep(self._delay)
        if job_id in self._pending_jobs:
            # Immediately report ready for dev convenience
            info = self._pending_jobs.pop(job_id)
            logger.info("[NULL] Pick status: job=%s → ready", job_id)
            return PickStatus(status="ready", slot="NULL-A1", tray_ready=True)
        logger.info("[NULL] Pick status: job=%s → not found", job_id)
        return PickStatus(status="failed")

    async def cancel_pick(self, job_id: str) -> bool:
        self._pending_jobs.pop(job_id, None)
        logger.info("[NULL] Pick cancelled: job=%s", job_id)
        return True

    async def push_article(self, sku: str, name: str) -> bool:
        logger.info("[NULL] Article pushed: %s (%s)", sku, name)
        return True

    async def read_all_inventory(self) -> list[ArticleInfo]:
        logger.info("[NULL] Returning empty inventory")
        return []
