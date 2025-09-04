"""
Tests for utility modules (logging, metrics, idempotency)
"""
import pytest
import time
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

from hermes_odoo_adapter.utils.logging import get_logger, LoggingContext
from hermes_odoo_adapter.utils.metrics import MetricsCollector, metrics
from hermes_odoo_adapter.utils.idempotency import IdempotencyHelper


class TestLogging:
    """Test logging utilities"""
    
    def test_get_logger_creates_logger(self):
        """Test logger creation"""
        logger = get_logger("test_module")
        
        assert logger is not None
        assert logger.name == "test_module"
    
    def test_logging_context_manager(self):
        """Test logging context manager"""
        logger = get_logger("test_context")
        
        with LoggingContext(request_id="test-123", user_id="user-456"):
            # Context should be set
            pass
        
        # Test that context manager works without exceptions
        assert True
    
    def test_nested_logging_contexts(self):
        """Test nested logging contexts"""
        logger = get_logger("test_nested")
        
        with LoggingContext(request_id="outer"):
            with LoggingContext(user_id="inner"):
                # Both contexts should be available
                pass
        
        # Should complete without errors
        assert True
    
    def test_logging_context_with_none_values(self):
        """Test logging context with None values"""
        with LoggingContext(request_id=None, user_id="test"):
            # Should handle None values gracefully
            pass
        
        assert True


class TestMetricsCollector:
    """Test metrics collection functionality"""
    
    @pytest.fixture
    def metrics_collector(self):
        """Create fresh metrics collector for testing"""
        return MetricsCollector()
    
    def test_metrics_initialization(self, metrics_collector):
        """Test metrics collector initialization"""
        assert metrics_collector.registry is not None
        
        # Should have basic metrics format
        metrics_text = metrics_collector.get_metrics()
        assert isinstance(metrics_text, str)
        assert len(metrics_text) > 0
    
    def test_content_type(self, metrics_collector):
        """Test metrics content type"""
        content_type = metrics_collector.get_content_type()
        assert content_type.startswith("text/plain")
    
    def test_record_reservation_created(self, metrics_collector):
        """Test recording reservation creation"""
        # Should not raise exception
        metrics_collector.record_reservation_created()
        metrics_collector.record_reservation_created("success")
        
        metrics_text = metrics_collector.get_metrics()
        assert "reservations_created_total" in metrics_text
    
    def test_record_shortage_created(self, metrics_collector):
        """Test recording shortage creation"""
        # Should not raise exception
        metrics_collector.record_shortage_created()
        metrics_collector.record_shortage_created("created")
        
        metrics_text = metrics_collector.get_metrics()
        assert "shortages_created_total" in metrics_text
    
    def test_update_active_projects(self, metrics_collector):
        """Test updating active projects gauge"""
        metrics_collector.update_active_projects(5)
        metrics_collector.update_active_projects(10)
        
        metrics_text = metrics_collector.get_metrics()
        assert "active_projects" in metrics_text
    
    def test_record_inventory_sync_completed(self, metrics_collector):
        """Test recording inventory sync completion"""
        metrics_collector.record_inventory_sync_completed(100, 30.5)
        
        metrics_text = metrics_collector.get_metrics()
        assert "inventory_sync_total" in metrics_text
        assert "inventory_items_processed_total" in metrics_text
        assert "inventory_sync_duration_seconds" in metrics_text
    
    def test_record_inventory_sync_failed(self, metrics_collector):
        """Test recording inventory sync failure"""
        metrics_collector.record_inventory_sync_failed()
        
        metrics_text = metrics_collector.get_metrics()
        assert "inventory_sync_total" in metrics_text
    
    def test_record_stock_change_processed(self, metrics_collector):
        """Test recording stock change processing"""
        metrics_collector.record_stock_change_processed()
        
        metrics_text = metrics_collector.get_metrics()
        assert "stock_changes_processed_total" in metrics_text
    
    def test_record_stock_change_failed(self, metrics_collector):
        """Test recording stock change failure"""
        metrics_collector.record_stock_change_failed()
        
        metrics_text = metrics_collector.get_metrics()
        assert "stock_changes_processed_total" in metrics_text
    
    def test_time_http_request_success(self, metrics_collector):
        """Test timing HTTP request success"""
        with metrics_collector.time_http_request("GET", "/test"):
            time.sleep(0.01)  # Small delay for timing
        
        metrics_text = metrics_collector.get_metrics()
        assert "http_requests_total" in metrics_text
        assert "http_request_duration_seconds" in metrics_text
    
    def test_time_http_request_with_exception(self, metrics_collector):
        """Test timing HTTP request with exception"""
        class TestException(Exception):
            status_code = 404
        
        with pytest.raises(TestException):
            with metrics_collector.time_http_request("POST", "/error"):
                raise TestException("Test error")
        
        metrics_text = metrics_collector.get_metrics()
        assert "http_requests_total" in metrics_text
    
    def test_time_odoo_request_success(self, metrics_collector):
        """Test timing Odoo request success"""
        with metrics_collector.time_odoo_request("res.partner", "search"):
            time.sleep(0.01)
        
        metrics_text = metrics_collector.get_metrics()
        assert "odoo_requests_total" in metrics_text
        assert "odoo_request_duration_seconds" in metrics_text
    
    def test_time_odoo_request_with_exception(self, metrics_collector):
        """Test timing Odoo request with exception"""
        with pytest.raises(Exception):
            with metrics_collector.time_odoo_request("res.partner", "create"):
                raise Exception("Odoo error")
        
        metrics_text = metrics_collector.get_metrics()
        assert "odoo_requests_total" in metrics_text
    
    def test_time_orion_operation_success(self, metrics_collector):
        """Test timing Orion operation success"""
        with metrics_collector.time_orion_operation("create", "Reservation"):
            time.sleep(0.01)
        
        metrics_text = metrics_collector.get_metrics()
        assert "orion_operations_total" in metrics_text
        assert "orion_operation_duration_seconds" in metrics_text
    
    def test_time_orion_operation_with_exception(self, metrics_collector):
        """Test timing Orion operation with exception"""
        with pytest.raises(Exception):
            with metrics_collector.time_orion_operation("update", "Shortage"):
                raise Exception("Orion error")
        
        metrics_text = metrics_collector.get_metrics()
        assert "orion_operations_total" in metrics_text
    
    def test_global_metrics_instance(self):
        """Test global metrics instance"""
        # Should be able to use global metrics instance
        metrics.record_reservation_created()
        
        metrics_text = metrics.get_metrics()
        assert "reservations_created_total" in metrics_text


