"""
NGSI-LD entity models for HERMES manufacturing context
"""
from datetime import datetime
from pathlib import Path
import json
from typing import Any, Dict, List, Optional, Union, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator

from ..settings import settings

_CONTEXT_FILE = Path(__file__).resolve().parents[2] / "contracts/context/context.jsonld"

def _load_custom_context() -> Dict[str, Any]:
    try:
        with open(_CONTEXT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("@context", {})
    except Exception:
        return {}

CUSTOM_CONTEXT = _load_custom_context()

DEFAULT_CONTEXT = [
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
    CUSTOM_CONTEXT,
]


class NGSILDProperty(BaseModel):
    """NGSI-LD Property model"""
    type: str = "Property"
    value: Any
    observedAt: Optional[datetime] = None
    unitCode: Optional[str] = None
    model_config = ConfigDict(extra="allow")


class NGSILDRelationship(BaseModel):
    """NGSI-LD Relationship model"""
    type: str = "Relationship" 
    object: str = Field(..., description="URI of the related entity")
    observedAt: Optional[datetime] = None
    model_config = ConfigDict(extra="allow")


class NGSILDEntity(BaseModel):
    """Base NGSI-LD Entity model"""
    id: str = Field(..., description="Entity ID (must be a URI)")
    type: str = Field(..., description="Entity type")
    context: List[str] = Field(default_factory=lambda: DEFAULT_CONTEXT.copy(), alias="@context")
    
    @field_validator("id")
    def validate_entity_id(cls, v: str) -> str:
        """Validate entity ID is a proper URI"""
        if not v.startswith("urn:ngsi-ld:"):
            raise ValueError("Entity ID must start with 'urn:ngsi-ld:'")
        return v
    
    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ReservationLine(BaseModel):
    """Individual line in a reservation"""
    sku: str = Field(..., description="Product SKU")
    qty: float = Field(..., description="Quantity to reserve", gt=0)
    unit: Optional[str] = Field(default="Unit", description="Unit of measure")
    model_config = ConfigDict(extra="forbid")


class ShortageLine(BaseModel):
    """Individual line in a shortage"""
    sku: str = Field(..., description="Product SKU")
    missing_qty: float = Field(..., description="Missing quantity", gt=0, alias="missingQty")
    required_qty: float = Field(..., description="Total required quantity", gt=0, alias="requiredQty") 
    available_qty: float = Field(..., description="Available quantity", ge=0, alias="availableQty")
    unit: Optional[str] = Field(default="Unit", description="Unit of measure")
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Project(NGSILDEntity):
    """HERMES Project entity"""
    type: Literal["Project"] = "Project"
    code: NGSILDProperty = Field(..., description="Project code/identifier")
    station: Optional[NGSILDProperty] = Field(None, description="Target station")
    status: NGSILDProperty = Field(..., description="Project status")
    
    @field_validator("id", mode="before")
    def generate_project_id(cls, v: str) -> str:
        """Generate project ID from code if not provided"""
        if not v.startswith("urn:ngsi-ld:"):
            return f"urn:ngsi-ld:Project:{v}"
        return v
    
    @classmethod
    def create(
        cls, 
        project_id: str,
        code: str, 
        status: str = "requested",
        station: Optional[str] = None
    ) -> "Project":
        """Factory method to create a Project"""
        project = cls(
            id=f"urn:ngsi-ld:Project:{project_id}" if not project_id.startswith("urn:") else project_id,
            code=NGSILDProperty(value=code),
            status=NGSILDProperty(value=status)
        )
        
        if station:
            project.station = NGSILDProperty(value=station)
            
        return project


class Reservation(NGSILDEntity):
    """HERMES Reservation entity for stock reservations"""
    type: Literal["Reservation"] = "Reservation"
    project_ref: NGSILDRelationship = Field(..., description="Reference to Project", alias="projectRef")
    lines: NGSILDProperty = Field(..., description="Reservation lines")
    status: NGSILDProperty = Field(..., description="Reservation status")
    source: NGSILDProperty = Field(..., description="Source system")
    created_at: Optional[NGSILDProperty] = Field(None, description="Creation timestamp", alias="createdAt")
    
    @field_validator("id", mode="before")
    def generate_reservation_id(cls, v: str) -> str:
        """Generate reservation ID if not provided"""
        if not v.startswith("urn:ngsi-ld:"):
            return f"urn:ngsi-ld:Reservation:{v}"
        return v
    
    @classmethod
    def create(
        cls,
        project_id: str,
        lines: List[ReservationLine],
        status: str = "pending",
        source: str = "odoo"
    ) -> "Reservation":
        """Factory method to create a Reservation"""
        # Convert project_id to full URI if needed
        if not project_id.startswith("urn:ngsi-ld:"):
            project_uri = f"urn:ngsi-ld:Project:{project_id}"
        else:
            project_uri = project_id
            
        # Extract project ID for reservation ID
        project_code = project_uri.split(":")[-1]
        
        return cls(
            id=f"urn:ngsi-ld:Reservation:{project_code}",
            project_ref=NGSILDRelationship(object=project_uri),
            lines=NGSILDProperty(value=[line.dict(by_alias=True) for line in lines]),
            status=NGSILDProperty(value=status),
            source=NGSILDProperty(value=source),
            created_at=NGSILDProperty(value=datetime.utcnow().isoformat())
        )
    
    model_config = ConfigDict(populate_by_name=True)


class Shortage(NGSILDEntity):
    """HERMES Shortage entity for insufficient stock"""
    type: Literal["Shortage"] = "Shortage"
    project_ref: NGSILDRelationship = Field(..., description="Reference to Project", alias="projectRef")
    lines: NGSILDProperty = Field(..., description="Shortage lines")
    status: NGSILDProperty = Field(..., description="Shortage status")
    created_at: Optional[NGSILDProperty] = Field(None, description="Creation timestamp", alias="createdAt")
    
    @field_validator("id", mode="before")
    def generate_shortage_id(cls, v: str) -> str:
        """Generate shortage ID if not provided"""
        if not v.startswith("urn:ngsi-ld:"):
            return f"urn:ngsi-ld:Shortage:{v}"
        return v
    
    @classmethod
    def create(
        cls,
        project_id: str,
        lines: List[ShortageLine],
        status: str = "open"
    ) -> "Shortage":
        """Factory method to create a Shortage"""
        # Convert project_id to full URI if needed
        if not project_id.startswith("urn:ngsi-ld:"):
            project_uri = f"urn:ngsi-ld:Project:{project_id}"
        else:
            project_uri = project_id
            
        # Extract project ID for shortage ID  
        project_code = project_uri.split(":")[-1]
        
        return cls(
            id=f"urn:ngsi-ld:Shortage:{project_code}",
            project_ref=NGSILDRelationship(object=project_uri),
            lines=NGSILDProperty(value=[line.dict(by_alias=True) for line in lines]),
            status=NGSILDProperty(value=status),
            created_at=NGSILDProperty(value=datetime.utcnow().isoformat())
        )
    
    model_config = ConfigDict(populate_by_name=True)


class InventoryItem(NGSILDEntity):
    """HERMES InventoryItem entity for stock levels"""
    type: Literal["InventoryItem"] = "InventoryItem"
    sku: NGSILDProperty = Field(..., description="Product SKU")
    available: NGSILDProperty = Field(..., description="Available quantity")
    reserved: NGSILDProperty = Field(..., description="Reserved quantity") 
    total: NGSILDProperty = Field(..., description="Total quantity on hand")
    updated_at: NGSILDProperty = Field(..., description="Last update timestamp", alias="updatedAt")
    location: Optional[NGSILDProperty] = Field(None, description="Storage location")
    
    @field_validator("id", mode="before")
    def generate_inventory_id(cls, v: str) -> str:
        """Generate inventory ID from SKU if not provided"""
        if not v.startswith("urn:ngsi-ld:"):
            return f"urn:ngsi-ld:InventoryItem:{v}"
        return v
    
    @classmethod
    def create(
        cls,
        sku: str,
        available: float,
        reserved: float = 0.0,
        location: Optional[str] = None
    ) -> "InventoryItem":
        """Factory method to create an InventoryItem"""
        item = cls(
            id=f"urn:ngsi-ld:InventoryItem:{sku}",
            sku=NGSILDProperty(value=sku),
            available=NGSILDProperty(value=available, unitCode="Unit"),
            reserved=NGSILDProperty(value=reserved, unitCode="Unit"),
            total=NGSILDProperty(value=available + reserved, unitCode="Unit"),
            updated_at=NGSILDProperty(value=datetime.utcnow().isoformat())
        )
        
        if location:
            item.location = NGSILDProperty(value=location)
            
        return item
    
    model_config = ConfigDict(populate_by_name=True)
