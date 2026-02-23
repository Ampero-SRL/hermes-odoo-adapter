"""
Warehouse abstraction layer for HERMES Odoo Adapter.

Provides a pluggable interface for different warehouse/ASRS backends.
Current implementations:
  - HanelSoapClient: Hanel vertical warehouse via SOAP 1.1
  - NullWarehouseClient: Dev/test stub (no external dependencies)
"""
from .base import WarehouseClient, PickResult, PickStatus, ArticleInfo
from .factory import create_warehouse_client

__all__ = [
    "WarehouseClient",
    "PickResult",
    "PickStatus",
    "ArticleInfo",
    "create_warehouse_client",
]
