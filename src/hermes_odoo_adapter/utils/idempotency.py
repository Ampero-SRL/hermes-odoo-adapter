"""
Idempotency utilities for HERMES Odoo Adapter
"""
import hashlib
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime


def generate_correlation_id() -> str:
    """Generate a unique correlation ID"""
    return str(uuid.uuid4())


def generate_entity_hash(data: Dict[str, Any], exclude_fields: Optional[List[str]] = None) -> str:
    """Generate a deterministic hash for entity data"""
    exclude_fields = exclude_fields or ["observedAt", "createdAt", "updatedAt"]
    
    # Create a copy and remove excluded fields
    cleaned_data = {}
    for key, value in data.items():
        if key not in exclude_fields:
            cleaned_data[key] = value
    
    # Sort keys for consistent hashing
    sorted_keys = sorted(cleaned_data.keys())
    hash_string = ""
    
    for key in sorted_keys:
        hash_string += f"{key}:{cleaned_data[key]}"
    
    return hashlib.sha256(hash_string.encode()).hexdigest()[:16]


def generate_project_key(project_code: str) -> str:
    """Generate a consistent key for project tracking"""
    return f"project:{project_code}"


def generate_reservation_key(project_id: str, lines: List[Dict[str, Any]]) -> str:
    """Generate a deterministic key for reservation idempotency"""
    # Sort lines by SKU for consistent ordering
    sorted_lines = sorted(lines, key=lambda x: x.get("sku", ""))
    
    # Create hash from project and lines
    line_data = ""
    for line in sorted_lines:
        line_data += f"{line.get('sku')}:{line.get('qty')}"
    
    combined = f"{project_id}:{line_data}"
    hash_value = hashlib.md5(combined.encode()).hexdigest()[:12]
    
    return f"reservation:{project_id}:{hash_value}"


def generate_shortage_key(project_id: str, lines: List[Dict[str, Any]]) -> str:
    """Generate a deterministic key for shortage idempotency"""
    # Sort lines by SKU for consistent ordering
    sorted_lines = sorted(lines, key=lambda x: x.get("sku", ""))
    
    # Create hash from project and shortage lines
    line_data = ""
    for line in sorted_lines:
        sku = line.get("sku", "")
        missing = line.get("missingQty", line.get("missing_qty", 0))
        line_data += f"{sku}:{missing}"
    
    combined = f"{project_id}:{line_data}"
    hash_value = hashlib.md5(combined.encode()).hexdigest()[:12]
    
    return f"shortage:{project_id}:{hash_value}"


class IdempotencyHelper:
    """Helper class for managing idempotency keys and deduplication"""
    
    def __init__(self):
        # In-memory cache for recent operations
        # In production, this should use Redis or similar
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_size_limit = 10000
    
    def is_duplicate(self, key: str, data_hash: str) -> bool:
        """Check if an operation is a duplicate"""
        cached_entry = self._cache.get(key)
        if not cached_entry:
            return False
        
        return cached_entry.get("hash") == data_hash
    
    def mark_processed(self, key: str, data_hash: str, result: Optional[Any] = None) -> None:
        """Mark an operation as processed"""
        self._cache[key] = {
            "hash": data_hash,
            "timestamp": datetime.utcnow().isoformat(),
            "result": result
        }
        
        # Simple cache size management
        if len(self._cache) > self._cache_size_limit:
            # Remove oldest 10% of entries
            sorted_items = sorted(
                self._cache.items(), 
                key=lambda x: x[1]["timestamp"]
            )
            to_remove = len(sorted_items) // 10
            for key, _ in sorted_items[:to_remove]:
                del self._cache[key]
    
    def get_cached_result(self, key: str) -> Optional[Any]:
        """Get cached result for a key"""
        cached_entry = self._cache.get(key)
        if cached_entry:
            return cached_entry.get("result")
        return None
    
    def clear_cache(self) -> None:
        """Clear the idempotency cache"""
        self._cache.clear()

    def clear_project(self, project_id: str) -> bool:
        """Clear a specific project from the idempotency cache"""
        project_key = generate_project_key(project_id)
        if project_key in self._cache:
            del self._cache[project_key]
            return True
        return False
    
    def generate_project_reservation_key(self, project_id: str, bom_lines: List[Dict[str, Any]]) -> str:
        """Generate idempotency key for project reservation"""
        return generate_reservation_key(project_id, bom_lines)
    
    def generate_project_shortage_key(self, project_id: str, shortage_lines: List[Dict[str, Any]]) -> str:
        """Generate idempotency key for project shortage"""
        return generate_shortage_key(project_id, shortage_lines)
    
    def should_process_project(self, project_id: str, project_data: Dict[str, Any]) -> bool:
        """Check if a project should be processed (not a duplicate)"""
        project_key = generate_project_key(project_id)
        data_hash = generate_entity_hash(project_data)
        
        return not self.is_duplicate(project_key, data_hash)
    
    def mark_project_processed(self, project_id: str, project_data: Dict[str, Any], result: Any) -> None:
        """Mark a project as processed"""
        project_key = generate_project_key(project_id)
        data_hash = generate_entity_hash(project_data)
        
        self.mark_processed(project_key, data_hash, result)


# Global idempotency helper instance
idempotency_helper = IdempotencyHelper()