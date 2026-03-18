"""add auth recovery and verification fields

Revision ID: 0005_auth_recovery_verify
Revises: 0004_add_refresh_tokens
Create Date: 2026-03-08
"""

from alembic import op
import sqlalchemy as sa


revision = '0005_auth_recovery_verify'
down_revision = '0004_add_refresh_tokens'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('auth_users') as batch:
        batch.add_column(sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column('verification_token_hash', sa.String(length=128), nullable=True))
        batch.add_column(sa.Column('verification_sent_at', sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column('verification_expires_at', sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column('password_reset_token_hash', sa.String(length=128), nullable=True))
        batch.add_column(sa.Column('password_reset_sent_at', sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column('password_reset_expires_at', sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))
        batch.create_index('ix_auth_users_verification_token_hash', ['verification_token_hash'], unique=False)
        batch.create_index('ix_auth_users_password_reset_token_hash', ['password_reset_token_hash'], unique=False)

    with op.batch_alter_table('auth_sessions') as batch:
        batch.add_column(sa.Column('ip_address', sa.String(length=64), nullable=True))
        batch.add_column(sa.Column('user_agent', sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('auth_sessions') as batch:
        batch.drop_column('user_agent')
        batch.drop_column('ip_address')

    with op.batch_alter_table('auth_users') as batch:
        batch.drop_index('ix_auth_users_password_reset_token_hash')
        batch.drop_index('ix_auth_users_verification_token_hash')
        batch.drop_column('locked_until')
        batch.drop_column('failed_login_attempts')
        batch.drop_column('password_reset_expires_at')
        batch.drop_column('password_reset_sent_at')
        batch.drop_column('password_reset_token_hash')
        batch.drop_column('verification_expires_at')
        batch.drop_column('verification_sent_at')
        batch.drop_column('verification_token_hash')
        batch.drop_column('email_verified_at')
