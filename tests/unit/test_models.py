"""
Tests for NGSI-LD models and data structures.

These match the current `hermes_odoo_adapter.models.ngsi_models` shapes:
- `InventoryItem` splits stock across `available` / `reserved` / `total`
  (each with `unitCode="Unit"`) — not the historical
  `available_quantity` / `reserved_quantity` / `total_quantity`.
- `Reservation` / `Shortage` use `projectRef` as the JSON-LD alias for
  the `project_ref` python attribute.
- `ShortageLine` carries `missing_qty` / `required_qty` / `available_qty`
  on the Python side; their JSON-LD aliases are `missingQty`,
  `requiredQty`, `availableQty`.
- Pydantic v2 serialisation uses `model_dump(by_alias=True)`; the
  legacy `dict(by_alias=True)` is deprecated and emits a warning.
"""
import pytest
from datetime import datetime

from hermes_odoo_adapter.models.ngsi_models import (
    NGSILDProperty,
    NGSILDRelationship,
    Project,
    Reservation,
    ReservationLine,
    Shortage,
    ShortageLine,
    InventoryItem,
)


class TestNGSILDProperties:
    """Test basic NGSI-LD property types"""

    def test_ngsi_ld_property_creation(self):
        prop = NGSILDProperty(value="test-value")
        assert prop.type == "Property"
        assert prop.value == "test-value"
        assert prop.observedAt is None
        assert prop.unitCode is None

    def test_ngsi_ld_property_with_metadata(self):
        observed_at = datetime.utcnow()
        prop = NGSILDProperty(value=42.5, observedAt=observed_at, unitCode="MTR")
        assert prop.type == "Property"
        assert prop.value == 42.5
        assert prop.observedAt == observed_at
        assert prop.unitCode == "MTR"

    def test_ngsi_ld_relationship_creation(self):
        rel = NGSILDRelationship(object="urn:ngsi-ld:Entity:123")
        assert rel.type == "Relationship"
        assert rel.object == "urn:ngsi-ld:Entity:123"


class TestProjectModel:
    """Test Project NGSI-LD entity"""

    def test_project_creation(self):
        project = Project.create("test-project", "TEST-001", "requested", "STATION-A")
        assert project.id == "urn:ngsi-ld:Project:test-project"
        assert project.type == "Project"
        assert project.code.value == "TEST-001"
        assert project.station.value == "STATION-A"
        assert project.status.value == "requested"

    def test_project_creation_without_station(self):
        project = Project.create("test-project", "TEST-001", "requested", None)
        assert project.id == "urn:ngsi-ld:Project:test-project"
        assert project.code.value == "TEST-001"
        assert project.station is None
        assert project.status.value == "requested"

    def test_project_serialization(self):
        project = Project.create("test-project", "TEST-001", "requested", "STATION-A")
        data = project.model_dump(by_alias=True)
        assert data["id"] == "urn:ngsi-ld:Project:test-project"
        assert data["type"] == "Project"
        assert data["code"]["type"] == "Property"
        assert data["code"]["value"] == "TEST-001"
        assert data["station"]["value"] == "STATION-A"
        assert data["status"]["value"] == "requested"
        assert "@context" in data


class TestReservationModel:
    """Test Reservation NGSI-LD entity"""

    def test_reservation_line_creation(self):
        line = ReservationLine(sku="TEST-001", qty=5.0)
        assert line.sku == "TEST-001"
        assert line.qty == 5.0
        assert line.unit == "Unit"  # default

    def test_reservation_creation(self):
        lines = [
            ReservationLine(sku="COMP-A", qty=2.0),
            ReservationLine(sku="COMP-B", qty=1.0),
        ]
        reservation = Reservation.create("test-project", lines)

        assert reservation.id == "urn:ngsi-ld:Reservation:test-project"
        assert reservation.type == "Reservation"
        assert reservation.project_ref.object == "urn:ngsi-ld:Project:test-project"
        assert len(reservation.lines.value) == 2
        assert reservation.lines.value[0]["sku"] == "COMP-A"
        assert reservation.lines.value[0]["qty"] == 2.0
        assert reservation.lines.value[1]["sku"] == "COMP-B"

    def test_reservation_serialization(self):
        lines = [ReservationLine(sku="TEST-001", qty=3.0)]
        reservation = Reservation.create("test-project", lines)
        data = reservation.model_dump(by_alias=True)

        assert data["id"] == "urn:ngsi-ld:Reservation:test-project"
        assert data["type"] == "Reservation"
        # the python attr is `project_ref` but the alias is `projectRef`
        assert data["projectRef"]["type"] == "Relationship"
        assert data["projectRef"]["object"] == "urn:ngsi-ld:Project:test-project"
        assert data["lines"]["type"] == "Property"
        assert data["lines"]["value"][0]["sku"] == "TEST-001"
        assert data["lines"]["value"][0]["qty"] == 3.0
        assert data["source"]["value"] == "odoo"  # default factory value


