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

    # Create agent_run_event table
    op.create_table(
        "agent_run_event",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
