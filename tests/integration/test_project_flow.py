"""
Integration tests for the complete project flow
"""
import pytest
import asyncio
from typing import Dict, Any

from hermes_odoo_adapter.workers.project_sync import ProjectSyncWorker
from hermes_odoo_adapter.models.ngsi_models import Reservation, Shortage


@pytest.mark.integration
class TestProjectFlowIntegration:
    """Test complete project processing flow"""
    
    @pytest.mark.asyncio
    async def test_happy_path_reservation_flow(self, mock_odoo_client, mock_orion_client):
        """Test successful project processing that creates a reservation"""
        # Setup mock data for happy path
        mock_odoo_client.get_product_by_sku.return_value = {
            "id": 123,
            "name": "Control Panel A1",
            "default_code": "CTRL-PANEL-A1"
        }
        
        mock_odoo_client.get_bom_for_product.return_value = {
            "id": 456,
            "product_id": [123, "Control Panel A1"],
            "product_qty": 1.0,
            "bom_line_ids": [789, 790]
        }
        
        mock_odoo_client.get_bom_lines.return_value = [
            {
                "id": 789,
                "product_id": [101, "LED Strip"],
                "product_qty": 2.0
            },
            {
                "id": 790,
                "product_id": [102, "Mounting Bracket"],
                "product_qty": 4.0
            }
        ]
        
        # Sufficient stock for both components
        mock_odoo_client.get_stock_for_products.return_value = [
            {
                "product_id": [101, "LED Strip"],
                "quantity": 10.0,
                "reserved_quantity": 0.0
            },
            {
                "product_id": [102, "Mounting Bracket"],
                "quantity": 20.0,
                "reserved_quantity": 5.0
            }
        ]
        
        # Mock product details for SKU lookup
        mock_odoo_client.read.return_value = [
            {"id": 101, "default_code": "LED-001"},
            {"id": 102, "default_code": "BRACKET-001"}
        ]
        
        # Mock Orion responses
        mock_orion_client.upsert_entity.return_value = {"status": "success"}
        
        # Create worker and process project
        worker = ProjectSyncWorker(mock_odoo_client, mock_orion_client)
        
        project_notification = {
            "id": "urn:ngsi-ld:Project:test-project-123",
            "type": "Project",
            "code": {"type": "Property", "value": "CTRL-PANEL-A1"},
            "station": {"type": "Property", "value": "STATION-A"},
            "status": {"type": "Property", "value": "requested"}
        }
        
        await worker.handle_project_notification(project_notification)
        
        # Verify calls were made
        mock_odoo_client.get_product_by_sku.assert_called_once_with("CTRL-PANEL-A1")
        mock_odoo_client.get_bom_for_product.assert_called_once_with(123)
        mock_odoo_client.get_bom_lines.assert_called_once_with([789, 790])
        mock_odoo_client.get_stock_for_products.assert_called_once_with([101, 102])
        
        # Verify Orion entities were created
        assert mock_orion_client.upsert_entity.call_count == 3  # 2 inventory items + 1 reservation
        
        # Check that a reservation was created (not a shortage)
        reservation_calls = [
            call for call in mock_orion_client.upsert_entity.call_args_list
            if call[0][0].type == "Reservation"
        ]
        assert len(reservation_calls) == 1
        
        reservation_entity = reservation_calls[0][0][0]
        assert reservation_entity.project_ref.object == "urn:ngsi-ld:Project:test-project-123"
        assert len(reservation_entity.lines.value) == 2
    
    @pytest.mark.asyncio
    async def test_shortage_flow(self, mock_odoo_client, mock_orion_client):
        """Test project processing that creates a shortage due to insufficient stock"""
        # Setup mock data for shortage scenario
        mock_odoo_client.get_product_by_sku.return_value = {
            "id": 123,
            "name": "Control Panel A1", 
            "default_code": "CTRL-PANEL-A1"
        }
        
        mock_odoo_client.get_bom_for_product.return_value = {
            "id": 456,
            "product_id": [123, "Control Panel A1"],
            "product_qty": 1.0,
            "bom_line_ids": [789]
        }
        
        mock_odoo_client.get_bom_lines.return_value = [
            {
                "id": 789,
                "product_id": [101, "Rare Component"],
                "product_qty": 5.0
            }
        ]
        
        # Insufficient stock
        mock_odoo_client.get_stock_for_products.return_value = [
            {
                "product_id": [101, "Rare Component"],
                "quantity": 2.0,  # Only 2 available, need 5
                "reserved_quantity": 0.0
            }
        ]
        
        # Mock product details
        mock_odoo_client.read.return_value = [
            {"id": 101, "default_code": "RARE-001"}
        ]
        
        mock_orion_client.upsert_entity.return_value = {"status": "success"}
        
        # Create worker and process project
        worker = ProjectSyncWorker(mock_odoo_client, mock_orion_client)
        
        project_notification = {
            "id": "urn:ngsi-ld:Project:test-shortage-456",
            "type": "Project",
            "code": {"type": "Property", "value": "CTRL-PANEL-A1"},
            "status": {"type": "Property", "value": "requested"}
        }
        
        await worker.handle_project_notification(project_notification)
        
        # Verify shortage was created
        shortage_calls = [
            call for call in mock_orion_client.upsert_entity.call_args_list
            if call[0][0].type == "Shortage"
        ]
        assert len(shortage_calls) == 1
        
        shortage_entity = shortage_calls[0][0][0]
        assert shortage_entity.project_ref.object == "urn:ngsi-ld:Project:test-shortage-456"
        
        shortage_line = shortage_entity.lines.value[0]
        assert shortage_line["sku"] == "RARE-001"
        assert shortage_line["missing_qty"] == 3.0  # 5 required - 2 available
        assert shortage_line["required_qty"] == 5.0
        assert shortage_line["available_qty"] == 2.0
    
    @pytest.mark.asyncio
    async def test_product_not_found_flow(self, mock_odoo_client, mock_orion_client):
        """Test handling when project code doesn't match any product"""
        # Setup mock to return no product
        mock_odoo_client.get_product_by_sku.return_value = None
        
        worker = ProjectSyncWorker(mock_odoo_client, mock_orion_client)
        
        project_notification = {
            "id": "urn:ngsi-ld:Project:test-unknown-789",
            "type": "Project",
            "code": {"type": "Property", "value": "UNKNOWN-PRODUCT"},
            "status": {"type": "Property", "value": "requested"}
        }
        
        await worker.handle_project_notification(project_notification)
        
        # Verify product lookup was attempted
        mock_odoo_client.get_product_by_sku.assert_called_once_with("UNKNOWN-PRODUCT")
        
        # No further Odoo calls should have been made
        mock_odoo_client.get_bom_for_product.assert_not_called()
        
        # No Orion entities should be created
        mock_orion_client.upsert_entity.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_no_bom_found_flow(self, mock_odoo_client, mock_orion_client):
        """Test handling when product has no BOM"""
        mock_odoo_client.get_product_by_sku.return_value = {
            "id": 123,
            "name": "Simple Product",
            "default_code": "SIMPLE-001"
        }
        
        # No BOM found
        mock_odoo_client.get_bom_for_product.return_value = None
        
        worker = ProjectSyncWorker(mock_odoo_client, mock_orion_client)
        
        project_notification = {
            "id": "urn:ngsi-ld:Project:test-no-bom-999",
            "type": "Project",
            "code": {"type": "Property", "value": "SIMPLE-001"},
            "status": {"type": "Property", "value": "requested"}
        }
        
        await worker.handle_project_notification(project_notification)
        
        # Verify calls up to BOM lookup
        mock_odoo_client.get_product_by_sku.assert_called_once_with("SIMPLE-001")
        mock_odoo_client.get_bom_for_product.assert_called_once_with(123)
        
        # No further calls should be made
        mock_odoo_client.get_bom_lines.assert_not_called()
        mock_orion_client.upsert_entity.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_mixed_availability_flow(self, mock_odoo_client, mock_orion_client):
        """Test project with some components available and some short"""
        mock_odoo_client.get_product_by_sku.return_value = {
            "id": 123,
            "name": "Mixed Product",
            "default_code": "MIXED-001"
        }
        
        mock_odoo_client.get_bom_for_product.return_value = {
            "id": 456,
            "product_id": [123, "Mixed Product"],
            "product_qty": 1.0,
            "bom_line_ids": [789, 790]
        }
        
        mock_odoo_client.get_bom_lines.return_value = [
            {
                "id": 789,
                "product_id": [101, "Available Component"],
                "product_qty": 2.0
            },
            {
                "id": 790,
                "product_id": [102, "Short Component"],
                "product_qty": 3.0
            }
        ]
        
        # Mixed stock availability
        mock_odoo_client.get_stock_for_products.return_value = [
            {
                "product_id": [101, "Available Component"],
                "quantity": 10.0,  # Sufficient
                "reserved_quantity": 0.0
            },
            {
                "product_id": [102, "Short Component"],
                "quantity": 1.0,   # Insufficient (need 3, have 1)
                "reserved_quantity": 0.0
            }
        ]
        
        mock_odoo_client.read.return_value = [
            {"id": 101, "default_code": "AVAIL-001"},
            {"id": 102, "default_code": "SHORT-001"}
        ]
        
        mock_orion_client.upsert_entity.return_value = {"status": "success"}
        
        worker = ProjectSyncWorker(mock_odoo_client, mock_orion_client)
        
        project_notification = {
            "id": "urn:ngsi-ld:Project:test-mixed-111",
            "type": "Project", 
            "code": {"type": "Property", "value": "MIXED-001"},
            "status": {"type": "Property", "value": "requested"}
        }
        
        await worker.handle_project_notification(project_notification)
        
        # Should create shortage (because not all components are available)
        shortage_calls = [
            call for call in mock_orion_client.upsert_entity.call_args_list
            if call[0][0].type == "Shortage"
        ]
        assert len(shortage_calls) == 1
        
        shortage_entity = shortage_calls[0][0][0]
        
        # Should only include the short component in shortage lines
        assert len(shortage_entity.lines.value) == 1
        shortage_line = shortage_entity.lines.value[0]
        assert shortage_line["sku"] == "SHORT-001"
        assert shortage_line["missing_qty"] == 2.0  # 3 required - 1 available
    
    @pytest.mark.asyncio
    async def test_idempotency_handling(self, mock_odoo_client, mock_orion_client):
        """Test that duplicate notifications are handled idempotently"""
        from hermes_odoo_adapter.utils.idempotency import idempotency_helper
        
        # Setup normal successful case
        mock_odoo_client.get_product_by_sku.return_value = {
            "id": 123,
            "name": "Test Product",
            "default_code": "TEST-001"
        }
        
        mock_odoo_client.get_bom_for_product.return_value = {
            "id": 456,
            "product_id": [123, "Test Product"],
            "product_qty": 1.0,
            "bom_line_ids": [789]
        }
        
        mock_odoo_client.get_bom_lines.return_value = [
            {
                "id": 789,
                "product_id": [101, "Component"],
                "product_qty": 1.0
            }
        ]
        
        mock_odoo_client.get_stock_for_products.return_value = [
            {
                "product_id": [101, "Component"],
                "quantity": 5.0,
                "reserved_quantity": 0.0
            }
        ]
        
        mock_odoo_client.read.return_value = [
            {"id": 101, "default_code": "COMP-001"}
        ]
        
        mock_orion_client.upsert_entity.return_value = {"status": "success"}
        
        worker = ProjectSyncWorker(mock_odoo_client, mock_orion_client)
        
        project_notification = {
            "id": "urn:ngsi-ld:Project:test-idempotent-222",
            "type": "Project",
            "code": {"type": "Property", "value": "TEST-001"},
            "status": {"type": "Property", "value": "requested"}
        }
        
        # Process first time - should work normally
        await worker.handle_project_notification(project_notification)
        
        first_call_count = mock_odoo_client.get_product_by_sku.call_count
        
        # Process second time - should be skipped due to idempotency
        await worker.handle_project_notification(project_notification)
        
        # Verify no additional calls were made
        assert mock_odoo_client.get_product_by_sku.call_count == first_call_count
    
    @pytest.mark.asyncio
    async def test_subscription_setup(self, mock_odoo_client, mock_orion_client):
        """Test Orion subscription setup"""
        mock_orion_client.ensure_subscription_exists.return_value = True
        
        worker = ProjectSyncWorker(mock_odoo_client, mock_orion_client)
        result = await worker.setup_subscription()
        
        assert result is True
        mock_orion_client.ensure_subscription_exists.assert_called_once()
        
        # Verify subscription configuration
        call_args = mock_orion_client.ensure_subscription_exists.call_args
        subscription_id = call_args[0][0]
        subscription_config = call_args[0][1]
        
        assert subscription_id == "hermes-project-subscription"
        assert subscription_config["subject"]["entities"][0]["type"] == "Project"
        assert "status==requested" in subscription_config["subject"]["condition"]["expression"]["q"]