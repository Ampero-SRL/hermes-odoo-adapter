"""
HERMES Odoo Adapter v2.0 - Hybrid ROS2 + FastAPI Application

Speaks four protocols:
  - ROS2 DDS (Vulcanexus/Fast-DDS) — services for Mission Controller
  - JSON-RPC — Odoo ERP stock and BOM operations
  - NGSI-LD over HTTP — FIWARE Orion-LD context broker
  - SOAP 1.1 — Hanel vertical warehouse (via pluggable WarehouseClient)
"""
import asyncio
import threading
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, Response, BackgroundTasks, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, FileResponse
from pydantic import BaseModel, ValidationError
import uvicorn

from .settings import settings
from .utils.logging import setup_logging, get_logger, LoggingContext
from .utils.metrics import metrics
from .utils.idempotency import generate_correlation_id, idempotency_helper
from .odoo_client import OdooClient, OdooError
from .orion_client import OrionClient, OrionError
from .warehouse import create_warehouse_client, WarehouseClient
from .workers.project_sync import ProjectSyncWorker
from .workers.inventory_sync import InventorySyncWorker
from .workers.warehouse_sync import WarehouseSyncWorker

# Setup logging first
setup_logging()
logger = get_logger(__name__)

# Global clients and workers
odoo_client: Optional[OdooClient] = None
orion_client: Optional[OrionClient] = None
warehouse_client: Optional[WarehouseClient] = None
project_worker: Optional[ProjectSyncWorker] = None
inventory_worker: Optional[InventorySyncWorker] = None
warehouse_worker: Optional[WarehouseSyncWorker] = None

# ROS2 globals
_ros2_node: Optional[Any] = None  # HermesAdapterNode
_ros2_thread: Optional[threading.Thread] = None
_ros2_executor: Optional[Any] = None  # rclpy.executors.MultiThreadedExecutor

CONTEXT_FILE = Path(__file__).resolve().parents[2] / "contracts/context/context.jsonld"


def _start_ros2_spin(node: Any) -> None:
    """Spin the rclpy executor in a daemon thread."""
    import rclpy
    from rclpy.executors import MultiThreadedExecutor

    global _ros2_executor
    _ros2_executor = MultiThreadedExecutor()
    _ros2_executor.add_node(node)
    try:
        _ros2_executor.spin()
    except Exception:
        pass  # Shutting down


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global odoo_client, orion_client, warehouse_client
    global project_worker, inventory_worker, warehouse_worker
    global _ros2_node, _ros2_thread

    logger.info("Starting HERMES Odoo Adapter", version="2.0.0")

    try:
        # 1. Initialize protocol clients
        odoo_client = OdooClient()
        orion_client = OrionClient()
        warehouse_client = create_warehouse_client(settings)

        # Wait for Orion to be reachable before proceeding
        if not await orion_client.wait_until_ready():
            raise RuntimeError("Orion-LD is not ready")

        await odoo_client.connect()
        await orion_client.connect()
        await warehouse_client.connect()

        # 2. Initialize workers
        project_worker = ProjectSyncWorker(odoo_client, orion_client)
        inventory_worker = InventorySyncWorker(odoo_client, orion_client)
        warehouse_worker = WarehouseSyncWorker(
            odoo_client, orion_client, warehouse_client
        )

        # Setup Orion subscription
        await project_worker.setup_subscription()

        # Start background tasks
        if settings.inventory_sync_enabled:
            asyncio.create_task(inventory_worker.start())

        if settings.warehouse_sync_enabled and settings.warehouse_backend != "null":
            asyncio.create_task(warehouse_worker.start())

        # 3. Initialize ROS2 node (Vulcanexus / Fast-DDS)
        if settings.ros2_enabled:
            try:
                import rclpy
                from .ros2_node import HermesAdapterNode

                rclpy.init()
                loop = asyncio.get_running_loop()
                _ros2_node = HermesAdapterNode(
                    odoo_client=odoo_client,
                    orion_client=orion_client,
                    warehouse_client=warehouse_client,
                    event_loop=loop,
                    node_name=settings.ros2_node_name,
                    stock_location_id=settings.stock_location_id,
                )
                _ros2_thread = threading.Thread(
                    target=_start_ros2_spin,
                    args=(_ros2_node,),
                    daemon=True,
                    name="rclpy-spin",
                )
                _ros2_thread.start()
                logger.info(
                    "ROS2 node started",
                    node_name=settings.ros2_node_name,
                )
            except ImportError:
                logger.warning(
                    "rclpy not available — ROS2 node disabled. "
                    "Install Vulcanexus/ROS2 Humble to enable DDS services."
                )
            except Exception as e:
                logger.error("Failed to start ROS2 node", error=str(e))

        logger.info("HERMES Odoo Adapter v2.0 started successfully")

        yield

    except Exception as e:
        logger.error("Failed to start application", error=str(e))
        raise
    finally:
        # Cleanup
        logger.info("Shutting down HERMES Odoo Adapter")

        # Stop ROS2
        if _ros2_node is not None:
            try:
                import rclpy

                if _ros2_executor is not None:
                    _ros2_executor.shutdown()
                _ros2_node.destroy_node()
                rclpy.shutdown()
            except Exception:
                pass

        if warehouse_worker:
            await warehouse_worker.stop()

        if inventory_worker:
            await inventory_worker.stop()

        if warehouse_client:
            await warehouse_client.close()

        if odoo_client:
            await odoo_client.close()

        if orion_client:
            await orion_client.close()

        logger.info("HERMES Odoo Adapter stopped")


