"""
SQLModel database models for authentication system.
"""

from datetime import datetime, timezone
from typing import Optional, List
import uuid

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import and_
import structlog

logger = structlog.get_logger(__name__)




# Link tables for many-to-many relationships using SQLModel
class UserRoleLink(SQLModel, table=True):
    """Link table for User-Role many-to-many relationship."""

    __tablename__ = "user_roles"

    user_id: Optional[uuid.UUID] = Field(
        default=None, foreign_key="users.id", primary_key=True
    )
    role_id: Optional[int] = Field(
        default=None, foreign_key="roles.id", primary_key=True
    )
    assigned_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class RolePermissionLink(SQLModel, table=True):
    """Link table for Role-Permission many-to-many relationship."""

    __tablename__ = "role_permissions"

    role_id: Optional[int] = Field(
        default=None, foreign_key="roles.id", primary_key=True
    )
    permission_id: Optional[int] = Field(
        default=None, foreign_key="permissions.id", primary_key=True
    )


class User(SQLModel, table=True):
    """User model for authentication."""

    __tablename__ = "users"

    # Primary key
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)

    # Basic user information
    username: str = Field(max_length=50, unique=True, index=True)
    email: str = Field(max_length=255, unique=True, index=True)
    hashed_password: str = Field(max_length=255)

    # User profile
    first_name: Optional[str] = Field(default=None, max_length=50)
    last_name: Optional[str] = Field(default=None, max_length=50)

    # Status and permissions
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)
    is_superuser: bool = Field(default=False)

    # Security fields
    failed_login_attempts: int = Field(default=0)
    locked_until: Optional[datetime] = Field(default=None)
    password_changed_at: Optional[datetime] = Field(default=None)

    # Verification
    verification_token: Optional[str] = Field(default=None, max_length=255)
    verification_token_expires: Optional[datetime] = Field(default=None)

    # Password reset
    reset_token: Optional[str] = Field(default=None, max_length=255)
    reset_token_expires: Optional[datetime] = Field(default=None)

    # Timestamps
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_login_at: Optional[datetime] = Field(default=None)

    # Relationships
    roles: List["Role"] = Relationship(back_populates="users", link_model=UserRoleLink)
    sessions: List["UserSession"] = Relationship(back_populates="user")
    audit_logs: List["AuditLog"] = Relationship(back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username

    @property
    def is_locked(self) -> bool:
        """Check if user account is locked."""
        if self.locked_until is None:
            return False
        return datetime.now(timezone.utc) < self.locked_until

    def has_permission(self, permission_name: str) -> bool:
        """Check if user has a specific permission."""
        for role in self.roles:
            for permission in role.permissions:
                if permission.name == permission_name:
                    return True
        return False

    def has_role(self, role_name: str) -> bool:
        """Check if user has a specific role."""
        return any(role.name == role_name for role in self.roles)


class Role(SQLModel, table=True):
    """Role model for role-based access control."""

    __tablename__ = "roles"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=50, unique=True, index=True)
    description: Optional[str] = Field(default=None)
    is_active: bool = Field(default=True)

    # Timestamps
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    users: List[User] = Relationship(back_populates="roles", link_model=UserRoleLink)
    permissions: List["Permission"] = Relationship(
        back_populates="roles", link_model=RolePermissionLink
    )

    def __repr__(self):
        return f"<Role(id={self.id}, name={self.name})>"


class Permission(SQLModel, table=True):
    """Permission model for fine-grained access control."""

    __tablename__ = "permissions"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=100, unique=True, index=True)
    description: Optional[str] = Field(default=None)
    resource: Optional[str] = Field(
        default=None, max_length=50
    )  # e.g., 'user', 'admin', 'analytics'
    action: Optional[str] = Field(
        default=None, max_length=50
    )  # e.g., 'read', 'write', 'delete'

    # Timestamps
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    roles: List[Role] = Relationship(
        back_populates="permissions", link_model=RolePermissionLink
    )

    def __repr__(self):
        return f"<Permission(id={self.id}, name={self.name})>"


