"""add learner preferences and memory columns

Revision ID: 0006_add_learner_preferences_memory
Revises: 0005_auth_recovery_verify
Create Date: 2026-03-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_add_learner_preferences_memory"
down_revision = "0005_auth_recovery_verify"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("learners") as batch:
        batch.add_column(
            sa.Column(
                "preferred_scenario",
                sa.String(length=120),
                nullable=False,
                server_default="General conversation",
            )
        )
        batch.add_column(
            sa.Column(
                "memory_notes",
                sa.JSON(),
                nullable=False,
                server_default="[]",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("learners") as batch:
        batch.drop_column("memory_notes")
        batch.drop_column("preferred_scenario")
