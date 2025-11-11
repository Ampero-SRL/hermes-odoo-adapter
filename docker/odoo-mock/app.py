"""
FastAPI-based Odoo JSON-RPC Mock Service
Simulates Odoo's JSON-RPC API for HERMES adapter development
"""
import json
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Odoo Mock Service",
    description="Mock Odoo JSON-RPC API for HERMES adapter development",
    version="1.0.0"
)

# Data store
DATA_DIR = Path("data")
PRODUCTS_FILE = DATA_DIR / "products.json"
BOMS_FILE = DATA_DIR / "boms.json"
STOCK_FILE = DATA_DIR / "stock.json"

# Load mock data
def load_data():
    """Load mock data from JSON files"""
    try:
        with open(PRODUCTS_FILE) as f:
            products = json.load(f)
    except FileNotFoundError:
        products = create_default_products()
        
    try:
        with open(BOMS_FILE) as f:
            boms = json.load(f)
    except FileNotFoundError:
        boms = create_default_boms()
        
    try:
        with open(STOCK_FILE) as f:
            stock = json.load(f)
    except FileNotFoundError:
        stock = create_default_stock()
        
    return products, boms, stock

def create_default_products():
    """Create default product data"""
    return [
        {
            "id": 1,
            "name": "Control Panel A1",
            "default_code": "CTRL-PANEL-A1",
            "uom_id": [1, "Unit"],
            "type": "product"
        },
        {
            "id": 2,
            "name": "Schneider Relay 24V",
            "default_code": "SCH-REL-24V",
            "uom_id": [1, "Unit"],
            "type": "product"
        },
        {
            "id": 3,
            "name": "ABB Circuit Breaker 10A",
            "default_code": "ABB-MCB-10A",
            "uom_id": [1, "Unit"],
            "type": "product"
        },
        {
            "id": 4,
            "name": "DIN Rail Terminal",
            "default_code": "DIN-TERM-2.5",
            "uom_id": [1, "Unit"],
            "type": "product"
        },
        {
            "id": 5,
            "name": "Wago Connector",
            "default_code": "WAGO-221-412",
            "uom_id": [1, "Unit"],
            "type": "product"
        }
    ]

def create_default_boms():
    """Create default BOM data"""
    return [
        {
            "id": 1,
            "product_id": [1, "Control Panel A1"],
            "product_tmpl_id": [1, "Control Panel A1"],
            "product_qty": 1.0,
            "bom_line_ids": [1, 2, 3, 4]
        }
    ]

def create_default_stock():
    """Create default stock data"""
    return [
        {
            "id": 1,
            "product_id": [2, "Schneider Relay 24V"],
            "location_id": [8, "WH/Stock"],
            "quantity": 10.0,
            "reserved_quantity": 2.0
        },
        {
            "id": 2,
            "product_id": [3, "ABB Circuit Breaker 10A"],
            "location_id": [8, "WH/Stock"],
            "quantity": 15.0,
            "reserved_quantity": 0.0
        },
        {
            "id": 3,
            "product_id": [4, "DIN Rail Terminal"],
            "location_id": [8, "WH/Stock"],
            "quantity": 50.0,
            "reserved_quantity": 5.0
        },
        {
            "id": 4,
            "product_id": [5, "Wago Connector"],
            "location_id": [8, "WH/Stock"],
            "quantity": 2.0,  # Low stock to test shortage
            "reserved_quantity": 0.0
        }
    ]

# Load data on startup
PRODUCTS, BOMS, STOCK = load_data()

# BOM Lines data
BOM_LINES = [
    {
        "id": 1,
        "bom_id": [1, "Control Panel A1 BOM"],
        "product_id": [2, "Schneider Relay 24V"],
        "product_qty": 4.0,
        "product_uom_id": [1, "Unit"]
    },
    {
        "id": 2,
        "bom_id": [1, "Control Panel A1 BOM"],
        "product_id": [3, "ABB Circuit Breaker 10A"],
        "product_qty": 2.0,
        "product_uom_id": [1, "Unit"]
    },
    {
        "id": 3,
        "bom_id": [1, "Control Panel A1 BOM"],
        "product_id": [4, "DIN Rail Terminal"],
        "product_qty": 8.0,
        "product_uom_id": [1, "Unit"]
    },
    {
        "id": 4,
        "bom_id": [1, "Control Panel A1 BOM"],
        "product_id": [5, "Wago Connector"],
        "product_qty": 6.0,  # This will cause shortage
        "product_uom_id": [1, "Unit"]
    }
]

