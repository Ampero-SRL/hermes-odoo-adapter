"""
Inventory synchronization worker - periodic sync of stock data from Odoo to Orion-LD
"""
import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from ..settings import settings
from ..models.ngsi_models import InventoryItem
from ..utils.logging import get_logger, LoggingContext
from ..utils.metrics import metrics
from ..odoo_client import OdooClient, OdooError
from ..orion_client import OrionClient, OrionError

logger = get_logger(__name__)


class InventorySyncWorker:
    """Worker for periodic synchronization of inventory data from Odoo to Orion-LD"""
    
    def __init__(self, odoo_client: OdooClient, orion_client: OrionClient):
        self.odoo_client = odoo_client
        self.orion_client = orion_client
        self.sync_interval = settings.inventory_sync_interval_minutes * 60
        self.batch_size = settings.inventory_sync_batch_size
        self.running = False
        self.last_sync_time: Optional[datetime] = None
        
        logger.info("Inventory sync worker initialized", 
                   sync_interval=self.sync_interval, 
                   batch_size=self.batch_size)
    
    async def start(self) -> None:
        """Start the inventory synchronization loop"""
        if self.running:
            logger.warning("Inventory sync worker already running")
            return
        
        self.running = True
        logger.info("Starting inventory sync worker")
        
        try:
            while self.running:
                try:
                    await self.sync_inventory()
                    
                    # Wait for next sync interval
                    if self.running:
                        logger.debug("Waiting for next sync", interval_seconds=self.sync_interval)
                        await asyncio.sleep(self.sync_interval)
                        
                except Exception as e:
                    logger.error("Error in inventory sync loop", error=str(e))
                    # Wait a bit before retrying to avoid rapid failure loops
                    if self.running:
                        await asyncio.sleep(60)  # Wait 1 minute on error
                        
        except asyncio.CancelledError:
            logger.info("Inventory sync worker cancelled")
        finally:
            self.running = False
    
    async def stop(self) -> None:
        """Stop the inventory synchronization loop"""
        if not self.running:
            return
        
        logger.info("Stopping inventory sync worker")
        self.running = False
    
    async def sync_inventory(self) -> Dict[str, Any]:
        """Perform full inventory synchronization"""
        sync_start = datetime.utcnow()
        
        with LoggingContext(sync_type="full_inventory"):
            logger.info("Starting inventory sync")
            
            try:
                # Get all products with stock from Odoo
                products_with_stock = await self._get_all_products_with_stock()
                
                if not products_with_stock:
                    logger.warning("No products with stock found")
                    return {"status": "completed", "products": 0}
                
                logger.info("Found products with stock", count=len(products_with_stock))
                
                # Process products in batches
                total_processed = 0
                total_updated = 0
                total_errors = 0
                
                for i in range(0, len(products_with_stock), self.batch_size):
                    batch = products_with_stock[i:i + self.batch_size]
                    
                    batch_result = await self._process_inventory_batch(batch)
                    total_processed += batch_result["processed"]
                    total_updated += batch_result["updated"]
                    total_errors += batch_result["errors"]
                    
                    # Small delay between batches to avoid overwhelming systems
                    if i + self.batch_size < len(products_with_stock):
                        await asyncio.sleep(0.1)
                
                self.last_sync_time = sync_start
                sync_duration = (datetime.utcnow() - sync_start).total_seconds()
                
                metrics.record_inventory_sync_completed(total_processed, sync_duration)
                
                logger.info("Inventory sync completed", 
                           processed=total_processed,
                           updated=total_updated,
                           errors=total_errors,
                           duration_seconds=sync_duration)
                
                return {
                    "status": "completed",
                    "processed": total_processed,
                    "updated": total_updated,
                    "errors": total_errors,
                    "duration_seconds": sync_duration
                }
                
            except Exception as e:
                logger.error("Inventory sync failed", error=str(e))
                metrics.record_inventory_sync_failed()
                raise
    
    async def _get_all_products_with_stock(self) -> List[Dict[str, Any]]:
        """Get all products that have stock quantities"""
        try:
            # Get all stock quants from internal locations (keep zero-qty rows)
            stock_quants = await self.odoo_client.search_read(
                "stock.quant",
                domain=[
                    ("location_id.usage", "=", "internal"),
                ],
                fields=["product_id", "location_id", "quantity", "reserved_quantity"],
                limit=0
            )
            
            # Aggregate stock per product for quick lookup
            stock_by_product: Dict[int, Dict[str, float]] = {}
            for quant in stock_quants:
                product_id = quant["product_id"][0]
                product_stock = stock_by_product.setdefault(product_id, {"total": 0.0, "reserved": 0.0})
                product_stock["total"] += float(quant.get("quantity", 0.0))
                product_stock["reserved"] += float(quant.get("reserved_quantity", 0.0))
            
            # Fetch all active inventory products that have a SKU so zero-stock items are still represented
            products = await self.odoo_client.search_read(
                "product.product",
                domain=[
                    ("active", "=", True),
                    ("type", "=", "product"),
                    (settings.sku_field, "!=", False),
                ],
                fields=["id", "name", settings.sku_field],
                limit=0
            )
            
            if not products:
                return []
            
            products_with_stock = []
            
            for product in products:
                product_id = product["id"]
                sku = product.get(settings.sku_field)
                if not sku:
                    continue
                
                stock_info = stock_by_product.get(product_id, {"total": 0.0, "reserved": 0.0})
                total_qty = stock_info["total"]
                reserved_qty = stock_info["reserved"]
                available_qty = max(total_qty - reserved_qty, 0.0)
                
                products_with_stock.append({
                    "product_id": product_id,
                    "sku": sku,
                    "name": product["name"],
                    "total_quantity": total_qty,
                    "reserved_quantity": reserved_qty,
                    "available_quantity": available_qty
                })
            
            return products_with_stock
            
        except OdooError as e:
            logger.error("Error fetching products with stock from Odoo", error=str(e))
            raise
    
    async def _process_inventory_batch(self, products: List[Dict[str, Any]]) -> Dict[str, int]:
        """Process a batch of products for inventory sync"""
        processed = 0
        updated = 0
        errors = 0
        
        for product in products:
            try:
                sku = product["sku"]
                available_qty = product["available_quantity"]
                reserved_qty = product["reserved_quantity"]
                
                # Create/update inventory item in Orion-LD
                inventory_item = InventoryItem.create(sku, available_qty, reserved_qty)
                
                result = await self.orion_client.upsert_entity(inventory_item)
                
                if (result is None) or "error" not in result:
                    updated += 1
                    logger.debug("Updated inventory item", 
                               sku=sku, 
                               available=available_qty, 
                               reserved=reserved_qty)
                else:
                    errors += 1
                    logger.warning("Failed to update inventory item", 
                                 sku=sku, 
                                 result=result)
                
                processed += 1
                
            except Exception as e:
                errors += 1
                logger.warning("Error processing product inventory", 
                             product_id=product.get("product_id"),
                             sku=product.get("sku"),
                             error=str(e))
        
        return {"processed": processed, "updated": updated, "errors": errors}
    
    async def handle_stock_change(self, webhook_payload: Dict[str, Any]) -> None:
        """Handle real-time stock change webhook from Odoo"""
        product_id = webhook_payload.get("product_id")
        sku = webhook_payload.get("sku")
        
        if not product_id or not sku:
            logger.warning("Invalid stock change payload", payload=webhook_payload)
            return
        
        with LoggingContext(product_id=product_id, sku=sku):
            logger.info("Processing stock change webhook")
            
            try:
                # Get current stock for this product
                stock_data = await self.odoo_client.get_stock_for_products([product_id])
                
                # Aggregate stock
                total_qty = sum(item["quantity"] for item in stock_data)
                reserved_qty = sum(item.get("reserved_quantity", 0) for item in stock_data)
                available_qty = total_qty - reserved_qty
                
                # Update inventory item
                inventory_item = InventoryItem.create(sku, available_qty, reserved_qty)
                await self.orion_client.upsert_entity(inventory_item)
                
                logger.info("Stock change processed", 
                           sku=sku, 
                           total=total_qty, 
                           reserved=reserved_qty, 
                           available=available_qty)
                
                metrics.record_stock_change_processed()
                
            except Exception as e:
                logger.error("Error processing stock change", error=str(e))
                metrics.record_stock_change_failed()
                raise
    
    async def sync_product_inventory(self, sku: str) -> Optional[Dict[str, Any]]:
        """Sync inventory for a specific product by SKU"""
        with LoggingContext(sku=sku):
            logger.info("Syncing inventory for specific product")
            
            try:
                # Get product by SKU
                product = await self.odoo_client.get_product_by_sku(sku)
                if not product:
                    logger.warning("Product not found", sku=sku)
                    return None
                
                # Get stock data
                stock_data = await self.odoo_client.get_stock_for_products([product["id"]])
                
                # Calculate quantities
                total_qty = sum(item["quantity"] for item in stock_data)
                reserved_qty = sum(item.get("reserved_quantity", 0) for item in stock_data)
                available_qty = total_qty - reserved_qty
                
                # Update inventory item
                inventory_item = InventoryItem.create(sku, available_qty, reserved_qty)
                result = await self.orion_client.upsert_entity(inventory_item)
                
                logger.info("Product inventory synced", 
                           sku=sku, 
                           total=total_qty, 
                           reserved=reserved_qty, 
                           available=available_qty)
                
                return {
                    "sku": sku,
                    "total_quantity": total_qty,
                    "reserved_quantity": reserved_qty,
                    "available_quantity": available_qty,
                    "updated": result and "error" not in result
                }
                
            except Exception as e:
                logger.error("Error syncing product inventory", error=str(e))
                raise
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status"""
        return {
            "running": self.running,
            "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "sync_interval_seconds": self.sync_interval,
            "batch_size": self.batch_size,
            "next_sync_due": (
                (self.last_sync_time + timedelta(seconds=self.sync_interval)).isoformat()
                if self.last_sync_time else None
            )
        }
