"""
Configuration settings for HERMES Odoo Adapter
"""
from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings


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
    poll_interval_seconds: int = Field(
        default=60, 
        description="Inventory sync polling interval",
        ge=10,
        le=3600
    )
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

    inventory_allowed_skus: List[str] = Field(
        default=[
            "CTRL-PANEL-A1",
            "LED-STRIP-24V-1M",
            "BRACKET-STEEL-001",
            "PCB-CTRL-REV21",
            "ENCLOSURE-IP65-300",
            "PSU-24VDC-5A",
            "CABLE-ASSY-2M",
            "SCREW-M4X12-DIN912",
            "RELAY-SAFETY-24V",
            "ESTOP-BTN-RED",
            "TFT-DISPLAY-7IN"
        ],
        description="List of SKU codes that should be exposed via the inventory API. Empty list means include every product."
    )
    
    # Project Mapping
    project_mapping_file: Optional[str] = Field(
        default=None,
        description="JSON file for project code to BOM mapping"
    )
    
    # Stock Location Configuration
    stock_location_names: List[str] = Field(
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
    
    # Retry and Circuit Breaker Configuration
    max_retries: int = Field(default=3, description="Maximum retry attempts", ge=0, le=10)
    retry_delay_seconds: float = Field(
        default=2.0, 
        description="Base retry delay in seconds",
        ge=0.1,
        le=60.0
    )
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
    
    @validator("orion_url", "odoo_url", "adapter_public_url")
    def validate_urls(cls, v: str) -> str:
        """Validate URL formats"""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v.rstrip("/")

    @validator("inventory_allowed_skus", pre=True)
    def parse_inventory_allowed_skus(cls, value):
        """Allow comma-separated env values for SKU filters"""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value
    
    @validator("stock_location_names", pre=True)
    def parse_location_names(cls, v):
        """Parse comma-separated location names from environment"""
        if isinstance(v, str):
            return [name.strip() for name in v.split(",") if name.strip()]
        return v
    
    @validator("log_level")
    def validate_log_level(cls, v: str) -> str:
        """Validate log level"""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v_upper
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
