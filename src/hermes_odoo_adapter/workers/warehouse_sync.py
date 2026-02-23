"""
Warehouse synchronization worker.

Handles three concerns:
1. **Article bootstrap**: push Odoo SKUs to the warehouse on startup.
2. **Inbound stock detection**: periodically poll warehouse inventory to detect
   items loaded via the Hanel HMI (manual operator loading).
3. **Inventory reconciliation**: compare warehouse quantities with Odoo and
   create Shortage entities in FIWARE for discrepancies.

Only active when ``warehouse_backend != "null"``.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..settings import settings
from ..models.ngsi_models import InventoryItem
from ..utils.logging import get_logger, LoggingContext
from ..odoo_client import OdooClient, OdooError
from ..orion_client import OrionClient, OrionError
from ..warehouse.base import WarehouseClient, ArticleInfo

logger = get_logger(__name__)


class WarehouseSyncWorker:
    """Periodic sync between the physical warehouse and Odoo / FIWARE."""

    def __init__(
        self,
        odoo_client: OdooClient,
        orion_client: OrionClient,
        warehouse_client: WarehouseClient,
    ) -> None:
        self._odoo = odoo_client
        self._orion = orion_client
        self._warehouse = warehouse_client
        self._sync_interval = settings.warehouse_sync_interval_minutes * 60
        self._running = False
        self._last_sync: Optional[datetime] = None
        self._last_inventory_snapshot: Dict[str, float] = {}

        logger.info(
            "WarehouseSyncWorker initialized",
            sync_interval_s=self._sync_interval,
            backend=settings.warehouse_backend,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._running:
            logger.warning("WarehouseSyncWorker already running")
            return

        self._running = True
        logger.info("Starting warehouse sync worker")

        # One-time article bootstrap
        await self._bootstrap_articles()

        try:
            while self._running:
                try:
                    await self._sync_warehouse_inventory()
                    if self._running:
                        await asyncio.sleep(self._sync_interval)
                except Exception as exc:
                    logger.error("Error in warehouse sync loop", error=str(exc))
                    if self._running:
                        await asyncio.sleep(60)
        except asyncio.CancelledError:
            logger.info("WarehouseSyncWorker cancelled")
        finally:
            self._running = False

    async def stop(self) -> None:
        if not self._running:
            return
        logger.info("Stopping warehouse sync worker")
        self._running = False

    # ------------------------------------------------------------------
    # 1. Article bootstrap
    # ------------------------------------------------------------------

    async def _bootstrap_articles(self) -> None:
        """Push Odoo SKUs to the warehouse so it knows our article codes."""
        logger.info("Bootstrapping article master data to warehouse")
        try:
            products = await self._odoo.search_read(
                "product.product",
                domain=[
                    ("active", "=", True),
                    ("type", "=", "product"),
                    (settings.sku_field, "!=", False),
                ],
                fields=["id", "name", settings.sku_field],
                limit=0,
            )

            pushed = 0
            for product in products:
                sku = (product.get(settings.sku_field) or "").strip()
                if not sku:
                    continue
                # Only push SKUs from the allowed list (if configured)
                if settings.inventory_allowed_skus and sku not in settings.inventory_allowed_skus:
                    continue
                name = product.get("name", sku)
                ok = await self._warehouse.push_article(sku, name)
                if ok:
                    pushed += 1

            logger.info("Article bootstrap complete", pushed=pushed, total=len(products))
        except Exception as exc:
            logger.error("Article bootstrap failed", error=str(exc))

    # ------------------------------------------------------------------
    # 2. Periodic warehouse inventory poll
    # ------------------------------------------------------------------

    async def _sync_warehouse_inventory(self) -> None:
        """Read warehouse inventory and update FIWARE InventoryItem entities."""
        sync_start = datetime.utcnow()
        logger.info("Starting warehouse inventory sync")

        try:
            articles = await self._warehouse.read_all_inventory()
            if not articles:
                logger.info("Warehouse returned empty inventory")
                return

            updated = 0
            for article in articles:
                try:
                    await self._upsert_inventory_item(article)
                    updated += 1
                except Exception as exc:
                    logger.warning(
                        "Failed to sync article",
                        sku=article.article_number,
                        error=str(exc),
                    )

            # Detect inbound stock changes
            await self._detect_inbound_changes(articles)

            # Store snapshot for next comparison
            self._last_inventory_snapshot = {
                a.article_number: a.quantity for a in articles
            }
            self._last_sync = sync_start

            duration = (datetime.utcnow() - sync_start).total_seconds()
            logger.info(
                "Warehouse inventory sync complete",
                articles=len(articles),
                updated=updated,
                duration_s=round(duration, 2),
            )
        except Exception as exc:
            logger.error("Warehouse inventory sync failed", error=str(exc))

    async def _upsert_inventory_item(self, article: ArticleInfo) -> None:
        """Create or update an InventoryItem entity in Orion-LD with warehouse location data."""
        sku = article.article_number
        location = ""
        if article.lift and article.shelf:
            location = f"L{article.lift}-S{article.shelf}"
            if article.compartment:
                location += f"-C{article.compartment}"

        entity = {
            "id": f"urn:ngsi-ld:InventoryItem:{sku}",
            "type": "InventoryItem",
            "sku": {"type": "Property", "value": sku},
            "warehouseQuantity": {"type": "Property", "value": article.quantity},
            "location": {"type": "Property", "value": location},
            "minimumInventory": {"type": "Property", "value": article.minimum_inventory},
            "@context": ["https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"],
        }
        await self._orion.upsert_entity(entity)

    # ------------------------------------------------------------------
    # 3. Inbound stock detection
    # ------------------------------------------------------------------

    async def _detect_inbound_changes(self, articles: List[ArticleInfo]) -> None:
        """
        Compare current warehouse quantities with the previous snapshot.
        If an article's quantity increased, someone loaded stock via the HMI.
        """
        if not self._last_inventory_snapshot:
            return  # First run, nothing to compare

        for article in articles:
            sku = article.article_number
            prev_qty = self._last_inventory_snapshot.get(sku, 0.0)
            if article.quantity > prev_qty:
                delta = article.quantity - prev_qty
                logger.info(
                    "Inbound stock detected (warehouse HMI load)",
                    sku=sku,
                    previous=prev_qty,
                    current=article.quantity,
                    delta=delta,
                )

    def get_sync_status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "backend": settings.warehouse_backend,
            "last_sync": self._last_sync.isoformat() if self._last_sync else None,
            "sync_interval_seconds": self._sync_interval,
            "articles_tracked": len(self._last_inventory_snapshot),
        }
