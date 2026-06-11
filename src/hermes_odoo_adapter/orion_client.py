"""
Orion-LD NGSI-LD client for HERMES Odoo Adapter
"""
import asyncio
import json
import logging
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
    
    def _get_headers(self, content_type: Optional[str] = "application/ld+json") -> Dict[str, str]:
        """Get HTTP headers for requests"""
        headers: Dict[str, str] = {
            "Accept": "application/ld+json",
        }
        
        if content_type:
            headers["Content-Type"] = content_type
        
        if self.tenant:
            headers["Fiware-Service"] = self.tenant
        
        if self.service_path and self.service_path != "/":
            headers["Fiware-ServicePath"] = self.service_path
        
        return headers
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        # `_make_request` catches `httpx.RequestError` and re-raises it
        # as `OrionConnectionError`, so tenacity needs to see the latter
        # to retry — otherwise the original retry-on-transport-error
        # contract silently breaks.
        retry=retry_if_exception_type(
            (httpx.RequestError, httpx.TimeoutException, OrionConnectionError)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        # Re-raise the original exception after the last failed attempt
        # rather than wrapping in tenacity's `RetryError`, so callers can
        # catch `OrionConnectionError` / `httpx.RequestError` directly.
        reraise=True,
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
        
        headers = self._get_headers(content_type="application/ld+json")
        
        try:
            if method.upper() == "GET":
                headers = self._get_headers(content_type=None)
                response = await self._client.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                response = await self._client.post(url, headers=headers, json=data, params=params)
            elif method.upper() == "PATCH":
                response = await self._client.patch(url, headers=headers, json=data, params=params)
            elif method.upper() == "PUT":
                response = await self._client.put(url, headers=headers, json=data, params=params)
            elif method.upper() == "DELETE":
                headers = self._get_headers(content_type=None)
                response = await self._client.delete(url, headers=headers, params=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Handle different response status codes
            if response.status_code == 204:
                # No content
                return None
            elif response.status_code in (200, 201, 207):
                # Success with content (207 = Multi-Status, partial update success)
                try:
                    result = response.json() if response.content else None
                    # Log partial success for 207
                    if response.status_code == 207 and result:
                        logger.debug("Partial update success", updated=result.get("updated"),
                                   not_updated=result.get("notUpdated"))
                    return result
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
                    if isinstance(error_data, dict):
                        error_details = error_data.get("detail") or error_data.get("description") or error_data.get(
                            "title"
                        ) or str(error_data)
                    else:
                        error_details = str(error_data)
                except Exception:
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
        entity_data = (
            entity.model_dump(by_alias=True, exclude_none=True)
            if hasattr(entity, "dict")
            else entity
        )
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
        entity_data = (
            entity.model_dump(by_alias=True, exclude_none=True)
            if hasattr(entity, "dict")
            else entity
        )
        entity_id = entity_data.get("id")
        entity_type = entity_data.get("type", "Unknown")
        
        if not entity_id:
            raise ValueError("Entity ID is required for upsert operation")
        
        # Try to get existing entity
        existing = await self.get_entity(entity_id)
        
        if existing:
            # Entity exists, update it
            # Remove id, type, and createdAt for update, but KEEP @context (required for PATCH with application/ld+json)
            update_data = {
                k: v
                for k, v in entity_data.items()
                if k not in ("id", "type", "createdAt")
            }
            logger.debug("Updating entity", entity_id=entity_id, keys=list(update_data.keys()))
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
        """Create an NGSI-LD subscription.

        Orion-LD returns **201 No Content** on a successful create, which
        bubbles up through ``_make_request`` as ``None``. ``None`` here
        therefore means "success, empty body" — not a failure. A failure
        path raises ``OrionAPIError`` from ``_make_request``, or returns a
        dict with an ``"error"`` key (e.g. 409 conflict).

        Defensive note: ``_make_request`` also returns ``None`` for **404**
        (the underlying GET handler), so a deployment where Orion's
        routing is broken (proxy misconfig, version mismatch) could look
        like a successful 201 create. After taking the success branch we
        verify via a follow-up ``get_subscription`` — if the subscription
        isn't actually there, downgrade to a logged failure.
        """
        sub_id = subscription.get("id")
        with metrics.time_orion_operation("subscribe", "Subscription"):
            logger.info(
                "Creating NGSI-LD subscription",
                notification_url=subscription.get("notification", {}).get("endpoint", {}).get("uri"),
            )
            try:
                result = await self._make_request(
                    "POST", "ngsi-ld/v1/subscriptions", subscription,
                )
            except OrionAPIError as exc:
                logger.error(
                    "Orion rejected the NGSI-LD subscription create",
                    status_code=exc.status_code,
                    response_body=exc.response_body,
                )
                return None

            if isinstance(result, dict) and result.get("error") == "conflict":
                # 409 — subscription already exists; treat as a benign
                # idempotent success.
                logger.info(
                    "NGSI-LD subscription already exists — treating as success",
                    subscription_id=sub_id,
                )
                return sub_id or "subscription_exists"

            # result is None (201 No Content) or a non-error dict — both
            # SHOULD be successes. Verify with a follow-up GET so a
            # silently-misrouted POST doesn't look like a successful create.
            if sub_id:
                try:
                    verify = await self.get_subscription(sub_id)
                except Exception as exc:
                    logger.warning(
                        "NGSI-LD subscription create verification failed",
                        subscription_id=sub_id,
                        error=str(exc),
                    )
                    return None
                if not verify:
                    logger.error(
                        "NGSI-LD subscription create returned success "
                        "but the entity is not retrievable — Orion routing "
                        "is likely broken",
                        subscription_id=sub_id,
                    )
                    return None

            return sub_id or "subscription_created"
    
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

    async def wait_until_ready(self, timeout_seconds: int = 60) -> bool:
        """Wait for Orion to respond before proceeding"""
        start = asyncio.get_event_loop().time()
        while True:
            if await self.health_check():
                logger.info("Orion-LD is reachable")
                return True
            if asyncio.get_event_loop().time() - start > timeout_seconds:
                logger.error("Timed out waiting for Orion-LD")
                return False
            await asyncio.sleep(2)
    
    async def ensure_subscription_exists(
        self,
        subscription_id: str,
        subscription_config: Dict[str, Any]
    ) -> bool:
        """Ensure a subscription exists and is active"""
        existing = await self.get_subscription(subscription_id)

        if existing:
            # Check if subscription is active
            status = existing.get("status", "active")  # Default to active if not present
            is_active = existing.get("isActive", True)  # Default to True if not present

            if status == "paused" or not is_active:
                logger.warning(
                    "NGSI-LD subscription exists but is paused - recreating",
                    subscription_id=subscription_id,
                    status=status,
                    is_active=is_active
                )
                # Delete paused subscription
                deleted = await self.delete_subscription(subscription_id)
                if not deleted:
                    logger.error("Failed to delete paused subscription", subscription_id=subscription_id)
                    return False
                # Fall through to create new subscription
            else:
                logger.info("NGSI-LD subscription exists and is active", subscription_id=subscription_id)
                return True

        # Create subscription (either because it didn't exist or we deleted a paused one)
        subscription_config["id"] = subscription_id
        created_id = await self.create_subscription(subscription_config)

        if created_id:
            logger.info("NGSI-LD subscription created", subscription_id=subscription_id)
            return True
        else:
            logger.error("Failed to create NGSI-LD subscription", subscription_id=subscription_id)
            return False
