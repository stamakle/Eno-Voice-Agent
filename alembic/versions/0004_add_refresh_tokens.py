"""add refresh token columns

Revision ID: 0004_add_refresh_tokens
Revises: 0003_add_auth_tables
Create Date: 2026-03-08
"""

from alembic import op
import sqlalchemy as sa


revision = '0004_add_refresh_tokens'
down_revision = '0003_add_auth_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('auth_sessions', sa.Column('refresh_token_hash', sa.String(length=128), nullable=True))
    op.add_column('auth_sessions', sa.Column('refresh_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_auth_sessions_refresh_token_hash', 'auth_sessions', ['refresh_token_hash'], unique=True)
    op.create_index('ix_auth_sessions_refresh_expires_at', 'auth_sessions', ['refresh_expires_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_auth_sessions_refresh_expires_at', table_name='auth_sessions')
    op.drop_index('ix_auth_sessions_refresh_token_hash', table_name='auth_sessions')
    op.drop_column('auth_sessions', 'refresh_expires_at')
    op.drop_column('auth_sessions', 'refresh_token_hash')
