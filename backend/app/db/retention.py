"""Retention helpers for identifying stale data.

This module provides query helpers to identify expired rows according to retention policy.
Actual deletion will be wired later; these helpers only select candidates.

Retention Policies (from SPEC):
- agent_run.tool_log: 24 hours
- agent_run rows: 30 days
- itinerary rows: 90 days
- idempotency entries: 24 hours after TTL
"""

from datetime import datetime, timedelta

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import Session

from backend.app.db.models.agent_run import AgentRun
from backend.app.db.models.idempotency import IdempotencyEntry
from backend.app.db.models.itinerary import Itinerary


def get_stale_agent_runs(
    session: Session,
    retention_days: int = 30,
) -> Select[tuple[AgentRun]]:
    """
    Get agent runs older than retention period.

    Args:
        session: SQLAlchemy session
        retention_days: Days to retain agent runs (default: 30)

    Returns:
        SQLAlchemy Select statement for stale agent runs

    Example:
        stmt = get_stale_agent_runs(session, retention_days=30)
        stale_runs = session.execute(stmt).scalars().all()
        # Later: delete these runs
    """
    cutoff = datetime.now(datetime.UTC) - timedelta(days=retention_days)

    stmt = select(AgentRun).where(AgentRun.created_at < cutoff)

    return stmt


def get_stale_agent_run_tool_logs(
    session: Session,
    retention_hours: int = 24,
) -> Select[tuple[AgentRun]]:
    """
    Get agent runs with tool_log that should be cleared (heavy JSONB data).

    Args:
        session: SQLAlchemy session
        retention_hours: Hours to retain tool logs (default: 24)

    Returns:
        SQLAlchemy Select statement for agent runs with stale tool_log

    Note:
        This returns runs where tool_log should be set to NULL to save space.
        The run itself is retained, but the heavy tool_log field is cleared.

    Example:
        stmt = get_stale_agent_run_tool_logs(session)
        runs_to_clear = session.execute(stmt).scalars().all()
        for run in runs_to_clear:
            run.tool_log = None
        session.commit()
    """
    cutoff = datetime.now(datetime.UTC) - timedelta(hours=retention_hours)

    stmt = select(AgentRun).where(
        and_(
            AgentRun.created_at < cutoff,
            AgentRun.tool_log.isnot(None),  # Only runs that still have tool_log
        )
    )

    return stmt


def get_stale_itineraries(
    session: Session,
    retention_days: int = 90,
) -> Select[tuple[Itinerary]]:
    """
    Get itineraries older than retention period.

    Args:
        session: SQLAlchemy session
        retention_days: Days to retain itineraries (default: 90)

    Returns:
        SQLAlchemy Select statement for stale itineraries

    Example:
        stmt = get_stale_itineraries(session, retention_days=90)
        stale_itineraries = session.execute(stmt).scalars().all()
    """
    cutoff = datetime.now(datetime.UTC) - timedelta(days=retention_days)

    stmt = select(Itinerary).where(Itinerary.created_at < cutoff)

    return stmt


def get_stale_idempotency_entries(
    session: Session,
) -> Select[tuple[IdempotencyEntry]]:
    """
    Get idempotency entries that have expired (past ttl_until).

    Args:
        session: SQLAlchemy session

    Returns:
        SQLAlchemy Select statement for expired idempotency entries

    Example:
        stmt = get_stale_idempotency_entries(session)
        stale_entries = session.execute(stmt).scalars().all()
    """
    now = datetime.now(datetime.UTC)

    stmt = select(IdempotencyEntry).where(
        or_(
            IdempotencyEntry.ttl_until < now,
            # Also clean up old pending entries (stuck requests from 24h+ ago)
            and_(
                IdempotencyEntry.status == "pending",
                IdempotencyEntry.created_at < now - timedelta(hours=24),
            ),
        )
    )

    return stmt


def get_retention_summary(session: Session) -> dict[str, int]:
    """
    Get a summary of stale data counts across all retention policies.

    Args:
        session: SQLAlchemy session

    Returns:
        Dictionary with counts of stale records by type

    Example:
        summary = get_retention_summary(session)
        print(f"Stale agent runs: {summary['agent_runs']}")
        print(f"Agent runs with stale tool_log: {summary['agent_run_tool_logs']}")
        print(f"Stale itineraries: {summary['itineraries']}")
        print(f"Stale idempotency entries: {summary['idempotency_entries']}")
    """
    from sqlalchemy import func

    # Count stale agent runs
    agent_runs_stmt = get_stale_agent_runs(session)
    agent_runs_count = session.execute(
        select(func.count()).select_from(agent_runs_stmt.subquery())
    ).scalar()

    # Count agent runs with stale tool_log
    tool_logs_stmt = get_stale_agent_run_tool_logs(session)
    tool_logs_count = session.execute(
        select(func.count()).select_from(tool_logs_stmt.subquery())
    ).scalar()

    # Count stale itineraries
    itineraries_stmt = get_stale_itineraries(session)
    itineraries_count = session.execute(
        select(func.count()).select_from(itineraries_stmt.subquery())
    ).scalar()

    # Count stale idempotency entries
    idempotency_stmt = get_stale_idempotency_entries(session)
    idempotency_count = session.execute(
        select(func.count()).select_from(idempotency_stmt.subquery())
    ).scalar()

    return {
        "agent_runs": agent_runs_count or 0,
        "agent_run_tool_logs": tool_logs_count or 0,
        "itineraries": itineraries_count or 0,
        "idempotency_entries": idempotency_count or 0,
    }
