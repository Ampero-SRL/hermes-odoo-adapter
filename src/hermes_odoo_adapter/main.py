"""
HERMES Odoo Adapter - Main FastAPI Application
"""
import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, Response, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ValidationError
import uvicorn

from .settings import settings
from .utils.logging import setup_logging, get_logger, LoggingContext
from .utils.metrics import metrics
from .utils.idempotency import generate_correlation_id
from .odoo_client import OdooClient, OdooError
from .orion_client import OrionClient, OrionError
from .workers.project_sync import ProjectSyncWorker
from .workers.inventory_sync import InventorySyncWorker

# Setup logging first
setup_logging()
logger = get_logger(__name__)

# Global clients and workers
odoo_client: Optional[OdooClient] = None
orion_client: Optional[OrionClient] = None
project_worker: Optional[ProjectSyncWorker] = None
inventory_worker: Optional[InventorySyncWorker] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global odoo_client, orion_client, project_worker, inventory_worker
    
    logger.info("Starting HERMES Odoo Adapter", version="0.1.0")
    
    try:
        # Initialize clients
        odoo_client = OdooClient()
        orion_client = OrionClient()
        
        await odoo_client.connect()
        await orion_client.connect()
        
        # Initialize workers
        project_worker = ProjectSyncWorker(odoo_client, orion_client)
        inventory_worker = InventorySyncWorker(odoo_client, orion_client)
        
        # Setup Orion subscription
        await project_worker.setup_subscription()
        
        # Start background tasks
        if settings.inventory_sync_enabled:
            asyncio.create_task(inventory_worker.start())
        
        logger.info("HERMES Odoo Adapter started successfully")
        
        yield
        
    except Exception as e:
        logger.error("Failed to start application", error=str(e))
        raise
    finally:
        # Cleanup
        logger.info("Shutting down HERMES Odoo Adapter")
        
        if inventory_worker:
            await inventory_worker.stop()
        
        if odoo_client:
            await odoo_client.close()
        
        if orion_client:
            await orion_client.close()
        
        logger.info("HERMES Odoo Adapter stopped")


