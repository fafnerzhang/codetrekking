"""Add user_garmin_credentials table

Revision ID: 5d6cd3b59299
Revises:
Create Date: 2025-08-18 16:47:36.874055

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "5d6cd3b59299"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create user_garmin_credentials table
    op.create_table(
        "user_garmin_credentials",
        sa.Column("id", UUID(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(), nullable=False),
        sa.Column("garmin_username", sa.String(length=255), nullable=False),
        sa.Column("encrypted_password", sa.Text(), nullable=False),
        sa.Column("encryption_version", sa.Integer(), nullable=False, default=1),
        sa.Column("created_at", sa.DateTime(), nullable=True, default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=True, default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    # Create indexes
    op.create_index(
        "idx_user_garmin_credentials_user_id", "user_garmin_credentials", ["user_id"]
    )
    op.create_index(
        "idx_user_garmin_credentials_created_at",
        "user_garmin_credentials",
        ["created_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index(
        "idx_user_garmin_credentials_created_at", table_name="user_garmin_credentials"
    )
    op.drop_index(
        "idx_user_garmin_credentials_user_id", table_name="user_garmin_credentials"
    )

    # Drop table
    op.drop_table("user_garmin_credentials")
