"""
Tests for Odoo JSON-RPC client
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from hermes_odoo_adapter.odoo_client import (
    OdooClient,
    OdooError,
    OdooAuthenticationError,
    OdooConnectionError,
    OdooAPIError,
    CircuitBreakerOpen,
    CircuitBreaker
)
from hermes_odoo_adapter.settings import settings


class TestCircuitBreaker:
    """Test circuit breaker functionality"""
    
    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker initial state"""
        cb = CircuitBreaker(failure_threshold=3, timeout_seconds=60)
        
        assert cb.state == "closed"
        assert cb.failure_count == 0
        assert cb.can_execute() is True
    
    def test_circuit_breaker_failure_accumulation(self):
        """Test failure accumulation in circuit breaker"""
        cb = CircuitBreaker(failure_threshold=3, timeout_seconds=60)
        
        # Record failures
        cb.record_failure()
        assert cb.state == "closed"
        assert cb.failure_count == 1
        
        cb.record_failure()
        assert cb.state == "closed"
        assert cb.failure_count == 2
        
        cb.record_failure()
        assert cb.state == "open"
        assert cb.failure_count == 3
        assert cb.can_execute() is False
    
    def test_circuit_breaker_success_reset(self):
        """Test circuit breaker reset on success"""
        cb = CircuitBreaker(failure_threshold=3, timeout_seconds=60)
        
        # Record some failures
        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2
        
        # Record success - should reset
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == "closed"
    
    @patch('time.time')
    def test_circuit_breaker_timeout_recovery(self, mock_time):
        """Test circuit breaker timeout recovery"""
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=60)
        
        # Set initial time
        mock_time.return_value = 1000
        
        # Trigger circuit breaker to open
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"
        assert cb.can_execute() is False
        
        # Time hasn't passed enough - should still be open
        mock_time.return_value = 1030
        assert cb.can_execute() is False
        
        # Time has passed - should transition to half-open
        mock_time.return_value = 1070
        assert cb.can_execute() is True
        assert cb.state == "half_open"