# Create FastAPI app
app = FastAPI(
    title="HERMES Odoo Adapter",
    description="FIWARE NGSI-LD adapter for Odoo ERP integration",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.testing else None,
    redoc_url="/redoc" if not settings.testing else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ReadinessResponse(BaseModel):
    status: str
    checks: Dict[str, bool]
    details: Dict[str, str]


class OrionNotification(BaseModel):
    subscriptionId: str
    data: List[Dict[str, Any]]


class RecomputeRequest(BaseModel):
    projectCode: Optional[str] = None
    station: Optional[str] = None


# Middleware for correlation ID and request timing
@app.middleware("http")
async def add_correlation_middleware(request: Request, call_next):
    """Add correlation ID and time requests"""
    correlation_id = generate_correlation_id()
    
    with LoggingContext(correlation_id=correlation_id):
        # Time the request
        with metrics.time_http_request(request.method, request.url.path):
            response = await call_next(request)
            
            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            
            return response


# Health and monitoring endpoints
@app.get("/healthz", response_model=HealthResponse, tags=["monitoring"])
async def health_check():
    """Liveness probe - check if service is running"""
    return HealthResponse(
        status="healthy",
        service="hermes-odoo-adapter",
        version="0.1.0"
    )


@app.get("/readyz", response_model=ReadinessResponse, tags=["monitoring"])
async def readiness_check():
    """Readiness probe - check if service is ready to accept requests"""
    checks = {}
    details = {}
    
    # Check Odoo connectivity
    if odoo_client:
        try:
            checks["odoo"] = await odoo_client.health_check()
            details["odoo"] = "Connected" if checks["odoo"] else "Connection failed"
        except Exception as e:
            checks["odoo"] = False
            details["odoo"] = f"Error: {str(e)}"
    else:
        checks["odoo"] = False
        details["odoo"] = "Client not initialized"
    
    # Check Orion-LD connectivity
    if orion_client:
        try:
            checks["orion"] = await orion_client.health_check()
            details["orion"] = "Connected" if checks["orion"] else "Connection failed"
        except Exception as e:
            checks["orion"] = False
            details["orion"] = f"Error: {str(e)}"
    else:
        checks["orion"] = False
        details["orion"] = "Client not initialized"
    
    # Overall status
    all_healthy = all(checks.values())
    status = "ready" if all_healthy else "not_ready"
    
    return ReadinessResponse(
        status=status,
        checks=checks,
        details=details
    )


@app.get("/metrics", tags=["monitoring"])
async def get_metrics():
    """Prometheus metrics endpoint"""
    return PlainTextResponse(
        content=metrics.get_metrics(),
        media_type=metrics.get_content_type()
    )


# Webhook endpoints
@app.post("/orion/notifications", tags=["webhooks"])
async def handle_orion_notification(notification: OrionNotification, background_tasks: BackgroundTasks):
    """Handle NGSI-LD notifications from Orion-LD"""
    logger.info("Received Orion notification", subscription_id=notification.subscriptionId, entity_count=len(notification.data))
    
    if not project_worker:
        raise HTTPException(status_code=503, detail="Project worker not available")
    
    # Process notifications in background
    for entity_data in notification.data:
        background_tasks.add_task(project_worker.handle_project_notification, entity_data)
    
    return {"message": "Notification received", "entities_queued": len(notification.data)}


@app.post("/odoo/webhook", tags=["webhooks"])
async def handle_odoo_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle webhooks from Odoo (if configured)"""
    if not settings.webhook_enabled:
        raise HTTPException(status_code=404, detail="Webhooks not enabled")
    
    try:
        payload = await request.json()
        logger.info("Received Odoo webhook", payload_keys=list(payload.keys()))
        
        # Handle different webhook types
        webhook_type = payload.get("type")
        
        if webhook_type == "stock_change" and inventory_worker:
            background_tasks.add_task(inventory_worker.handle_stock_change, payload)
        
        return {"message": "Webhook received"}
        
    except Exception as e:
        logger.error("Error processing Odoo webhook", error=str(e))
        raise HTTPException(status_code=400, detail=f"Webhook processing error: {str(e)}")


# Administrative endpoints
@app.post("/admin/recompute/{project_id}", tags=["admin"])
async def recompute_project(project_id: str, request: RecomputeRequest = RecomputeRequest(), background_tasks: BackgroundTasks):
    """Force recomputation of a project's reservation/shortage"""
    logger.info("Manual recompute requested", project_id=project_id)
    
    if not project_worker:
        raise HTTPException(status_code=503, detail="Project worker not available")
    
    try:
        # Create a synthetic project entity for recomputation
        project_entity = {
            "id": f"urn:ngsi-ld:Project:{project_id}",
            "type": "Project",
            "code": {"type": "Property", "value": request.projectCode or project_id},
            "status": {"type": "Property", "value": "requested"}
        }
        
        if request.station:
            project_entity["station"] = {"type": "Property", "value": request.station}
        
        # Process in background
        background_tasks.add_task(project_worker.handle_project_notification, project_entity)
        
        return {"message": f"Recomputation queued for project {project_id}"}
        
    except Exception as e:
        logger.error("Error queuing recomputation", project_id=project_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Recomputation error: {str(e)}")


@app.get("/admin/inventory/sync", tags=["admin"])
async def trigger_inventory_sync(background_tasks: BackgroundTasks):
    """Manually trigger inventory synchronization"""
    logger.info("Manual inventory sync requested")
    
    if not inventory_worker:
        raise HTTPException(status_code=503, detail="Inventory worker not available")
    
    try:
        background_tasks.add_task(inventory_worker.sync_inventory)
        return {"message": "Inventory synchronization queued"}
        
    except Exception as e:
        logger.error("Error triggering inventory sync", error=str(e))
        raise HTTPException(status_code=500, detail=f"Inventory sync error: {str(e)}")


@app.get("/admin/inventory/status", tags=["admin"])
async def get_inventory_sync_status():
    """Get inventory synchronization status"""
    if not inventory_worker:
        raise HTTPException(status_code=503, detail="Inventory worker not available")
    
    try:
        return inventory_worker.get_sync_status()
    except Exception as e:
        logger.error("Error getting inventory sync status", error=str(e))
        raise HTTPException(status_code=500, detail=f"Status error: {str(e)}")


@app.post("/admin/inventory/sync/{sku}", tags=["admin"])
async def sync_product_inventory(sku: str, background_tasks: BackgroundTasks):
    """Sync inventory for a specific product by SKU"""
    logger.info("Manual product inventory sync requested", sku=sku)
    
    if not inventory_worker:
        raise HTTPException(status_code=503, detail="Inventory worker not available")
    
    try:
        background_tasks.add_task(inventory_worker.sync_product_inventory, sku)
        return {"message": f"Inventory synchronization queued for SKU {sku}"}
        
    except Exception as e:
        logger.error("Error triggering product inventory sync", sku=sku, error=str(e))
        raise HTTPException(status_code=500, detail=f"Product sync error: {str(e)}")


# Debug endpoints (only in non-production)
if not settings.testing:
    
    @app.get("/debug/reservation/{project_id}", tags=["debug"])
    async def debug_get_reservation(project_id: str):
        """Get reservation details for debugging"""
        if not orion_client:
            raise HTTPException(status_code=503, detail="Orion client not available")
        
        try:
            entity_id = f"urn:ngsi-ld:Reservation:{project_id}"
            reservation = await orion_client.get_entity(entity_id)
            
            if not reservation:
                raise HTTPException(status_code=404, detail="Reservation not found")
            
            return reservation
            
        except OrionError as e:
            raise HTTPException(status_code=500, detail=f"Orion error: {str(e)}")
    
    @app.get("/debug/shortage/{project_id}", tags=["debug"])
    async def debug_get_shortage(project_id: str):
        """Get shortage details for debugging"""
        if not orion_client:
            raise HTTPException(status_code=503, detail="Orion client not available")
        
        try:
            entity_id = f"urn:ngsi-ld:Shortage:{project_id}"
            shortage = await orion_client.get_entity(entity_id)
            
            if not shortage:
                raise HTTPException(status_code=404, detail="Shortage not found")
            
            return shortage
            
        except OrionError as e:
            raise HTTPException(status_code=500, detail=f"Orion error: {str(e)}")
    
    @app.get("/debug/inventory/{sku}", tags=["debug"])
    async def debug_get_inventory(sku: str):
        """Get inventory item for debugging"""
        if not orion_client:
            raise HTTPException(status_code=503, detail="Orion client not available")
        
        try:
            entity_id = f"urn:ngsi-ld:InventoryItem:{sku}"
            inventory = await orion_client.get_entity(entity_id)
            
            if not inventory:
                raise HTTPException(status_code=404, detail="Inventory item not found")
            
            return inventory
            
        except OrionError as e:
            raise HTTPException(status_code=500, detail=f"Orion error: {str(e)}")


# Error handlers
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors"""
    logger.warning("Validation error", errors=exc.errors(), path=request.url.path)
    return HTTPException(status_code=422, detail=exc.errors())


@app.exception_handler(OdooError)
async def odoo_exception_handler(request: Request, exc: OdooError):
    """Handle Odoo-related errors"""
    logger.error("Odoo error", error=str(exc), path=request.url.path)
    return HTTPException(status_code=502, detail=f"Odoo error: {str(exc)}")


@app.exception_handler(OrionError)
async def orion_exception_handler(request: Request, exc: OrionError):
    """Handle Orion-LD related errors"""
    logger.error("Orion error", error=str(exc), path=request.url.path)
    return HTTPException(status_code=502, detail=f"Orion error: {str(exc)}")


def main():
    """Main entry point"""
    uvicorn.run(
        "hermes_odoo_adapter.main:app",
        host="0.0.0.0",
        port=8080,
        log_config=None,  # Use our own logging config
        access_log=False,  # Disable default access log
    )


if __name__ == "__main__":
    main()