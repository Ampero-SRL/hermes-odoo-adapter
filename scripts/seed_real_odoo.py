#!/usr/bin/env python3
"""
Seed script for populating real Odoo with demo manufacturing data

This script connects to a real Odoo instance and creates products, BOMs,
and stock records for the HERMES manufacturing demo.
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add src to Python path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from hermes_odoo_adapter.odoo_client import OdooClient, OdooError
from hermes_odoo_adapter.utils.logging import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Default Odoo connection settings
ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069/jsonrpc")
ODOO_DB = os.getenv("ODOO_DB", "odoo")
ODOO_USER = os.getenv("ODOO_USER", "admin")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "admin")


class RealOdooSeeder:
    """Seeder for real Odoo ERP system"""
    
    def __init__(self, url: str = ODOO_URL, database: str = ODOO_DB, 
                 username: str = ODOO_USER, password: str = ODOO_PASSWORD):
        self.client = OdooClient(url, database, username, password)
        self.created_records = {
            "products": [],
            "boms": [],
            "stock_locations": [],
            "stock_quants": []
        }
    
    async def connect(self):
        """Connect to Odoo"""
        await self.client.connect()
        logger.info("Connected to Odoo")
    
    async def close(self):
        """Close connection"""
        await self.client.close()
    
    async def verify_modules(self) -> bool:
        """Verify required modules are installed"""
        logger.info("Verifying required Odoo modules")
        
        required_modules = ["base", "product", "mrp", "stock"]
        
        try:
            # Check installed modules
            modules = await self.client.search_read(
                "ir.module.module",
                [("name", "in", required_modules), ("state", "=", "installed")],
                ["name", "state"]
            )
            
            installed_modules = {m["name"] for m in modules}
            missing_modules = set(required_modules) - installed_modules
            
            if missing_modules:
                logger.error(f"Missing required modules: {missing_modules}")
                logger.info("Please install missing modules in Odoo before running this script")
                return False
            
            logger.info(f"✓ All required modules are installed: {required_modules}")
            return True
            
        except Exception as e:
            logger.error(f"Error checking modules: {e}")
            return False
    
    async def get_or_create_category(self, name: str, parent_id: Optional[int] = None) -> int:
        """Get or create product category"""
        try:
            # Try to find existing category
            categories = await self.client.search_read(
                "product.category",
                [("name", "=", name)],
                ["id", "name"]
            )
            
            if categories:
                return categories[0]["id"]
            
            # Create new category
            category_data = {"name": name}
            if parent_id:
                category_data["parent_id"] = parent_id
            
            category_id = await self.client.create("product.category", category_data)
            logger.info(f"Created product category: {name} (ID: {category_id})")
            return category_id
            
        except Exception as e:
            logger.error(f"Error creating category {name}: {e}")
            return 1  # Default to 'All' category
    
    async def archive_default_products(self):
        """Archive default Odoo demo products to keep only HERMES products"""
        logger.info("Archiving default Odoo products")

        # Get our HERMES categories
        our_categories = await self.client.search_read(
            "product.category",
            [("name", "in", ["HERMES Electrical - Components", "HERMES Electrical - Finished Goods"])],
            ["id"]
        )

        if not our_categories:
            logger.warning("HERMES categories not found, skipping archive")
            return

        our_cat_ids = [c["id"] for c in our_categories]

        # Find all active products NOT in our categories
        demo_products = await self.client.search_read(
            "product.product",
            [("categ_id", "not in", our_cat_ids), ("active", "=", True)],
            ["id", "name"]
        )

        if not demo_products:
            logger.info("No default products to archive")
            return

        logger.info(f"Archiving {len(demo_products)} default Odoo products")

        # Archive them (set active=False)
        for product in demo_products:
            try:
                await self.client.write("product.product", [product["id"]], {"active": False})
            except Exception as e:
                logger.warning(f"Could not archive product {product['id']}: {e}")

        logger.info(f"✓ Archived {len(demo_products)} default products")

    async def setup_visual_customization(self):
        """Set up Odoo visual customizations"""
        logger.info("Applying visual customizations")

        try:
            # Set company name and details
            company_data = {
                "name": "HERMES Manufacturing Demo",
                "email": "demo@hermes-manufacturing.local",
            }

            # Update the main company (usually ID 1)
            companies = await self.client.search("res.company", [], limit=1)
            if companies:
                await self.client.write("res.company", companies, company_data)
                logger.info("✓ Updated company details")

        except Exception as e:
            logger.warning(f"Could not apply all visual customizations: {e}")

    async def seed_products(self) -> Dict[str, int]:
        """Seed products and return SKU to ID mapping"""
        logger.info("Seeding products in real Odoo")

        # Create HERMES parent category
        hermes_parent_cat = await self.get_or_create_category("HERMES Electrical")

        # Create product categories under HERMES parent
        finished_goods_cat = await self.get_or_create_category("HERMES Electrical - Finished Goods")
        components_cat = await self.get_or_create_category("HERMES Electrical - Components") 
        
        # Get default UoM (Units)
        uom_units = await self.client.search_read(
            "uom.uom",
            [("name", "=", "Units")],
            ["id", "name"]
        )
        
        if not uom_units:
            logger.error("Could not find 'Units' UoM in Odoo")
            return {}
        
        uom_id = uom_units[0]["id"]
        
        products_data = [
            # Finished products
            {
                "name": "Industrial Control Panel A1",
                "default_code": "CTRL-PANEL-A1",
                "type": "product",
                "categ_id": finished_goods_cat,
                "uom_id": uom_id,
                "uom_po_id": uom_id,
                "sale_ok": True,
                "purchase_ok": False,
                "list_price": 1500.0,
                "standard_price": 950.0,
            },
            {
                "name": "Safety Control System B2",
                "default_code": "SAFETY-SYS-B2",
                "type": "product", 
                "categ_id": finished_goods_cat,
                "uom_id": uom_id,
                "uom_po_id": uom_id,
                "sale_ok": True,
                "purchase_ok": False,
                "list_price": 2200.0,
                "standard_price": 1400.0,
            },
            {
                "name": "HMI Display Unit C3",
                "default_code": "HMI-DISPLAY-C3",
                "type": "product",
                "categ_id": finished_goods_cat,
                "uom_id": uom_id,
                "uom_po_id": uom_id,
                "sale_ok": True,
                "purchase_ok": False,
                "list_price": 800.0,
                "standard_price": 500.0,
            },
            
            # Components
            {
                "name": "LED Strip 24V 1m",
                "default_code": "LED-STRIP-24V-1M",
                "type": "product",
                "categ_id": components_cat,
                "uom_id": uom_id,
                "uom_po_id": uom_id,
                "sale_ok": False,
                "purchase_ok": True,
                "standard_price": 25.0,
            },
            {
                "name": "Mounting Bracket Steel",
                "default_code": "BRACKET-STEEL-001",
                "type": "product",
                "categ_id": components_cat,
                "uom_id": uom_id,
                "uom_po_id": uom_id,
                "sale_ok": False,
                "purchase_ok": True,
                "standard_price": 12.50,
            },
            {
                "name": "Control PCB Rev2.1",
                "default_code": "PCB-CTRL-REV21",
                "type": "product",
                "categ_id": components_cat,
                "uom_id": uom_id,
                "uom_po_id": uom_id,
                "sale_ok": False,
                "purchase_ok": True,
                "standard_price": 125.0,
            },
            {
                "name": "Safety Relay 24VDC",
                "default_code": "RELAY-SAFETY-24V",
                "type": "product",
                "categ_id": components_cat,
                "uom_id": uom_id,
                "uom_po_id": uom_id,
                "sale_ok": False,
                "purchase_ok": True,
                "standard_price": 85.0,
            },
            {
                "name": "Emergency Stop Button Red",
                "default_code": "ESTOP-BTN-RED",
                "type": "product",
                "categ_id": components_cat,
                "uom_id": uom_id,
                "uom_po_id": uom_id,
                "sale_ok": False,
                "purchase_ok": True,
                "standard_price": 45.0,
            },
            {
                "name": "Display TFT 7inch",
                "default_code": "TFT-DISPLAY-7IN",
                "type": "product",
                "categ_id": components_cat,
                "uom_id": uom_id,
                "uom_po_id": uom_id,
                "sale_ok": False,
                "purchase_ok": True,
                "standard_price": 180.0,
            },
            {
                "name": "Enclosure IP65 300x200x120",
                "default_code": "ENCLOSURE-IP65-300",
                "type": "product",
                "categ_id": components_cat,
                "uom_id": uom_id,
                "uom_po_id": uom_id,
                "sale_ok": False,
                "purchase_ok": True,
                "standard_price": 95.0,
            },
            {
                "name": "Power Supply 24VDC 5A",
                "default_code": "PSU-24VDC-5A",
                "type": "product",
                "categ_id": components_cat,
                "uom_id": uom_id,
                "uom_po_id": uom_id,
                "sale_ok": False,
                "purchase_ok": True,
                "standard_price": 55.0,
            },
            {
                "name": "Cable Assembly 2m",
                "default_code": "CABLE-ASSY-2M",
                "type": "product",
                "categ_id": components_cat,
                "uom_id": uom_id,
                "uom_po_id": uom_id,
                "sale_ok": False,
                "purchase_ok": True,
                "standard_price": 15.0,
            },
            {
                "name": "Screws M4x12 DIN912",
                "default_code": "SCREW-M4X12-DIN912",
                "type": "product",
                "categ_id": components_cat,
                "uom_id": uom_id,
                "uom_po_id": uom_id,
                "sale_ok": False,
                "purchase_ok": True,
                "standard_price": 0.25,
            }
        ]
        
        sku_to_id = {}
        
        for product_data in products_data:
            try:
                # Check if product already exists
                existing = await self.client.search_read(
                    "product.product",
                    [("default_code", "=", product_data["default_code"])],
                    ["id", "default_code"]
                )
                
                if existing:
                    product_id = existing[0]["id"]
                    sku_to_id[product_data["default_code"]] = product_id
                    logger.info(f"Product already exists: {product_data['name']} (ID: {product_id})")
                    continue
                
                # Create new product
                product_id = await self.client.create("product.product", product_data)
                sku_to_id[product_data["default_code"]] = product_id
                self.created_records["products"].append(product_id)
                
                logger.info(f"Created product: {product_data['name']} (ID: {product_id})")
                
            except Exception as e:
                logger.error(f"Error creating product {product_data['name']}: {e}")
        
        logger.info(f"Seeded {len(sku_to_id)} products")
        return sku_to_id
    
    async def seed_boms(self, sku_to_id: Dict[str, int]):
        """Create Bills of Materials"""
        logger.info("Creating Bills of Materials")
        
        # BOM definitions
        bom_definitions = {
            "CTRL-PANEL-A1": [
                ("LED-STRIP-24V-1M", 2.0),
                ("BRACKET-STEEL-001", 4.0),
                ("PCB-CTRL-REV21", 1.0),
                ("ENCLOSURE-IP65-300", 1.0),
                ("PSU-24VDC-5A", 1.0),
                ("CABLE-ASSY-2M", 3.0),
                ("SCREW-M4X12-DIN912", 12.0)
            ],
            "SAFETY-SYS-B2": [
                ("RELAY-SAFETY-24V", 2.0),
                ("ESTOP-BTN-RED", 1.0),
                ("PCB-CTRL-REV21", 1.0),
                ("ENCLOSURE-IP65-300", 1.0),
                ("PSU-24VDC-5A", 1.0),
                ("CABLE-ASSY-2M", 2.0),
                ("SCREW-M4X12-DIN912", 8.0)
            ],
            "HMI-DISPLAY-C3": [
                ("TFT-DISPLAY-7IN", 1.0),
                ("PCB-CTRL-REV21", 1.0),
                ("ENCLOSURE-IP65-300", 1.0),
                ("PSU-24VDC-5A", 1.0),
                ("CABLE-ASSY-2M", 2.0),
                ("SCREW-M4X12-DIN912", 6.0)
            ]
        }
        
        for product_sku, components in bom_definitions.items():
            if product_sku not in sku_to_id:
                logger.warning(f"Product {product_sku} not found, skipping BOM")
                continue
            
            product_id = sku_to_id[product_sku]
            product_record = await self.client.read(
                "product.product", product_id, ["product_tmpl_id"]
            )
            if not product_record or not product_record[0].get("product_tmpl_id"):
                logger.error(f"Could not retrieve template for {product_sku}, skipping BOM")
                continue
            product_tmpl_id = product_record[0]["product_tmpl_id"][0]
            
            try:
                # Check if BOM already exists
                existing_boms = await self.client.search_read(
                    "mrp.bom",
                    [("product_id", "=", product_id)],
                    ["id", "product_id"]
                )
                
                if existing_boms:
                    logger.info(f"BOM already exists for {product_sku}")
                    continue
                
                # Create BOM lines data
                bom_lines = []
                for component_sku, qty in components:
                    if component_sku not in sku_to_id:
                        logger.warning(f"Component {component_sku} not found, skipping")
                        continue
                    
                    component_id = sku_to_id[component_sku]
                    bom_lines.append((0, 0, {
                        "product_id": component_id,
                        "product_qty": qty,
                    }))
                
                if not bom_lines:
                    logger.warning(f"No valid components found for BOM {product_sku}")
                    continue
                
                # Create BOM
                bom_data = {
                    "product_id": product_id,
                    "product_tmpl_id": product_tmpl_id,
                    "product_qty": 1.0,
                    "type": "normal",
                    "bom_line_ids": bom_lines
                }
                
                bom_id = await self.client.create("mrp.bom", bom_data)
                self.created_records["boms"].append(bom_id)
                
                logger.info(f"Created BOM for {product_sku} with {len(bom_lines)} components (ID: {bom_id})")
                
            except Exception as e:
                logger.error(f"Error creating BOM for {product_sku}: {e}")
        
        logger.info("BOM creation completed")
    
    async def seed_stock_quantities(self, sku_to_id: Dict[str, int]):
        """Create initial stock quantities"""
        logger.info("Setting initial stock quantities")
        
        # Find stock location
        stock_locations = await self.client.search_read(
            "stock.location",
            [("usage", "=", "internal"), ("name", "ilike", "stock")],
            ["id", "name"]
        )
        
        if not stock_locations:
            logger.error("Could not find stock location")
            return
        
        stock_location_id = stock_locations[0]["id"]
        logger.info(f"Using stock location: {stock_locations[0]['name']} (ID: {stock_location_id})")
        
        # Stock quantities (SKU -> quantity)
        stock_quantities = {
            # Components with good stock
            "LED-STRIP-24V-1M": 50.0,
            "BRACKET-STEEL-001": 100.0,
            "PCB-CTRL-REV21": 25.0,
            "ENCLOSURE-IP65-300": 15.0,
            "PSU-24VDC-5A": 30.0,
            "CABLE-ASSY-2M": 80.0,
            "SCREW-M4X12-DIN912": 500.0,
            
            # Components with limited stock (for shortage scenarios)
            "RELAY-SAFETY-24V": 8.0,   # Low stock
            "ESTOP-BTN-RED": 12.0,
            "TFT-DISPLAY-7IN": 5.0,    # Very low stock
        }
        
        inventory_id = await self.client.create(
            "stock.inventory",
            {
                "name": "Initial HERMES stock seed",
                "location_ids": [(6, 0, [stock_location_id])],
            },
        )
        lines_created = 0

        for sku, quantity in stock_quantities.items():
            if sku not in sku_to_id:
                logger.warning(f"SKU {sku} not found, skipping stock adjustment")
                continue
            
            product_id = sku_to_id[sku]
            
            try:
                product_data = await self.client.read(
                    "product.product", product_id, ["uom_id"]
                )
                uom_id = product_data[0]["uom_id"][0]

                line_vals = {
                    "inventory_id": inventory_id,
                    "product_id": product_id,
                    "location_id": stock_location_id,
                    "product_qty": quantity,
                    "product_uom_id": uom_id,
                }
                await self.client.create("stock.inventory.line", line_vals)
                lines_created += 1
                logger.info(f"Prepared stock line for {sku}: {quantity} units")
            except Exception as e:
                logger.error(f"Error preparing stock for {sku}: {e}")

        if lines_created:
            await self.client.call("stock.inventory", "action_start", [[inventory_id]])
            await self.client.call("stock.inventory", "action_validate", [[inventory_id]])
            logger.info("Stock quantity setup completed")
        else:
            logger.warning("No stock lines were created; skipping inventory validation")
    
    async def verify_setup(self, sku_to_id: Dict[str, int]):
        """Verify the seeded data"""
        logger.info("Verifying seeded data")
        
        # Check products
        product_count = len(sku_to_id)
        logger.info(f"✓ {product_count} products created")
        
        # Check BOMs
        bom_count = await self.client.search("mrp.bom", [], count=True)
        logger.info(f"✓ {bom_count} BOMs in system")
        
        # Check stock
        stock_count = await self.client.search("stock.quant", [("quantity", ">", 0)], count=True)
        logger.info(f"✓ {stock_count} stock records with positive quantity")
        
        logger.info("✅ Real Odoo setup verification completed")


async def main():
    """Main seeding function"""
    logger.info("🏭 Starting Real Odoo seeding")
    
    seeder = RealOdooSeeder()
    
    try:
        # Connect and verify
        await seeder.connect()
        
        if not await seeder.verify_modules():
            return 1
        
        # Apply visual customizations
        await seeder.setup_visual_customization()

        # Seed data
        sku_to_id = await seeder.seed_products()
        if not sku_to_id:
            logger.error("❌ Failed to seed products")
            return 1

        await seeder.seed_boms(sku_to_id)
        await seeder.seed_stock_quantities(sku_to_id)

        # Archive default Odoo products (keep only HERMES)
        await seeder.archive_default_products()

        # Verify
        await seeder.verify_setup(sku_to_id)
        
        logger.info("🎉 Real Odoo seeding completed successfully!")
        
        print("\n" + "="*60)
        print("🏭 REAL ODOO SETUP COMPLETED")
        print("="*60)
        print("📊 What was created:")
        print(f"  • {len(sku_to_id)} Products (finished goods + components)")
        print(f"  • {len(seeder.created_records['boms'])} Bills of Materials")
        print("  • Initial stock quantities")
        print("\n🔗 Access Odoo:")
        print("  URL: http://localhost:8069")
        print("  User: admin")
        print("  Password: admin")
        print("  Database: odoo")
        print("\n🧪 Test the integration:")
        print("  1. Start the adapter: make up")
        print("  2. Seed Orion with projects: python scripts/seed_orion_demo.py")
        print("  3. Test project processing via Orion-LD")
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
