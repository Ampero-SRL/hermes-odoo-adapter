"""
Odoo JSON-RPC client with retry logic and circuit breaker
"""
import asyncio
from typing import Any, Dict, List, Optional, Union
from contextlib import asynccontextmanager

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from .settings import settings
from .utils.logging import get_logger
from .utils.metrics import metrics

logger = get_logger(__name__)


class OdooError(Exception):
    """Base exception for Odoo-related errors"""
    pass


class OdooAuthenticationError(OdooError):
    """Authentication failed with Odoo"""
    pass


class OdooConnectionError(OdooError):
    """Connection issues with Odoo"""
    pass


class OdooAPIError(OdooError):
    """API-level errors from Odoo"""
    def __init__(self, message: str, fault_code: Optional[str] = None, fault_string: Optional[str] = None):
        super().__init__(message)
        self.fault_code = fault_code
        self.fault_string = fault_string


class CircuitBreakerOpen(OdooError):
    """Circuit breaker is open, rejecting requests"""
    pass


class CircuitBreaker:
    """Simple circuit breaker implementation"""
    
    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "closed"  # closed, open, half_open
    
    def can_execute(self) -> bool:
        """Check if request can be executed"""
        import time
        current_time = time.time()
        
        if self.state == "closed":
            return True
        elif self.state == "open":
            if current_time - self.last_failure_time > self.timeout_seconds:
                self.state = "half_open"
                return True
            return False
        else:  # half_open
            return True
    
    def record_success(self) -> None:
        """Record a successful operation"""
        self.failure_count = 0
        self.state = "closed"
    
    def record_failure(self) -> None:
        """Record a failed operation"""
        import time
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"


