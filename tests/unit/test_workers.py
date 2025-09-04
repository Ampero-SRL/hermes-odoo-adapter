"""
Tests for worker modules (project sync and inventory sync)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from hermes_odoo_adapter.workers.project_sync import ProjectSyncWorker
from hermes_odoo_adapter.workers.inventory_sync import InventorySyncWorker
from hermes_odoo_adapter.models.ngsi_models import Reservation, Shortage


class TestProjectSyncWorker:
    """Test project sync worker functionality"""
    
    @pytest.fixture
    def project_worker(self, mock_odoo_client, mock_orion_client):
        """Create project sync worker with mocked dependencies"""
        return ProjectSyncWorker(mock_odoo_client, mock_orion_client)
    
    def test_worker_initialization(self, project_worker, mock_odoo_client, mock_orion_client):
        """Test worker initialization"""
        assert project_worker.odoo_client == mock_odoo_client
        assert project_worker.orion_client == mock_orion_client
        assert project_worker.subscription_id == "hermes-project-subscription"
    
    @pytest.mark.asyncio
    async def test_setup_subscription_success(self, project_worker, mock_orion_client):
        """Test successful subscription setup"""
        mock_orion_client.ensure_subscription_exists.return_value = True
        
        result = await project_worker.setup_subscription()
        
        assert result is True
        mock_orion_client.ensure_subscription_exists.assert_called_once()
        
        # Verify subscription configuration
        call_args = mock_orion_client.ensure_subscription_exists.call_args
        subscription_id = call_args[0][0]
        subscription_config = call_args[0][1]
        
        assert subscription_id == "hermes-project-subscription"
        assert subscription_config["description"] == "HERMES Project status change subscription"
        assert subscription_config["subject"]["entities"][0]["type"] == "Project"
        assert "status==requested" in subscription_config["subject"]["condition"]["expression"]["q"]
    
    @pytest.mark.asyncio
    async def test_setup_subscription_failure(self, project_worker, mock_orion_client):
        """Test subscription setup failure"""
        mock_orion_client.ensure_subscription_exists.return_value = False
        
        result = await project_worker.setup_subscription()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_setup_subscription_exception(self, project_worker, mock_orion_client):
        """Test subscription setup with exception"""
        mock_orion_client.ensure_subscription_exists.side_effect = Exception("Orion error")
        
        result = await project_worker.setup_subscription()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_handle_non_project_entity(self, project_worker):
        """Test handling non-Project entity notifications"""
        entity_data = {
            "id": "urn:ngsi-ld:SomeOtherEntity:123",
            "type": "SomeOtherEntity"
        }
        
        # Should return without processing
        await project_worker.handle_project_notification(entity_data)
        
        # No calls should be made to Odoo/Orion
        project_worker.odoo_client.get_product_by_sku.assert_not_called()
        project_worker.orion_client.upsert_entity.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_project_notification_success(self, project_worker):
        """Test successful project notification handling"""
        # Setup mocks for successful flow
        project_worker.odoo_client.get_product_by_sku.return_value = {
            "id": 123,
            "name": "Test Product"
        }
        
        project_worker.odoo_client.get_bom_for_product.return_value = {
            "id": 456,
            "bom_line_ids": [789]
        }
        
        project_worker.odoo_client.get_bom_lines.return_value = [
            {
                "id": 789,
                "product_id": [101, "Component"],
                "product_qty": 2.0
            }
        ]
        
        project_worker.odoo_client.get_stock_for_products.return_value = [
            {
                "product_id": [101, "Component"],
                "quantity": 10.0,
                "reserved_quantity": 0.0
            }
        ]
        
        project_worker.odoo_client.read.return_value = [
            {"id": 101, "default_code": "COMP-001"}
        ]
        
        project_worker.orion_client.upsert_entity.return_value = {"status": "success"}
        
        entity_data = {
            "id": "urn:ngsi-ld:Project:test-123",
            "type": "Project",
            "code": {"type": "Property", "value": "TEST-PRODUCT"},
            "status": {"type": "Property", "value": "requested"}
        }
        
        with patch('hermes_odoo_adapter.utils.idempotency.idempotency_helper') as mock_idempotency:
            mock_idempotency.should_process_project.return_value = True
            
            await project_worker.handle_project_notification(entity_data)
        
        # Verify all steps were called
        project_worker.odoo_client.get_product_by_sku.assert_called_once_with("TEST-PRODUCT")
        project_worker.odoo_client.get_bom_for_product.assert_called_once_with(123)
        project_worker.odoo_client.get_bom_lines.assert_called_once_with([789])
        project_worker.odoo_client.get_stock_for_products.assert_called_once_with([101])
        
        # Should create entities in Orion
        assert project_worker.orion_client.upsert_entity.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_handle_project_notification_idempotency_skip(self, project_worker):
        """Test skipping duplicate project notifications"""
        entity_data = {
            "id": "urn:ngsi-ld:Project:duplicate-123",
            "type": "Project", 
            "code": {"type": "Property", "value": "DUPLICATE-PRODUCT"},
            "status": {"type": "Property", "value": "requested"}
        }
        
        with patch('hermes_odoo_adapter.utils.idempotency.idempotency_helper') as mock_idempotency:
            mock_idempotency.should_process_project.return_value = False  # Already processed
            
            await project_worker.handle_project_notification(entity_data)
        
        # No Odoo calls should be made
        project_worker.odoo_client.get_product_by_sku.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_non_requested_status(self, project_worker):
        """Test handling project with non-requested status"""
        entity_data = {
            "id": "urn:ngsi-ld:Project:completed-123",
            "type": "Project",
            "code": {"type": "Property", "value": "COMPLETED-PRODUCT"},
            "status": {"type": "Property", "value": "completed"}
        }
        
        with patch('hermes_odoo_adapter.utils.idempotency.idempotency_helper') as mock_idempotency:
            mock_idempotency.should_process_project.return_value = True
            
            await project_worker.handle_project_notification(entity_data)
        
        # Should not process non-requested projects
        project_worker.odoo_client.get_product_by_sku.assert_not_called()
    
    def test_extract_property_value(self, project_worker):
        """Test NGSI-LD property value extraction"""
        entity_data = {
            "code": {"type": "Property", "value": "TEST-CODE"},
            "station": {"type": "Property", "value": "STATION-A"},
            "invalid_property": {"type": "Relationship", "object": "urn:test"},
            "missing_value": {"type": "Property"},
            "non_property": "simple_value"
        }
        
        # Valid property extraction
        assert project_worker._extract_property_value(entity_data, "code") == "TEST-CODE"
        assert project_worker._extract_property_value(entity_data, "station") == "STATION-A"
        
        # Invalid cases
        assert project_worker._extract_property_value(entity_data, "invalid_property") is None
        assert project_worker._extract_property_value(entity_data, "missing_value") is None
        assert project_worker._extract_property_value(entity_data, "non_property") is None
        assert project_worker._extract_property_value(entity_data, "nonexistent") is None
    
    @pytest.mark.asyncio
    async def test_get_product_by_project_code_direct(self, project_worker):
        """Test getting product by project code (direct SKU match)"""
        expected_product = {"id": 123, "name": "Direct Product", "default_code": "DIRECT-001"}
        project_worker.odoo_client.get_product_by_sku.return_value = expected_product
        
        result = await project_worker._get_product_by_project_code("DIRECT-001")
        
        assert result == expected_product
        project_worker.odoo_client.get_product_by_sku.assert_called_once_with("DIRECT-001")
    
    @pytest.mark.asyncio
    async def test_get_product_with_mapping_file(self, project_worker, tmp_path):
        """Test getting product using project mapping file"""
        # Create temporary mapping file
        mapping = {"PROJECT-001": "PRODUCT-SKU-001"}
        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text('{"PROJECT-001": "PRODUCT-SKU-001"}')
        
        expected_product = {"id": 456, "name": "Mapped Product"}
        
        # First call returns None (no direct match), second returns mapped product
        project_worker.odoo_client.get_product_by_sku.side_effect = [None, expected_product]
        
        with patch('hermes_odoo_adapter.settings.settings') as mock_settings:
            mock_settings.project_mapping_file = str(mapping_file)
            
            result = await project_worker._get_product_by_project_code("PROJECT-001")
        
        assert result == expected_product
        
        # Should try direct lookup first, then mapped lookup
        assert project_worker.odoo_client.get_product_by_sku.call_count == 2
        project_worker.odoo_client.get_product_by_sku.assert_any_call("PROJECT-001")
        project_worker.odoo_client.get_product_by_sku.assert_any_call("PRODUCT-SKU-001")
    
    @pytest.mark.asyncio
    async def test_load_project_mapping_file_not_found(self, project_worker):
        """Test loading non-existent project mapping file"""
        with patch('hermes_odoo_adapter.settings.settings') as mock_settings:
            mock_settings.project_mapping_file = "/nonexistent/path/mapping.json"
            
            result = await project_worker._load_project_mapping()
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_load_project_mapping_no_file_configured(self, project_worker):
        """Test loading project mapping when no file is configured"""
        with patch('hermes_odoo_adapter.settings.settings') as mock_settings:
            mock_settings.project_mapping_file = None
            
            result = await project_worker._load_project_mapping()
        
        assert result is None


class TestInventorySyncWorker:
    """Test inventory sync worker functionality"""
    
    @pytest.fixture
    def inventory_worker(self, mock_odoo_client, mock_orion_client):
        """Create inventory sync worker with mocked dependencies"""
        worker = InventorySyncWorker(mock_odoo_client, mock_orion_client)
        worker.sync_interval = 0.01  # Very short for testing
        return worker
    
    def test_worker_initialization(self, inventory_worker, mock_odoo_client, mock_orion_client):
        """Test worker initialization"""
        assert inventory_worker.odoo_client == mock_odoo_client
        assert inventory_worker.orion_client == mock_orion_client
        assert inventory_worker.running is False
        assert inventory_worker.last_sync_time is None
    
    @pytest.mark.asyncio
    async def test_sync_inventory_empty_result(self, inventory_worker):
        """Test inventory sync with no products"""
        inventory_worker.odoo_client.search_read.return_value = []
        inventory_worker.odoo_client.read.return_value = []
        
        result = await inventory_worker.sync_inventory()
        
        assert result["status"] == "completed"
        assert result["products"] == 0
    
    @pytest.mark.asyncio
    async def test_sync_inventory_with_products(self, inventory_worker):
        """Test inventory sync with products"""
        mock_stock_quants = [
            {
                "product_id": [101, "Product A"],
                "location_id": [8, "Stock"],
                "quantity": 10.0,
                "reserved_quantity": 2.0
            }
        ]
        
        mock_products = [
            {
                "id": 101,
                "name": "Product A", 
                "default_code": "PROD-A-001",
                "active": True
            }
        ]
        
        inventory_worker.odoo_client.search_read.return_value = mock_stock_quants
        inventory_worker.odoo_client.read.return_value = mock_products
        inventory_worker.orion_client.upsert_entity.return_value = {"status": "success"}
        
        result = await inventory_worker.sync_inventory()
        
        assert result["status"] == "completed"
        assert result["processed"] == 1
        assert result["updated"] == 1
        assert result["errors"] == 0
    
    def test_get_sync_status(self, inventory_worker):
        """Test sync status reporting"""
        status = inventory_worker.get_sync_status()
        
        assert "running" in status
        assert "last_sync_time" in status
        assert "sync_interval_seconds" in status
        assert "batch_size" in status
        assert "next_sync_due" in status
        
        assert status["running"] is False
        assert status["last_sync_time"] is None
    
    def test_get_sync_status_after_sync(self, inventory_worker):
        """Test sync status after a sync has been performed"""
        # Simulate a sync has occurred
        inventory_worker.last_sync_time = datetime.utcnow()
        
        status = inventory_worker.get_sync_status()
        
        assert status["last_sync_time"] is not None
        assert status["next_sync_due"] is not None
    
    @pytest.mark.asyncio
    async def test_handle_stock_change_webhook(self, inventory_worker):
        """Test handling stock change webhook"""
        webhook_payload = {
            "product_id": 123,
            "sku": "WEBHOOK-TEST"
        }
        
        mock_stock_data = [
            {
                "product_id": [123, "Webhook Product"],
                "quantity": 15.0,
                "reserved_quantity": 3.0
            }
        ]
        
        inventory_worker.odoo_client.get_stock_for_products.return_value = mock_stock_data
        inventory_worker.orion_client.upsert_entity.return_value = {"status": "success"}
        
        await inventory_worker.handle_stock_change(webhook_payload)
        
        inventory_worker.odoo_client.get_stock_for_products.assert_called_once_with([123])
        inventory_worker.orion_client.upsert_entity.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_stock_change_invalid_payload(self, inventory_worker):
        """Test handling invalid stock change webhook payload"""
        # Missing required fields
        invalid_payloads = [
            {"product_id": 123},  # Missing SKU
            {"sku": "TEST"},      # Missing product_id
            {}                    # Missing both
        ]
        
        for payload in invalid_payloads:
            await inventory_worker.handle_stock_change(payload)
            
            # Should not make any Odoo/Orion calls
            inventory_worker.odoo_client.get_stock_for_products.assert_not_called()
            inventory_worker.orion_client.upsert_entity.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_sync_product_inventory_success(self, inventory_worker):
        """Test syncing specific product inventory"""
        mock_product = {"id": 123, "name": "Test Product"}
        mock_stock_data = [
            {
                "product_id": [123, "Test Product"],
                "quantity": 20.0,
                "reserved_quantity": 5.0
            }
        ]
        
        inventory_worker.odoo_client.get_product_by_sku.return_value = mock_product
        inventory_worker.odoo_client.get_stock_for_products.return_value = mock_stock_data
        inventory_worker.orion_client.upsert_entity.return_value = {"status": "success"}
        
        result = await inventory_worker.sync_product_inventory("TEST-SKU")
        
        assert result is not None
        assert result["sku"] == "TEST-SKU"
        assert result["total_quantity"] == 20.0
        assert result["reserved_quantity"] == 5.0
        assert result["available_quantity"] == 15.0
        assert result["updated"] is True
    
    @pytest.mark.asyncio
    async def test_sync_product_inventory_not_found(self, inventory_worker):
        """Test syncing non-existent product inventory"""
        inventory_worker.odoo_client.get_product_by_sku.return_value = None
        
        result = await inventory_worker.sync_product_inventory("NONEXISTENT")
        
        assert result is None
        inventory_worker.odoo_client.get_product_by_sku.assert_called_once_with("NONEXISTENT")
        inventory_worker.orion_client.upsert_entity.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_all_products_with_stock_filtering(self, inventory_worker):
        """Test product filtering in stock retrieval"""
        # Mix of active/inactive products with/without SKU
        mock_stock_quants = [
            {"product_id": [101, "Active with SKU"], "quantity": 10.0, "reserved_quantity": 0.0},
            {"product_id": [102, "Inactive with SKU"], "quantity": 5.0, "reserved_quantity": 0.0},
            {"product_id": [103, "Active without SKU"], "quantity": 8.0, "reserved_quantity": 0.0}
        ]
        
        mock_products = [
            {"id": 101, "name": "Active with SKU", "default_code": "ACTIVE-001", "active": True},
            {"id": 102, "name": "Inactive with SKU", "default_code": "INACTIVE-001", "active": False},
            {"id": 103, "name": "Active without SKU", "default_code": False, "active": True}  # No SKU
        ]
        
        inventory_worker.odoo_client.search_read.return_value = mock_stock_quants
        inventory_worker.odoo_client.read.return_value = mock_products
        
        result = await inventory_worker._get_all_products_with_stock()
        
        # Should only include active product with SKU
        assert len(result) == 1
        assert result[0]["sku"] == "ACTIVE-001"
        assert result[0]["total_quantity"] == 10.0
    
    @pytest.mark.asyncio
    async def test_process_inventory_batch_mixed_results(self, inventory_worker):
        """Test processing inventory batch with mixed success/failure"""
        products = [
            {"sku": "SUCCESS-001", "available_quantity": 10.0, "reserved_quantity": 0.0},
            {"sku": "FAILURE-001", "available_quantity": 5.0, "reserved_quantity": 0.0}
        ]
        
        def mock_upsert_side_effect(entity):
            if entity.sku.value == "FAILURE-001":
                raise Exception("Orion error")
            return {"status": "success"}
        
        inventory_worker.orion_client.upsert_entity.side_effect = mock_upsert_side_effect
        
        result = await inventory_worker._process_inventory_batch(products)
        
        assert result["processed"] == 2
        assert result["updated"] == 1
        assert result["errors"] == 1
    
    @pytest.mark.asyncio
    async def test_worker_start_stop_lifecycle(self, inventory_worker):
        """Test worker start/stop lifecycle"""
        import asyncio
        
        # Mock successful sync to avoid errors
        inventory_worker.odoo_client.search_read.return_value = []
        inventory_worker.odoo_client.read.return_value = []
        
        # Start worker in background
        worker_task = asyncio.create_task(inventory_worker.start())
        
        # Give it time to start
        await asyncio.sleep(0.005)
        
        assert inventory_worker.running is True
        
        # Stop worker
        await inventory_worker.stop()
        
        # Clean up
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        
        assert inventory_worker.running is False