class UserSession(SQLModel, table=True):
    """User session model for tracking active sessions."""

    __tablename__ = "sessions"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)

    # Session tokens
    refresh_token: str = Field(max_length=500, unique=True, index=True)
    refresh_token_expires: datetime

    # Session metadata
    ip_address: Optional[str] = Field(default=None, max_length=45)  # Support IPv6
    user_agent: Optional[str] = Field(default=None)
    device_id: Optional[str] = Field(default=None, max_length=255)
    device_name: Optional[str] = Field(default=None, max_length=100)

    # Session status
    is_active: bool = Field(default=True)
    revoked_at: Optional[datetime] = Field(default=None)
    revoked_reason: Optional[str] = Field(default=None, max_length=100)

    # Timestamps
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_accessed_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user: Optional[User] = Relationship(back_populates="sessions")

    def __repr__(self):
        return (
            f"<Session(id={self.id}, user_id={self.user_id}, active={self.is_active})>"
        )

    @property
    def is_expired(self) -> bool:
        """Check if session is expired."""
        from datetime import timezone

        return datetime.now(timezone.utc) > self.refresh_token_expires

    @property
    def is_valid(self) -> bool:
        """Check if session is valid (active and not expired)."""
        return self.is_active and not self.is_expired and self.revoked_at is None


class AuditLog(SQLModel, table=True):
    """Audit log model for tracking user actions and security events."""

    __tablename__ = "audit_logs"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: Optional[uuid.UUID] = Field(
        default=None, foreign_key="users.id", index=True
    )

    # Event details
    event_type: str = Field(
        max_length=50, index=True
    )  # login, logout, password_change, etc.
    event_category: str = Field(
        max_length=50, index=True
    )  # auth, admin, user, security
    event_description: Optional[str] = Field(default=None)

    # Request details
    ip_address: Optional[str] = Field(default=None, max_length=45)
    user_agent: Optional[str] = Field(default=None)
    request_method: Optional[str] = Field(default=None, max_length=10)
    request_path: Optional[str] = Field(default=None, max_length=500)

    # Status and metadata
    status: str = Field(default="success", max_length=20)  # success, failure, warning
    session_metadata: Optional[str] = Field(
        default=None
    )  # JSON string for additional data

    # Timestamps
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc), index=True
    )

    # Relationships
    user: Optional[User] = Relationship(back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog(id={self.id}, event_type={self.event_type}, user_id={self.user_id})>"


class UserGarminCredentials(SQLModel, table=True):
    """Encrypted Garmin credentials storage."""

    __tablename__ = "user_garmin_credentials"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True, unique=True)
    garmin_username: str = Field(max_length=255)
    encrypted_password: str = Field()
    encryption_version: int = Field(default=1)
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user: Optional[User] = Relationship()

    def __repr__(self):
        return f"<UserGarminCredentials(id={self.id}, user_id={self.user_id}, username={self.garmin_username})>"


class TrainingPhase(SQLModel, table=True):
    """Training phase with weeks of structured workouts."""

    __tablename__ = "training_phases"

    # Composite primary key: (user_id, phase_id)
    user_id: uuid.UUID = Field(foreign_key="users.id", primary_key=True)
    phase_id: str = Field(max_length=100, primary_key=True)

    # Phase metadata
    name: str = Field(max_length=200)
    tag: Optional[str] = Field(default=None, max_length=50)  # Short tag: base, build, peak, taper
    description: Optional[str] = Field(default=None)  # Phase objectives and training focus
    coach_id: Optional[str] = Field(default=None, max_length=100)
    phase_type: Optional[str] = Field(default=None, max_length=50)  # Deprecated: use tag instead
    start_date: Optional[datetime] = Field(default=None)
    end_date: Optional[datetime] = Field(default=None)

    # JSON fields
    workout_focus: Optional[str] = Field(default=None)  # JSON array of focus areas
    critical_workouts: Optional[str] = Field(default=None)  # JSON array of critical workout definitions (deprecated)
    notes: Optional[str] = Field(default=None)  # Additional notes

    # Timestamps
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user: Optional[User] = Relationship()
    weeks: List["TrainingWeek"] = Relationship(
        back_populates="phase",
        sa_relationship_kwargs={
            "primaryjoin": "and_(TrainingPhase.user_id==TrainingWeek.user_id, TrainingPhase.phase_id==TrainingWeek.phase_id)",
            "cascade": "all, delete-orphan",
            "viewonly": False
        }
    )

    def __repr__(self):
        return f"<TrainingPhase(user_id={self.user_id}, phase_id={self.phase_id}, name={self.name})>"