class JsonRpcRequest(BaseModel):
    """JSON-RPC request model"""
    jsonrpc: str = "2.0"
    method: str
    params: Dict[str, Any]
    id: Optional[int] = None

class JsonRpcResponse(BaseModel):
    """JSON-RPC response model"""
    jsonrpc: str = "2.0"
    result: Any = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[int] = None

@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "odoo-mock"}

@app.post("/jsonrpc")
async def jsonrpc_endpoint(request: JsonRpcRequest):
    """Main JSON-RPC endpoint mimicking Odoo's API"""
    
    logger.info(f"JSON-RPC call: {request.method}")
    
    try:
        if request.method == "call":
            return handle_call(request)
        raise HTTPException(status_code=400, detail=f"Unknown method: {request.method}")
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return JsonRpcResponse(
            id=request.id,
            error={"code": -1, "message": str(e)}
        )

def handle_call(request: JsonRpcRequest) -> JsonRpcResponse:
    """Handle Odoo call method"""
    params = request.params
    service = params.get("service")
    method = params.get("method")
    args = params.get("args", [])

    if service == "common":
        result = handle_common_service(method, args)
        return JsonRpcResponse(id=request.id, result=result)

    if service == "object":
        if method != "execute_kw":
            raise ValueError(f"Unsupported object method: {method}")
        if len(args) < 6:
            raise ValueError("Invalid execute_kw arguments")

        db, uid, password, model, model_method, method_args = args[:6]
        kwargs = args[6] if len(args) > 6 else {}

        logger.info(
            "Call: %s.%s (db=%s, uid=%s) args=%s kwargs=%s",
            model,
            model_method,
            db,
            uid,
            method_args,
            kwargs,
        )

        if model == "product.product":
            result = handle_product_product(model_method, method_args, kwargs)
        elif model == "mrp.bom":
            result = handle_mrp_bom(model_method, method_args, kwargs)
        elif model == "mrp.bom.line":
            result = handle_mrp_bom_line(model_method, method_args, kwargs)
        elif model == "stock.quant":
            result = handle_stock_quant(model_method, method_args, kwargs)
        else:
            raise ValueError(f"Unknown model: {model}")

        return JsonRpcResponse(id=request.id, result=result)

    raise ValueError(f"Unknown service: {service}")

def handle_common_service(method: str, args: List[Any]) -> Any:
    """Handle calls to the 'common' service"""
    if method == "authenticate":
        # args: [db, username, password, context]
        return 1  # Mock admin user ID
    if method == "version":
        return {
            "server_version": "17.0",
            "server_version_info": [17, 0, 0, "final", 0],
            "server_serie": "17.0",
            "protocol_version": 1,
        }
    raise ValueError(f"Unknown common method: {method}")

def handle_product_product(method: str, args: List, kwargs: Dict) -> Any:
    """Handle product.product model calls"""
    if method == "search_read":
        domain = args[0] if args else []
        fields = kwargs.get("fields", ["id", "name", "default_code", "uom_id"])
        
        # Simple domain filtering
        filtered_products = PRODUCTS
        for condition in domain:
            if len(condition) == 3:
                field, operator, value = condition
                if field == "default_code" and operator == "=":
                    filtered_products = [p for p in filtered_products if p.get("default_code") == value]
                elif field == "id" and operator == "in":
                    filtered_products = [p for p in filtered_products if p.get("id") in value]
        
        # Return only requested fields
        result = []
        for product in filtered_products:
            item = {field: product.get(field) for field in fields if field in product}
            result.append(item)
        
        return result
    
    elif method == "search":
        domain = args[0] if args else []
        # Return IDs only
        filtered_products = PRODUCTS
        for condition in domain:
            if len(condition) == 3:
                field, operator, value = condition
                if field == "default_code" and operator == "=":
                    filtered_products = [p for p in filtered_products if p.get("default_code") == value]
        
        return [p["id"] for p in filtered_products]
    
    elif method == "read":
        ids = args[0] if args else []
        if isinstance(ids, int):
            ids = [ids]
        fields = kwargs.get("fields", ["id", "name", "default_code", "uom_id", "active"])
        result = []
        for product in PRODUCTS:
            if product.get("id") in ids:
                item = {field: product.get(field) for field in fields if field in product}
                # Assume all products active unless specified
                item.setdefault("active", True)
                result.append(item)
        return result
    
    raise ValueError(f"Unknown method: {method}")

