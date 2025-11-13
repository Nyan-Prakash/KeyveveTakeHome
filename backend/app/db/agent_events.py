"""Helper functions for agent run event logging."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models.agent_run_event import AgentRunEvent


def append_event(
    session: Session,
    org_id: UUID,
    run_id: UUID,
    *,
    kind: str,
    payload: dict[str, Any],
) -> None:
    """Append an event to the agent run event log.

    Args:
        session: Database session
        org_id: Organization ID for tenancy
        run_id: Agent run ID
        kind: Event kind (e.g., "node_event", "heartbeat")
        payload: Event payload as JSON-serializable dict

    Note:
        All writes are scoped by org_id for tenancy.
    """
    event = AgentRunEvent(
        run_id=run_id,
        org_id=org_id,
        kind=kind,
        payload=payload,
        ts=datetime.now(UTC),
    )
    session.add(event)
    session.commit()


def list_events_since(
    session: Session,
    org_id: UUID,
    run_id: UUID,
    ts: datetime | None,
) -> list[AgentRunEvent]:
    """List events for a run since a given timestamp.

    Args:
        session: Database session
        org_id: Organization ID for tenancy
        run_id: Agent run ID
        ts: Timestamp to filter events (None = all events)

    Returns:
        List of events ordered by timestamp ascending

    Note:
        All reads are scoped by org_id for tenancy.
    """
    stmt = (
        select(AgentRunEvent)
        .where(AgentRunEvent.org_id == org_id, AgentRunEvent.run_id == run_id)
        .order_by(AgentRunEvent.ts)
    )

    if ts is not None:
        stmt = stmt.where(AgentRunEvent.ts > ts)

    return list(session.execute(stmt).scalars().all())
