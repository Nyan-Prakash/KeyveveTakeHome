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


class EditPlanRequest(BaseModel):
    """Request to edit an existing plan with what-if changes."""

    delta_budget_usd_cents: int | None = None
    shift_dates_days: int | None = None
    new_prefs: dict[str, Any] | None = None
    description: str | None = None  # Human-readable description of the change


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


@router.get("/{run_id}")
def get_plan(
    run_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """Get the final itinerary and metadata for a completed run.

    Returns the full itinerary plus system info for the right-rail UI:
    - itinerary: ItineraryV1 with days, cost_breakdown, decisions, citations
    - violations: List of constraint violations
    - node_timings: Execution time per node (if available)
    - tool_call_counts: Tool usage counts (if available)
    - status: Run status (running/completed/error)

    Args:
        run_id: Agent run ID
        current_user: Authenticated user context
        session: Database session

    Returns:
        Dict with itinerary and metadata

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

    # Load the itinerary if it exists
    from backend.app.db.models.itinerary import Itinerary

    stmt = select(Itinerary).where(Itinerary.run_id == run_id)
    itinerary_record = session.execute(stmt).scalar_one_or_none()

    # Build response
    response: dict[str, Any] = {
        "run_id": str(run_id),
        "status": agent_run.status,
        "created_at": (
            agent_run.created_at.isoformat() if agent_run.created_at else None
        ),
        "completed_at": (
            agent_run.completed_at.isoformat() if agent_run.completed_at else None
        ),
    }

    # Add itinerary if available
    if itinerary_record:
        response["itinerary"] = itinerary_record.data

    # Extract violations from plan_snapshot if available
    # (Last snapshot typically contains final state with violations)
    if agent_run.plan_snapshot and len(agent_run.plan_snapshot) > 0:
        last_snapshot = agent_run.plan_snapshot[-1]
        if "violations" in last_snapshot:
            response["violations"] = last_snapshot["violations"]
        else:
            response["violations"] = []
    else:
        response["violations"] = []

    # Extract tool metrics from tool_log if available
    if agent_run.tool_log:
        # Tool call counts
        if "tool_call_counts" in agent_run.tool_log:
            response["tool_call_counts"] = agent_run.tool_log["tool_call_counts"]
        else:
            response["tool_call_counts"] = {}

        # Node timings
        if "node_timings" in agent_run.tool_log:
            response["node_timings"] = agent_run.tool_log["node_timings"]
        else:
            response["node_timings"] = {}
            
        # Weather data for frontend display
        if "weather_by_date" in agent_run.tool_log:
            response["weather_by_date"] = agent_run.tool_log["weather_by_date"]
    else:
        response["tool_call_counts"] = {}
        response["node_timings"] = {}
        response["weather_by_date"] = {}

    # Add cost if available
    if agent_run.cost_usd is not None:
        response["cost_usd"] = float(agent_run.cost_usd)

    return response


@router.post("/{run_id}/edit", response_model=StartPlanResponse, status_code=status.HTTP_201_CREATED)
def edit_plan(
    run_id: UUID,
    edit_request: EditPlanRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> StartPlanResponse:
    """Apply what-if edits to an existing plan and create a new run.

    This endpoint allows users to make iterative refinements to their itinerary:
    - Change budget (e.g., "Make it $300 cheaper")
    - Shift dates forward/backward
    - Update preferences (e.g., "More kid-friendly")

    The original run is preserved, and a new run is created with the modified intent.

    Args:
        run_id: Original run ID to base edits on
        edit_request: What-if edit parameters
        current_user: Authenticated user context
        session: Database session

    Returns:
        StartPlanResponse with new run_id
    """
    # Load original run and verify org scoping
    stmt = select(AgentRun).where(AgentRun.run_id == run_id)
    original_run = session.execute(stmt).scalar_one_or_none()

    if not original_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original run not found",
        )

    if original_run.org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this run",
        )

    # Clone and modify the intent
    original_intent = original_run.intent
    if not isinstance(original_intent, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Original run has invalid intent format",
        )

    # Deep copy the intent
    import copy
    modified_intent = copy.deepcopy(original_intent)

    # Apply delta budget
    if edit_request.delta_budget_usd_cents is not None:
        current_budget = modified_intent.get("budget_usd_cents", 0)
        modified_intent["budget_usd_cents"] = max(
            10000,  # Minimum $100 budget
            current_budget + edit_request.delta_budget_usd_cents,
        )

    # Apply date shift
    if edit_request.shift_dates_days is not None:
        from datetime import date, timedelta

        date_window = modified_intent.get("date_window", {})
        if "start" in date_window:
            start_date = date.fromisoformat(date_window["start"])
            start_date += timedelta(days=edit_request.shift_dates_days)
            date_window["start"] = start_date.isoformat()

        if "end" in date_window:
            end_date = date.fromisoformat(date_window["end"])
            end_date += timedelta(days=edit_request.shift_dates_days)
            date_window["end"] = end_date.isoformat()

        modified_intent["date_window"] = date_window

    # Apply preference updates
    if edit_request.new_prefs is not None:
        current_prefs = modified_intent.get("prefs", {})
        current_prefs.update(edit_request.new_prefs)
        modified_intent["prefs"] = current_prefs

    # Validate the modified intent
    try:
        validated_intent = IntentV1.model_validate(modified_intent)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Modified intent is invalid: {str(e)}",
        ) from e

    # Start a new run with the modified intent
    new_run_id = start_run(
        session=session,
        org_id=current_user.org_id,
        user_id=current_user.user_id,
        intent=validated_intent,
    )

    return StartPlanResponse(run_id=new_run_id)
