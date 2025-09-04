"""
Prometheus metrics utilities for HERMES Odoo Adapter
"""
import time
from typing import Optional, Dict, Any
from contextlib import contextmanager
from functools import wraps

from prometheus_client import (
    Counter,
    Histogram, 
    Gauge,
    Info,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# Custom registry for our metrics
REGISTRY = CollectorRegistry()

# Application info
app_info = Info(
    "hermes_odoo_adapter_info",
    "Information about the HERMES Odoo Adapter",
    registry=REGISTRY
)

# HTTP request metrics
http_requests_total = Counter(
    "hermes_odoo_adapter_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
    registry=REGISTRY
)

http_request_duration_seconds = Histogram(
    "hermes_odoo_adapter_http_request_duration_seconds", 
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    registry=REGISTRY
)

# Odoo integration metrics
odoo_requests_total = Counter(
    "hermes_odoo_adapter_odoo_requests_total",
    "Total requests to Odoo",
    ["model", "method", "status"],
    registry=REGISTRY
)

odoo_request_duration_seconds = Histogram(
    "hermes_odoo_adapter_odoo_request_duration_seconds",
    "Odoo request duration in seconds", 
    ["model", "method"],
    registry=REGISTRY
)

# Orion-LD integration metrics
orion_operations_total = Counter(
    "hermes_odoo_adapter_orion_operations_total",
    "Total operations with Orion-LD",
    ["operation", "entity_type", "status"],
    registry=REGISTRY
)

orion_operation_duration_seconds = Histogram(
    "hermes_odoo_adapter_orion_operation_duration_seconds",
    "Orion-LD operation duration in seconds",
    ["operation", "entity_type"],
    registry=REGISTRY
)

# Business logic metrics
reservations_created_total = Counter(
    "hermes_odoo_adapter_reservations_created_total",
    "Total reservations created",
    ["status"],
    registry=REGISTRY
)

shortages_created_total = Counter(
    "hermes_odoo_adapter_shortages_created_total", 
    "Total shortages created",
    ["status"],
    registry=REGISTRY
)

inventory_sync_duration_seconds = Histogram(
    "hermes_odoo_adapter_inventory_sync_duration_seconds",
    "Inventory synchronization duration in seconds",
    registry=REGISTRY
)

inventory_sync_total = Counter(
    "hermes_odoo_adapter_inventory_sync_total",
    "Total inventory synchronizations",
    ["status"],
    registry=REGISTRY
)

inventory_items_processed_total = Counter(
    "hermes_odoo_adapter_inventory_items_processed_total", 
    "Total inventory items processed during sync",
    registry=REGISTRY
)

stock_changes_processed_total = Counter(
    "hermes_odoo_adapter_stock_changes_processed_total",
    "Total stock change events processed",
    ["status"],
    registry=REGISTRY
)

# Current state gauges
active_projects_gauge = Gauge(
    "hermes_odoo_adapter_active_projects",
    "Number of active projects being tracked",
    registry=REGISTRY
)

last_inventory_sync_timestamp = Gauge(
    "hermes_odoo_adapter_last_inventory_sync_timestamp",
    "Timestamp of last inventory synchronization",
    registry=REGISTRY
)


class MetricsCollector:
    """Utility class for collecting and managing metrics"""
    
    def __init__(self):
        self.registry = REGISTRY
        
        # Set application info
        app_info.info({
            "version": "0.1.0",
            "service": "hermes_odoo_adapter",
        })
    
    def get_metrics(self) -> str:
        """Get Prometheus metrics in text format"""
        return generate_latest(self.registry).decode('utf-8')
    
    def get_content_type(self) -> str:
        """Get Prometheus content type"""
        return CONTENT_TYPE_LATEST
    
    @contextmanager
    def time_http_request(self, method: str, endpoint: str):
        """Context manager to time HTTP requests"""
        start_time = time.time()
        status_code = "500"  # Default to error
        
        try:
            yield
            status_code = "200"  # Success
        except Exception as e:
            # Determine status code from exception if possible
            if hasattr(e, 'status_code'):
                status_code = str(e.status_code)
            raise
        finally:
            duration = time.time() - start_time
            http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
            http_requests_total.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
    
    @contextmanager
    def time_odoo_request(self, model: str, method: str):
        """Context manager to time Odoo requests"""
        start_time = time.time()
        status = "error"  # Default to error
        
        try:
            yield
            status = "success"
        except Exception:
            raise
        finally:
            duration = time.time() - start_time
            odoo_request_duration_seconds.labels(model=model, method=method).observe(duration)
            odoo_requests_total.labels(model=model, method=method, status=status).inc()
    
    @contextmanager
    def time_orion_operation(self, operation: str, entity_type: str):
        """Context manager to time Orion-LD operations"""
        start_time = time.time()
        status = "error"  # Default to error
        
        try:
            yield
            status = "success"
        except Exception:
            raise
        finally:
            duration = time.time() - start_time
            orion_operation_duration_seconds.labels(operation=operation, entity_type=entity_type).observe(duration)
            orion_operations_total.labels(operation=operation, entity_type=entity_type, status=status).inc()
    
    def record_reservation_created(self, status: str = "created"):
        """Record a reservation creation"""
        reservations_created_total.labels(status=status).inc()
    
    def record_shortage_created(self, status: str = "created"):
        """Record a shortage creation"""
        shortages_created_total.labels(status=status).inc()
    
    def update_active_projects(self, count: int):
        """Update active projects gauge"""
        active_projects_gauge.set(count)
    
    def record_inventory_sync_completed(self, items_processed: int, duration: float):
        """Record inventory sync completion"""
        inventory_sync_total.labels(status="success").inc()
        inventory_items_processed_total.inc(items_processed)
        inventory_sync_duration_seconds.observe(duration)
        last_inventory_sync_timestamp.set_to_current_time()
    
    def record_inventory_sync_failed(self):
        """Record inventory sync failure"""
        inventory_sync_total.labels(status="failed").inc()
    
    def record_stock_change_processed(self):
        """Record stock change webhook processing success"""
        stock_changes_processed_total.labels(status="success").inc()
    
    def record_stock_change_failed(self):
        """Record stock change webhook processing failure"""
        stock_changes_processed_total.labels(status="failed").inc()


# Global metrics instance
metrics = MetricsCollector()


def time_function(metric_name: str, labels: Optional[Dict[str, str]] = None):
    """Decorator to time function execution"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create histogram if not exists
            histogram = Histogram(
                f"hermes_odoo_adapter_{metric_name}_duration_seconds",
                f"Duration of {func.__name__} in seconds",
                list(labels.keys()) if labels else [],
                registry=REGISTRY
            )
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                if labels:
                    histogram.labels(**labels).observe(duration)
                else:
                    histogram.observe(duration)
        return wrapper
    return decorator


def count_calls(metric_name: str, labels: Optional[Dict[str, str]] = None):
    """Decorator to count function calls"""
    def decorator(func):
        # Create counter if not exists
        counter = Counter(
            f"hermes_odoo_adapter_{metric_name}_total",
            f"Total calls to {func.__name__}",
            list(labels.keys()) if labels else [],
            registry=REGISTRY
        )
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                if labels:
                    counter.labels(**labels).inc()
                else:
                    counter.inc()
                return result
            except Exception:
                # Still count failed calls
                if labels:
                    counter.labels(**labels).inc()
                else:
                    counter.inc()
                raise
        return wrapper
    return decorator