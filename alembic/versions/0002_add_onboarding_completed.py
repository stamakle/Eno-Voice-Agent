"""add onboarding_completed to learners

Revision ID: 0002_add_onboarding_completed
Revises: 0001_initial_schema
Create Date: 2026-03-08
"""

from alembic import op
import sqlalchemy as sa


revision = '0002_add_onboarding_completed'
down_revision = '0001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('learners', sa.Column('onboarding_completed', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column('learners', 'onboarding_completed')
