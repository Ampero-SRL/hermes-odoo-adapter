#!/usr/bin/env python3
"""
Seed script for populating Orion-LD with demo HERMES project data

This script creates sample Project entities in Orion-LD to demonstrate
the complete project workflow from request to reservation/shortage creation.
"""
import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Any

import httpx

# Add src to Python path for imports  
sys.path.append(str(Path(__file__).parent.parent / "src"))

from hermes_odoo_adapter.models.ngsi_models import Project
from hermes_odoo_adapter.utils.logging import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)

ORION_URL = "http://localhost:1026"
NGSI_LD_CONTEXT = "https://fiware.github.io/NGSI-LD_Tutorials/datamodels/ngsi-context.jsonld"


class OrionSeeder:
    """Seeder for Orion-LD NGSI-LD Context Broker"""
    
    def __init__(self, base_url: str = ORION_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Content-Type": "application/ld+json",
                "Accept": "application/ld+json"
            }
        )
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
    
    async def clear_all_entities(self):
        """Clear all existing entities in Orion-LD"""
        logger.info("Clearing existing entities from Orion-LD")
        
        entity_types = ["Project", "Reservation", "Shortage", "InventoryItem"]
        
        for entity_type in entity_types:
            try:
                # Get all entities of this type
                response = await self.client.get(
                    f"{self.base_url}/ngsi-ld/v1/entities",
                    params={"type": entity_type}
                )
                
                if response.status_code == 200:
                    entities = response.json()
                    
                    # Delete each entity
                    for entity in entities:
                        entity_id = entity.get("id")
                        if entity_id:
                            delete_response = await self.client.delete(
                                f"{self.base_url}/ngsi-ld/v1/entities/{entity_id}"
                            )
                            if delete_response.status_code == 204:
                                logger.debug(f"Deleted entity: {entity_id}")
                            else:
                                logger.warning(f"Failed to delete entity {entity_id}: {delete_response.status_code}")
                    
                    logger.info(f"Cleared {len(entities)} {entity_type} entities")
                
                elif response.status_code == 404:
                    # No entities of this type found
                    logger.info(f"No {entity_type} entities found to clear")
                else:
                    logger.warning(f"Failed to fetch {entity_type} entities: {response.status_code}")
                    
            except Exception as e:
                logger.warning(f"Error clearing {entity_type} entities: {e}")
    
    async def seed_demo_projects(self) -> List[Dict[str, Any]]:
        """Seed demo project entities"""
        logger.info("Seeding demo project entities")
        
        # Demo projects with different scenarios
        projects_data = [
            {
                "project_id": "demo-project-001",
                "code": "CTRL-PANEL-A1",
                "station": "STATION-A", 
                "status": "planning",
                "description": "Demo project for Industrial Control Panel - should create reservation"
            },
            {
                "project_id": "demo-project-002", 
                "code": "SAFETY-SYS-B2",
                "station": "STATION-B",
                "status": "planning",
                "description": "Demo project for Safety System - may create shortage (low relay stock)"
            },
            {
                "project_id": "demo-project-003",
                "code": "HMI-DISPLAY-C3",
                "station": "STATION-C",
                "status": "planning", 
                "description": "Demo project for HMI Display - may create shortage (low display stock)"
            },
            {
                "project_id": "demo-project-004",
                "code": "CTRL-PANEL-A1",
                "station": "STATION-D",
                "status": "planning",
                "description": "Second control panel project for testing multiple projects"
            },
            {
                "project_id": "demo-project-005",
                "code": "UNKNOWN-PRODUCT",
                "station": "STATION-E",
                "status": "planning",
                "description": "Project with unknown product code (should fail gracefully)"
            }
        ]
        
        created_projects = []
        
        for project_data in projects_data:
            project = Project.create(
                project_data["project_id"],
                project_data["code"], 
                project_data["station"],
                project_data["status"]
            )
            
            try:
                # Add custom description property
                project_dict = project.dict(by_alias=True)
                project_dict["description"] = {
                    "type": "Property",
                    "value": project_data["description"]
                }
                
                response = await self.client.post(
                    f"{self.base_url}/ngsi-ld/v1/entities",
                    json=project_dict
                )
                
                if response.status_code in (201, 204):
                    logger.info(f"Created project: {project_data['project_id']} ({project_data['code']})")
                    created_projects.append(project_dict)
                elif response.status_code == 409:
                    logger.warning(f"Project {project_data['project_id']} already exists")
                else:
                    logger.error(f"Failed to create project {project_data['project_id']}: {response.status_code} - {response.text}")
                    
            except Exception as e:
                logger.error(f"Error creating project {project_data['project_id']}: {e}")
        
        logger.info(f"Seeded {len(created_projects)} demo projects")
        return created_projects
    
    async def create_sample_inventory_items(self):
        """Create sample inventory items for demonstration"""
        logger.info("Creating sample inventory items")
        
        from hermes_odoo_adapter.models.ngsi_models import InventoryItem
        
        # Sample inventory data matching the Odoo seed data
        inventory_items = [
            ("LED-STRIP-24V-1M", 45.0, 5.0),        # Available: 45, Reserved: 5  
            ("BRACKET-STEEL-001", 80.0, 20.0),      # Available: 80, Reserved: 20
            ("PCB-CTRL-REV21", 22.0, 3.0),          # Available: 22, Reserved: 3
            ("ENCLOSURE-IP65-300", 13.0, 2.0),      # Available: 13, Reserved: 2
            ("PSU-24VDC-5A", 25.0, 5.0),            # Available: 25, Reserved: 5
            ("CABLE-ASSY-2M", 70.0, 10.0),          # Available: 70, Reserved: 10
            ("SCREW-M4X12-DIN912", 450.0, 50.0),    # Available: 450, Reserved: 50
            ("RELAY-SAFETY-24V", 6.0, 2.0),         # Available: 6, Reserved: 2 (LOW STOCK)
            ("ESTOP-BTN-RED", 11.0, 1.0),           # Available: 11, Reserved: 1
            ("TFT-DISPLAY-7IN", 5.0, 0.0),          # Available: 5, Reserved: 0 (VERY LOW)
        ]
        
        created_count = 0
        
        for sku, available, reserved in inventory_items:
            inventory_item = InventoryItem.create(sku, available, reserved)
            
            try:
                response = await self.client.post(
                    f"{self.base_url}/ngsi-ld/v1/entities",
                    json=inventory_item.dict(by_alias=True)
                )
                
                if response.status_code in (201, 204):
                    logger.info(f"Created inventory item: {sku} (Available: {available}, Reserved: {reserved})")
                    created_count += 1
                elif response.status_code == 409:
                    logger.debug(f"Inventory item {sku} already exists")
                else:
                    logger.error(f"Failed to create inventory item {sku}: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Error creating inventory item {sku}: {e}")
        
        logger.info(f"Created {created_count} inventory items")
    
    async def verify_seeded_data(self):
        """Verify that seeded data is accessible"""
        logger.info("Verifying seeded data in Orion-LD")
        
        entity_types = [
            ("Project", "demo projects"),
            ("InventoryItem", "inventory items"),
            ("Reservation", "reservations"),
            ("Shortage", "shortages")
        ]
        
        for entity_type, description in entity_types:
            try:
                response = await self.client.get(
                    f"{self.base_url}/ngsi-ld/v1/entities",
                    params={"type": entity_type}
                )
                
                if response.status_code == 200:
                    entities = response.json()
                    count = len(entities) if isinstance(entities, list) else 0
                    logger.info(f"✓ {count} {description} available")
                    
                    # Show details for projects
                    if entity_type == "Project" and entities:
                        for entity in entities[:3]:  # Show first 3
                            code = entity.get("code", {}).get("value", "N/A")
                            status = entity.get("status", {}).get("value", "N/A")
                            station = entity.get("station", {}).get("value", "N/A")
                            logger.info(f"  • {entity['id']}: {code} at {station} ({status})")
                
                elif response.status_code == 404:
                    logger.info(f"✓ 0 {description} (none found)")
                else:
                    logger.error(f"✗ Failed to fetch {description}: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"✗ Error fetching {description}: {e}")


async def main():
    """Main seeding function"""
    logger.info("🌱 Starting Orion-LD seeding")
    
    seeder = OrionSeeder()
    
    try:
        # Check if Orion-LD is available
        response = await seeder.client.get(f"{ORION_URL}/version")
        if response.status_code != 200:
            logger.error("❌ Orion-LD service is not available. Make sure it's running on localhost:1026")
            return 1
        
        version_info = response.json()
        logger.info(f"✓ Orion-LD service is available (version: {version_info.get('version', 'unknown')})")
        
        # Clear existing entities
        await seeder.clear_all_entities()
        
        # Seed demo data
        projects = await seeder.seed_demo_projects()
        await seeder.create_sample_inventory_items()
        
        # Verify seeded data
        await seeder.verify_seeded_data()
        
        logger.info("🎉 Orion-LD seeding completed successfully!")
        
        # Print summary
        print("\n" + "="*60)
        print("🌐 ORION-LD SEEDED DATA SUMMARY")
        print("="*60)
        print("📋 Demo Projects:")
        print("  • demo-project-001: CTRL-PANEL-A1 @ STATION-A")
        print("  • demo-project-002: SAFETY-SYS-B2 @ STATION-B (shortage scenario)")
        print("  • demo-project-003: HMI-DISPLAY-C3 @ STATION-C (shortage scenario)")
        print("  • demo-project-004: CTRL-PANEL-A1 @ STATION-D")
        print("  • demo-project-005: UNKNOWN-PRODUCT @ STATION-E (error scenario)")
        print("\n📦 Inventory Items:")
        print("  • Component stock levels reflecting Odoo Mock data")
        print("  • Some items have low stock for shortage testing")
        print("\n🎯 Next Steps:")
        print("  1. Start the HERMES adapter:")
        print("     make up")
        print("  2. Trigger a project by changing status to 'requested':")
        print("     curl -X PATCH http://localhost:1026/ngsi-ld/v1/entities/urn:ngsi-ld:Project:demo-project-001/attrs \\")
        print("       -H 'Content-Type: application/ld+json' \\")
        print("       -d '{\"status\": {\"type\": \"Property\", \"value\": \"requested\"}}'")
        print("  3. Check results:")
        print("     curl http://localhost:1026/ngsi-ld/v1/entities?type=Reservation")
        print("     curl http://localhost:1026/ngsi-ld/v1/entities?type=Shortage")
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