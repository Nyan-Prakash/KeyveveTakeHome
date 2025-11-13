"""init_db

Revision ID: 0001
Revises:
Create Date: 2025-01-12 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create orgs table
    op.create_table(
        'orgs',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('org_id', UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'email', name='uq_user_org_email')
    )
    op.create_index('ix_users_org_id', 'users', ['org_id'])
    op.create_index('ix_users_org_id_email', 'users', ['org_id', 'email'])

    # Create refresh_tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('user_id', UUID(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])

    # Create destinations table
    op.create_table(
        'destinations',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('org_id', UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'slug', name='uq_destination_org_slug')
    )
    op.create_index('ix_destinations_org_id', 'destinations', ['org_id'])

    # Create knowledge_items table
    op.create_table(
        'knowledge_items',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('org_id', UUID(), nullable=False),
        sa.Column('destination_id', UUID(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('kind', sa.String(length=50), nullable=False),
        sa.Column('raw_source_ref', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_knowledge_items_org_id', 'knowledge_items', ['org_id'])
    op.create_index('ix_knowledge_items_org_id_destination_id', 'knowledge_items', ['org_id', 'destination_id'])

    # Create embeddings table
    op.create_table(
        'embeddings',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('org_id', UUID(), nullable=False),
        sa.Column('knowledge_item_id', UUID(), nullable=False),
        sa.Column('vector', sa.LargeBinary(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_embeddings_org_id', 'embeddings', ['org_id'])
    op.create_index('ix_embeddings_org_id_knowledge_item_id', 'embeddings', ['org_id', 'knowledge_item_id'])

    # Create agent_runs table
    op.create_table(
        'agent_runs',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('org_id', UUID(), nullable=False),
        sa.Column('user_id', UUID(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('rng_seed', sa.Integer(), nullable=False),
        sa.Column('cost_usd_cents', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('plan_snapshot', JSONB(), nullable=True),
        sa.Column('error_summary', sa.Text(), nullable=True),
        sa.Column('trace_id', sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_agent_runs_org_id', 'agent_runs', ['org_id'])
    op.create_index('ix_agent_runs_org_user_started', 'agent_runs', ['org_id', 'user_id', 'started_at'])

    # Create itineraries table
    op.create_table(
        'itineraries',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('org_id', UUID(), nullable=False),
        sa.Column('agent_run_id', UUID(), nullable=False),
        sa.Column('itinerary_json', JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_itineraries_org_id', 'itineraries', ['org_id'])
    op.create_index('ix_itineraries_org_id_agent_run_id', 'itineraries', ['org_id', 'agent_run_id'])

    # Create idempotency_keys table
    op.create_table(
        'idempotency_keys',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('user_id', UUID(), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('ttl_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('response_hash', sa.String(length=64), nullable=True),
        sa.Column('headers_hash', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'key', name='uq_idempotency_user_key')
    )
    op.create_index('ix_idempotency_keys_ttl_until', 'idempotency_keys', ['ttl_until'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('ix_idempotency_keys_ttl_until', table_name='idempotency_keys')
    op.drop_table('idempotency_keys')

    op.drop_index('ix_itineraries_org_id_agent_run_id', table_name='itineraries')
    op.drop_index('ix_itineraries_org_id', table_name='itineraries')
    op.drop_table('itineraries')

    op.drop_index('ix_agent_runs_org_user_started', table_name='agent_runs')
    op.drop_index('ix_agent_runs_org_id', table_name='agent_runs')
    op.drop_table('agent_runs')

    op.drop_index('ix_embeddings_org_id_knowledge_item_id', table_name='embeddings')
    op.drop_index('ix_embeddings_org_id', table_name='embeddings')
    op.drop_table('embeddings')

    op.drop_index('ix_knowledge_items_org_id_destination_id', table_name='knowledge_items')
    op.drop_index('ix_knowledge_items_org_id', table_name='knowledge_items')
    op.drop_table('knowledge_items')

    op.drop_index('ix_destinations_org_id', table_name='destinations')
    op.drop_table('destinations')

    op.drop_index('ix_refresh_tokens_user_id', table_name='refresh_tokens')
    op.drop_table('refresh_tokens')

    op.drop_index('ix_users_org_id_email', table_name='users')
    op.drop_index('ix_users_org_id', table_name='users')
    op.drop_table('users')

    op.drop_table('orgs')
