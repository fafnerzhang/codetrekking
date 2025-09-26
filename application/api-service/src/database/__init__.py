"""
Database package for authentication system.
"""

from .config import (
    get_db,
    get_database_settings,
    init_database,
    check_database_connection,
    engine,
    SessionLocal,
)

from .models import (
    User,
    Role,
    Permission,
    UserSession,
    AuditLog,
    UserRoleLink,
    RolePermissionLink,
    UserGarminCredentials,
    # Legacy aliases
    UserRole,
    RolePermission,
)

from .elasticsearch import (
    get_elasticsearch_storage,
    get_elasticsearch_instance,
    get_elasticsearch_settings,
    check_elasticsearch_connection,
)

__all__ = [
    # Configuration
    "get_db",
    "get_database_settings",
    "init_database",
    "check_database_connection",
    "engine",
    "SessionLocal",
    # Models
    "User",
    "Role",
    "Permission",
    "UserSession",
    "AuditLog",
    "UserRoleLink",
    "RolePermissionLink",
    "UserGarminCredentials",
    # Legacy aliases
    "UserRole",
    "RolePermission",
    # Elasticsearch
    "get_elasticsearch_storage",
    "get_elasticsearch_instance",
    "get_elasticsearch_settings",
    "check_elasticsearch_connection",
]
