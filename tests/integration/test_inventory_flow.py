"""
Integration tests for the inventory synchronization flow
"""
import pytest
from unittest.mock import AsyncMock
from datetime import datetime, timedelta

from hermes_odoo_adapter.workers.inventory_sync import InventorySyncWorker


@pytest.mark.integration
class TestInventorySyncIntegration:
    """Test complete inventory synchronization flow"""
    
    @pytest.mark.asyncio
    async def test_full_inventory_sync_flow(self, mock_odoo_client, mock_orion_client):
        """Test complete inventory synchronization from Odoo to Orion-LD"""
        # Setup mock data for inventory sync
        mock_stock_quants = [
            {
                "product_id": [101, "LED Strip"],
                "location_id": [8, "WH/Stock"],
                "quantity": 25.0,
                "reserved_quantity": 5.0
            },
            {
                "product_id": [102, "Mounting Bracket"],
                "location_id": [8, "WH/Stock"],
                "quantity": 50.0,
                "reserved_quantity": 10.0
            },
            {
                "product_id": [103, "Controller Board"],
                "location_id": [8, "WH/Stock"],
                "quantity": 15.0,
                "reserved_quantity": 0.0
            }
        ]
        
        mock_products = [
            {
                "id": 101,
                "name": "LED Strip",
                "default_code": "LED-STRIP-001",
                "active": True
            },
            {
                "id": 102,
                "name": "Mounting Bracket",
                "default_code": "BRACKET-002",
                "active": True
            },
            {
                "id": 103,
                "name": "Controller Board",
                "default_code": "CTRL-BOARD-003",
                "active": True
            }
        ]
        
        # Mock Odoo responses
        mock_odoo_client.search_read.return_value = mock_stock_quants
        mock_odoo_client.read.return_value = mock_products
        
        # Mock Orion responses
        mock_orion_client.upsert_entity.return_value = {"status": "success"}
        
        # Create worker
        worker = InventorySyncWorker(mock_odoo_client, mock_orion_client)
        
        # Run sync
        result = await worker.sync_inventory()
        
        # Verify results
        assert result["status"] == "completed"
        assert result["processed"] == 3
        assert result["updated"] == 3
        assert result["errors"] == 0
        
        # Verify Odoo calls
        mock_odoo_client.search_read.assert_called_once()
        call_args = mock_odoo_client.search_read.call_args
        assert call_args[0][0] == "stock.quant"  # model
        
        # Verify domain includes only internal locations with positive quantity
        domain = call_args[0][1]
        assert ("location_id.usage", "=", "internal") in domain
        assert ("quantity", ">", 0) in domain
        
        # Verify product details were fetched
        mock_odoo_client.read.assert_called_once_with(
            "product.product",
            [101, 102, 103],
            ["id", "name", "default_code", "active"]
        )
        
        # Verify Orion entities were created/updated
        assert mock_orion_client.upsert_entity.call_count == 3
        
        # Check specific inventory items
        upsert_calls = mock_orion_client.upsert_entity.call_args_list
        
        # LED Strip inventory item
        led_entity = next(call[0][0] for call in upsert_calls 
                         if call[0][0].sku.value == "LED-STRIP-001")
        assert led_entity.type == "InventoryItem"
        assert led_entity.available_quantity.value == 20.0  # 25 - 5 reserved
        assert led_entity.reserved_quantity.value == 5.0
        assert led_entity.total_quantity.value == 25.0
        
        # Mounting Bracket inventory item
        bracket_entity = next(call[0][0] for call in upsert_calls 
                             if call[0][0].sku.value == "BRACKET-002")
        assert bracket_entity.available_quantity.value == 40.0  # 50 - 10 reserved
        assert bracket_entity.reserved_quantity.value == 10.0
        assert bracket_entity.total_quantity.value == 50.0
        
        # Controller Board inventory item
        controller_entity = next(call[0][0] for call in upsert_calls 
                                if call[0][0].sku.value == "CTRL-BOARD-003")
        assert controller_entity.available_quantity.value == 15.0  # No reservations
        assert controller_entity.reserved_quantity.value == 0.0
        assert controller_entity.total_quantity.value == 15.0
    
    @pytest.mark.asyncio
    async def test_batch_processing(self, mock_odoo_client, mock_orion_client):
        """Test inventory sync with batch processing"""
        # Create enough products to trigger batching (batch size is 100 by default)
        mock_stock_quants = []
        mock_products = []
        
        for i in range(150):  # More than batch size
            mock_stock_quants.append({
                "product_id": [i + 1, f"Product {i + 1}"],
                "location_id": [8, "WH/Stock"],
                "quantity": 10.0,
                "reserved_quantity": 0.0
            })
            
            mock_products.append({
                "id": i + 1,
                "name": f"Product {i + 1}",
                "default_code": f"PROD-{i + 1:03d}",
                "active": True
            })
        
        mock_odoo_client.search_read.return_value = mock_stock_quants
        mock_odoo_client.read.return_value = mock_products
        mock_orion_client.upsert_entity.return_value = {"status": "success"}
        
        # Create worker with small batch size for testing
        worker = InventorySyncWorker(mock_odoo_client, mock_orion_client)
        worker.batch_size = 50  # Override for testing
        
        result = await worker.sync_inventory()
        
        # Should process all 150 products in 3 batches
        assert result["processed"] == 150
        assert result["updated"] == 150
        assert mock_orion_client.upsert_entity.call_count == 150
    
    @pytest.mark.asyncio
    async def test_sync_with_inactive_products(self, mock_odoo_client, mock_orion_client):
        """Test sync filtering out inactive products"""
        mock_stock_quants = [
            {
                "product_id": [101, "Active Product"],
                "location_id": [8, "WH/Stock"],
                "quantity": 10.0,
                "reserved_quantity": 0.0
            },
            {
                "product_id": [102, "Inactive Product"],
                "location_id": [8, "WH/Stock"],
                "quantity": 5.0,
                "reserved_quantity": 0.0
            }
        ]
        
        mock_products = [
            {
                "id": 101,
                "name": "Active Product",
                "default_code": "ACTIVE-001",
                "active": True
            },
            {
                "id": 102,
                "name": "Inactive Product",
                "default_code": "INACTIVE-001",
                "active": False  # Inactive product
            }
        ]
        
        mock_odoo_client.search_read.return_value = mock_stock_quants
        mock_odoo_client.read.return_value = mock_products
        mock_orion_client.upsert_entity.return_value = {"status": "success"}
        
        worker = InventorySyncWorker(mock_odoo_client, mock_orion_client)
        result = await worker.sync_inventory()
        
        # Should only process active product
        assert result["processed"] == 1
        assert result["updated"] == 1
        assert mock_orion_client.upsert_entity.call_count == 1
        
        # Verify only active product was synced
        upserted_entity = mock_orion_client.upsert_entity.call_args[0][0]
        assert upserted_entity.sku.value == "ACTIVE-001"
    
    @pytest.mark.asyncio
    async def test_sync_with_products_without_sku(self, mock_odoo_client, mock_orion_client):
        """Test sync filtering out products without SKU"""
        mock_stock_quants = [
            {
                "product_id": [101, "Product with SKU"],
                "location_id": [8, "WH/Stock"],
                "quantity": 10.0,
                "reserved_quantity": 0.0
            },
            {
                "product_id": [102, "Product without SKU"],
                "location_id": [8, "WH/Stock"],
                "quantity": 5.0,
                "reserved_quantity": 0.0
            }
        ]
        
        mock_products = [
            {
                "id": 101,
                "name": "Product with SKU",
                "default_code": "WITH-SKU-001",
                "active": True
            },
            {
                "id": 102,
                "name": "Product without SKU",
                "default_code": False,  # No SKU
                "active": True
            }
        ]
        
        mock_odoo_client.search_read.return_value = mock_stock_quants
        mock_odoo_client.read.return_value = mock_products
        mock_orion_client.upsert_entity.return_value = {"status": "success"}
        
        worker = InventorySyncWorker(mock_odoo_client, mock_orion_client)
        result = await worker.sync_inventory()
        
        # Should only process product with SKU
        assert result["processed"] == 1
        assert result["updated"] == 1
        assert mock_orion_client.upsert_entity.call_count == 1
    
    @pytest.mark.asyncio
    async def test_stock_aggregation_across_locations(self, mock_odoo_client, mock_orion_client):
        """Test aggregating stock quantities across multiple locations"""
        # Same product in multiple locations
        mock_stock_quants = [
            {
                "product_id": [101, "Multi-location Product"],
                "location_id": [8, "WH/Stock"],
                "quantity": 10.0,
                "reserved_quantity": 2.0
            },
            {
                "product_id": [101, "Multi-location Product"],
                "location_id": [9, "WH/Stock/Shelf A"],
                "quantity": 15.0,
                "reserved_quantity": 3.0
            },
            {
                "product_id": [101, "Multi-location Product"],
                "location_id": [10, "WH/Stock/Shelf B"],
                "quantity": 8.0,
                "reserved_quantity": 0.0
            }
        ]
        
        mock_products = [
            {
                "id": 101,
                "name": "Multi-location Product",
                "default_code": "MULTI-LOC-001",
                "active": True
            }
        ]
        
        mock_odoo_client.search_read.return_value = mock_stock_quants
        mock_odoo_client.read.return_value = mock_products
        mock_orion_client.upsert_entity.return_value = {"status": "success"}
        
        worker = InventorySyncWorker(mock_odoo_client, mock_orion_client)
        result = await worker.sync_inventory()
        
        # Should process 1 product (aggregated)
        assert result["processed"] == 1
        assert result["updated"] == 1
        assert mock_orion_client.upsert_entity.call_count == 1
        
        # Check aggregated quantities
        inventory_entity = mock_orion_client.upsert_entity.call_args[0][0]
        assert inventory_entity.total_quantity.value == 33.0  # 10 + 15 + 8
        assert inventory_entity.reserved_quantity.value == 5.0  # 2 + 3 + 0
        assert inventory_entity.available_quantity.value == 28.0  # 33 - 5
    
    @pytest.mark.asyncio
    async def test_sync_error_handling(self, mock_odoo_client, mock_orion_client):
        """Test error handling during inventory sync"""
        mock_stock_quants = [
            {
                "product_id": [101, "Good Product"],
                "location_id": [8, "WH/Stock"],
                "quantity": 10.0,
                "reserved_quantity": 0.0
            },
            {
                "product_id": [102, "Problem Product"],
                "location_id": [8, "WH/Stock"],
                "quantity": 5.0,
                "reserved_quantity": 0.0
            }
        ]
        
        mock_products = [
            {
                "id": 101,
                "name": "Good Product",
                "default_code": "GOOD-001",
                "active": True
            },
            {
                "id": 102,
                "name": "Problem Product",
                "default_code": "PROBLEM-001",
                "active": True
            }
        ]
        
        mock_odoo_client.search_read.return_value = mock_stock_quants
        mock_odoo_client.read.return_value = mock_products
        
        # Make Orion upsert fail for second product
        def mock_upsert_side_effect(entity):
            if entity.sku.value == "PROBLEM-001":
                raise Exception("Orion connection error")
            return {"status": "success"}
        
        mock_orion_client.upsert_entity.side_effect = mock_upsert_side_effect
        
        worker = InventorySyncWorker(mock_odoo_client, mock_orion_client)
        result = await worker.sync_inventory()
        
        # Should process both but only update one successfully
        assert result["processed"] == 2
        assert result["updated"] == 1
        assert result["errors"] == 1
        assert mock_orion_client.upsert_entity.call_count == 2
    
    @pytest.mark.asyncio
    async def test_single_product_sync(self, mock_odoo_client, mock_orion_client):
        """Test syncing inventory for a single product by SKU"""
        mock_product = {
            "id": 123,
            "name": "Test Product",
            "default_code": "TEST-001"
        }
        
        mock_stock_data = [
            {
                "product_id": [123, "Test Product"],
                "location_id": [8, "WH/Stock"],
                "quantity": 20.0,
                "reserved_quantity": 5.0
            }
        ]
        
        mock_odoo_client.get_product_by_sku.return_value = mock_product
        mock_odoo_client.get_stock_for_products.return_value = mock_stock_data
        mock_orion_client.upsert_entity.return_value = {"status": "success"}
        
        worker = InventorySyncWorker(mock_odoo_client, mock_orion_client)
        result = await worker.sync_product_inventory("TEST-001")
        
        assert result is not None
        assert result["sku"] == "TEST-001"
        assert result["total_quantity"] == 20.0
        assert result["reserved_quantity"] == 5.0
        assert result["available_quantity"] == 15.0
        assert result["updated"] is True
        
        # Verify calls
        mock_odoo_client.get_product_by_sku.assert_called_once_with("TEST-001")
        mock_odoo_client.get_stock_for_products.assert_called_once_with([123])
        mock_orion_client.upsert_entity.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_single_product_sync_not_found(self, mock_odoo_client, mock_orion_client):
        """Test syncing inventory for non-existent product"""
        mock_odoo_client.get_product_by_sku.return_value = None
        
        worker = InventorySyncWorker(mock_odoo_client, mock_orion_client)
        result = await worker.sync_product_inventory("NONEXISTENT")
        
        assert result is None
        mock_odoo_client.get_product_by_sku.assert_called_once_with("NONEXISTENT")
        mock_orion_client.upsert_entity.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_stock_change_webhook_handling(self, mock_odoo_client, mock_orion_client):
        """Test handling real-time stock change webhooks"""
        webhook_payload = {
            "product_id": 123,
            "sku": "WEBHOOK-001",
            "change_type": "quantity_update"
        }
        
        mock_stock_data = [
            {
                "product_id": [123, "Webhook Product"],
                "location_id": [8, "WH/Stock"],
                "quantity": 30.0,
                "reserved_quantity": 7.0
            }
        ]
        
        mock_odoo_client.get_stock_for_products.return_value = mock_stock_data
        mock_orion_client.upsert_entity.return_value = {"status": "success"}
        
        worker = InventorySyncWorker(mock_odoo_client, mock_orion_client)
        await worker.handle_stock_change(webhook_payload)
        
        # Verify stock was fetched and updated
        mock_odoo_client.get_stock_for_products.assert_called_once_with([123])
        mock_orion_client.upsert_entity.assert_called_once()
        
        # Check the inventory entity
        inventory_entity = mock_orion_client.upsert_entity.call_args[0][0]
        assert inventory_entity.sku.value == "WEBHOOK-001"
        assert inventory_entity.total_quantity.value == 30.0
        assert inventory_entity.reserved_quantity.value == 7.0
        assert inventory_entity.available_quantity.value == 23.0
    
    def test_sync_status_reporting(self, mock_odoo_client, mock_orion_client):
        """Test sync status reporting"""
        worker = InventorySyncWorker(mock_odoo_client, mock_orion_client)
        
        # Test initial status
        status = worker.get_sync_status()
        assert status["running"] is False
        assert status["last_sync_time"] is None
        assert status["sync_interval_seconds"] > 0
        assert status["batch_size"] > 0
        assert status["next_sync_due"] is None
    
    @pytest.mark.asyncio
    async def test_worker_lifecycle(self, mock_odoo_client, mock_orion_client):
        """Test inventory worker start/stop lifecycle"""
        # Mock successful sync for the lifecycle test
        mock_odoo_client.search_read.return_value = []
        mock_odoo_client.read.return_value = []
        
        worker = InventorySyncWorker(mock_odoo_client, mock_orion_client)
        worker.sync_interval = 0.1  # Very short interval for testing
        
        # Start worker
        import asyncio
        worker_task = asyncio.create_task(worker.start())
        
        # Let it run briefly
        await asyncio.sleep(0.05)
        
        # Check it's running
        assert worker.running is True
        
        # Stop worker
        await worker.stop()
        
        # Wait for cleanup
        await asyncio.sleep(0.1)
        
        # Clean up task
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        
        assert worker.running is False