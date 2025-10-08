"""add_type_ts_aligned_fields_to_training_tables

Revision ID: fbdef3bb42ac
Revises: add_workout_plan
Create Date: 2025-10-07 18:00:54.333017

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fbdef3bb42ac'
down_revision: Union[str, Sequence[str], None] = 'add_workout_plan'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add type.ts aligned fields to training_phases and training_weeks tables."""

    # Add new fields to training_phases
    op.add_column('training_phases', sa.Column('tag', sa.String(length=50), nullable=True))
    op.add_column('training_phases', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('training_phases', sa.Column('workout_focus', sa.Text(), nullable=True))

    # Add new fields to training_weeks
    op.add_column('training_weeks', sa.Column('start_date', sa.DateTime(), nullable=True))
    op.add_column('training_weeks', sa.Column('end_date', sa.DateTime(), nullable=True))
    op.add_column('training_weeks', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('training_weeks', sa.Column('weekly_mileage', sa.Float(), nullable=True))
    op.add_column('training_weeks', sa.Column('critical_workouts', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove type.ts aligned fields from training tables."""

    # Remove fields from training_weeks
    op.drop_column('training_weeks', 'critical_workouts')
    op.drop_column('training_weeks', 'weekly_mileage')
    op.drop_column('training_weeks', 'description')
    op.drop_column('training_weeks', 'end_date')
    op.drop_column('training_weeks', 'start_date')

    # Remove fields from training_phases
    op.drop_column('training_phases', 'workout_focus')
    op.drop_column('training_phases', 'description')
    op.drop_column('training_phases', 'tag')
