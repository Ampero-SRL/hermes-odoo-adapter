"""
Project synchronization worker - handles BOM resolution and stock checking
"""
import json
from typing import Any, Dict, List, Optional, Tuple

from ..settings import settings
from ..models.ngsi_models import (
    Reservation,
    Shortage,
    InventoryItem,
    ReservationLine,
    ShortageLine,
    CUSTOM_CONTEXT,
)
from ..utils.logging import get_logger, LoggingContext
from ..utils.metrics import metrics
from ..utils.idempotency import idempotency_helper
from ..odoo_client import OdooClient, OdooError
from ..orion_client import OrionClient, OrionError

logger = get_logger(__name__)


class ProjectSyncWorker:
    """Worker for synchronizing project requests with Odoo BOM and stock data"""
    
    def __init__(self, odoo_client: OdooClient, orion_client: OrionClient):
        self.odoo_client = odoo_client
        self.orion_client = orion_client
        self.subscription_id = "urn:ngsi-ld:Subscription:hermes-project"
        
    async def setup_subscription(self) -> bool:
        """Setup Orion-LD subscription for Project entities"""
        subscription_config = {
            "type": "Subscription",
            "@context": ["https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"],
            "description": "HERMES Project entity subscription",
            "entities": [{"type": "Project"}],
            "notification": {
                "attributes": ["code", "station", "status", "productId", "quantity"],
                "format": "normalized",
                "endpoint": {
                    "uri": f"{settings.adapter_public_url}/orion/notifications",
                    "accept": "application/json"
                }
            },
            "expires": "2030-01-01T00:00:00.000Z"
        }
        
        try:
            success = await self.orion_client.ensure_subscription_exists(
                self.subscription_id,
                subscription_config
            )
            
            if success:
                logger.info("Project subscription setup completed", subscription_id=self.subscription_id)
            else:
                logger.error("Failed to setup project subscription", subscription_id=self.subscription_id)
            
            return success
            
        except Exception as e:
            logger.error("Error setting up project subscription", error=str(e))
            return False
    
    async def handle_project_notification(self, entity_data: Dict[str, Any]) -> None:
        """Handle a project notification from Orion-LD"""
        entity_id = entity_data.get("id")
        entity_type = entity_data.get("type")
        
        if entity_type != "Project":
            logger.warning("Received non-Project entity", entity_id=entity_id, entity_type=entity_type)
            return
        
        # Extract project details
        project_id = entity_id.split(":")[-1] if entity_id else "unknown"
        project_code = self._extract_property_value(entity_data, "code")
        station = self._extract_property_value(entity_data, "station")
        status = self._extract_property_value(entity_data, "status")
        quantity = self._extract_property_value(entity_data, "quantity")

        # Default quantity to 1 if not provided
        if quantity is None:
            quantity = 1
        quantity = int(quantity)

        with LoggingContext(project_id=project_id):
            logger.info("Processing project notification",
                       project_code=project_code, station=station, status=status, quantity=quantity)

            try:
                # Check idempotency
                if not idempotency_helper.should_process_project(project_id, entity_data):
                    logger.info("Project already processed, skipping", project_id=project_id)
                    return

                if status == "requested":
                    result = await self._process_project_request(project_id, project_code, station, quantity)
                    idempotency_helper.mark_project_processed(project_id, entity_data, result)
                else:
                    logger.debug("Project status not 'requested', ignoring", status=status)
                
            except Exception as e:
                logger.error("Error processing project", project_id=project_id, error=str(e))
                raise
    
    async def _process_project_request(self, project_id: str, project_code: str, station: Optional[str], quantity: int = 1) -> Dict[str, Any]:
        """Process a project request - check BOM and stock"""
        logger.info("Processing project request", project_id=project_id, project_code=project_code, quantity=quantity)
        
        try:
            # Step 1: Find product by project code
            product = await self._get_product_by_project_code(project_code)
            if not product:
                error_msg = f"No product found for project code: {project_code}"
                logger.warning(error_msg, project_code=project_code)
                return {"error": error_msg}
            
            logger.info("Found product", product_id=product["id"], product_name=product.get("name"))
            
            # Step 2: Get BOM for product
            bom = await self.odoo_client.get_bom_for_product(product["id"])
            if not bom:
                error_msg = f"No BOM found for product: {product.get('name')}"
                logger.warning(error_msg, product_id=product["id"])
                return {"error": error_msg}
            
            logger.info("Found BOM", bom_id=bom["id"], bom_line_count=len(bom.get("bom_line_ids", [])))
            
            # Step 3: Get BOM lines
            bom_lines = []
            if bom.get("bom_line_ids"):
                bom_lines = await self.odoo_client.get_bom_lines(bom["bom_line_ids"])
            
            if not bom_lines:
                error_msg = f"No BOM lines found for BOM: {bom['id']}"
                logger.warning(error_msg, bom_id=bom["id"])
                return {"error": error_msg}
            
            logger.info("Retrieved BOM lines", line_count=len(bom_lines))

            # Step 4: Check stock availability
            result = await self._check_stock_availability(project_id, bom_lines, quantity)

            return result
            
        except OdooError as e:
            logger.error("Odoo error during project processing", project_id=project_id, error=str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error during project processing", project_id=project_id, error=str(e))
            raise
    
    async def _get_product_by_project_code(self, project_code: str) -> Optional[Dict[str, Any]]:
        """Get product by project code (using SKU field)"""
        # Try direct SKU lookup first
        product = await self.odoo_client.get_product_by_sku(project_code)
        
        if not product:
            # Try loading project mapping file
            mapping = await self._load_project_mapping()
            if mapping and project_code in mapping:
                mapped_sku = mapping[project_code]
                logger.info("Using project mapping", project_code=project_code, mapped_sku=mapped_sku)
                product = await self.odoo_client.get_product_by_sku(mapped_sku)
        
        return product
    
    async def _load_project_mapping(self) -> Optional[Dict[str, str]]:
        """Load project code to SKU mapping from file"""
        if not settings.project_mapping_file:
            return None
        
        try:
            import os
            if not os.path.exists(settings.project_mapping_file):
                return None
                
            with open(settings.project_mapping_file, 'r') as f:
                mapping = json.load(f)
            
            logger.debug("Loaded project mapping", mapping_count=len(mapping))
            return mapping
            
        except Exception as e:
            logger.warning("Failed to load project mapping", file=settings.project_mapping_file, error=str(e))
            return None
    
    async def _check_stock_availability(self, project_id: str, bom_lines: List[Dict[str, Any]], quantity: int = 1) -> Dict[str, Any]:
        """Check stock availability for BOM lines and create Reservation or Shortage"""
        logger.info("Checking stock availability", project_id=project_id, bom_line_count=len(bom_lines), project_quantity=quantity)
        
        # Get all product IDs from BOM lines
        product_ids = [line["product_id"][0] for line in bom_lines]
        
        # Get stock data for all products
        stock_data = await self.odoo_client.get_stock_for_products(product_ids)
        
        # Aggregate stock by product
        stock_by_product = {}
        for stock_item in stock_data:
            product_id = stock_item["product_id"][0]
            stock_qty = stock_item["quantity"]  # Renamed to avoid shadowing quantity parameter
            reserved = stock_item.get("reserved_quantity", 0)

            if product_id not in stock_by_product:
                stock_by_product[product_id] = {"total": 0, "reserved": 0}

            stock_by_product[product_id]["total"] += stock_qty
            stock_by_product[product_id]["reserved"] += reserved
        
        # Check each BOM line
        reservation_lines = []
        shortage_lines = []
        
        for bom_line in bom_lines:
            product_id = bom_line["product_id"][0]
            product_name = bom_line["product_id"][1]
            bom_qty = bom_line["product_qty"]
            required_qty = bom_qty * quantity  # Multiply by project quantity
            
            # Get product SKU
            product_data = await self.odoo_client.read("product.product", [product_id], [settings.sku_field])
            sku = product_data[0].get(settings.sku_field) if product_data else f"PRODUCT_{product_id}"
            
            # Calculate available stock
            stock_info = stock_by_product.get(product_id, {"total": 0, "reserved": 0})
            total_stock = stock_info["total"]
            reserved_stock = stock_info["reserved"]
            available_stock = total_stock - (reserved_stock if settings.include_reserved_stock else 0)
            
            logger.debug("Stock check", 
                        sku=sku, required=required_qty, total=total_stock, 
                        reserved=reserved_stock, available=available_stock)
            
            if available_stock >= required_qty:
                # Sufficient stock - add to reservation
                reservation_lines.append(ReservationLine(
                    sku=sku,
                    qty=required_qty
                ))
                
                # Update inventory item
                await self._upsert_inventory_item(sku, available_stock - required_qty, reserved_stock + required_qty)
                
            else:
                # Insufficient stock - add to shortage
                missing_qty = required_qty - available_stock
                shortage_lines.append(ShortageLine(
                    sku=sku,
                    missing_qty=missing_qty,
                    required_qty=required_qty,
                    available_qty=available_stock
                ))
        
        # Create appropriate entity
        if shortage_lines:
            # Create shortage
            shortage = Shortage.create(project_id, shortage_lines)
            await self.orion_client.upsert_entity(shortage)

            # Update Project status to shortage
            await self._update_project_status(project_id, "shortage")

            metrics.record_shortage_created()
            logger.info("Created shortage", project_id=project_id, shortage_line_count=len(shortage_lines))

            return {"type": "shortage", "lines": len(shortage_lines)}
            
        elif reservation_lines:
            # Create reservation
            reservation = Reservation.create(project_id, reservation_lines)
            await self.orion_client.upsert_entity(reservation)

            # Update Project status to processing
            await self._update_project_status(project_id, "processing")

            metrics.record_reservation_created()
            logger.info("Created reservation", project_id=project_id, reservation_line_count=len(reservation_lines))

            return {"type": "reservation", "lines": len(reservation_lines)}
            
        else:
            logger.warning("No BOM lines processed", project_id=project_id)
            return {"type": "error", "message": "No valid BOM lines"}
    
    async def _upsert_inventory_item(self, sku: str, available: float, reserved: float) -> None:
        """Create or update inventory item entity"""
        try:
            inventory_item = InventoryItem.create(sku, available, reserved)
            await self.orion_client.upsert_entity(inventory_item)
            logger.debug("Updated inventory item", sku=sku, available=available, reserved=reserved)

        except Exception as e:
            logger.warning("Failed to update inventory item", sku=sku, error=str(e))

    async def _update_project_status(self, project_id: str, status: str) -> None:
        """Update Project entity status"""
        try:
            # Ensure project_id is a full URI
            if not project_id.startswith("urn:ngsi-ld:"):
                project_uri = f"urn:ngsi-ld:Project:{project_id}"
            else:
                project_uri = project_id

            update_data = {
                "status": {
                    "type": "Property",
                    "value": status
                },
                "@context": ["https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"]
            }

            await self.orion_client.update_entity(project_uri, update_data, "Project")
            logger.info("Updated project status", project_id=project_id, status=status)

        except Exception as e:
            logger.warning("Failed to update project status", project_id=project_id, status=status, error=str(e))

    def _extract_property_value(self, entity_data: Dict[str, Any], property_name: str) -> Optional[str]:
        """Extract value from NGSI-LD property"""
        prop = entity_data.get(property_name)
        if prop and isinstance(prop, dict) and prop.get("type") == "Property":
            return prop.get("value")
        return None
