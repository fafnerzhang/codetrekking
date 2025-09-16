"""
Database configuration and connection management using SQLModel.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import ConfigDict, Field
from sqlmodel import create_engine, SQLModel, Session
from sqlalchemy.pool import QueuePool
import structlog

logger = structlog.get_logger(__name__)


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""

    # Database URL (can be used directly or constructed from parts)
    database_url: Optional[str] = None

    # PostgreSQL Connection Components
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "codetrekking"  # Updated to match environment
    db_user: str = "codetrekking"  # Updated to match environment
    db_password: str = "ChangeMe"  # Updated to match environment

    # Legacy field names for backward compatibility
    postgres_host: Optional[str] = None
    postgres_port: Optional[int] = None
    postgres_db: Optional[str] = None
    postgres_user: Optional[str] = None
    postgres_password: Optional[str] = None

    # Connection Pool Settings
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600

    # SQLAlchemy Settings
    echo_sql: bool = False

    # JWT Settings
    jwt_secret_key: str = Field(
        default="CHANGE_ME_IN_PRODUCTION",
        description="JWT secret key - must be set via environment variable",
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30

    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",  # Ignore extra environment variables
    )

    @property
    def database_url_computed(self) -> str:
        """Construct database URL from settings."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache()
def get_database_settings() -> DatabaseSettings:
    """Get cached database settings."""
    return DatabaseSettings()


# SQLAlchemy setup
settings = get_database_settings()

# Create engine with connection pooling
engine = create_engine(
    settings.database_url_computed,
    poolclass=QueuePool,
    pool_size=settings.pool_size,
    max_overflow=settings.max_overflow,
    pool_timeout=settings.pool_timeout,
    pool_recycle=settings.pool_recycle,
    echo=settings.echo_sql,
)


# Create session factory
def SessionLocal():
    """Create a new database session."""
    return Session(engine)


# SQLModel handles the base class automatically
# Base = SQLModel (this is handled automatically)


# Metadata from SQLModel
def get_metadata():
    """Get SQLModel metadata."""
    return SQLModel.metadata


def get_db():
    """
    Database dependency for FastAPI.

    Yields:
        Session: SQLModel database session
    """
    with Session(engine) as db:
        try:
            yield db
        except Exception as e:
            logger.error("Database session error", error=str(e))
            db.rollback()
            raise


async def init_database():
    """Initialize database tables."""
    try:
        # Import models to register them with SQLModel

        # Create all tables using SQLModel
        SQLModel.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")

        # Initialize default roles and permissions
        await _create_default_roles_and_permissions()

    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        raise


async def _create_default_roles_and_permissions():
    """Create default roles and permissions."""
    from .models import Role, Permission, RolePermission

    with Session(engine) as db:
        try:
            # Check if roles already exist
            if db.query(Role).count() > 0:
                logger.info("Roles already exist, skipping initialization")
                return

            # Create default permissions
            permissions = [
                Permission(name="read_profile", description="Read user profile"),
                Permission(name="update_profile", description="Update user profile"),
                Permission(name="delete_profile", description="Delete user profile"),
                Permission(name="read_admin", description="Read admin data"),
                Permission(name="write_admin", description="Write admin data"),
                Permission(name="manage_users", description="Manage other users"),
            ]

            for perm in permissions:
                db.add(perm)

            db.flush()  # Get IDs

            # Create default roles
            user_role = Role(name="user", description="Standard user")
            admin_role = Role(name="admin", description="Administrator")

            db.add(user_role)
            db.add(admin_role)
            db.flush()  # Get IDs

            # Assign permissions to roles
            user_permissions = ["read_profile", "update_profile"]
            admin_permissions = [
                "read_profile",
                "update_profile",
                "delete_profile",
                "read_admin",
                "write_admin",
                "manage_users",
            ]

            # User role permissions
            for perm_name in user_permissions:
                perm = db.query(Permission).filter(Permission.name == perm_name).first()
                if perm:
                    db.add(RolePermission(role_id=user_role.id, permission_id=perm.id))

            # Admin role permissions
            for perm_name in admin_permissions:
                perm = db.query(Permission).filter(Permission.name == perm_name).first()
                if perm:
                    db.add(RolePermission(role_id=admin_role.id, permission_id=perm.id))

            db.commit()
            logger.info("Default roles and permissions created successfully")

        except Exception as e:
            db.rollback()
            logger.error("Failed to create default roles and permissions", error=str(e))
            raise


def check_database_connection() -> bool:
    """
    Check if database connection is working.

    Returns:
        bool: True if connection is working, False otherwise
    """
    try:
        from sqlalchemy import text

        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            return result.fetchone() is not None
    except Exception as e:
        logger.error("Database connection check failed", error=str(e))
        return False
