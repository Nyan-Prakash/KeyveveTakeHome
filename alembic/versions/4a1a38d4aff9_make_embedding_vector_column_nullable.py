"""Make embedding vector column nullable

Revision ID: 4a1a38d4aff9
Revises: 003
Create Date: 2025-11-18 14:43:40.703766

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4a1a38d4aff9'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make the vector column nullable in the embedding table."""
    # For SQLite, we need to recreate the table since it doesn't support ALTER COLUMN
    # First, create a temporary table with the correct schema
    op.execute("""
        CREATE TABLE embedding_temp (
            embedding_id VARCHAR(36) NOT NULL,
            item_id VARCHAR(36) NOT NULL,
            vector TEXT,
            created_at DATETIME NOT NULL,
            chunk_text TEXT,
            chunk_metadata JSON,
            PRIMARY KEY (embedding_id),
            FOREIGN KEY(item_id) REFERENCES knowledge_item (item_id) ON DELETE CASCADE
        )
    """)
    
    # Copy data from old table to new table
    op.execute("""
        INSERT INTO embedding_temp 
        SELECT embedding_id, item_id, vector, created_at, chunk_text, chunk_metadata
        FROM embedding
    """)
    
    # Drop the old table
    op.drop_table('embedding')
    
    # Rename the temporary table
    op.execute("ALTER TABLE embedding_temp RENAME TO embedding")


def downgrade() -> None:
    """Make the vector column NOT NULL again."""
    # Reverse operation - recreate table with NOT NULL vector
    op.execute("""
        CREATE TABLE embedding_temp (
            embedding_id VARCHAR(36) NOT NULL,
            item_id VARCHAR(36) NOT NULL,
            vector TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            chunk_text TEXT,
            chunk_metadata JSON,
            PRIMARY KEY (embedding_id),
            FOREIGN KEY(item_id) REFERENCES knowledge_item (item_id) ON DELETE CASCADE
        )
    """)
    
    # Copy data (this will fail if there are NULL vectors)
    op.execute("""
        INSERT INTO embedding_temp 
        SELECT embedding_id, item_id, vector, created_at, chunk_text, chunk_metadata
        FROM embedding
        WHERE vector IS NOT NULL
    """)
    
    op.drop_table('embedding')
    op.execute("ALTER TABLE embedding_temp RENAME TO embedding")