def handle_mrp_bom(method: str, args: List, kwargs: Dict) -> Any:
    """Handle mrp.bom model calls"""
    if method == "search_read":
        domain = args[0] if args else []
        fields = kwargs.get("fields", ["id", "product_id", "product_tmpl_id", "product_qty", "bom_line_ids"])
        
        # Simple domain filtering
        filtered_boms = BOMS
        for condition in domain:
            if len(condition) == 3:
                field, operator, value = condition
                if field == "product_id" and operator == "=":
                    filtered_boms = [b for b in filtered_boms if b.get("product_id", [None])[0] == value]
        
        # Return only requested fields
        result = []
        for bom in filtered_boms:
            item = {field: bom.get(field) for field in fields if field in bom}
            result.append(item)
        
        return result
    
    raise ValueError(f"Unknown method: {method}")

def handle_mrp_bom_line(method: str, args: List, kwargs: Dict) -> Any:
    """Handle mrp.bom.line model calls"""
    if method == "search_read":
        domain = args[0] if args else []
        fields = kwargs.get("fields", ["id", "bom_id", "product_id", "product_qty", "product_uom_id"])
        
        # Simple domain filtering
        filtered_lines = BOM_LINES
        for condition in domain:
            if len(condition) == 3:
                field, operator, value = condition
                if field == "bom_id" and operator == "=":
                    filtered_lines = [l for l in filtered_lines if l.get("bom_id", [None])[0] == value]
                elif field == "id" and operator == "in":
                    filtered_lines = [l for l in filtered_lines if l.get("id") in value]
        
        # Return only requested fields
        result = []
        for line in filtered_lines:
            item = {field: line.get(field) for field in fields if field in line}
            result.append(item)
        
        return result
    
    raise ValueError(f"Unknown method: {method}")

def handle_stock_quant(method: str, args: List, kwargs: Dict) -> Any:
    """Handle stock.quant model calls"""
    if method == "search_read":
        domain = args[0] if args else []
        fields = kwargs.get("fields", ["id", "product_id", "location_id", "quantity", "reserved_quantity"])
        
        # Simple domain filtering
        filtered_stock = STOCK
        for condition in domain:
            if len(condition) == 3:
                field, operator, value = condition
                if field == "product_id" and operator == "in":
                    filtered_stock = [s for s in filtered_stock if s.get("product_id", [None])[0] in value]
                elif field == "location_id.usage" and operator == "=":
                    # Mock: assume all our locations are internal
                    pass  # Keep all stock
        
        # Return only requested fields
        result = []
        for stock in filtered_stock:
            item = {field: stock.get(field) for field in fields if field in stock}
            result.append(item)
        
        return result
    
    raise ValueError(f"Unknown method: {method}")

@app.get("/")
async def root():
    """Root endpoint with service info"""
    return {
        "service": "Odoo Mock Service",
        "version": "1.0.0",
        "endpoints": {
            "/jsonrpc": "Main JSON-RPC endpoint",
            "/healthz": "Health check",
            "/debug/products": "List all products",
            "/debug/boms": "List all BOMs",
            "/debug/stock": "List all stock"
        }
    }

@app.get("/debug/products")
async def debug_products():
    """Debug endpoint to list all products"""
    return {"products": PRODUCTS}

@app.get("/debug/boms")
async def debug_boms():
    """Debug endpoint to list all BOMs"""
    return {"boms": BOMS, "bom_lines": BOM_LINES}

@app.get("/debug/stock")
async def debug_stock():
    """Debug endpoint to list all stock"""
    return {"stock": STOCK}

@app.post("/debug/stock/{product_id}")
async def update_stock(product_id: int, quantity: float):
    """Debug endpoint to update stock quantity"""
    for stock_item in STOCK:
        if stock_item["product_id"][0] == product_id:
            stock_item["quantity"] = quantity
            return {"message": f"Updated stock for product {product_id} to {quantity}"}
    
    raise HTTPException(status_code=404, detail="Product not found in stock")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8069)