class TestOdooClient:
    """Test Odoo client functionality"""
    
    @pytest.fixture
    def odoo_client(self):
        """Create test Odoo client"""
        return OdooClient(
            url="http://test.odoo.com/jsonrpc",
            database="test_db",
            username="test_user",
            password="test_pass"
        )
    
    def test_odoo_client_initialization(self, odoo_client):
        """Test Odoo client initialization"""
        assert odoo_client.url == "http://test.odoo.com/jsonrpc"
        assert odoo_client.database == "test_db"
        assert odoo_client.username == "test_user"
        assert odoo_client.password == "test_pass"
        assert odoo_client._user_id is None
        assert odoo_client._client is None
    
    @pytest.mark.asyncio
    async def test_authentication_success(self, odoo_client):
        """Test successful authentication"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": 123}
        mock_client.post.return_value = mock_response
        
        odoo_client._client = mock_client
        
        await odoo_client._authenticate()
        
        assert odoo_client._user_id == 123
        mock_client.post.assert_called_once()
        
        # Verify the request payload
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["method"] == "call"
        assert payload["params"]["service"] == "common"
        assert payload["params"]["method"] == "authenticate"
        assert payload["params"]["args"] == ["test_db", "test_user", "test_pass", {}]
    
    @pytest.mark.asyncio
    async def test_authentication_failure(self, odoo_client):
        """Test authentication failure"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": False}
        mock_client.post.return_value = mock_response
        
        odoo_client._client = mock_client
        
        with pytest.raises(OdooAuthenticationError, match="Authentication failed"):
            await odoo_client._authenticate()
        
        assert odoo_client._user_id is None
    
    @pytest.mark.asyncio
    async def test_make_request_success(self, odoo_client):
        """Test successful request"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": {"data": "test"}}
        mock_response.raise_for_status.return_value = None
        mock_client.post.return_value = mock_response
        
        odoo_client._client = mock_client
        
        result = await odoo_client._make_request("test_service", "test_method", ["arg1", "arg2"])
        
        assert result == {"data": "test"}
        mock_client.post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_make_request_api_error(self, odoo_client):
        """Test request with API error"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "error": {
                "message": "Test error",
                "code": 500,
                "data": {"fault_string": "Internal error"}
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_client.post.return_value = mock_response
        
        odoo_client._client = mock_client
        
        with pytest.raises(OdooAPIError, match="Test error"):
            await odoo_client._make_request("test_service", "test_method", [])
    
    @pytest.mark.asyncio
    async def test_make_request_http_error(self, odoo_client):
        """Test request with HTTP error"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_client.post.return_value = mock_response
        mock_client.post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Server Error", request=MagicMock(), response=mock_response
        )
        
        odoo_client._client = mock_client
        
        with pytest.raises(OdooConnectionError, match="HTTP error 500"):
            await odoo_client._make_request("test_service", "test_method", [])
    
    @pytest.mark.asyncio
    async def test_make_request_connection_error(self, odoo_client):
        """Test request with connection error"""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.RequestError("Connection failed")
        
        odoo_client._client = mock_client
        
        with pytest.raises(OdooConnectionError, match="Request error"):
            await odoo_client._make_request("test_service", "test_method", [])
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_open(self, odoo_client):
        """Test request when circuit breaker is open"""
        # Force circuit breaker to open state
        odoo_client.circuit_breaker.state = "open"
        
        with pytest.raises(CircuitBreakerOpen, match="Circuit breaker is open"):
            await odoo_client._make_request("test_service", "test_method", [])
    
    @pytest.mark.asyncio
    async def test_call_method(self, odoo_client):
        """Test calling Odoo model method"""
        # Setup authentication
        odoo_client._user_id = 123
        
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": [{"id": 1, "name": "Test"}]}
        mock_response.raise_for_status.return_value = None
        mock_client.post.return_value = mock_response
        
        odoo_client._client = mock_client
        
        result = await odoo_client.call("res.partner", "search_read", [["name", "=", "Test"]])
        
        assert result == [{"id": 1, "name": "Test"}]
        
        # Verify the request payload
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["params"]["service"] == "object"
        assert payload["params"]["method"] == "execute_kw"
        assert payload["params"]["args"][0] == "test_db"  # database
        assert payload["params"]["args"][1] == 123  # user_id
        assert payload["params"]["args"][2] == "test_pass"  # password
        assert payload["params"]["args"][3] == "res.partner"  # model
        assert payload["params"]["args"][4] == "search_read"  # method
        assert payload["params"]["args"][5] == [[["name", "=", "Test"]]]  # args
    
    @pytest.mark.asyncio
    async def test_search_method(self, odoo_client):
        """Test search method"""
        with patch.object(odoo_client, 'call', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = [1, 2, 3]
            
            result = await odoo_client.search("res.partner", [["active", "=", True]], limit=10)
            
            assert result == [1, 2, 3]
            mock_call.assert_called_once_with("res.partner", "search", [["active", "=", True]], limit=10)
    
    @pytest.mark.asyncio
    async def test_read_method(self, odoo_client):
        """Test read method"""
        with patch.object(odoo_client, 'call', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = [{"id": 1, "name": "Test"}]
            
            result = await odoo_client.read("res.partner", [1], ["name"])
            
            assert result == [{"id": 1, "name": "Test"}]
            mock_call.assert_called_once_with("res.partner", "read", [1], fields=["name"])
    
    @pytest.mark.asyncio
    async def test_get_product_by_sku(self, odoo_client):
        """Test getting product by SKU"""
        with patch.object(odoo_client, 'search_read', new_callable=AsyncMock) as mock_search_read:
            mock_search_read.return_value = [{"id": 123, "name": "Test Product", "default_code": "TEST-001"}]
            
            result = await odoo_client.get_product_by_sku("TEST-001")
            
            assert result == {"id": 123, "name": "Test Product", "default_code": "TEST-001"}
            mock_search_read.assert_called_once_with(
                "product.product",
                [["default_code", "=", "TEST-001"]],
                fields=["id", "name", "default_code", "uom_id"]
            )
    
    @pytest.mark.asyncio
    async def test_get_product_by_sku_not_found(self, odoo_client):
        """Test getting product by SKU when not found"""
        with patch.object(odoo_client, 'search_read', new_callable=AsyncMock) as mock_search_read:
            mock_search_read.return_value = []
            
            result = await odoo_client.get_product_by_sku("NONEXISTENT")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, odoo_client):
        """Test successful health check"""
        with patch.object(odoo_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"server_version": "15.0"}
            
            result = await odoo_client.health_check()
            
            assert result is True
            mock_request.assert_called_once_with("common", "version", [])
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, odoo_client):
        """Test health check failure"""
        with patch.object(odoo_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = OdooConnectionError("Connection failed")
            
            result = await odoo_client.health_check()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_context_manager(self, odoo_client):
        """Test async context manager"""
        with patch.object(odoo_client, 'connect', new_callable=AsyncMock) as mock_connect:
            with patch.object(odoo_client, 'close', new_callable=AsyncMock) as mock_close:
                
                async with odoo_client as client:
                    assert client == odoo_client
                
                mock_connect.assert_called_once()
                mock_close.assert_called_once()
    
    @pytest.mark.asyncio  
    async def test_auto_reconnect_on_401(self, odoo_client):
        """Test automatic re-authentication on 401 error"""
        # Setup initial auth
        odoo_client._user_id = 123
        
        mock_client = AsyncMock()
        
        # First call fails with 401
        mock_response_401 = MagicMock()
        mock_response_401.status_code = 401
        mock_response_401.text = "Unauthorized"
        
        # Second call (after re-auth) succeeds
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"result": 456}  # New user ID
        mock_response_success.raise_for_status.return_value = None
        
        mock_client.post.side_effect = [
            httpx.HTTPStatusError("401 Unauthorized", 
                                request=MagicMock(), 
                                response=mock_response_401),
            mock_response_success
        ]
        
        odoo_client._client = mock_client
        
        # First call should trigger re-auth but still raise the error
        with pytest.raises(OdooConnectionError, match="HTTP error 401"):
            await odoo_client._make_request("test_service", "test_method", [])
        
        # Verify that user_id was cleared for re-auth
        assert odoo_client._user_id is None