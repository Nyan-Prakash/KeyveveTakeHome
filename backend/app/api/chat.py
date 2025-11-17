"""Chat API endpoints for conversational itinerary planning."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.auth import CurrentUser, get_current_user
from backend.app.api.plan import get_db_session
from backend.app.chat.edit_parser import parse_edit_request
from backend.app.chat.intent_extractor import Message, extract_intent_from_conversation
from backend.app.db.models.agent_run import AgentRun
from backend.app.graph import start_run
from backend.app.models.intent import IntentV1

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    """Single chat message in conversation."""

    role: str = Field(description="Role: 'user' or 'assistant'")
    content: str = Field(description="Message content")


class ChatPlanRequest(BaseModel):
    """Request to chat about travel planning."""

    message: str = Field(description="User's message")
    conversation_history: list[ChatMessage] = Field(
        default=[], description="Previous messages in conversation"
    )
    run_id: UUID | None = Field(
        default=None, description="Run ID if editing existing itinerary"
    )


class ChatPlanResponse(BaseModel):
    """Response from chat planning endpoint."""

    assistant_message: str = Field(description="Assistant's response")
    intent: dict[str, Any] | None = Field(
        default=None, description="Extracted intent (if complete)"
    )
    run_id: UUID | None = Field(
        default=None, description="Run ID (if planning started)"
    )
    is_complete: bool = Field(
        default=False, description="Whether intent extraction/edit is complete"
    )
    is_generating: bool = Field(
        default=False, description="Whether itinerary generation has started"
    )


@router.post("", response_model=ChatPlanResponse)
async def chat_plan(
    request: ChatPlanRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> ChatPlanResponse:
    """Chat interface for conversational travel planning.

    Supports two modes:
    1. Initial planning: Extract intent from conversation, start new run when complete
    2. Edit mode: Parse edit requests for existing itinerary, start new run with changes

    Args:
        request: Chat request with message and context
        current_user: Authenticated user
        session: Database session

    Returns:
        ChatPlanResponse with assistant message and run status
    """
    # Convert ChatMessage to Message for intent extractor
    history = [
        Message(role=msg.role, content=msg.content)
        for msg in request.conversation_history
    ]

    # Check if this is an edit request (run_id provided)
    if request.run_id:
        # Edit mode: Parse edit request and apply to existing itinerary
        return await _handle_edit_request(
            request.message, request.run_id, current_user, session
        )
    else:
        # Initial planning mode: Extract intent from conversation
        return await _handle_initial_planning(
            request.message, history, current_user, session
        )


async def _handle_initial_planning(
    user_message: str,
    conversation_history: list[Message],
    current_user: CurrentUser,
    session: Session,
) -> ChatPlanResponse:
    """Handle initial planning conversation - extract intent and start run when complete.

    Args:
        user_message: User's latest message
        conversation_history: Previous conversation
        current_user: Authenticated user
        session: Database session

    Returns:
        ChatPlanResponse with extraction result
    """
    # Extract intent from conversation
    result = await extract_intent_from_conversation(user_message, conversation_history)

    # If intent is complete, start a new run
    if result.is_complete and result.intent:
        run_id = start_run(
            session=session,
            org_id=current_user.org_id,
            user_id=current_user.user_id,
            intent=result.intent,
        )

        return ChatPlanResponse(
            assistant_message=result.assistant_message,
            intent=result.intent.model_dump(),
            run_id=run_id,
            is_complete=True,
            is_generating=True,
        )
    else:
        # Still gathering information
        return ChatPlanResponse(
            assistant_message=result.assistant_message,
            intent=None,
            run_id=None,
            is_complete=False,
            is_generating=False,
        )


async def _handle_edit_request(
    user_message: str,
    run_id: UUID,
    current_user: CurrentUser,
    session: Session,
) -> ChatPlanResponse:
    """Handle edit request for existing itinerary.

    Args:
        user_message: User's edit request
        run_id: ID of existing run to edit
        current_user: Authenticated user
        session: Database session

    Returns:
        ChatPlanResponse with edit result

    Raises:
        HTTPException: If run not found or access denied
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

    # Get current intent from original run
    original_intent_dict = original_run.intent
    if not isinstance(original_intent_dict, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Original run has invalid intent format",
        )

    current_intent = IntentV1.model_validate(original_intent_dict)

    # Parse edit request
    parsed_edit = await parse_edit_request(user_message, current_intent)

    # Check if we have actual changes to apply
    has_changes = (
        parsed_edit.delta_budget_usd_cents is not None
        or parsed_edit.shift_dates_days is not None
        or parsed_edit.new_prefs is not None
    )

    if not has_changes:
        # No changes parsed - return clarification message
        return ChatPlanResponse(
            assistant_message=parsed_edit.assistant_message,
            intent=None,
            run_id=None,
            is_complete=False,
            is_generating=False,
        )

    # Apply edits to create new intent
    import copy
    from datetime import timedelta

    modified_intent_dict = copy.deepcopy(original_intent_dict)

    # Apply budget delta
    if parsed_edit.delta_budget_usd_cents is not None:
        current_budget = modified_intent_dict.get("budget_usd_cents", 0)
        modified_intent_dict["budget_usd_cents"] = max(
            10000,  # Minimum $100 budget
            current_budget + parsed_edit.delta_budget_usd_cents,
        )

    # Apply date shift
    if parsed_edit.shift_dates_days is not None:
        from datetime import date

        date_window = modified_intent_dict.get("date_window", {})
        if "start" in date_window:
            start_date = date.fromisoformat(date_window["start"])
            start_date += timedelta(days=parsed_edit.shift_dates_days)
            date_window["start"] = start_date.isoformat()

        if "end" in date_window:
            end_date = date.fromisoformat(date_window["end"])
            end_date += timedelta(days=parsed_edit.shift_dates_days)
            date_window["end"] = end_date.isoformat()

        modified_intent_dict["date_window"] = date_window

    # Apply preference updates
    if parsed_edit.new_prefs is not None:
        current_prefs = modified_intent_dict.get("prefs", {})
        current_prefs.update(parsed_edit.new_prefs)
        modified_intent_dict["prefs"] = current_prefs

    # Validate the modified intent
    try:
        validated_intent = IntentV1.model_validate(modified_intent_dict)
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

    return ChatPlanResponse(
        assistant_message=parsed_edit.assistant_message,
        intent=validated_intent.model_dump(),
        run_id=new_run_id,
        is_complete=True,
        is_generating=True,
    )