class OdooClient:
    """Async Odoo JSON-RPC client with retry logic and circuit breaker"""
    
    def __init__(
        self,
        url: Optional[str] = None,
        database: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.url = url or settings.odoo_url
        self.database = database or settings.odoo_db
        self.username = username or settings.odoo_user
        self.password = password or settings.odoo_password
        
        self._user_id: Optional[int] = None
        self._session_id: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None
        
        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=settings.circuit_breaker_failure_threshold,
            timeout_seconds=settings.circuit_breaker_timeout_seconds
        )
        
        logger.info("Odoo client initialized", url=self.url, database=self.database)
    
    async def __aenter__(self) -> "OdooClient":
        """Async context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit"""
        await self.close()
    
    async def connect(self) -> None:
        """Initialize HTTP client and authenticate"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
            )
        
        if self._user_id is None:
            await self._authenticate()
    
    async def close(self) -> None:
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._user_id = None
        self._session_id = None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logger, "WARNING")
    )
    async def _authenticate(self) -> None:
        """Authenticate with Odoo and get user ID"""
        logger.info("Authenticating with Odoo", database=self.database, username=self.username)
        
        try:
            response = await self._make_request("common", "authenticate", [
                self.database, self.username, self.password, {}
            ])
            
            if not response or response == False:
                raise OdooAuthenticationError("Authentication failed - invalid credentials")
            
            self._user_id = response
            logger.info("Odoo authentication successful", user_id=self._user_id)
            
        except httpx.RequestError as e:
            raise OdooConnectionError(f"Failed to connect to Odoo: {e}")
        except Exception as e:
            raise OdooAuthenticationError(f"Authentication error: {e}")
    
    async def _make_request(self, service: str, method: str, params: List[Any]) -> Any:
        """Make a JSON-RPC request to Odoo"""
        if not self.circuit_breaker.can_execute():
            raise CircuitBreakerOpen("Circuit breaker is open")
        
        if not self._client:
            await self.connect()
        
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": service,
                "method": method,
                "args": params
            },
            "id": 1
        }
        
        try:
            response = await self._client.post(self.url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            error = data.get("error")
            if error:
                self.circuit_breaker.record_failure()
                raise OdooAPIError(
                    f"Odoo API error: {error.get('message', 'Unknown error')}",
                    fault_code=error.get('code'),
                    fault_string=error.get('data', {}).get('fault_string')
                )
            
            self.circuit_breaker.record_success()
            return data.get("result")
            
        except httpx.HTTPStatusError as e:
            self.circuit_breaker.record_failure()
            if e.response.status_code == 401:
                # Re-authenticate and retry
                self._user_id = None
                await self._authenticate()
                raise
            raise OdooConnectionError(f"HTTP error {e.response.status_code}: {e.response.text}")
        except httpx.RequestError as e:
            self.circuit_breaker.record_failure()
            raise OdooConnectionError(f"Request error: {e}")
    
    @asynccontextmanager
    async def _timed_request(self, model: str, method: str):
        """Context manager for timing Odoo requests"""
        with metrics.time_odoo_request(model, method):
            yield
    
    async def call(self, model: str, method: str, *args, **kwargs) -> Any:
        """Make a call to an Odoo model method"""
        if not self._user_id:
            await self._authenticate()
        
        params = [
            self.database,
            self._user_id, 
            self.password,
            model,
            method,
            list(args),
            kwargs
        ]
        
        async with self._timed_request(model, method):
            return await self._make_request("object", "execute_kw", params)
    
    async def search(self, model: str, domain: List[Any], **kwargs) -> List[int]:
        """Search for record IDs"""
        return await self.call(model, "search", domain, **kwargs)
    
    async def read(self, model: str, ids: Union[int, List[int]], fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Read record data"""
        if isinstance(ids, int):
            ids = [ids]
        
        kwargs = {}
        if fields:
            kwargs["fields"] = fields
        
        return await self.call(model, "read", ids, **kwargs)
    
    async def search_read(
        self, 
        model: str, 
        domain: List[Any], 
        fields: Optional[List[str]] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Search and read records in one call"""
        call_kwargs = kwargs.copy()
        if fields:
            call_kwargs["fields"] = fields
        
        return await self.call(model, "search_read", domain, **call_kwargs)
    
    async def create(self, model: str, values: Dict[str, Any]) -> int:
        """Create a new record"""
        return await self.call(model, "create", values)
    
    async def write(self, model: str, ids: Union[int, List[int]], values: Dict[str, Any]) -> bool:
        """Update existing records"""
        if isinstance(ids, int):
            ids = [ids]
        return await self.call(model, "write", ids, values)
    
    async def unlink(self, model: str, ids: Union[int, List[int]]) -> bool:
        """Delete records"""
        if isinstance(ids, int):
            ids = [ids]
        return await self.call(model, "unlink", ids)
    
    async def get_product_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """Get product by SKU (default_code)"""
        domain = [(settings.sku_field, "=", sku)]
        products = await self.search_read(
            "product.product",
            domain,
            fields=["id", "name", settings.sku_field, "uom_id"]
        )
        return products[0] if products else None
    
    async def get_bom_for_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Get BOM for a product"""
        domain = [("product_id", "=", product_id)]
        boms = await self.search_read(
            "mrp.bom",
            domain,
            fields=["id", "product_id", "product_tmpl_id", "product_qty", "bom_line_ids"]
        )
        return boms[0] if boms else None
    
    async def get_bom_lines(self, bom_line_ids: List[int]) -> List[Dict[str, Any]]:
        """Get BOM lines"""
        return await self.read(
            "mrp.bom.line",
            bom_line_ids,
            fields=["id", "bom_id", "product_id", "product_qty", "product_uom_id"]
        )
    
    async def get_stock_for_products(self, product_ids: List[int]) -> List[Dict[str, Any]]:
        """Get stock quantities for products"""
        domain = [
            ("product_id", "in", product_ids),
            ("location_id.usage", "=", "internal"),  # Only internal locations
        ]
        
        return await self.search_read(
            "stock.quant",
            domain,
            fields=["id", "product_id", "location_id", "quantity", "reserved_quantity"]
        )
    
    async def consume_stock(self, sku: str, quantity: int, project_id: str, location_id: int) -> Dict[str, Any]:
        """
        Consume (decrement) stock for a given SKU

        Args:
            sku: Product SKU (default_code)
            quantity: Quantity to consume
            project_id: NGSI-LD Project URN for traceability
            location_id: Odoo location ID where stock is consumed from

        Returns:
            Dict with operation details (quant_id, product_id, old_qty, new_qty)
        """
        logger.info("Consuming stock", sku=sku, quantity=quantity, project_id=project_id, location_id=location_id)

        # Find product by SKU
        products = await self.search_read(
            "product.product",
            domain=[("default_code", "=", sku)],
            fields=["id", "name", "uom_id"]
        )

        if not products:
            raise OdooAPIError(f"SKU {sku} not found in Odoo")

        product = products[0]
        product_id = product["id"]

        # Find existing quant at the location
        quants = await self.search_read(
            "stock.quant",
            domain=[("product_id", "=", product_id), ("location_id", "=", location_id)],
            fields=["id", "quantity", "reserved_quantity"],
            limit=1
        )

        if quants:
            quant = quants[0]
            quant_id = quant["id"]
            old_qty = quant["quantity"]
            new_quantity = max(0, old_qty - quantity)

            # Update the quant quantity
            await self.write("stock.quant", quant_id, {"quantity": new_quantity})

            logger.info("Stock consumed successfully",
                       sku=sku, quant_id=quant_id, old_qty=old_qty, new_qty=new_quantity)

            return {
                "quant_id": quant_id,
                "product_id": product_id,
                "old_qty": old_qty,
                "new_qty": new_quantity
            }
        else:
            # No stock at location - this is acceptable for MVP (just log it)
            logger.warning("No stock found at location for consumption",
                          sku=sku, location_id=location_id)
            return {
                "product_id": product_id,
                "message": "No stock found at location",
                "consumed": 0
            }

    async def produce_stock(self, sku: str, quantity: int, project_id: str, location_id: int) -> Dict[str, Any]:
        """
        Produce (increment) stock for a given SKU

        Args:
            sku: Product SKU (default_code)
            quantity: Quantity to produce
            project_id: NGSI-LD Project URN for traceability
            location_id: Odoo location ID where stock is produced to

        Returns:
            Dict with operation details (quant_id, product_id, old_qty, new_qty)
        """
        logger.info("Producing stock", sku=sku, quantity=quantity, project_id=project_id, location_id=location_id)

        # Find product by SKU
        products = await self.search_read(
            "product.product",
            domain=[("default_code", "=", sku)],
            fields=["id", "name", "uom_id"]
        )

        if not products:
            raise OdooAPIError(f"SKU {sku} not found in Odoo")

        product = products[0]
        product_id = product["id"]

        # Find existing quant at the location
        quants = await self.search_read(
            "stock.quant",
            domain=[("product_id", "=", product_id), ("location_id", "=", location_id)],
            fields=["id", "quantity", "reserved_quantity"],
            limit=1
        )

        if quants:
            # Update existing quant
            quant = quants[0]
            quant_id = quant["id"]
            old_qty = quant["quantity"]
            new_quantity = old_qty + quantity

            await self.write("stock.quant", quant_id, {"quantity": new_quantity})

            logger.info("Stock produced successfully",
                       sku=sku, quant_id=quant_id, old_qty=old_qty, new_qty=new_quantity)

            return {
                "quant_id": quant_id,
                "product_id": product_id,
                "old_qty": old_qty,
                "new_qty": new_quantity
            }
        else:
            # Create new quant if it doesn't exist
            quant_id = await self.create("stock.quant", {
                "product_id": product_id,
                "location_id": location_id,
                "quantity": quantity
            })

            logger.info("New stock quant created",
                       sku=sku, quant_id=quant_id, quantity=quantity)

            return {
                "quant_id": quant_id,
                "product_id": product_id,
                "old_qty": 0,
                "new_qty": quantity
            }

    async def health_check(self) -> bool:
        """Check if Odoo is accessible"""
        try:
            # Simple version check
            result = await self._make_request("common", "version", [])
            return bool(result)
        except Exception as e:
            logger.warning("Odoo health check failed", error=str(e))
            return False
