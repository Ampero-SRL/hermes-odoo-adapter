"""
Configuration settings for HERMES Odoo Adapter
"""
import json
from typing import Annotated, Any, List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _parse_str_list(value: Any) -> Any:
    """Accept JSON list `["a","b"]` OR comma-separated `a,b` strings.

    Used by the env-loaded `List[str]` settings below. Pairs with
    ``Annotated[List[str], NoDecode]`` to disable pydantic-settings'
    JSON pre-decoding for fields whose `.env.example` uses the
    comma-separated form (so the validator sees the raw string and
    can decide what to do with it).
    """
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if stripped.startswith("["):
        try:
            decoded = json.loads(stripped)
            if isinstance(decoded, list):
                return decoded
        except (ValueError, json.JSONDecodeError):
            pass
    return [item.strip() for item in stripped.split(",") if item.strip()]


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Service Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    metrics_port: int = Field(default=9090, description="Prometheus metrics port")
    testing: bool = Field(default=False, description="Testing mode flag")
    
    # Orion-LD NGSI-LD Context Broker
    orion_url: str = Field(default="http://localhost:1026", description="Orion-LD base URL")
    orion_tenant: Optional[str] = Field(default=None, description="FIWARE service tenant")
    orion_service_path: str = Field(default="/", description="FIWARE service path")
    
    # Adapter Configuration
    adapter_public_url: str = Field(
        default="http://localhost:8080", 
        description="Public URL for Orion subscription callbacks"
    )
    
    # Odoo ERP Configuration
    odoo_url: str = Field(default="http://localhost:8069/jsonrpc", description="Odoo JSON-RPC URL")
    odoo_db: str = Field(default="odoo", description="Odoo database name")
    odoo_user: str = Field(default="admin", description="Odoo username")
    odoo_password: str = Field(default="admin", description="Odoo password")
    
    # Product/SKU Configuration
    sku_field: str = Field(
        default="default_code", 
        description="Odoo product field to use as SKU identifier"
    )
    
    # Polling Configuration
    inventory_sync_enabled: bool = Field(
        default=True, 
        description="Enable periodic inventory synchronization"
    )
    inventory_sync_interval_minutes: int = Field(
        default=10,
        description="Inventory sync interval in minutes",
        ge=1,
        le=1440
    )
    inventory_sync_batch_size: int = Field(
        default=100,
        description="Number of products to process per batch during sync",
        ge=10,
        le=1000
    )

    # ``NoDecode`` skips pydantic-settings' JSON pre-decoding so the
    # ``@field_validator(mode="before")`` below can accept the bare
    # comma-separated `FOO,BAR,BAZ` form straight from `.env` (which is
    # what the shipped `.env.example` uses). Without NoDecode the
    # env-source tries `json.loads` first and dies on the comma-
    # separated value.
    inventory_allowed_skus: Annotated[List[str], NoDecode] = Field(
        default=[
            # Finished product
            "CTRL-PANEL-A1",
            # HERMES ASRS components (match class_names.yaml on Jetson)
            "EL-SAFETY-RELAY",
            "EL-IFACE-RELAY",
            "EL-CONTACTOR",
            "EL-AUX-CONTACT",
            "EL-FUSE-CARRIER",
            "EL-TERMINAL-BLK",
        ],
        description="List of SKU codes that should be exposed via the inventory API. Empty list means include every product."
    )
    
    # Project Mapping
    project_mapping_file: Optional[str] = Field(
        default=None,
        description="JSON file for project code to BOM mapping"
    )
    
    # Stock Location Configuration
    # Same NoDecode rationale as `inventory_allowed_skus` — the env
    # form is `Stock,WH/Stock,…` and pydantic-settings would otherwise
    # try to JSON-decode it first.
    stock_location_names: Annotated[List[str], NoDecode] = Field(
        default=["Stock", "WH/Stock"],
        description="Stock location names to include in calculations"
    )
    stock_location_id: int = Field(
        default=8,
        description="Odoo location ID for stock consume/produce operations (typically WH/Stock)",
        ge=1
    )
    include_reserved_stock: bool = Field(
        default=True,
        description="Include reserved stock in availability calculations"
    )
    
    # Circuit Breaker Configuration (Odoo client resilience)
    circuit_breaker_failure_threshold: int = Field(
        default=5,
        description="Circuit breaker failure threshold",
        ge=1,
        le=50
    )
    circuit_breaker_timeout_seconds: int = Field(
        default=60,
        description="Circuit breaker timeout in seconds",
        ge=10,
        le=3600
    )
    
    # Warehouse / ASRS Configuration
    warehouse_backend: str = Field(
        default="null",
        description=(
            "Warehouse backend: 'hanel_hostcom' (real MP 12N TCP telegrams, "
            "production), 'hanel_soap' (legacy JWS/HOST-WEB, preserved but "
            "not used in HERMES), or 'null' (dev/test no-op)."
        ),
    )
    asrs_soap_url: Optional[str] = Field(
        default=None,
        description="Hanel SOAP WSDL URL (e.g. http://172.16.x.x/ws/com?wsdl)"
    )
    asrs_soap_timeout: int = Field(
        default=10,
        description="SOAP request timeout in seconds",
        ge=1,
        le=60,
    )

    # Hänel HOST-COM (TCP/2200 telegram protocol) Configuration
    hanel_hostcom_host: Optional[str] = Field(
        default=None,
        description="Hanel MP 12N IP address for HOST-COM TCP protocol"
    )
    hanel_hostcom_port: int = Field(
        default=2200,
        description="Hanel MP 12N TCP port (HOST-COM is always 2200)",
        ge=1,
        le=65535,
    )
    hanel_elevator_num: int = Field(
        default=1,
        description="Elevator number (xxx in HOST-COM telegrams)",
        ge=1,
        le=99,
    )
    hanel_pickup_point: int = Field(
        default=1,
        description="Pickup point number (y in HOST-COM telegrams)",
        ge=1,
        le=8,
    )
    hanel_default_tray: int = Field(
        default=8,
        description="Default tray (bancale) number for HERMES components",
        ge=1,
    )
    hanel_sku_tray_map: dict = Field(
        default={
            # HERMES demo: every component lives on tray 8. Override any
            # individual SKU here to demonstrate the orchestrator calling
            # a different tray (e.g. tray 1 for a teach-in demo).
            "CTRL-PANEL-A1": 8,
            "EL-SAFETY-RELAY": 8,
            "EL-IFACE-RELAY": 8,
            "EL-CONTACTOR": 8,
            "EL-AUX-CONTACT": 8,
            "EL-FUSE-CARRIER": 8,
            "EL-TERMINAL-BLK": 8,
        },
        description="SKU → tray_number map for HOST-COM get_shelf calls"
    )
    warehouse_sync_enabled: bool = Field(
        default=False,
        description="Enable periodic warehouse inventory sync (only for non-null backends)"
    )
    warehouse_sync_interval_minutes: int = Field(
        default=1,
        description="Warehouse sync interval in minutes",
        ge=1,
        le=60,
    )

    # ROS2 Configuration
    ros2_enabled: bool = Field(
        default=True,
        description="Enable ROS2 node (Vulcanexus/Fast-DDS services and topics)"
    )
    ros2_node_name: str = Field(
        default="hermes_adapter",
        description="ROS2 node name"
    )

    # Security Configuration
    api_key_header: str = Field(default="X-API-Key", description="API key header name")
    api_key: Optional[str] = Field(default=None, description="API key for authentication")
    
    # Feature Flags
    write_enabled: bool = Field(
        default=False, 
        description="Enable write operations to Odoo (create reservations/MOs)"
    )
    webhook_enabled: bool = Field(
        default=False,
        description="Enable webhook endpoints for real-time updates"
    )
    
    @field_validator("orion_url", "odoo_url", "adapter_public_url")
    @classmethod
    def validate_urls(cls, v: str) -> str:
        """Validate URL formats"""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v.rstrip("/")

    @field_validator("inventory_allowed_skus", mode="before")
    @classmethod
    def parse_inventory_allowed_skus(cls, value):
        """Accept JSON list `["A","B"]` OR comma-separated `A,B` env strings."""
        return _parse_str_list(value)

    @field_validator("stock_location_names", mode="before")
    @classmethod
    def parse_location_names(cls, v):
        """Accept JSON list `["A","B"]` OR comma-separated `A,B` env strings."""
        return _parse_str_list(v)

    @field_validator("hanel_sku_tray_map", mode="before")
    @classmethod
    def parse_hanel_sku_tray_map(cls, v):
        """Accept JSON object or ``SKU=N,SKU=N`` strings from env."""
        if isinstance(v, str):
            import json
            s = v.strip()
            if not s:
                return {}
            if s.startswith("{"):
                return json.loads(s)
            out: dict[str, int] = {}
            for pair in s.split(","):
                if "=" in pair:
                    k, val = pair.split("=", 1)
                    out[k.strip()] = int(val.strip())
            return out
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level"""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v_upper
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # `.env.example` carries a few historical knobs
        # (POLL_INTERVAL_SECONDS, MAX_RETRIES, RETRY_DELAY_SECONDS) that
        # are no longer modelled on `Settings`. Pinning `extra="ignore"`
        # explicitly (a) preserves the documented contract that
        # `.env.example` may carry unmodeled fields, and (b) protects
        # against a future tightening of the upstream default (the
        # pydantic-settings project has discussed switching to
        # `extra="forbid"` in v3). Trade-off: typo'd env var names
        # (e.g. `OROIN_URL`) silently fall back to the field default
        # rather than crashing fast. Operators with strict-config
        # requirements should set `extra="forbid"` in their fork.
        extra="ignore",
    )


# Global settings instance
settings = Settings()
