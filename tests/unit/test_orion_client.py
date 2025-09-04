"""
Tests for Orion-LD NGSI-LD client
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import json

from hermes_odoo_adapter.orion_client import (
    OrionClient,
    OrionError,
    OrionConnectionError,
    OrionAPIError
)
from hermes_odoo_adapter.models.ngsi_models import Reservation, ReservationLine


class TestOrionClient:
    """Test Orion-LD client functionality"""
    
    @pytest.fixture
    def orion_client(self):
        """Create test Orion client"""
        return OrionClient(
            base_url="http://test.orion.com:1026",
            tenant="test-tenant",
            service_path="/test"
        )
    
    def test_orion_client_initialization(self, orion_client):
        """Test Orion client initialization"""
        assert orion_client.base_url == "http://test.orion.com:1026"
        assert orion_client.tenant == "test-tenant"
        assert orion_client.service_path == "/test"
        assert orion_client._client is None
    
    def test_headers_generation(self, orion_client):
        """Test HTTP headers generation"""
        headers = orion_client._get_headers()
        
        expected_headers = {
            "Content-Type": "application/ld+json",
            "Accept": "application/ld+json",
            "Fiware-Service": "test-tenant",
            "Fiware-ServicePath": "/test"
        }
        
        assert headers == expected_headers
    
    def test_headers_without_tenant(self):
        """Test headers generation without tenant"""
        client = OrionClient(base_url="http://test.orion.com:1026")
        headers = client._get_headers()
        
        assert "Fiware-Service" not in headers
        assert "Fiware-ServicePath" not in headers
    
    def test_headers_with_root_service_path(self):
        """Test headers with root service path"""
        client = OrionClient(
            base_url="http://test.orion.com:1026",
            tenant="test-tenant",
            service_path="/"
        )
        headers = client._get_headers()
        
        assert "Fiware-ServicePath" not in headers
    
    @pytest.mark.asyncio
    async def test_make_request_get_success(self, orion_client):
        """Test successful GET request"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"test": "data"}
        mock_response.content = b'{"test": "data"}'
        mock_client.get.return_value = mock_response
        
        orion_client._client = mock_client
        
        result = await orion_client._make_request("GET", "ngsi-ld/v1/entities")
        
        assert result == {"test": "data"}
        mock_client.get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_make_request_post_success(self, orion_client):
        """Test successful POST request"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"created": True}
        mock_response.content = b'{"created": true}'
        mock_client.post.return_value = mock_response
        
        orion_client._client = mock_client
        
        data = {"id": "test", "type": "Entity"}
        result = await orion_client._make_request("POST", "ngsi-ld/v1/entities", data)
        
        assert result == {"created": True}
        mock_client.post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_make_request_204_no_content(self, orion_client):
        """Test request returning 204 No Content"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_client.delete.return_value = mock_response
        
        orion_client._client = mock_client
        
        result = await orion_client._make_request("DELETE", "ngsi-ld/v1/entities/test")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_make_request_404_not_found(self, orion_client):
        """Test request returning 404 Not Found"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_client.get.return_value = mock_response
        
        orion_client._client = mock_client
        
        result = await orion_client._make_request("GET", "ngsi-ld/v1/entities/nonexistent")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_make_request_409_conflict(self, orion_client):
        """Test request returning 409 Conflict"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_client.post.return_value = mock_response
        
        orion_client._client = mock_client
        
        result = await orion_client._make_request("POST", "ngsi-ld/v1/entities", {"data": "test"})
        
        assert result["error"] == "conflict"
        assert result["message"] == "Entity already exists"
    
    @pytest.mark.asyncio
    async def test_make_request_api_error(self, orion_client):
        """Test request with API error"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "detail": "Invalid entity format",
            "title": "Bad Request"
        }
        mock_response.text = "Bad Request"
        mock_client.post.return_value = mock_response
        
        orion_client._client = mock_client
        
        with pytest.raises(OrionAPIError, match="Invalid entity format"):
            await orion_client._make_request("POST", "ngsi-ld/v1/entities", {"bad": "data"})
    
    @pytest.mark.asyncio
    async def test_make_request_connection_error(self, orion_client):
        """Test request with connection error"""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.RequestError("Connection failed")
        
        orion_client._client = mock_client
        
        with pytest.raises(OrionConnectionError, match="Request error"):
            await orion_client._make_request("GET", "ngsi-ld/v1/entities")
    
    @pytest.mark.asyncio
    async def test_create_entity(self, orion_client):
        """Test entity creation"""
        lines = [ReservationLine(sku="TEST-001", qty=2.0)]
        reservation = Reservation.create("test-project", lines)
        
        with patch.object(orion_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"created": True}
            
            result = await orion_client.create_entity(reservation)
            
            assert result == {"created": True}
            mock_request.assert_called_once_with("POST", "ngsi-ld/v1/entities", reservation.dict(by_alias=True))
    
    @pytest.mark.asyncio
    async def test_create_entity_with_dict(self, orion_client):
        """Test entity creation with dictionary input"""
        entity_dict = {
            "id": "urn:ngsi-ld:Test:123",
            "type": "Test",
            "value": {"type": "Property", "value": "test"}
        }
        
        with patch.object(orion_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"created": True}
            
            result = await orion_client.create_entity(entity_dict)
            
            assert result == {"created": True}
            mock_request.assert_called_once_with("POST", "ngsi-ld/v1/entities", entity_dict)
    
    @pytest.mark.asyncio
    async def test_get_entity(self, orion_client):
        """Test entity retrieval"""
        entity_id = "urn:ngsi-ld:Test:123"
        expected_entity = {"id": entity_id, "type": "Test"}
        
        with patch.object(orion_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = expected_entity
            
            result = await orion_client.get_entity(entity_id)
            
            assert result == expected_entity
            mock_request.assert_called_once_with("GET", f"ngsi-ld/v1/entities/{entity_id}")
    
    @pytest.mark.asyncio
    async def test_update_entity(self, orion_client):
        """Test entity update"""
        entity_id = "urn:ngsi-ld:Test:123"
        updates = {"value": {"type": "Property", "value": "updated"}}
        
        with patch.object(orion_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"updated": True}
            
            result = await orion_client.update_entity(entity_id, updates, "Test")
            
            assert result == {"updated": True}
            mock_request.assert_called_once_with("PATCH", f"ngsi-ld/v1/entities/{entity_id}/attrs", updates)
    
    @pytest.mark.asyncio
    async def test_upsert_entity_create_new(self, orion_client):
        """Test upsert creating new entity"""
        lines = [ReservationLine(sku="TEST-001", qty=1.0)]
        reservation = Reservation.create("new-project", lines)
        
        with patch.object(orion_client, 'get_entity', new_callable=AsyncMock) as mock_get:
            with patch.object(orion_client, 'create_entity', new_callable=AsyncMock) as mock_create:
                mock_get.return_value = None  # Entity doesn't exist
                mock_create.return_value = {"created": True}
                
                result = await orion_client.upsert_entity(reservation)
                
                assert result == {"created": True}
                mock_get.assert_called_once()
                mock_create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_upsert_entity_update_existing(self, orion_client):
        """Test upsert updating existing entity"""
        lines = [ReservationLine(sku="TEST-001", qty=1.0)]
        reservation = Reservation.create("existing-project", lines)
        
        existing_entity = {"id": reservation.id, "type": "Reservation"}
        
        with patch.object(orion_client, 'get_entity', new_callable=AsyncMock) as mock_get:
            with patch.object(orion_client, 'update_entity', new_callable=AsyncMock) as mock_update:
                mock_get.return_value = existing_entity  # Entity exists
                mock_update.return_value = {"updated": True}
                
                result = await orion_client.upsert_entity(reservation)
                
                assert result == {"updated": True}
                mock_get.assert_called_once()
                mock_update.assert_called_once()
                
                # Verify update data excludes id, type, @context
                update_call_args = mock_update.call_args[0]
                update_data = update_call_args[1]
                assert "id" not in update_data
                assert "type" not in update_data
                assert "@context" not in update_data
    
    @pytest.mark.asyncio
    async def test_upsert_entity_no_id(self, orion_client):
        """Test upsert with entity missing ID"""
        entity_dict = {"type": "Test", "value": {"type": "Property", "value": "test"}}
        
        with pytest.raises(ValueError, match="Entity ID is required"):
            await orion_client.upsert_entity(entity_dict)
    
    @pytest.mark.asyncio
    async def test_delete_entity(self, orion_client):
        """Test entity deletion"""
        entity_id = "urn:ngsi-ld:Test:123"
        
        with patch.object(orion_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = None  # 204 No Content
            
            result = await orion_client.delete_entity(entity_id)
            
            assert result is True
            mock_request.assert_called_once_with("DELETE", f"ngsi-ld/v1/entities/{entity_id}")
    
    @pytest.mark.asyncio
    async def test_query_entities(self, orion_client):
        """Test entity querying"""
        expected_entities = [
            {"id": "urn:ngsi-ld:Test:1", "type": "Test"},
            {"id": "urn:ngsi-ld:Test:2", "type": "Test"}
        ]
        
        with patch.object(orion_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = expected_entities
            
            result = await orion_client.query_entities(
                entity_type="Test",
                query="value>10",
                attrs=["value"],
                limit=50,
                offset=0
            )
            
            assert result == expected_entities
            
            # Verify request parameters
            call_args = mock_request.call_args
            assert call_args[0][0] == "GET"
            assert call_args[0][1] == "ngsi-ld/v1/entities"
            
            params = call_args[1]["params"]
            assert params["type"] == "Test"
            assert params["q"] == "value>10"
            assert params["attrs"] == "value"
            assert params["limit"] == 50
            assert params["offset"] == 0
    
    @pytest.mark.asyncio
    async def test_query_entities_empty_result(self, orion_client):
        """Test entity querying with empty result"""
        with patch.object(orion_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = None  # Empty result
            
            result = await orion_client.query_entities(entity_type="NonExistent")
            
            assert result == []
    
    @pytest.mark.asyncio
    async def test_create_subscription(self, orion_client):
        """Test subscription creation"""
        subscription = {
            "id": "test-subscription",
            "subject": {
                "entities": [{"type": "Test"}]
            },
            "notification": {
                "endpoint": {"uri": "http://test.com/notify"}
            }
        }
        
        with patch.object(orion_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"subscriptionId": "test-subscription"}
            
            result = await orion_client.create_subscription(subscription)
            
            assert result == "test-subscription"
            mock_request.assert_called_once_with("POST", "ngsi-ld/v1/subscriptions", subscription)
    
    @pytest.mark.asyncio
    async def test_create_subscription_failure(self, orion_client):
        """Test subscription creation failure"""
        subscription = {"invalid": "subscription"}
        
        with patch.object(orion_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"error": "Invalid subscription"}
            
            result = await orion_client.create_subscription(subscription)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_subscription(self, orion_client):
        """Test subscription retrieval"""
        subscription_id = "test-subscription"
        expected_subscription = {"id": subscription_id, "status": "active"}
        
        with patch.object(orion_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = expected_subscription
            
            result = await orion_client.get_subscription(subscription_id)
            
            assert result == expected_subscription
            mock_request.assert_called_once_with("GET", f"ngsi-ld/v1/subscriptions/{subscription_id}")
    
    @pytest.mark.asyncio
    async def test_delete_subscription(self, orion_client):
        """Test subscription deletion"""
        subscription_id = "test-subscription"
        
        with patch.object(orion_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = None  # 204 No Content
            
            result = await orion_client.delete_subscription(subscription_id)
            
            assert result is True
            mock_request.assert_called_once_with("DELETE", f"ngsi-ld/v1/subscriptions/{subscription_id}")
    
    @pytest.mark.asyncio
    async def test_list_subscriptions(self, orion_client):
        """Test subscriptions listing"""
        expected_subscriptions = [
            {"id": "sub1", "status": "active"},
            {"id": "sub2", "status": "inactive"}
        ]
        
        with patch.object(orion_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = expected_subscriptions
            
            result = await orion_client.list_subscriptions()
            
            assert result == expected_subscriptions
            mock_request.assert_called_once_with("GET", "ngsi-ld/v1/subscriptions")
    
    @pytest.mark.asyncio
    async def test_ensure_subscription_exists_create_new(self, orion_client):
        """Test ensuring subscription exists by creating new one"""
        subscription_id = "new-subscription"
        subscription_config = {
            "subject": {"entities": [{"type": "Test"}]},
            "notification": {"endpoint": {"uri": "http://test.com"}}
        }
        
        with patch.object(orion_client, 'get_subscription', new_callable=AsyncMock) as mock_get:
            with patch.object(orion_client, 'create_subscription', new_callable=AsyncMock) as mock_create:
                mock_get.return_value = None  # Subscription doesn't exist
                mock_create.return_value = subscription_id
                
                result = await orion_client.ensure_subscription_exists(subscription_id, subscription_config)
                
                assert result is True
                mock_get.assert_called_once_with(subscription_id)
                mock_create.assert_called_once()
                
                # Verify ID was added to config
                create_call_args = mock_create.call_args[0][0]
                assert create_call_args["id"] == subscription_id
    
    @pytest.mark.asyncio
    async def test_ensure_subscription_exists_already_exists(self, orion_client):
        """Test ensuring subscription exists when it already exists"""
        subscription_id = "existing-subscription"
        subscription_config = {}
        existing_subscription = {"id": subscription_id, "status": "active"}
        
        with patch.object(orion_client, 'get_subscription', new_callable=AsyncMock) as mock_get:
            with patch.object(orion_client, 'create_subscription', new_callable=AsyncMock) as mock_create:
                mock_get.return_value = existing_subscription  # Subscription exists
                
                result = await orion_client.ensure_subscription_exists(subscription_id, subscription_config)
                
                assert result is True
                mock_get.assert_called_once_with(subscription_id)
                mock_create.assert_not_called()  # Should not try to create
    
    @pytest.mark.asyncio
    async def test_ensure_subscription_exists_creation_failure(self, orion_client):
        """Test ensuring subscription exists when creation fails"""
        subscription_id = "failed-subscription"
        subscription_config = {}
        
        with patch.object(orion_client, 'get_subscription', new_callable=AsyncMock) as mock_get:
            with patch.object(orion_client, 'create_subscription', new_callable=AsyncMock) as mock_create:
                mock_get.return_value = None  # Subscription doesn't exist
                mock_create.return_value = None  # Creation failed
                
                result = await orion_client.ensure_subscription_exists(subscription_id, subscription_config)
                
                assert result is False
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, orion_client):
        """Test successful health check"""
        with patch.object(orion_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"version": "1.4.0"}
            
            result = await orion_client.health_check()
            
            assert result is True
            mock_request.assert_called_once_with("GET", "version")
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, orion_client):
        """Test health check failure"""
        with patch.object(orion_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = OrionConnectionError("Connection failed")
            
            result = await orion_client.health_check()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_context_manager(self, orion_client):
        """Test async context manager"""
        with patch.object(orion_client, 'connect', new_callable=AsyncMock) as mock_connect:
            with patch.object(orion_client, 'close', new_callable=AsyncMock) as mock_close:
                
                async with orion_client as client:
                    assert client == orion_client
                
                mock_connect.assert_called_once()
                mock_close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_unsupported_http_method(self, orion_client):
        """Test unsupported HTTP method"""
        orion_client._client = AsyncMock()
        
        with pytest.raises(ValueError, match="Unsupported HTTP method"):
            await orion_client._make_request("INVALID", "test-endpoint")
    
    @pytest.mark.asyncio
    async def test_json_decode_error_handling(self, orion_client):
        """Test handling of JSON decode errors"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "doc", 0)
        mock_response.text = "Not JSON response"
        mock_response.content = b"Not JSON response"
        mock_client.get.return_value = mock_response
        
        orion_client._client = mock_client
        
        result = await orion_client._make_request("GET", "test-endpoint")
        
        assert result == {"raw_response": "Not JSON response"}
    
    @pytest.mark.asyncio
    async def test_retry_mechanism(self, orion_client):
        """Test request retry mechanism"""
        mock_client = AsyncMock()
        
        # First call fails, second succeeds
        mock_client.get.side_effect = [
            httpx.RequestError("Temporary failure"),
            MagicMock(status_code=200, json=lambda: {"success": True}, content=b'{"success": true}')
        ]
        
        orion_client._client = mock_client
        
        result = await orion_client._make_request("GET", "test-endpoint")
        
        assert result == {"success": True}
        assert mock_client.get.call_count == 2