class TestShortageModel:
    """Test Shortage NGSI-LD entity"""

    def test_shortage_line_creation(self):
        line = ShortageLine(
            sku="TEST-001",
            missing_qty=3.0,
            required_qty=5.0,
            available_qty=2.0,
        )
        assert line.sku == "TEST-001"
        assert line.missing_qty == 3.0
        assert line.required_qty == 5.0
        assert line.available_qty == 2.0

    def test_shortage_creation(self):
        lines = [
            ShortageLine(sku="COMP-A", missing_qty=1.0, required_qty=3.0, available_qty=2.0),
            ShortageLine(sku="COMP-B", missing_qty=2.0, required_qty=2.0, available_qty=0.0),
        ]
        shortage = Shortage.create("test-project", lines)

        assert shortage.id == "urn:ngsi-ld:Shortage:test-project"
        assert shortage.type == "Shortage"
        assert shortage.project_ref.object == "urn:ngsi-ld:Project:test-project"
        assert len(shortage.lines.value) == 2
        # ShortageLine fields get camelCase aliases on serialise (missingQty etc.)
        assert shortage.lines.value[0]["sku"] == "COMP-A"
        assert shortage.lines.value[0]["missingQty"] == 1.0
        assert shortage.lines.value[1]["missingQty"] == 2.0

    def test_shortage_serialization(self):
        lines = [
            ShortageLine(sku="TEST-001", missing_qty=1.0, required_qty=4.0, available_qty=3.0),
        ]
        shortage = Shortage.create("test-project", lines)
        data = shortage.model_dump(by_alias=True)

        assert data["id"] == "urn:ngsi-ld:Shortage:test-project"
        assert data["type"] == "Shortage"
        assert data["projectRef"]["type"] == "Relationship"
        assert data["projectRef"]["object"] == "urn:ngsi-ld:Project:test-project"
        assert data["lines"]["type"] == "Property"
        line = data["lines"]["value"][0]
        assert line["sku"] == "TEST-001"
        assert line["missingQty"] == 1.0
        assert line["requiredQty"] == 4.0
        assert line["availableQty"] == 3.0


class TestInventoryItemModel:
    """Test InventoryItem NGSI-LD entity"""

    def test_inventory_item_creation(self):
        item = InventoryItem.create("TEST-001", 10.0, 2.0)
        assert item.id == "urn:ngsi-ld:InventoryItem:TEST-001"
        assert item.type == "InventoryItem"
        assert item.sku.value == "TEST-001"
        assert item.available.value == 10.0
        assert item.reserved.value == 2.0
        # total = available + reserved
        assert item.total.value == 12.0

    def test_inventory_item_zero_quantities(self):
        item = InventoryItem.create("TEST-002", 0.0, 0.0)
        assert item.sku.value == "TEST-002"
        assert item.available.value == 0.0
        assert item.reserved.value == 0.0
        assert item.total.value == 0.0

    def test_inventory_item_serialization(self):
        item = InventoryItem.create("TEST-001", 15.5, 3.5)
        data = item.model_dump(by_alias=True)
        assert data["id"] == "urn:ngsi-ld:InventoryItem:TEST-001"
        assert data["type"] == "InventoryItem"
        assert data["sku"]["value"] == "TEST-001"
        assert data["available"]["value"] == 15.5
        assert data["reserved"]["value"] == 3.5
        assert data["total"]["value"] == 19.0
        assert data["available"]["unitCode"] == "Unit"
        assert "@context" in data
