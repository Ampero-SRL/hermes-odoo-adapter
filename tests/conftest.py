"""
Test configuration and fixtures for HERMES Odoo Adapter
"""
import asyncio
import json
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator, Dict, Any
from unittest.mock import AsyncMock, MagicMock

from httpx import AsyncClient
from fastapi.testclient import TestClient

from hermes_odoo_adapter.main import app
from hermes_odoo_adapter.settings import settings
from hermes_odoo_adapter.odoo_client import OdooClient
from hermes_odoo_adapter.orion_client import OrionClient
from hermes_odoo_adapter.workers.project_sync import ProjectSyncWorker
from hermes_odoo_adapter.workers.inventory_sync import InventorySyncWorker


# Test Settings Override
@pytest.fixture(scope="session", autouse=True)
def test_settings():
    """Override settings for testing"""
    settings.testing = True
    settings.log_level = "DEBUG"
    settings.odoo_url = "http://localhost:8069/jsonrpc"
    settings.orion_url = "http://localhost:1026"
    settings.inventory_sync_enabled = False  # Disable background sync during tests
    return settings


# Event loop fixtures
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# HTTP Client Fixtures
@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Synchronous test client"""
    with TestClient(app) as client:
        yield client


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Asynchronous test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


# Mock External Services
@pytest.fixture
def mock_odoo_client():
    """Mock Odoo client"""
    client = AsyncMock(spec=OdooClient)
    
    # Mock authentication
    client.connect = AsyncMock()
    client.close = AsyncMock()
    client.health_check = AsyncMock(return_value=True)
    
    # Mock common operations
    client.get_product_by_sku = AsyncMock()
    client.get_bom_for_product = AsyncMock()
    client.get_bom_lines = AsyncMock()
    client.get_stock_for_products = AsyncMock()
    client.search_read = AsyncMock()
    client.read = AsyncMock()
    client.call = AsyncMock()
    
    return client


@pytest.fixture
def mock_orion_client():
    """Mock Orion-LD client"""
    client = AsyncMock(spec=OrionClient)
    
    # Mock connection
    client.connect = AsyncMock()
    client.close = AsyncMock()
    client.health_check = AsyncMock(return_value=True)
    
    # Mock NGSI-LD operations
    client.create_entity = AsyncMock()
    client.get_entity = AsyncMock()
    client.update_entity = AsyncMock()
    client.upsert_entity = AsyncMock()
    client.delete_entity = AsyncMock()
    client.query_entities = AsyncMock()
    
    # Mock subscriptions
    client.create_subscription = AsyncMock()
    client.get_subscription = AsyncMock()
    client.ensure_subscription_exists = AsyncMock(return_value=True)
    
    return client


@pytest.fixture
def mock_project_worker(mock_odoo_client, mock_orion_client):
    """Mock project sync worker"""
    worker = AsyncMock(spec=ProjectSyncWorker)
    worker.odoo_client = mock_odoo_client
    worker.orion_client = mock_orion_client
    worker.setup_subscription = AsyncMock(return_value=True)
    worker.handle_project_notification = AsyncMock()
    return worker


@pytest.fixture
def mock_inventory_worker(mock_odoo_client, mock_orion_client):
    """Mock inventory sync worker"""
    worker = AsyncMock(spec=InventorySyncWorker)
    worker.odoo_client = mock_odoo_client
    worker.orion_client = mock_orion_client
    worker.start = AsyncMock()
    worker.stop = AsyncMock()
    worker.sync_inventory = AsyncMock()
    worker.handle_stock_change = AsyncMock()
    worker.sync_product_inventory = AsyncMock()
    worker.get_sync_status = MagicMock(return_value={
        "running": False,
        "last_sync_time": None,
        "sync_interval_seconds": 600,
        "batch_size": 100
    })
    return worker


# Test Data Fixtures
@pytest.fixture
def sample_product():
    """Sample product data"""
    return {
        "id": 123,
        "name": "Test Product",
        "default_code": "TEST-001",
        "active": True,
        "uom_id": [1, "Units"]
    }


@pytest.fixture
def sample_bom():
    """Sample BOM data"""
    return {
        "id": 456,
        "product_id": [123, "Test Product"],
        "product_tmpl_id": [89, "Test Product Template"],
        "product_qty": 1.0,
        "bom_line_ids": [789, 790]
    }


@pytest.fixture
def sample_bom_lines():
    """Sample BOM lines data"""
    return [
        {
            "id": 789,
            "bom_id": [456, "Test BOM"],
            "product_id": [101, "Component A"],
            "product_qty": 2.0,
            "product_uom_id": [1, "Units"]
        },
        {
            "id": 790,
            "bom_id": [456, "Test BOM"],
            "product_id": [102, "Component B"],
            "product_qty": 1.0,
            "product_uom_id": [1, "Units"]
        }
    ]


@pytest.fixture
def sample_stock_data():
    """Sample stock data"""
    return [
        {
            "id": 1001,
            "product_id": [101, "Component A"],
            "location_id": [8, "WH/Stock"],
            "quantity": 10.0,
            "reserved_quantity": 2.0
        },
        {
            "id": 1002,
            "product_id": [102, "Component B"],
            "location_id": [8, "WH/Stock"], 
            "quantity": 5.0,
            "reserved_quantity": 0.0
        }
    ]


@pytest.fixture
def sample_project_notification():
    """Sample Orion-LD project notification"""
    return {
        "subscriptionId": "hermes-project-subscription",
        "data": [{
            "id": "urn:ngsi-ld:Project:test-project-001",
            "type": "Project",
            "code": {
                "type": "Property",
                "value": "TEST-PROJECT-001"
            },
            "station": {
                "type": "Property",
                "value": "STATION-A"
            },
            "status": {
                "type": "Property",
                "value": "requested"
            },
            "@context": "https://fiware.github.io/NGSI-LD_Tutorials/datamodels/ngsi-context.jsonld"
        }]
    }


@pytest.fixture
def sample_reservation():
    """Sample reservation entity"""
    return {
        "id": "urn:ngsi-ld:Reservation:test-project-001",
        "type": "Reservation",
        "project_ref": {
            "type": "Relationship",
            "object": "urn:ngsi-ld:Project:test-project-001"
        },
        "lines": {
            "type": "Property",
            "value": [
                {"sku": "COMP-A", "qty": 2.0},
                {"sku": "COMP-B", "qty": 1.0}
            ]
        },
        "dateCreated": {
            "type": "Property",
            "value": {"@type": "DateTime", "@value": "2023-01-01T00:00:00Z"}
        },
        "@context": "https://fiware.github.io/NGSI-LD_Tutorials/datamodels/ngsi-context.jsonld"
    }


@pytest.fixture
def sample_shortage():
    """Sample shortage entity"""
    return {
        "id": "urn:ngsi-ld:Shortage:test-project-002",
        "type": "Shortage",
        "project_ref": {
            "type": "Relationship", 
            "object": "urn:ngsi-ld:Project:test-project-002"
        },
        "lines": {
            "type": "Property",
            "value": [
                {
                    "sku": "COMP-C",
                    "missing_qty": 3.0,
                    "required_qty": 5.0,
                    "available_qty": 2.0
                }
            ]
        },
        "dateCreated": {
            "type": "Property",
            "value": {"@type": "DateTime", "@value": "2023-01-01T00:00:00Z"}
        },
        "@context": "https://fiware.github.io/NGSI-LD_Tutorials/datamodels/ngsi-context.jsonld"
    }


# Mock Application State
@pytest.fixture
async def app_with_mocks(mock_odoo_client, mock_orion_client, mock_project_worker, mock_inventory_worker):
    """Application with mocked dependencies"""
    # Patch global instances
    import hermes_odoo_adapter.main as main_module
    
    original_odoo = main_module.odoo_client
    original_orion = main_module.orion_client
    original_project = main_module.project_worker
    original_inventory = main_module.inventory_worker
    
    main_module.odoo_client = mock_odoo_client
    main_module.orion_client = mock_orion_client
    main_module.project_worker = mock_project_worker
    main_module.inventory_worker = mock_inventory_worker
    
    try:
        yield app
    finally:
        # Restore originals
        main_module.odoo_client = original_odoo
        main_module.orion_client = original_orion
        main_module.project_worker = original_project
        main_module.inventory_worker = original_inventory


# Database/State Management
@pytest.fixture
def temp_project_mapping_file(tmp_path):
    """Create temporary project mapping file"""
    mapping = {
        "PROJECT-001": "PRODUCT-001",
        "PROJECT-002": "PRODUCT-002",
        "TEST-PROJECT-001": "TEST-001"
    }
    
    mapping_file = tmp_path / "test_project_mapping.json"
    mapping_file.write_text(json.dumps(mapping, indent=2))
    
    return str(mapping_file)


# Utility Functions
def assert_ngsi_ld_entity(entity: Dict[str, Any], expected_type: str, expected_id: str = None):
    """Assert that a dictionary is a valid NGSI-LD entity"""
    assert "type" in entity, "Entity must have a type"
    assert entity["type"] == expected_type, f"Entity type should be {expected_type}"
    
    if expected_id:
        assert "id" in entity, "Entity must have an id"
        assert entity["id"] == expected_id, f"Entity id should be {expected_id}"
    
    # Check for @context
    assert "@context" in entity or "Link" in entity, "Entity must have @context or Link header"


def create_mock_response(data: Any, status_code: int = 200):
    """Create a mock HTTP response"""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = data
    response.text = json.dumps(data) if isinstance(data, (dict, list)) else str(data)
    return response