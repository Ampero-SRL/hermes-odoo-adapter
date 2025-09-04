"""
Integration tests for API endpoints
"""
import pytest
import json
from unittest.mock import patch

from hermes_odoo_adapter.main import app


@pytest.mark.integration
class TestAPIEndpointsIntegration:
    """Test API endpoints with realistic scenarios"""
    
    @pytest.mark.asyncio
    async def test_orion_notification_endpoint(self, async_client, app_with_mocks, 
                                               mock_project_worker):
        """Test Orion-LD notification endpoint"""
        notification_payload = {
            "subscriptionId": "hermes-project-subscription",
            "data": [
                {
                    "id": "urn:ngsi-ld:Project:integration-test-001",
                    "type": "Project",
                    "code": {
                        "type": "Property",
                        "value": "INT-TEST-001"
                    },
                    "station": {
                        "type": "Property", 
                        "value": "TEST-STATION"
                    },
                    "status": {
                        "type": "Property",
                        "value": "requested"
                    }
                }
            ]
        }
        
        mock_project_worker.handle_project_notification.return_value = None
        
        response = await async_client.post("/orion/notifications", 
                                         json=notification_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Notification received"
        assert data["entities_queued"] == 1
        
        # Verify project worker was called for each entity
        assert mock_project_worker.handle_project_notification.call_count == 1
    
    @pytest.mark.asyncio
    async def test_multiple_entities_notification(self, async_client, app_with_mocks,
                                                  mock_project_worker):
        """Test notification with multiple entities"""
        notification_payload = {
            "subscriptionId": "hermes-project-subscription",
            "data": [
                {
                    "id": "urn:ngsi-ld:Project:multi-test-001",
                    "type": "Project",
                    "code": {"type": "Property", "value": "MULTI-001"},
                    "status": {"type": "Property", "value": "requested"}
                },
                {
                    "id": "urn:ngsi-ld:Project:multi-test-002", 
                    "type": "Project",
                    "code": {"type": "Property", "value": "MULTI-002"},
                    "status": {"type": "Property", "value": "requested"}
                }
            ]
        }
        
        mock_project_worker.handle_project_notification.return_value = None
        
        response = await async_client.post("/orion/notifications",
                                         json=notification_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["entities_queued"] == 2
        
        # Both entities should be processed
        assert mock_project_worker.handle_project_notification.call_count == 2
    
    @pytest.mark.asyncio
    async def test_admin_recompute_endpoint(self, async_client, app_with_mocks,
                                           mock_project_worker):
        """Test manual project recomputation endpoint"""
        recompute_request = {
            "projectCode": "ADMIN-TEST-001",
            "station": "ADMIN-STATION"
        }
        
        mock_project_worker.handle_project_notification.return_value = None
        
        response = await async_client.post("/admin/recompute/admin-project-123",
                                         json=recompute_request)
        
        assert response.status_code == 200
        data = response.json()
        assert "Recomputation queued for project admin-project-123" in data["message"]
        
        # Verify synthetic project entity was created and processed
        assert mock_project_worker.handle_project_notification.call_count == 1
        call_args = mock_project_worker.handle_project_notification.call_args[0][0]
        
        assert call_args["id"] == "urn:ngsi-ld:Project:admin-project-123"
        assert call_args["type"] == "Project"
        assert call_args["code"]["value"] == "ADMIN-TEST-001"
        assert call_args["station"]["value"] == "ADMIN-STATION"
        assert call_args["status"]["value"] == "requested"
    
    @pytest.mark.asyncio
    async def test_recompute_without_optional_fields(self, async_client, app_with_mocks,
                                                    mock_project_worker):
        """Test recomputation without optional fields"""
        # Empty request body - should use project ID as project code
        response = await async_client.post("/admin/recompute/simple-project")
        
        assert response.status_code == 200
        
        # Verify call was made with project ID as code
        call_args = mock_project_worker.handle_project_notification.call_args[0][0]
        assert call_args["code"]["value"] == "simple-project"  # Uses project_id as default
        assert "station" not in call_args  # No station field should be present
    
    @pytest.mark.asyncio
    async def test_inventory_sync_trigger(self, async_client, app_with_mocks,
                                         mock_inventory_worker):
        """Test manual inventory sync trigger"""
        mock_inventory_worker.sync_inventory.return_value = {
            "status": "completed",
            "processed": 150,
            "updated": 145,
            "errors": 5
        }
        
        response = await async_client.get("/admin/inventory/sync")
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Inventory synchronization queued"
    
    @pytest.mark.asyncio
    async def test_inventory_sync_status(self, async_client, app_with_mocks,
                                        mock_inventory_worker):
        """Test inventory sync status endpoint"""
        mock_status = {
            "running": True,
            "last_sync_time": "2023-01-01T12:00:00Z",
            "sync_interval_seconds": 600,
            "batch_size": 100,
            "next_sync_due": "2023-01-01T12:10:00Z"
        }
        
        mock_inventory_worker.get_sync_status.return_value = mock_status
        
        response = await async_client.get("/admin/inventory/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data == mock_status
    
    @pytest.mark.asyncio
    async def test_single_product_inventory_sync(self, async_client, app_with_mocks,
                                                mock_inventory_worker):
        """Test single product inventory sync"""
        mock_inventory_worker.sync_product_inventory.return_value = {
            "sku": "TEST-PRODUCT-001",
            "total_quantity": 25.0,
            "reserved_quantity": 5.0,
            "available_quantity": 20.0,
            "updated": True
        }
        
        response = await async_client.post("/admin/inventory/sync/TEST-PRODUCT-001")
        
        assert response.status_code == 200
        data = response.json()
        assert "TEST-PRODUCT-001" in data["message"]
    
    @pytest.mark.asyncio
    async def test_odoo_webhook_endpoint(self, async_client, app_with_mocks,
                                        mock_inventory_worker):
        """Test Odoo webhook endpoint"""
        webhook_payload = {
            "type": "stock_change",
            "product_id": 123,
            "sku": "WEBHOOK-TEST-001",
            "old_quantity": 10.0,
            "new_quantity": 15.0
        }
        
        mock_inventory_worker.handle_stock_change.return_value = None
        
        # Enable webhooks for this test
        with patch('hermes_odoo_adapter.settings.settings') as mock_settings:
            mock_settings.webhook_enabled = True
            
            response = await async_client.post("/odoo/webhook", json=webhook_payload)
            
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Webhook received"
            
            # Verify stock change handler was called
            mock_inventory_worker.handle_stock_change.assert_called_once_with(webhook_payload)
    
    @pytest.mark.asyncio
    async def test_odoo_webhook_disabled(self, async_client, app_with_mocks):
        """Test Odoo webhook when feature is disabled"""
        webhook_payload = {
            "type": "stock_change",
            "product_id": 123
        }
        
        # Webhooks disabled by default in settings
        response = await async_client.post("/odoo/webhook", json=webhook_payload)
        
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Webhooks not enabled"
    
    @pytest.mark.asyncio
    async def test_debug_endpoints(self, async_client, app_with_mocks, mock_orion_client):
        """Test debug endpoints (when not in testing mode)"""
        # Mock non-testing mode
        with patch('hermes_odoo_adapter.settings.settings') as mock_settings:
            mock_settings.testing = False
            
            # Test debug reservation endpoint
            mock_reservation = {
                "id": "urn:ngsi-ld:Reservation:debug-test",
                "type": "Reservation",
                "project_ref": {
                    "type": "Relationship",
                    "object": "urn:ngsi-ld:Project:debug-test"
                },
                "lines": {
                    "type": "Property",
                    "value": [{"sku": "DEBUG-001", "qty": 2.0}]
                }
            }
            
            mock_orion_client.get_entity.return_value = mock_reservation
            
            response = await async_client.get("/debug/reservation/debug-test")
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "urn:ngsi-ld:Reservation:debug-test"
            assert data["type"] == "Reservation"
            
            # Verify correct entity ID was requested
            mock_orion_client.get_entity.assert_called_with("urn:ngsi-ld:Reservation:debug-test")
    
    @pytest.mark.asyncio
    async def test_debug_entity_not_found(self, async_client, app_with_mocks, mock_orion_client):
        """Test debug endpoint when entity not found"""
        with patch('hermes_odoo_adapter.settings.settings') as mock_settings:
            mock_settings.testing = False
            
            mock_orion_client.get_entity.return_value = None  # Not found
            
            response = await async_client.get("/debug/shortage/nonexistent")
            
            assert response.status_code == 404
            data = response.json()
            assert data["detail"] == "Shortage not found"
    
    @pytest.mark.asyncio
    async def test_service_unavailable_responses(self, async_client):
        """Test responses when services are not available"""
        # Test with no workers initialized (default app state)
        
        # Project recompute without worker
        response = await async_client.post("/admin/recompute/test")
        assert response.status_code == 503
        assert "Project worker not available" in response.json()["detail"]
        
        # Inventory sync without worker
        response = await async_client.get("/admin/inventory/sync")
        assert response.status_code == 503
        assert "Inventory worker not available" in response.json()["detail"]
        
        # Inventory status without worker
        response = await async_client.get("/admin/inventory/status")
        assert response.status_code == 503
        assert "Inventory worker not available" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_validation_errors(self, async_client, app_with_mocks):
        """Test request validation errors"""
        # Invalid JSON in notification
        response = await async_client.post("/orion/notifications",
                                         content="invalid json",
                                         headers={"Content-Type": "application/json"})
        assert response.status_code == 422
        
        # Missing required fields in notification
        invalid_notification = {
            "subscriptionId": "test"
            # Missing 'data' field
        }
        
        response = await async_client.post("/orion/notifications", json=invalid_notification)
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_error_handling_in_endpoints(self, async_client, app_with_mocks,
                                              mock_project_worker):
        """Test error handling in endpoints"""
        # Simulate worker error
        mock_project_worker.handle_project_notification.side_effect = Exception("Worker failed")
        
        notification_payload = {
            "subscriptionId": "error-test",
            "data": [{
                "id": "urn:ngsi-ld:Project:error-test",
                "type": "Project",
                "code": {"type": "Property", "value": "ERROR-001"},
                "status": {"type": "Property", "value": "requested"}
            }]
        }
        
        # The endpoint should still return 200 since background task handles the error
        response = await async_client.post("/orion/notifications", json=notification_payload)
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_correlation_id_middleware(self, async_client):
        """Test that correlation ID is added to responses"""
        response = await async_client.get("/healthz")
        
        assert response.status_code == 200
        assert "X-Correlation-ID" in response.headers
        
        # Correlation ID should be a valid format (UUID-like)
        correlation_id = response.headers["X-Correlation-ID"]
        assert len(correlation_id) > 0
        assert "-" in correlation_id  # UUID format check
    
    @pytest.mark.asyncio
    async def test_metrics_format(self, async_client):
        """Test metrics endpoint format"""
        response = await async_client.get("/metrics")
        
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        
        # Check for expected Prometheus metrics format
        content = response.text
        assert "# HELP" in content
        assert "# TYPE" in content
        assert "hermes_odoo_adapter" in content
    
    @pytest.mark.asyncio
    async def test_readiness_check_detailed(self, async_client, app_with_mocks,
                                           mock_odoo_client, mock_orion_client):
        """Test detailed readiness check"""
        # Configure mock health checks
        mock_odoo_client.health_check.return_value = True
        mock_orion_client.health_check.return_value = True
        
        response = await async_client.get("/readyz")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "ready"
        assert "checks" in data
        assert "details" in data
        assert "odoo" in data["checks"]
        assert "orion" in data["checks"]
        assert data["checks"]["odoo"] is True
        assert data["checks"]["orion"] is True
        assert "Connected" in data["details"]["odoo"]
        assert "Connected" in data["details"]["orion"]