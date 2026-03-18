"""add auth tables

Revision ID: 0003_add_auth_tables
Revises: 0002_add_onboarding_completed
Create Date: 2026-03-08
"""

from alembic import op
import sqlalchemy as sa


revision = '0003_add_auth_tables'
down_revision = '0002_add_onboarding_completed'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'auth_users',
        sa.Column('user_id', sa.String(length=120), primary_key=True),
        sa.Column('learner_id', sa.String(length=120), sa.ForeignKey('learners.learner_id'), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('password_salt', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_auth_users_learner_id', 'auth_users', ['learner_id'], unique=True)
    op.create_index('ix_auth_users_email', 'auth_users', ['email'], unique=True)

    op.create_table(
        'auth_sessions',
        sa.Column('session_id', sa.String(length=120), primary_key=True),
        sa.Column('user_id', sa.String(length=120), sa.ForeignKey('auth_users.user_id'), nullable=False),
        sa.Column('learner_id', sa.String(length=120), sa.ForeignKey('learners.learner_id'), nullable=False),
        sa.Column('token_hash', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_auth_sessions_user_id', 'auth_sessions', ['user_id'], unique=False)
    op.create_index('ix_auth_sessions_learner_id', 'auth_sessions', ['learner_id'], unique=False)
    op.create_index('ix_auth_sessions_token_hash', 'auth_sessions', ['token_hash'], unique=True)
    op.create_index('ix_auth_sessions_expires_at', 'auth_sessions', ['expires_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_auth_sessions_expires_at', table_name='auth_sessions')
    op.drop_index('ix_auth_sessions_token_hash', table_name='auth_sessions')
    op.drop_index('ix_auth_sessions_learner_id', table_name='auth_sessions')
    op.drop_index('ix_auth_sessions_user_id', table_name='auth_sessions')
    op.drop_table('auth_sessions')
    op.drop_index('ix_auth_users_email', table_name='auth_users')
    op.drop_index('ix_auth_users_learner_id', table_name='auth_users')
    op.drop_table('auth_users')
