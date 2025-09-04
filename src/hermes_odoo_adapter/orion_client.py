"""
Orion-LD NGSI-LD client for HERMES Odoo Adapter
"""
import json
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

import httpx
from tenacity import (
    retry,
    stop_after_attempt, 
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from .settings import settings
from .models.ngsi_models import NGSILDEntity
from .utils.logging import get_logger
from .utils.metrics import metrics

logger = get_logger(__name__)


class OrionError(Exception):
    """Base exception for Orion-LD related errors"""
    pass


class OrionConnectionError(OrionError):
    """Connection issues with Orion-LD"""
    pass


class OrionAPIError(OrionError):
    """API-level errors from Orion-LD"""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class OrionClient:
    """Async Orion-LD NGSI-LD client"""
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        tenant: Optional[str] = None,
        service_path: Optional[str] = None,
    ):
        self.base_url = (base_url or settings.orion_url).rstrip("/")
        self.tenant = tenant or settings.orion_tenant
        self.service_path = service_path or settings.orion_service_path
        
        self._client: Optional[httpx.AsyncClient] = None
        
        logger.info("Orion client initialized", base_url=self.base_url, tenant=self.tenant)
    
    async def __aenter__(self) -> "OrionClient":
        """Async context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit"""
        await self.close()
    
    async def connect(self) -> None:
        """Initialize HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
            )
    
    async def close(self) -> None:
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _get_headers(self, content_type: str = "application/ld+json") -> Dict[str, str]:
        """Get HTTP headers for requests"""
        headers = {
            "Content-Type": content_type,
            "Accept": "application/ld+json",
        }
        
        if self.tenant:
            headers["Fiware-Service"] = self.tenant
        
        if self.service_path and self.service_path != "/":
            headers["Fiware-ServicePath"] = self.service_path
        
        return headers
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logger, "WARNING")
    )
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Union[Dict, List]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Make HTTP request to Orion-LD"""
        if not self._client:
            await self.connect()
        
        url = urljoin(self.base_url + "/", endpoint.lstrip("/"))
        headers = self._get_headers()
        
        try:
            if method.upper() == "GET":
                response = await self._client.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                response = await self._client.post(url, headers=headers, json=data, params=params)
            elif method.upper() == "PATCH":
                response = await self._client.patch(url, headers=headers, json=data, params=params)
            elif method.upper() == "PUT":
                response = await self._client.put(url, headers=headers, json=data, params=params)
            elif method.upper() == "DELETE":
                response = await self._client.delete(url, headers=headers, params=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Handle different response status codes
            if response.status_code == 204:
                # No content
                return None
            elif response.status_code in (200, 201):
                # Success with content
                try:
                    return response.json() if response.content else None
                except json.JSONDecodeError:
                    return {"raw_response": response.text}
            elif response.status_code == 404:
                # Entity not found - this might be expected
                return None
            elif response.status_code == 409:
                # Conflict - entity already exists (for POST)
                logger.warning("Entity conflict", status_code=response.status_code, url=url)
                return {"error": "conflict", "message": "Entity already exists"}
            else:
                # Other errors
                error_details = ""
                try:
                    error_data = response.json()
                    error_details = error_data.get("detail", error_data.get("title", str(error_data)))
                except:
                    error_details = response.text
                
                raise OrionAPIError(
                    f"Orion-LD API error: {error_details}",
                    status_code=response.status_code,
                    response_body=response.text
                )
                
        except httpx.RequestError as e:
            raise OrionConnectionError(f"Request error: {e}")
    
    async def create_entity(self, entity: Union[NGSILDEntity, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Create a new NGSI-LD entity"""
        entity_data = entity.dict(by_alias=True) if hasattr(entity, 'dict') else entity
        entity_type = entity_data.get("type", "Unknown")
        
        with metrics.time_orion_operation("create", entity_type):
            logger.info("Creating NGSI-LD entity", entity_id=entity_data.get("id"), entity_type=entity_type)
            return await self._make_request("POST", "ngsi-ld/v1/entities", entity_data)
    
    async def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get an NGSI-LD entity by ID"""
        with metrics.time_orion_operation("get", "Entity"):
            logger.debug("Getting NGSI-LD entity", entity_id=entity_id)
            return await self._make_request("GET", f"ngsi-ld/v1/entities/{entity_id}")
    
    async def update_entity(
        self, 
        entity_id: str, 
        updates: Dict[str, Any], 
        entity_type: str = "Entity"
    ) -> Optional[Dict[str, Any]]:
        """Update an NGSI-LD entity (PATCH)"""
        with metrics.time_orion_operation("update", entity_type):
            logger.info("Updating NGSI-LD entity", entity_id=entity_id, entity_type=entity_type)
            return await self._make_request("PATCH", f"ngsi-ld/v1/entities/{entity_id}/attrs", updates)
    
    async def upsert_entity(self, entity: Union[NGSILDEntity, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Upsert an NGSI-LD entity (create or update)"""
        entity_data = entity.dict(by_alias=True) if hasattr(entity, 'dict') else entity
        entity_id = entity_data.get("id")
        entity_type = entity_data.get("type", "Unknown")
        
        if not entity_id:
            raise ValueError("Entity ID is required for upsert operation")
        
        # Try to get existing entity
        existing = await self.get_entity(entity_id)
        
        if existing:
            # Entity exists, update it
            # Remove id, type, and @context for update
            update_data = {k: v for k, v in entity_data.items() 
                          if k not in ("id", "type", "@context")}
            return await self.update_entity(entity_id, update_data, entity_type)
        else:
            # Entity doesn't exist, create it
            return await self.create_entity(entity_data)
    
    async def delete_entity(self, entity_id: str) -> bool:
        """Delete an NGSI-LD entity"""
        with metrics.time_orion_operation("delete", "Entity"):
            logger.info("Deleting NGSI-LD entity", entity_id=entity_id)
            result = await self._make_request("DELETE", f"ngsi-ld/v1/entities/{entity_id}")
            return result is None  # 204 No Content indicates success
    
    async def query_entities(
        self,
        entity_type: Optional[str] = None,
        id_pattern: Optional[str] = None,
        query: Optional[str] = None,
        attrs: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Query NGSI-LD entities"""
        params = {}
        
        if entity_type:
            params["type"] = entity_type
        if id_pattern:
            params["idPattern"] = id_pattern
        if query:
            params["q"] = query
        if attrs:
            params["attrs"] = ",".join(attrs)
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset
        
        with metrics.time_orion_operation("query", entity_type or "Entity"):
            logger.debug("Querying NGSI-LD entities", params=params)
            result = await self._make_request("GET", "ngsi-ld/v1/entities", params=params)
            return result if isinstance(result, list) else []
    
    async def create_subscription(self, subscription: Dict[str, Any]) -> Optional[str]:
        """Create an NGSI-LD subscription"""
        with metrics.time_orion_operation("subscribe", "Subscription"):
            logger.info("Creating NGSI-LD subscription", notification_url=subscription.get("notification", {}).get("endpoint", {}).get("uri"))
            result = await self._make_request("POST", "ngsi-ld/v1/subscriptions", subscription)
            
            if result and "error" not in result:
                # Extract subscription ID from location header or response
                return subscription.get("id", "subscription_created")
            return None
    
    async def get_subscription(self, subscription_id: str) -> Optional[Dict[str, Any]]:
        """Get an NGSI-LD subscription"""
        with metrics.time_orion_operation("get", "Subscription"):
            return await self._make_request("GET", f"ngsi-ld/v1/subscriptions/{subscription_id}")
    
    async def delete_subscription(self, subscription_id: str) -> bool:
        """Delete an NGSI-LD subscription"""
        with metrics.time_orion_operation("delete", "Subscription"):
            logger.info("Deleting NGSI-LD subscription", subscription_id=subscription_id)
            result = await self._make_request("DELETE", f"ngsi-ld/v1/subscriptions/{subscription_id}")
            return result is None
    
    async def list_subscriptions(self) -> List[Dict[str, Any]]:
        """List all NGSI-LD subscriptions"""
        with metrics.time_orion_operation("list", "Subscription"):
            result = await self._make_request("GET", "ngsi-ld/v1/subscriptions")
            return result if isinstance(result, list) else []
    
    async def health_check(self) -> bool:
        """Check if Orion-LD is accessible"""
        try:
            result = await self._make_request("GET", "version")
            return bool(result)
        except Exception as e:
            logger.warning("Orion-LD health check failed", error=str(e))
            return False
    
    async def ensure_subscription_exists(
        self,
        subscription_id: str,
        subscription_config: Dict[str, Any]
    ) -> bool:
        """Ensure a subscription exists, create if missing"""
        existing = await self.get_subscription(subscription_id)
        
        if existing:
            logger.info("NGSI-LD subscription exists", subscription_id=subscription_id)
            return True
        
        # Create subscription
        subscription_config["id"] = subscription_id
        created_id = await self.create_subscription(subscription_config)
        
        if created_id:
            logger.info("NGSI-LD subscription created", subscription_id=subscription_id)
            return True
        else:
            logger.error("Failed to create NGSI-LD subscription", subscription_id=subscription_id)
            return False