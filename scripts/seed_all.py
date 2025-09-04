#!/usr/bin/env python3
"""
Combined seeding script for both Odoo Mock and Orion-LD

This script seeds both services with demo data and verifies the complete setup.
"""
import asyncio
import sys
import subprocess
from pathlib import Path

# Add src to Python path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from hermes_odoo_adapter.utils.logging import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def run_seeding_script(script_path: Path) -> int:
    """Run a seeding script and return exit code"""
    logger.info(f"Running {script_path.name}")
    
    try:
        # Run the script using Python
        process = await asyncio.create_subprocess_exec(
            sys.executable, str(script_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        
        # Stream output in real-time
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            print(line.decode().rstrip())
        
        await process.wait()
        return process.returncode
        
    except Exception as e:
        logger.error(f"Error running {script_path.name}: {e}")
        return 1


async def check_services():
    """Check if required services are running"""
    logger.info("Checking required services...")
    
    import httpx
    
    services = [
        ("Odoo Mock", "http://localhost:8069/healthz"),
        ("Orion-LD", "http://localhost:1026/version")
    ]
    
    all_healthy = True
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        for service_name, health_url in services:
            try:
                response = await client.get(health_url)
                if response.status_code == 200:
                    logger.info(f"✓ {service_name} is running")
                else:
                    logger.error(f"✗ {service_name} returned status {response.status_code}")
                    all_healthy = False
            except Exception as e:
                logger.error(f"✗ {service_name} is not accessible: {e}")
                all_healthy = False
    
    return all_healthy


async def main():
    """Main function"""
    logger.info("🚀 Starting complete HERMES demo data seeding")
    
    # Check if services are running
    if not await check_services():
        logger.error("❌ Some required services are not running. Please start them first:")
        print("   make up")
        return 1
    
    scripts_dir = Path(__file__).parent
    
    # Run seeding scripts in order
    scripts = [
        scripts_dir / "seed_odoo_demo.py",
        scripts_dir / "seed_orion_demo.py"
    ]
    
    for script in scripts:
        if not script.exists():
            logger.error(f"❌ Script not found: {script}")
            return 1
        
        exit_code = await run_seeding_script(script)
        if exit_code != 0:
            logger.error(f"❌ {script.name} failed with exit code {exit_code}")
            return exit_code
        
        logger.info(f"✅ {script.name} completed successfully")
    
    # Final summary
    logger.info("🎉 Complete demo data seeding finished!")
    
    print("\n" + "="*70)
    print("🎯 HERMES DEMO ENVIRONMENT READY!")
    print("="*70)
    print("📊 What was seeded:")
    print("  • Odoo Mock: Products, BOMs, Stock levels")
    print("  • Orion-LD: Demo projects, Inventory items")
    print("\n🎮 Try these demo scenarios:")
    print()
    print("1️⃣ Successful reservation (good stock):")
    print("   curl -X PATCH http://localhost:1026/ngsi-ld/v1/entities/urn:ngsi-ld:Project:demo-project-001/attrs \\")
    print("     -H 'Content-Type: application/ld+json' \\")
    print("     -d '{\"status\": {\"type\": \"Property\", \"value\": \"requested\"}}'")
    print()
    print("2️⃣ Shortage scenario (low stock):")
    print("   curl -X PATCH http://localhost:1026/ngsi-ld/v1/entities/urn:ngsi-ld:Project:demo-project-002/attrs \\")
    print("     -H 'Content-Type: application/ld+json' \\")
    print("     -d '{\"status\": {\"type\": \"Property\", \"value\": \"requested\"}}'")
    print()
    print("3️⃣ Unknown product (error handling):")
    print("   curl -X PATCH http://localhost:1026/ngsi-ld/v1/entities/urn:ngsi-ld:Project:demo-project-005/attrs \\")
    print("     -H 'Content-Type: application/ld+json' \\")
    print("     -d '{\"status\": {\"type\": \"Property\", \"value\": \"requested\"}}'")
    print()
    print("🔍 Check results:")
    print("   curl 'http://localhost:1026/ngsi-ld/v1/entities?type=Reservation' | jq")
    print("   curl 'http://localhost:1026/ngsi-ld/v1/entities?type=Shortage' | jq")
    print()
    print("📈 Monitor the adapter:")
    print("   curl http://localhost:8080/metrics")
    print("   curl http://localhost:8080/readyz")
    print("   make logs-adapter")
    print("="*70)
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)