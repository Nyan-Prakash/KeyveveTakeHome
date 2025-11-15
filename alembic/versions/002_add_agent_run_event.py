"""Add agent_run_event table for SSE streaming

Revision ID: 002
Revises: 001
Create Date: 2025-11-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create agent_run_event table for SSE streaming."""

    # Get the database dialect to handle PostgreSQL vs SQLite differences
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == 'postgresql'
    
    if is_postgresql:
        uuid_type = postgresql.UUID(as_uuid=True)
    else:
        uuid_type = sa.String(36)  # Store UUIDs as strings in SQLite

    # Create agent_run_event table
    op.create_table(
        "agent_run_event",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", uuid_type, nullable=False),
        sa.Column("org_id", uuid_type, nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON() if is_postgresql else sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["agent_run.run_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["org_id"], ["org.org_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_event_run_ts", "agent_run_event", ["run_id", "ts"])
    op.create_index("idx_event_org_run", "agent_run_event", ["org_id", "run_id"])


def downgrade() -> None:
    """Drop agent_run_event table."""

    op.drop_index("idx_event_org_run", table_name="agent_run_event")
    op.drop_index("idx_event_run_ts", table_name="agent_run_event")
    op.drop_table("agent_run_event")
