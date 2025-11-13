"""Initial schema for PR2: org, user, refresh_token, destination, knowledge_item, embedding, agent_run, itinerary, idempotency

Revision ID: 001
Revises:
Create Date: 2025-11-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all PR2 tables with proper indexes and constraints."""

    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Create org table
    op.create_table(
        'org',
        sa.Column('org_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Create user table
    op.create_table(
        'user',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['org.org_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('org_id', 'email', name='uq_user_org_email'),
    )
    op.create_index('idx_user_org', 'user', ['org_id'])

    # Create refresh_token table
    op.create_table(
        'refresh_token',
        sa.Column('token_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token_hash', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.user_id'], ondelete='CASCADE'),
    )
    op.create_index('idx_refresh_user', 'refresh_token', ['user_id', 'revoked'])

    # Create destination table
    op.create_table(
        'destination',
        sa.Column('dest_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('city', sa.Text(), nullable=False),
        sa.Column('country', sa.Text(), nullable=False),
        sa.Column('geo', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('fixture_path', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['org.org_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('org_id', 'city', 'country', name='uq_destination_org_city_country'),
    )

    # Create knowledge_item table
    op.create_table(
        'knowledge_item',
        sa.Column('item_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('dest_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('item_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['org.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['dest_id'], ['destination.dest_id'], ondelete='SET NULL'),
    )
    op.create_index('idx_knowledge_org_dest', 'knowledge_item', ['org_id', 'dest_id'])

    # Create embedding table (pgvector)
    op.create_table(
        'embedding',
        sa.Column('embedding_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('vector', Vector(1536), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['item_id'], ['knowledge_item.item_id'], ondelete='CASCADE'),
    )
    # Create ivfflat index for vector similarity search
    op.execute(
        'CREATE INDEX idx_embedding_vector ON embedding USING ivfflat (vector vector_cosine_ops) WITH (lists = 100)'
    )

    # Create agent_run table
    op.create_table(
        'agent_run',
        sa.Column('run_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('intent', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('plan_snapshot', postgresql.ARRAY(postgresql.JSONB(astext_type=sa.Text())), nullable=True),
        sa.Column('tool_log', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('cost_usd', sa.Numeric(10, 6), nullable=True),
        sa.Column('trace_id', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['org.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.user_id'], ondelete='CASCADE'),
    )
    op.create_index('idx_run_org_user', 'agent_run', ['org_id', 'user_id', 'created_at'])

    # Create itinerary table
    op.create_table(
        'itinerary',
        sa.Column('itinerary_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['org.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['run_id'], ['agent_run.run_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.user_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('org_id', 'itinerary_id', name='uq_itinerary_org_id'),
    )
    op.create_index('idx_itinerary_org_user', 'itinerary', ['org_id', 'user_id', 'created_at'])

    # Create idempotency table
    op.create_table(
        'idempotency',
        sa.Column('key', sa.Text(), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ttl_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('body_hash', sa.Text(), nullable=False),
        sa.Column('headers_hash', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        'idx_idempotency_ttl',
        'idempotency',
        ['ttl_until'],
        postgresql_where=sa.text("status = 'completed'")
    )


def downgrade() -> None:
    """Drop all tables in reverse order."""
    op.drop_index('idx_idempotency_ttl', table_name='idempotency')
    op.drop_table('idempotency')

    op.drop_index('idx_itinerary_org_user', table_name='itinerary')
    op.drop_table('itinerary')

    op.drop_index('idx_run_org_user', table_name='agent_run')
    op.drop_table('agent_run')

    op.execute('DROP INDEX IF EXISTS idx_embedding_vector')
    op.drop_table('embedding')

    op.drop_index('idx_knowledge_org_dest', table_name='knowledge_item')
    op.drop_table('knowledge_item')

    op.drop_table('destination')

    op.drop_index('idx_refresh_user', table_name='refresh_token')
    op.drop_table('refresh_token')

    op.drop_index('idx_user_org', table_name='user')
    op.drop_table('user')

    op.drop_table('org')

    # Optionally drop pgvector extension (commented out to be safe)
    # op.execute('DROP EXTENSION IF EXISTS vector')