class TrainingWeek(SQLModel, table=True):
    """Training week within a phase."""

    __tablename__ = "training_weeks"

    # Composite primary key: (user_id, phase_id, week_id)
    # Foreign key to TrainingPhase (user_id, phase_id)
    user_id: uuid.UUID = Field(primary_key=True, foreign_key="training_phases.user_id")
    phase_id: str = Field(max_length=100, primary_key=True, foreign_key="training_phases.phase_id")
    week_id: str = Field(max_length=100, primary_key=True)

    # Week metadata
    week_number: int  # 1-based week number within phase
    start_date: Optional[datetime] = Field(default=None)  # Week start date
    end_date: Optional[datetime] = Field(default=None)  # Week end date
    description: Optional[str] = Field(default=None)  # Weekly focus and training objectives
    weekly_mileage: Optional[float] = Field(default=None)  # Planned weekly mileage in km
    critical_workouts: Optional[str] = Field(default=None)  # JSON array of CriticalWorkout objects

    # Legacy fields (still supported for backward compatibility)
    weekly_tss_target: Optional[float] = Field(default=None)
    focus: Optional[str] = Field(default=None, max_length=200)  # Deprecated: use description
    notes: Optional[str] = Field(default=None)  # Additional notes

    # Timestamps
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    phase: Optional[TrainingPhase] = Relationship(
        back_populates="weeks",
        sa_relationship_kwargs={
            "primaryjoin": "and_(TrainingWeek.user_id==TrainingPhase.user_id, TrainingWeek.phase_id==TrainingPhase.phase_id)",
            "viewonly": False
        }
    )
    workouts: List["WorkoutPlan"] = Relationship(
        back_populates="week",
        sa_relationship_kwargs={
            "primaryjoin": "and_(TrainingWeek.user_id==WorkoutPlan.user_id, TrainingWeek.phase_id==WorkoutPlan.phase_id, TrainingWeek.week_id==WorkoutPlan.week_id)",
            "cascade": "all, delete-orphan",
            "viewonly": False
        }
    )

    def __repr__(self):
        return f"<TrainingWeek(user_id={self.user_id}, phase_id={self.phase_id}, week_id={self.week_id}, week_number={self.week_number})>"


class WorkoutPlan(SQLModel, table=True):
    """Individual workout within a training week."""

    __tablename__ = "workout_plans"

    # Primary key
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)

    # Foreign key to week (composite: user_id, phase_id, week_id)
    user_id: uuid.UUID = Field(foreign_key="training_weeks.user_id", index=True)
    phase_id: str = Field(max_length=100, foreign_key="training_weeks.phase_id", index=True)
    week_id: str = Field(max_length=100, foreign_key="training_weeks.week_id", index=True)

    # Workout metadata
    name: str = Field(max_length=200)
    day_of_week: int = Field(ge=0, le=6)  # 0=Monday, 6=Sunday
    workout_type: str = Field(max_length=50)  # threshold, intervals, long_run, recovery, etc.

    # JSON fields for workout structure
    segments: Optional[str] = Field(default=None)  # JSON array of WorkoutPlanSegment
    workout_metadata: Optional[str] = Field(default=None)  # JSON object with TSS, duration, etc.

    # Timestamps
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    week: Optional[TrainingWeek] = Relationship(
        back_populates="workouts",
        sa_relationship_kwargs={
            "primaryjoin": "and_(WorkoutPlan.user_id==TrainingWeek.user_id, WorkoutPlan.phase_id==TrainingWeek.phase_id, WorkoutPlan.week_id==TrainingWeek.week_id)",
            "viewonly": False
        }
    )

    def __repr__(self):
        return f"<WorkoutPlan(id={self.id}, name={self.name}, week_id={self.week_id})>"


# Convenience aliases for backward compatibility
UserRole = UserRoleLink
RolePermission = RolePermissionLink
