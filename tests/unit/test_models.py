"""
Tests for NGSI-LD models and data structures
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
    InventoryItem
)


class TestNGSILDProperties:
    """Test basic NGSI-LD property types"""
    
    def test_ngsi_ld_property_creation(self):
        """Test creation of NGSI-LD property"""
        prop = NGSILDProperty(value="test-value")
        
        assert prop.type == "Property"
        assert prop.value == "test-value"
        assert prop.observedAt is None
        assert prop.unitCode is None
    
    def test_ngsi_ld_property_with_metadata(self):
        """Test NGSI-LD property with metadata"""
        observed_at = datetime.utcnow()
        prop = NGSILDProperty(
            value=42.5,
            observedAt=observed_at,
            unitCode="MTR"
        )
        
        assert prop.type == "Property"
        assert prop.value == 42.5
        assert prop.observedAt == observed_at
        assert prop.unitCode == "MTR"
    
    def test_ngsi_ld_relationship_creation(self):
        """Test creation of NGSI-LD relationship"""
        rel = NGSILDRelationship(object="urn:ngsi-ld:Entity:123")
        
        assert rel.type == "Relationship"
        assert rel.object == "urn:ngsi-ld:Entity:123"
    
    def test_ngsi_ld_relationship_validation(self):
        """Test NGSI-LD relationship validation"""
        with pytest.raises(ValueError, match="must be a URN"):
            NGSILDRelationship(object="invalid-urn")


class TestProjectModel:
    """Test Project NGSI-LD entity"""
    
    def test_project_creation(self):
        """Test creating a Project entity"""
        project = Project.create("test-project", "TEST-001", "STATION-A", "requested")
        
        assert project.id == "urn:ngsi-ld:Project:test-project"
        assert project.type == "Project"
        assert project.code.value == "TEST-001"
        assert project.station.value == "STATION-A" 
        assert project.status.value == "requested"
        assert project.dateCreated.value is not None
    
    def test_project_creation_without_station(self):
        """Test creating a Project entity without station"""
        project = Project.create("test-project", "TEST-001", None, "requested")
        
        assert project.id == "urn:ngsi-ld:Project:test-project"
        assert project.type == "Project"
        assert project.code.value == "TEST-001"
        assert project.station is None
        assert project.status.value == "requested"
    
    def test_project_serialization(self):
        """Test Project entity serialization"""
        project = Project.create("test-project", "TEST-001", "STATION-A", "requested")
        data = project.dict(by_alias=True)
        
        assert data["id"] == "urn:ngsi-ld:Project:test-project"
        assert data["type"] == "Project"
        assert data["code"]["type"] == "Property"
        assert data["code"]["value"] == "TEST-001"
        assert data["station"]["type"] == "Property"
        assert data["station"]["value"] == "STATION-A"
        assert data["status"]["type"] == "Property"
        assert data["status"]["value"] == "requested"
        assert "@context" in data


class TestReservationModel:
    """Test Reservation NGSI-LD entity"""
    
    def test_reservation_line_creation(self):
        """Test creating a ReservationLine"""
        line = ReservationLine(sku="TEST-001", qty=5.0)
        
        assert line.sku == "TEST-001"
        assert line.qty == 5.0
    
    def test_reservation_creation(self):
        """Test creating a Reservation entity"""
        lines = [
            ReservationLine(sku="COMP-A", qty=2.0),
            ReservationLine(sku="COMP-B", qty=1.0)
        ]
        
        reservation = Reservation.create("test-project", lines)
        
        assert reservation.id == "urn:ngsi-ld:Reservation:test-project"
        assert reservation.type == "Reservation"
        assert reservation.project_ref.object == "urn:ngsi-ld:Project:test-project"
        assert len(reservation.lines.value) == 2
        assert reservation.lines.value[0]["sku"] == "COMP-A"
        assert reservation.lines.value[0]["qty"] == 2.0
        assert reservation.lines.value[1]["sku"] == "COMP-B"
        assert reservation.lines.value[1]["qty"] == 1.0
    
    def test_reservation_empty_lines(self):
        """Test creating a Reservation with empty lines"""
        reservation = Reservation.create("test-project", [])
        
        assert reservation.id == "urn:ngsi-ld:Reservation:test-project"
        assert len(reservation.lines.value) == 0
    
    def test_reservation_serialization(self):
        """Test Reservation entity serialization"""
        lines = [ReservationLine(sku="TEST-001", qty=3.0)]
        reservation = Reservation.create("test-project", lines)
        data = reservation.dict(by_alias=True)
        
        assert data["id"] == "urn:ngsi-ld:Reservation:test-project"
        assert data["type"] == "Reservation"
        assert data["project_ref"]["type"] == "Relationship"
        assert data["project_ref"]["object"] == "urn:ngsi-ld:Project:test-project"
        assert data["lines"]["type"] == "Property"
        assert len(data["lines"]["value"]) == 1
        assert data["lines"]["value"][0]["sku"] == "TEST-001"
        assert data["lines"]["value"][0]["qty"] == 3.0


class TestShortageModel:
    """Test Shortage NGSI-LD entity"""
    
    def test_shortage_line_creation(self):
        """Test creating a ShortageLine"""
        line = ShortageLine(
            sku="TEST-001",
            missing_qty=3.0,
            required_qty=5.0,
            available_qty=2.0
        )
        
        assert line.sku == "TEST-001"
        assert line.missing_qty == 3.0
        assert line.required_qty == 5.0
        assert line.available_qty == 2.0
    
    def test_shortage_creation(self):
        """Test creating a Shortage entity"""
        lines = [
            ShortageLine(
                sku="COMP-A",
                missing_qty=1.0,
                required_qty=3.0,
                available_qty=2.0
            ),
            ShortageLine(
                sku="COMP-B",
                missing_qty=2.0,
                required_qty=2.0,
                available_qty=0.0
            )
        ]
        
        shortage = Shortage.create("test-project", lines)
        
        assert shortage.id == "urn:ngsi-ld:Shortage:test-project"
        assert shortage.type == "Shortage"
        assert shortage.project_ref.object == "urn:ngsi-ld:Project:test-project"
        assert len(shortage.lines.value) == 2
        assert shortage.lines.value[0]["sku"] == "COMP-A"
        assert shortage.lines.value[0]["missing_qty"] == 1.0
        assert shortage.lines.value[1]["sku"] == "COMP-B"
        assert shortage.lines.value[1]["missing_qty"] == 2.0
    
    def test_shortage_serialization(self):
        """Test Shortage entity serialization"""
        lines = [
            ShortageLine(
                sku="TEST-001",
                missing_qty=1.0,
                required_qty=4.0,
                available_qty=3.0
            )
        ]
        shortage = Shortage.create("test-project", lines)
        data = shortage.dict(by_alias=True)
        
        assert data["id"] == "urn:ngsi-ld:Shortage:test-project"
        assert data["type"] == "Shortage"
        assert data["project_ref"]["type"] == "Relationship"
        assert data["project_ref"]["object"] == "urn:ngsi-ld:Project:test-project"
        assert data["lines"]["type"] == "Property"
        assert len(data["lines"]["value"]) == 1
        assert data["lines"]["value"][0]["sku"] == "TEST-001"
        assert data["lines"]["value"][0]["missing_qty"] == 1.0
        assert data["lines"]["value"][0]["required_qty"] == 4.0
        assert data["lines"]["value"][0]["available_qty"] == 3.0


class TestInventoryItemModel:
    """Test InventoryItem NGSI-LD entity"""
    
    def test_inventory_item_creation(self):
        """Test creating an InventoryItem entity"""
        item = InventoryItem.create("TEST-001", 10.0, 2.0)
        
        assert item.id == "urn:ngsi-ld:InventoryItem:TEST-001"
        assert item.type == "InventoryItem"
        assert item.sku.value == "TEST-001"
        assert item.available_quantity.value == 10.0
        assert item.reserved_quantity.value == 2.0
        assert item.total_quantity.value == 12.0  # available + reserved
    
    def test_inventory_item_zero_quantities(self):
        """Test creating an InventoryItem with zero quantities"""
        item = InventoryItem.create("TEST-002", 0.0, 0.0)
        
        assert item.sku.value == "TEST-002"
        assert item.available_quantity.value == 0.0
        assert item.reserved_quantity.value == 0.0
        assert item.total_quantity.value == 0.0
    
    def test_inventory_item_serialization(self):
        """Test InventoryItem entity serialization"""
        item = InventoryItem.create("TEST-001", 15.5, 3.5)
        data = item.dict(by_alias=True)
        
        assert data["id"] == "urn:ngsi-ld:InventoryItem:TEST-001"
        assert data["type"] == "InventoryItem"
        assert data["sku"]["type"] == "Property"
        assert data["sku"]["value"] == "TEST-001"
        assert data["available_quantity"]["type"] == "Property"
        assert data["available_quantity"]["value"] == 15.5
        assert data["reserved_quantity"]["type"] == "Property"
        assert data["reserved_quantity"]["value"] == 3.5
        assert data["total_quantity"]["type"] == "Property"
        assert data["total_quantity"]["value"] == 19.0
        assert data["available_quantity"]["unitCode"] == "EA"
        assert "@context" in data