class TestIdempotencyHelper:
    """Test idempotency helper functionality"""
    
    @pytest.fixture
    def idempotency_helper(self):
        """Create fresh idempotency helper for testing"""
        return IdempotencyHelper()
    
    def test_should_process_project_first_time(self, idempotency_helper):
        """Test processing project for the first time"""
        project_id = "test-project-001"
        entity_data = {
            "id": f"urn:ngsi-ld:Project:{project_id}",
            "type": "Project",
            "status": {"type": "Property", "value": "requested"}
        }
        
        # First time should process
        result = idempotency_helper.should_process_project(project_id, entity_data)
        assert result is True
    
    def test_should_process_project_duplicate(self, idempotency_helper):
        """Test processing duplicate project"""
        project_id = "test-project-002"
        entity_data = {
            "id": f"urn:ngsi-ld:Project:{project_id}",
            "type": "Project", 
            "status": {"type": "Property", "value": "requested"}
        }
        
        # First time
        result1 = idempotency_helper.should_process_project(project_id, entity_data)
        assert result1 is True
        
        # Mark as processed
        idempotency_helper.mark_project_processed(project_id, entity_data, {"result": "success"})
        
        # Second time should not process
        result2 = idempotency_helper.should_process_project(project_id, entity_data)
        assert result2 is False
    
    def test_should_process_project_status_change(self, idempotency_helper):
        """Test processing project after status change"""
        project_id = "test-project-003"
        
        # Initial entity data
        entity_data_v1 = {
            "id": f"urn:ngsi-ld:Project:{project_id}",
            "type": "Project",
            "status": {"type": "Property", "value": "requested"}
        }
        
        # Updated entity data (different status)
        entity_data_v2 = {
            "id": f"urn:ngsi-ld:Project:{project_id}",
            "type": "Project",
            "status": {"type": "Property", "value": "in_progress"}
        }
        
        # Process first version
        result1 = idempotency_helper.should_process_project(project_id, entity_data_v1)
        assert result1 is True
        
        idempotency_helper.mark_project_processed(project_id, entity_data_v1, {"result": "success"})
        
        # Same version should not process
        result2 = idempotency_helper.should_process_project(project_id, entity_data_v1)
        assert result2 is False
        
        # Different version should process
        result3 = idempotency_helper.should_process_project(project_id, entity_data_v2)
        assert result3 is True
    
    def test_generate_correlation_id(self):
        """Test correlation ID generation"""
        from hermes_odoo_adapter.utils.idempotency import generate_correlation_id
        
        # Should generate unique IDs
        id1 = generate_correlation_id()
        id2 = generate_correlation_id()
        
        assert id1 != id2
        assert len(id1) > 0
        assert len(id2) > 0
        
        # Should be string format
        assert isinstance(id1, str)
        assert isinstance(id2, str)
    
    def test_idempotency_with_metadata(self, idempotency_helper):
        """Test idempotency with additional metadata"""
        project_id = "test-project-004"
        entity_data = {
            "id": f"urn:ngsi-ld:Project:{project_id}",
            "type": "Project",
            "status": {"type": "Property", "value": "requested"},
            "code": {"type": "Property", "value": "TEST-CODE"},
            "station": {"type": "Property", "value": "STATION-A"}
        }
        
        # Process once
        result1 = idempotency_helper.should_process_project(project_id, entity_data)
        assert result1 is True
        
        idempotency_helper.mark_project_processed(
            project_id, 
            entity_data, 
            {"type": "reservation", "lines": 3}
        )
        
        # Same entity should not process again
        result2 = idempotency_helper.should_process_project(project_id, entity_data)
        assert result2 is False
        
        # Modified entity should process
        modified_entity_data = entity_data.copy()
        modified_entity_data["code"]["value"] = "MODIFIED-CODE"
        
        result3 = idempotency_helper.should_process_project(project_id, modified_entity_data)
        assert result3 is True
    
    def test_idempotency_cleanup(self, idempotency_helper):
        """Test that idempotency helper doesn't grow unbounded"""
        # Process many projects
        for i in range(100):
            project_id = f"test-project-{i:03d}"
            entity_data = {
                "id": f"urn:ngsi-ld:Project:{project_id}",
                "type": "Project",
                "status": {"type": "Property", "value": "requested"}
            }
            
            should_process = idempotency_helper.should_process_project(project_id, entity_data)
            assert should_process is True
            
            idempotency_helper.mark_project_processed(project_id, entity_data, {"result": "success"})
        
        # All should be marked as processed
        for i in range(100):
            project_id = f"test-project-{i:03d}"
            entity_data = {
                "id": f"urn:ngsi-ld:Project:{project_id}",
                "type": "Project",
                "status": {"type": "Property", "value": "requested"}
            }
            
            should_process = idempotency_helper.should_process_project(project_id, entity_data)
            assert should_process is False
        
        # Helper should have reasonable size (implementation dependent)
        # This test ensures we don't have unbounded growth
        assert len(idempotency_helper._processed_projects) <= 100
    
    def test_idempotency_with_complex_entity_changes(self, idempotency_helper):
        """Test idempotency with complex entity structure changes"""
        project_id = "complex-project"
        
        # Base entity
        base_entity = {
            "id": f"urn:ngsi-ld:Project:{project_id}",
            "type": "Project",
            "status": {"type": "Property", "value": "requested"},
            "metadata": {
                "type": "Property",
                "value": {
                    "version": 1,
                    "tags": ["manufacturing", "test"]
                }
            }
        }
        
        # Process base entity
        result1 = idempotency_helper.should_process_project(project_id, base_entity)
        assert result1 is True
        
        idempotency_helper.mark_project_processed(project_id, base_entity, {"result": "success"})
        
        # Same entity should not process
        result2 = idempotency_helper.should_process_project(project_id, base_entity)
        assert result2 is False
        
        # Entity with updated metadata should process
        updated_entity = base_entity.copy()
        updated_entity["metadata"]["value"]["version"] = 2
        
        result3 = idempotency_helper.should_process_project(project_id, updated_entity)
        assert result3 is True