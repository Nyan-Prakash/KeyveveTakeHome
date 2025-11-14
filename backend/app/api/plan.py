"""Plan API endpoints for starting and streaming agent runs."""

import asyncio
import time
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from backend.app.api.auth import CurrentUser, get_current_user
from backend.app.db.agent_events import list_events_since
from backend.app.db.models.agent_run import AgentRun
from backend.app.db.session import get_session_factory
from backend.app.graph import start_run
from backend.app.models.intent import IntentV1

router = APIRouter(prefix="/plan", tags=["plan"])


class StartPlanResponse(BaseModel):
    """Response from starting a plan."""

    run_id: UUID


def get_db_session() -> Generator[Session, None, None]:
    """Dependency to get a database session."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


@router.post("", response_model=StartPlanResponse, status_code=status.HTTP_201_CREATED)
def create_plan(
    intent: IntentV1,
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> StartPlanResponse:
    """Start a new travel plan generation.

    Creates an agent run and begins asynchronous processing.
    Use the returned run_id to stream progress via /plan/{run_id}/stream.

    Args:
        intent: User's travel intent
        current_user: Authenticated user context
        session: Database session

    Returns:
        StartPlanResponse with run_id
    """
    # Start the run in the background
    run_id = start_run(
        session=session,
        org_id=current_user.org_id,
        user_id=current_user.user_id,
        intent=intent,
    )

    return StartPlanResponse(run_id=run_id)


@router.get("/{run_id}/stream")
async def stream_plan(
    run_id: UUID,
    last_ts: str | None = Query(
        None, description="ISO timestamp of last received event"
    ),
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> EventSourceResponse:
    """Stream agent run progress via Server-Sent Events (SSE).

    Features:
    - Bearer auth required
    - Heartbeat every 1 second
    - Throttle ≤10 events/second
    - Resume by last_ts
    - Org scoping (other org's run_id = 403)

    Args:
        run_id: Agent run ID
        last_ts: Optional ISO timestamp to resume from
        current_user: Authenticated user context
        session: Database session

    Returns:
        SSE stream of events

    Raises:
        HTTPException: 404 if run not found, 403 if org mismatch
    """

    # Load agent run and verify org scoping
    stmt = select(AgentRun).where(AgentRun.run_id == run_id)
    agent_run = session.execute(stmt).scalar_one_or_none()

    if not agent_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run not found",
        )

    if agent_run.org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this run",
        )

    # Parse last_ts if provided
    resume_ts: datetime | None = None
    if last_ts:
        try:
            resume_ts = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid last_ts format (use ISO 8601)",
            ) from e

    async def event_generator() -> Any:
        """Generate SSE events for the stream.

        Yields:
            dict: SSE event data
        """
        last_sent_ts = resume_ts
        last_heartbeat = time.time()
        events_this_second = 0
        second_start = time.time()

        # Replay events if resuming
        if last_sent_ts:
            replay_events = list_events_since(
                session, current_user.org_id, run_id, last_sent_ts
            )
            for event in replay_events[:10]:  # Limit to 10 for initial replay
                yield {
                    "event": "replay",
                    "data": {
                        "id": event.id,
                        "kind": event.kind,
                        "ts": event.ts.isoformat(),
                        "payload": event.payload,
                    },
                }
                last_sent_ts = event.ts
                events_this_second += 1

        # Stream loop
        while True:
            current_time = time.time()

            # Reset event counter every second
            if current_time - second_start >= 1.0:
                events_this_second = 0
                second_start = current_time

            # Check for new events
            new_events = list_events_since(
                session, current_user.org_id, run_id, last_sent_ts
            )

            # Throttle to ≤10 events/second
            events_to_send = new_events[: (10 - events_this_second)]

            if events_to_send:
                for event in events_to_send:
                    yield {
                        "event": "message",
                        "data": {
                            "id": event.id,
                            "kind": event.kind,
                            "ts": event.ts.isoformat(),
                            "payload": event.payload,
                        },
                    }
                    last_sent_ts = event.ts
                    events_this_second += 1
                last_heartbeat = current_time

            # Send heartbeat if no events in last second
            elif current_time - last_heartbeat >= 1.0:
                yield {
                    "event": "heartbeat",
                    "data": {
                        "ts": datetime.now(UTC).isoformat(),
                    },
                }
                last_heartbeat = current_time

            # Check if run is complete
            session.expire_all()  # Refresh from DB
            stmt = select(AgentRun).where(AgentRun.run_id == run_id)
            agent_run = session.execute(stmt).scalar_one_or_none()

            if agent_run and agent_run.status in ("completed", "error"):
                # Send any remaining events
                final_events = list_events_since(
                    session, current_user.org_id, run_id, last_sent_ts
                )
                for event in final_events:
                    yield {
                        "event": "message",
                        "data": {
                            "id": event.id,
                            "kind": event.kind,
                            "ts": event.ts.isoformat(),
                            "payload": event.payload,
                        },
                    }
                # Exit loop
                break

            # Sleep briefly to avoid busy loop
            await asyncio.sleep(0.1)

    return EventSourceResponse(event_generator())
