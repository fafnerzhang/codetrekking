"""Add workout plan tables

Revision ID: add_workout_plan
Revises: 5d6cd3b59299
Create Date: 2025-10-07 11:15:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "add_workout_plan"
down_revision: Union[str, Sequence[str], None] = "5d6cd3b59299"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Create training_phases table
    op.create_table(
        "training_phases",
        sa.Column("user_id", UUID(), nullable=False),
        sa.Column("phase_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("coach_id", sa.String(length=100), nullable=True),
        sa.Column("phase_type", sa.String(length=50), nullable=True),
        sa.Column("start_date", sa.DateTime(), nullable=True),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("critical_workouts", sa.Text(), nullable=True),  # JSON
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("user_id", "phase_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    # Create indexes for training_phases
    op.create_index("idx_training_phases_user_id", "training_phases", ["user_id"])
    op.create_index("idx_training_phases_phase_type", "training_phases", ["phase_type"])
    op.create_index("idx_training_phases_created_at", "training_phases", ["created_at"])

    # Create training_weeks table
    op.create_table(
        "training_weeks",
        sa.Column("user_id", UUID(), nullable=False),
        sa.Column("phase_id", sa.String(length=100), nullable=False),
        sa.Column("week_id", sa.String(length=100), nullable=False),
        sa.Column("week_number", sa.Integer(), nullable=False),
        sa.Column("weekly_tss_target", sa.Float(), nullable=True),
        sa.Column("focus", sa.String(length=200), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("user_id", "phase_id", "week_id"),
        sa.ForeignKeyConstraint(
            ["user_id", "phase_id"],
            ["training_phases.user_id", "training_phases.phase_id"],
            ondelete="CASCADE"
        ),
    )

    # Create indexes for training_weeks
    op.create_index("idx_training_weeks_user_phase", "training_weeks", ["user_id", "phase_id"])
    op.create_index("idx_training_weeks_week_number", "training_weeks", ["week_number"])

    # Create workout_plans table
    op.create_table(
        "workout_plans",
        sa.Column("id", UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(), nullable=False),
        sa.Column("phase_id", sa.String(length=100), nullable=False),
        sa.Column("week_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("workout_type", sa.String(length=50), nullable=False),
        sa.Column("segments", sa.Text(), nullable=True),  # JSON
        sa.Column("workout_metadata", sa.Text(), nullable=True),  # JSON
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id", "phase_id", "week_id"],
            ["training_weeks.user_id", "training_weeks.phase_id", "training_weeks.week_id"],
            ondelete="CASCADE"
        ),
    )

    # Create indexes for workout_plans
    op.create_index("idx_workout_plans_user_id", "workout_plans", ["user_id"])
    op.create_index("idx_workout_plans_phase_id", "workout_plans", ["phase_id"])
    op.create_index("idx_workout_plans_week_id", "workout_plans", ["week_id"])
    op.create_index("idx_workout_plans_user_phase_week", "workout_plans", ["user_id", "phase_id", "week_id"])
    op.create_index("idx_workout_plans_day_of_week", "workout_plans", ["day_of_week"])
    op.create_index("idx_workout_plans_workout_type", "workout_plans", ["workout_type"])


def downgrade() -> None:
    """Downgrade schema."""

    # Drop workout_plans table and indexes
    op.drop_index("idx_workout_plans_workout_type", table_name="workout_plans")
    op.drop_index("idx_workout_plans_day_of_week", table_name="workout_plans")
    op.drop_index("idx_workout_plans_user_phase_week", table_name="workout_plans")
    op.drop_index("idx_workout_plans_week_id", table_name="workout_plans")
    op.drop_index("idx_workout_plans_phase_id", table_name="workout_plans")
    op.drop_index("idx_workout_plans_user_id", table_name="workout_plans")
    op.drop_table("workout_plans")

    # Drop training_weeks table and indexes
    op.drop_index("idx_training_weeks_week_number", table_name="training_weeks")
    op.drop_index("idx_training_weeks_user_phase", table_name="training_weeks")
    op.drop_table("training_weeks")

    # Drop training_phases table and indexes
    op.drop_index("idx_training_phases_created_at", table_name="training_phases")
    op.drop_index("idx_training_phases_phase_type", table_name="training_phases")
    op.drop_index("idx_training_phases_user_id", table_name="training_phases")
    op.drop_table("training_phases")
