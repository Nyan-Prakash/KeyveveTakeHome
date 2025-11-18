"""Add chunk_text and chunk_metadata columns to embedding table

Revision ID: 003
Revises: 002
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    """Add chunk_text and chunk_metadata columns to embedding table."""
    # Add chunk_text column
    op.add_column('embedding', sa.Column('chunk_text', sa.Text(), nullable=True))
    
    # Add chunk_metadata column - use JSON for SQLite compatibility
    # This will be JSONB in PostgreSQL and JSON in SQLite
    try:
        # Try PostgreSQL JSONB first
        op.add_column('embedding', sa.Column('chunk_metadata', JSONB, nullable=True))
    except Exception:
        # Fallback to regular JSON for SQLite
        op.add_column('embedding', sa.Column('chunk_metadata', sa.JSON(), nullable=True))


def downgrade():
    """Remove chunk_text and chunk_metadata columns from embedding table."""
    op.drop_column('embedding', 'chunk_metadata')
    op.drop_column('embedding', 'chunk_text')