# Create FastAPI app
app = FastAPI(
    title="HERMES Odoo Adapter",
    description="Hybrid ROS2 + FastAPI adapter for Odoo ERP, FIWARE, and warehouse integration",
    version="2.0.0",
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


class ConsumeRequest(BaseModel):
    """Request to consume (decrement) stock for a SKU"""
    project_id: str
    sku: str
    quantity: int

    class Config:
        json_schema_extra = {
            "example": {
                "project_id": "urn:ngsi-ld:Project:P123",
                "sku": "PCB-CTRL-REV21",
                "quantity": 1
            }
        }


class ProduceRequest(BaseModel):
    """Request to produce (increment) stock for a SKU"""
    project_id: str
    sku: str
    quantity: int = 1

    class Config:
        json_schema_extra = {
            "example": {
                "project_id": "urn:ngsi-ld:Project:P123",
                "sku": "CTRL-PANEL-A1",
                "quantity": 1
            }
        }


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
        version="2.0.0"
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
    
    # Check warehouse connectivity
    if warehouse_client:
        try:
            checks["warehouse"] = await warehouse_client.health_check()
            details["warehouse"] = (
                f"Connected ({settings.warehouse_backend})"
                if checks["warehouse"]
                else "Connection failed"
            )
        except Exception as e:
            checks["warehouse"] = False
            details["warehouse"] = f"Error: {str(e)}"
    else:
        checks["warehouse"] = False
        details["warehouse"] = "Client not initialized"

    # Check ROS2 node
    if _ros2_node is not None:
        checks["ros2"] = True
        details["ros2"] = f"Node '{settings.ros2_node_name}' running"
    elif settings.ros2_enabled:
        checks["ros2"] = False
        details["ros2"] = "Node not started"
    # If ros2_enabled is False, skip the check entirely

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


@app.get("/context.jsonld", tags=["meta"])
async def get_context_document():
    """Serve NGSI-LD context document"""
    if not CONTEXT_FILE.exists():
        raise HTTPException(status_code=404, detail="Context document not found")
    return FileResponse(CONTEXT_FILE, media_type="application/ld+json")


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


# Stock Operation API Endpoints
@app.post("/api/consume", tags=["stock-operations"])
async def consume_stock(request: ConsumeRequest, background_tasks: BackgroundTasks):
    """
    Consume (decrement) stock for a given SKU

    This endpoint is called by the mission controller when components are picked
    from inventory during mission execution.
    """
    logger.info("Stock consume request received", sku=request.sku, quantity=request.quantity, project_id=request.project_id)

    if not odoo_client:
        raise HTTPException(status_code=503, detail="Odoo client not available")

    try:
        # Perform stock consumption
        result = await odoo_client.consume_stock(
            sku=request.sku,
            quantity=request.quantity,
            project_id=request.project_id,
            location_id=settings.stock_location_id
        )

        # Trigger inventory sync update for this SKU in background
        if inventory_worker:
            background_tasks.add_task(inventory_worker.sync_product_inventory, request.sku)

        return {
            "status": "ok",
            "message": f"Consumed {request.quantity} units of {request.sku}",
            "details": result
        }

    except OdooError as e:
        logger.error("Failed to consume stock", error=str(e), sku=request.sku)
        raise HTTPException(status_code=500, detail=f"Odoo error: {str(e)}")
    except Exception as e:
        logger.error("Unexpected error consuming stock", error=str(e), sku=request.sku)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.post("/api/produce", tags=["stock-operations"])
async def produce_stock(request: ProduceRequest, background_tasks: BackgroundTasks):
    """
    Produce (increment) stock for a given SKU

    This endpoint is called by the mission controller when a finished product
    is completed and added to inventory.
    """
    logger.info("Stock produce request received", sku=request.sku, quantity=request.quantity, project_id=request.project_id)

    if not odoo_client:
        raise HTTPException(status_code=503, detail="Odoo client not available")

    try:
        # Perform stock production
        result = await odoo_client.produce_stock(
            sku=request.sku,
            quantity=request.quantity,
            project_id=request.project_id,
            location_id=settings.stock_location_id
        )

        # Trigger inventory sync update for this SKU in background
        if inventory_worker:
            background_tasks.add_task(inventory_worker.sync_product_inventory, request.sku)

        return {
            "status": "ok",
            "message": f"Produced {request.quantity} units of {request.sku}",
            "details": result
        }

    except OdooError as e:
        logger.error("Failed to produce stock", error=str(e), sku=request.sku)
        raise HTTPException(status_code=500, detail=f"Odoo error: {str(e)}")
    except Exception as e:
        logger.error("Unexpected error producing stock", error=str(e), sku=request.sku)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# Administrative endpoints
@app.post("/admin/recompute/{project_id}", tags=["admin"])
async def recompute_project(
    project_id: str,
    background_tasks: BackgroundTasks,
    request: RecomputeRequest = Body(default_factory=RecomputeRequest),
):
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


@app.delete("/admin/idempotency/{project_id}", tags=["admin"])
async def clear_project_idempotency(project_id: str):
    """
    Clear idempotency cache for a specific project.

    Use this when you want to reprocess a project that was already processed.
    Call this BEFORE creating a new project with the same ID.
    """
    logger.info("Clearing idempotency cache for project", project_id=project_id)

    cleared = idempotency_helper.clear_project(project_id)

    return {
        "status": "success" if cleared else "not_found",
        "message": f"Idempotency cache {'cleared' if cleared else 'not found'} for project {project_id}",
        "project_id": project_id
    }


@app.delete("/admin/idempotency", tags=["admin"])
async def clear_all_idempotency():
    """
    Clear entire idempotency cache.

    Use this to reset all project processing state.
    """
    logger.info("Clearing all idempotency cache")

    idempotency_helper.clear_cache()

    return {
        "status": "success",
        "message": "All idempotency cache cleared"
    }


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
