"""
Tests for health and monitoring endpoints
"""
import pytest
from unittest.mock import patch


class TestHealthEndpoints:
    """Test health check endpoints"""
    
    def test_health_check(self, client):
        """Test basic health check endpoint"""
        response = client.get("/healthz")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["service"] == "hermes-odoo-adapter"
        assert data["version"] == "0.1.0"
    
    @pytest.mark.asyncio
    async def test_readiness_check_all_healthy(self, async_client, app_with_mocks, 
                                               mock_odoo_client, mock_orion_client):
        """Test readiness check when all services are healthy"""
        # Mock health checks to return True
        mock_odoo_client.health_check.return_value = True
        mock_orion_client.health_check.return_value = True
        
        response = await async_client.get("/readyz")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "ready"
        assert data["checks"]["odoo"] is True
        assert data["checks"]["orion"] is True
        assert data["details"]["odoo"] == "Connected"
        assert data["details"]["orion"] == "Connected"
    
    @pytest.mark.asyncio
    async def test_readiness_check_odoo_unhealthy(self, async_client, app_with_mocks,
                                                  mock_odoo_client, mock_orion_client):
        """Test readiness check when Odoo is unhealthy"""
        # Mock Odoo health check to fail
        mock_odoo_client.health_check.return_value = False
        mock_orion_client.health_check.return_value = True
        
        response = await async_client.get("/readyz")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "not_ready"
        assert data["checks"]["odoo"] is False
        assert data["checks"]["orion"] is True
        assert data["details"]["odoo"] == "Connection failed"
        assert data["details"]["orion"] == "Connected"
    
    @pytest.mark.asyncio
    async def test_readiness_check_with_exception(self, async_client, app_with_mocks,
                                                  mock_odoo_client, mock_orion_client):
        """Test readiness check when health check raises exception"""
        # Mock Odoo health check to raise exception
        mock_odoo_client.health_check.side_effect = Exception("Connection timeout")
        mock_orion_client.health_check.return_value = True
        
        response = await async_client.get("/readyz")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "not_ready"
        assert data["checks"]["odoo"] is False
        assert data["checks"]["orion"] is True
        assert "Connection timeout" in data["details"]["odoo"]
        assert data["details"]["orion"] == "Connected"
    
    def test_metrics_endpoint(self, client):
        """Test Prometheus metrics endpoint"""
        response = client.get("/metrics")
        
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        
        # Check for some expected metrics
        metrics_text = response.text
        assert "hermes_odoo_adapter_info" in metrics_text
        assert "hermes_odoo_adapter_http_requests_total" in metrics_text


class TestHealthEndpointsWithoutMocks:
    """Test health endpoints without mocked dependencies"""
    
    def test_readiness_check_no_clients(self, client):
        """Test readiness check when clients are not initialized"""
        # This will test the actual application startup state
        response = client.get("/readyz")
        
        assert response.status_code == 200
        data = response.json()
        
        # When clients are not initialized, they should be marked as not ready
        assert data["status"] in ["ready", "not_ready"]  # Depends on app state
        assert "odoo" in data["checks"]
        assert "orion" in data["checks"]
        assert "odoo" in data["details"]
        assert "orion" in data["details"]