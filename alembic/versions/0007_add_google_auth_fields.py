"""add google auth fields

Revision ID: 0007_add_google_auth_fields
Revises: 0006_add_learner_preferences_memory
Create Date: 2026-03-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_add_google_auth_fields"
down_revision = "0006_add_learner_preferences_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("auth_users") as batch:
        batch.add_column(
            sa.Column(
                "auth_provider",
                sa.String(length=32),
                nullable=False,
                server_default="local",
            )
        )
        batch.add_column(
            sa.Column(
                "google_subject",
                sa.String(length=255),
                nullable=True,
            )
        )
        batch.create_index("ix_auth_users_google_subject", ["google_subject"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("auth_users") as batch:
        batch.drop_index("ix_auth_users_google_subject")
        batch.drop_column("google_subject")
        batch.drop_column("auth_provider")
