#!/usr/bin/env python3
"""
Seed script for populating Odoo Mock with demo manufacturing data

This script populates the Odoo Mock service with realistic manufacturing data
including products, BOMs, and stock quantities for the HERMES demo scenario.
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List, Any

import httpx

# Add src to Python path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from hermes_odoo_adapter.utils.logging import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)

ODOO_MOCK_URL = "http://localhost:8069"


class OdooMockSeeder:
    """Seeder for Odoo Mock service"""
    
    def __init__(self, base_url: str = ODOO_MOCK_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
    
    async def clear_all_data(self):
        """Clear all existing data in Odoo Mock"""
        logger.info("Clearing all existing data from Odoo Mock")
        
        endpoints = [
            "/debug/products/clear",
            "/debug/boms/clear", 
            "/debug/stock/clear"
        ]
        
        for endpoint in endpoints:
            try:
                response = await self.client.post(f"{self.base_url}{endpoint}")
                if response.status_code == 200:
                    logger.info(f"Cleared data from {endpoint}")
                else:
                    logger.warning(f"Failed to clear {endpoint}: {response.status_code}")
            except Exception as e:
                logger.warning(f"Error clearing {endpoint}: {e}")
    
    async def seed_products(self) -> Dict[str, int]:
        """Seed products and return SKU to ID mapping"""
        logger.info("Seeding products")
        
        products = [
            # Final products (what gets manufactured)
            {
                "name": "Industrial Control Panel A1",
                "default_code": "CTRL-PANEL-A1",
                "uom_id": [1, "Units"],
                "active": True,
                "categ_id": [1, "Manufactured Products"]
            },
            {
                "name": "Safety Control System B2", 
                "default_code": "SAFETY-SYS-B2",
                "uom_id": [1, "Units"],
                "active": True,
                "categ_id": [1, "Manufactured Products"]
            },
            {
                "name": "HMI Display Unit C3",
                "default_code": "HMI-DISPLAY-C3", 
                "uom_id": [1, "Units"],
                "active": True,
                "categ_id": [1, "Manufactured Products"]
            },
            
            # Components (raw materials)
            {
                "name": "Safety Relay 24VDC",
                "default_code": "EL-SAFETY-RELAY",
                "uom_id": [1, "Units"],
                "active": True,
                "categ_id": [2, "Components"]
            },
            {
                "name": "Interface Relay 24VDC",
                "default_code": "EL-IFACE-RELAY",
                "uom_id": [1, "Units"],
                "active": True,
                "categ_id": [2, "Components"]
            },
            {
                "name": "Contactor",
                "default_code": "EL-CONTACTOR",
                "uom_id": [1, "Units"], 
                "active": True,
                "categ_id": [2, "Components"]
            },
            {
                "name": "Auxiliary Contact Block",
                "default_code": "EL-AUX-CONTACT",
                "uom_id": [1, "Units"],
                "active": True,
                "categ_id": [2, "Components"]
            },
            {
                "name": "Modular Fuse Carrier",
                "default_code": "EL-FUSE-CARRIER",
                "uom_id": [1, "Units"],
                "active": True,
                "categ_id": [2, "Components"]
            },
            {
                "name": "Terminal Block Grey",
                "default_code": "EL-TERMINAL-BLK",
                "uom_id": [1, "Units"],
                "active": True,
                "categ_id": [2, "Components"]
            }
        ]
        
        sku_to_id = {}
        product_id = 1
        
        for product in products:
            try:
                response = await self.client.post(
                    f"{self.base_url}/debug/products",
                    json={**product, "id": product_id}
                )
                
                if response.status_code == 200:
                    sku_to_id[product["default_code"]] = product_id
                    logger.info(f"Created product: {product['name']} (ID: {product_id})")
                    product_id += 1
                else:
                    logger.error(f"Failed to create product {product['name']}: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Error creating product {product['name']}: {e}")
        
        logger.info(f"Seeded {len(sku_to_id)} products")
        return sku_to_id
    
    async def seed_boms(self, sku_to_id: Dict[str, int]):
        """Seed Bills of Materials"""
        logger.info("Seeding BOMs")
        
        # BOM definitions: product_sku -> list of (component_sku, quantity)
        bom_definitions = {
            "CTRL-PANEL-A1": [
                ("EL-SAFETY-RELAY", 1.0),
                ("EL-IFACE-RELAY", 1.0),
                ("EL-CONTACTOR", 1.0),
                ("EL-AUX-CONTACT", 1.0),
                ("EL-FUSE-CARRIER", 1.0),
            ],
            "SAFETY-SYS-B2": [
                ("EL-SAFETY-RELAY", 2.0),
                ("EL-CONTACTOR", 1.0),
                ("EL-TERMINAL-BLK", 2.0),
            ],
            "HMI-DISPLAY-C3": [
                ("EL-IFACE-RELAY", 1.0),
                ("EL-FUSE-CARRIER", 1.0),
                ("EL-TERMINAL-BLK", 2.0),
            ]
        }
        
        bom_id = 1
        bom_line_id = 1
        
        for product_sku, components in bom_definitions.items():
            if product_sku not in sku_to_id:
                logger.warning(f"Product {product_sku} not found in SKU mapping")
                continue
            
            product_id = sku_to_id[product_sku]
            
            # Create BOM lines
            bom_line_ids = []
            for component_sku, qty in components:
                if component_sku not in sku_to_id:
                    logger.warning(f"Component {component_sku} not found in SKU mapping")
                    continue
                
                component_id = sku_to_id[component_sku]
                
                bom_line = {
                    "id": bom_line_id,
                    "bom_id": [bom_id, f"BOM for {product_sku}"],
                    "product_id": [component_id, component_sku],
                    "product_qty": qty,
                    "product_uom_id": [1, "Units"]
                }
                
                try:
                    response = await self.client.post(
                        f"{self.base_url}/debug/bom_lines",
                        json=bom_line
                    )
                    
                    if response.status_code == 200:
                        bom_line_ids.append(bom_line_id)
                        logger.debug(f"Created BOM line: {component_sku} x {qty}")
                        bom_line_id += 1
                    else:
                        logger.error(f"Failed to create BOM line for {component_sku}")
                        
                except Exception as e:
                    logger.error(f"Error creating BOM line for {component_sku}: {e}")
            
            # Create BOM header
            bom = {
                "id": bom_id,
                "product_id": [product_id, product_sku],
                "product_tmpl_id": [product_id, product_sku],
                "product_qty": 1.0,
                "bom_line_ids": bom_line_ids,
                "active": True
            }
            
            try:
                response = await self.client.post(
                    f"{self.base_url}/debug/boms",
                    json=bom
                )
                
                if response.status_code == 200:
                    logger.info(f"Created BOM for {product_sku} with {len(bom_line_ids)} lines")
                    bom_id += 1
                else:
                    logger.error(f"Failed to create BOM for {product_sku}: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Error creating BOM for {product_sku}: {e}")
        
        logger.info(f"Seeded BOMs for {len(bom_definitions)} products")
    
    async def seed_stock(self, sku_to_id: Dict[str, int]):
        """Seed stock quantities"""
        logger.info("Seeding stock quantities")
        
        # Stock definitions: sku -> (total_qty, reserved_qty)
        stock_definitions = {
            "EL-SAFETY-RELAY": (20.0, 2.0),
            "EL-IFACE-RELAY": (20.0, 1.0),
            "EL-CONTACTOR": (20.0, 1.0),
            "EL-AUX-CONTACT": (20.0, 1.0),
            "EL-FUSE-CARRIER": (20.0, 1.0),
            "EL-TERMINAL-BLK": (40.0, 4.0),
            
            # Final products (usually zero stock as they're manufactured to order)
            "CTRL-PANEL-A1": (0.0, 0.0),
            "SAFETY-SYS-B2": (1.0, 0.0),     # One in stock
            "HMI-DISPLAY-C3": (0.0, 0.0)
        }
        
        stock_id = 1
        location_id = 8  # Stock location
        
        for sku, (total_qty, reserved_qty) in stock_definitions.items():
            if sku not in sku_to_id:
                logger.warning(f"SKU {sku} not found in mapping")
                continue
            
            product_id = sku_to_id[sku]
            available_qty = total_qty - reserved_qty
            
            # Create stock quant record
            stock_quant = {
                "id": stock_id,
                "product_id": [product_id, sku],
                "location_id": [location_id, "WH/Stock"],
                "quantity": total_qty,
                "reserved_quantity": reserved_qty,
                "available_quantity": available_qty
            }
            
            try:
                response = await self.client.post(
                    f"{self.base_url}/debug/stock",
                    json=stock_quant
                )
                
                if response.status_code == 200:
                    logger.info(f"Set stock for {sku}: {available_qty} available ({total_qty} total, {reserved_qty} reserved)")
                    stock_id += 1
                else:
                    logger.error(f"Failed to set stock for {sku}: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Error setting stock for {sku}: {e}")
        
        logger.info(f"Seeded stock for {len(stock_definitions)} products")
    
    async def verify_seeded_data(self):
        """Verify that seeded data is accessible"""
        logger.info("Verifying seeded data")
        
        endpoints = [
            ("/debug/products", "products"),
            ("/debug/boms", "BOMs"),
            ("/debug/stock", "stock records")
        ]
        
        for endpoint, name in endpoints:
            try:
                response = await self.client.get(f"{self.base_url}{endpoint}")
                if response.status_code == 200:
                    data = response.json()
                    count = len(data) if isinstance(data, list) else len(data.get("data", []))
                    logger.info(f"✓ {count} {name} available")
                else:
                    logger.error(f"✗ Failed to fetch {name}: {response.status_code}")
            except Exception as e:
                logger.error(f"✗ Error fetching {name}: {e}")


async def main():
    """Main seeding function"""
    logger.info("🌱 Starting Odoo Mock seeding")
    
    seeder = OdooMockSeeder()
    
    try:
        # Check if Odoo Mock is available
        response = await seeder.client.get(f"{ODOO_MOCK_URL}/healthz")
        if response.status_code != 200:
            logger.error("❌ Odoo Mock service is not available. Make sure it's running on localhost:8069")
            return 1
        
        logger.info("✓ Odoo Mock service is available")
        
        # Clear existing data
        await seeder.clear_all_data()
        
        # Seed data in order (products first, then BOMs, then stock)
        sku_to_id = await seeder.seed_products()
        
        if not sku_to_id:
            logger.error("❌ Failed to seed products. Cannot continue.")
            return 1
        
        await seeder.seed_boms(sku_to_id)
        await seeder.seed_stock(sku_to_id)
        
        # Verify seeded data
        await seeder.verify_seeded_data()
        
        logger.info("🎉 Odoo Mock seeding completed successfully!")
        
        # Print summary
        print("\n" + "="*60)
        print("📊 SEEDED DATA SUMMARY")
        print("="*60)
        print("🏭 Final Products:")
        print("  • CTRL-PANEL-A1 (5-part ASRS demo BOM)")
        print("  • SAFETY-SYS-B2")
        print("  • HMI-DISPLAY-C3")
        print("\n🔩 Components:")
        print("  • Electronic components (PCBs, displays, relays)")
        print("  • Mechanical parts (brackets, screws, cables)")
        print("  • Power supplies and enclosures")
        print("\n📦 Stock Scenarios:")
        print("  • Most components have good stock levels")
        print("  • EL-SAFETY-RELAY / EL-IFACE-RELAY / EL-CONTACTOR")
        print("  • EL-AUX-CONTACT / EL-FUSE-CARRIER / EL-TERMINAL-BLK")
        print("  • Final products manufactured to order")
        print("\n🧪 Try these test scenarios:")
        print("  curl -X POST http://localhost:8080/admin/recompute/test-001 \\")
        print("    -H 'Content-Type: application/json' \\")
        print("    -d '{\"projectCode\": \"CTRL-PANEL-A1\", \"station\": \"STATION-A\"}'")
        print("="*60)
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Seeding failed: {e}")
        return 1
    finally:
        await seeder.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
