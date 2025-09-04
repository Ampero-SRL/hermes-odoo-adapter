"""
NGSI-LD models for HERMES Odoo Adapter
"""

from .ngsi_models import (
    NGSILDEntity,
    NGSILDProperty,
    NGSILDRelationship,
    Project,
    Reservation,
    Shortage,
    InventoryItem,
    ReservationLine,
    ShortageLine,
)

__all__ = [
    "NGSILDEntity",
    "NGSILDProperty", 
    "NGSILDRelationship",
    "Project",
    "Reservation",
    "Shortage",
    "InventoryItem", 
    "ReservationLine",
    "ShortageLine",
]