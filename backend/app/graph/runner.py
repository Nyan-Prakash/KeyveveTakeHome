"""LangGraph runner for orchestrating travel planning."""

import random
import threading
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from langgraph.graph import StateGraph
from sqlalchemy.orm import Session

from backend.app.db.agent_events import append_event
from backend.app.db.models.agent_run import AgentRun
from backend.app.models.intent import IntentV1

from .nodes import (
    intent_node,
    planner_node,
    repair_node,
    responder_node,
    selector_node,
    synth_node,
    tool_exec_node,
    verifier_node,
)
from .state import OrchestratorState


def _build_graph() -> Any:
    """Build the LangGraph orchestrator graph.

    Graph flow:
        Intent → Planner → Selector → ToolExec → Verifier → Repair → Synth → Responder

    Returns:
        Compiled LangGraph graph
    """
    # Create graph with typed state
    graph = StateGraph(OrchestratorState)

    # Add nodes
    graph.add_node("intent", intent_node)
    graph.add_node("planner", planner_node)
    graph.add_node("selector", selector_node)
    graph.add_node("tool_exec", tool_exec_node)
    graph.add_node("verifier", verifier_node)
    graph.add_node("repair", repair_node)
    graph.add_node("synth", synth_node)
    graph.add_node("responder", responder_node)

    # Define edges (linear flow for PR4)
    graph.set_entry_point("intent")
    graph.add_edge("intent", "planner")
    graph.add_edge("planner", "selector")
    graph.add_edge("selector", "tool_exec")
    graph.add_edge("tool_exec", "verifier")
    graph.add_edge("verifier", "repair")
    graph.add_edge("repair", "synth")
    graph.add_edge("synth", "responder")
    graph.set_finish_point("responder")

    return graph.compile()


def _execute_graph(
    session: Session,
    run_id: UUID,
    org_id: UUID,
    user_id: UUID,
    trace_id: str,
    intent: IntentV1,
    seed: int,
) -> None:
    """Execute the LangGraph in a background thread.

    This function runs the graph and emits events to the event log
    as it progresses through nodes.

    Args:
        session: Database session
        run_id: Agent run ID
        org_id: Organization ID
        user_id: User ID
        trace_id: Trace ID for this run
        intent: User intent
        seed: Random seed for determinism
    """
    try:
        # Build graph
        graph = _build_graph()

        # Initialize state
        initial_state = OrchestratorState(
            trace_id=trace_id,
            org_id=org_id,
            user_id=user_id,
            seed=seed,
            intent=intent,
        )

        # Execute graph
        node_sequence = [
            "intent",
            "planner",
            "selector",
            "tool_exec",
            "verifier",
            "repair",
            "synth",
            "responder",
        ]

        current_state = initial_state
        for node_name in node_sequence:
            # Emit node start event
            append_event(
                session,
                org_id,
                run_id,
                kind="node_event",
                payload={
                    "node": node_name,
                    "status": "running",
                    "ts": datetime.now(UTC).isoformat(),
                    "message": f"Running {node_name} node...",
                },
            )

            # Execute node
            node_fn = graph.nodes[node_name].func
            current_state = node_fn(current_state)

            # Emit node completion event
            append_event(
                session,
                org_id,
                run_id,
                kind="node_event",
                payload={
                    "node": node_name,
                    "status": "completed",
                    "ts": datetime.now(UTC).isoformat(),
                    "message": f"Completed {node_name} node",
                },
            )

        # Update agent run with final status
        agent_run = session.get(AgentRun, run_id)
        if agent_run:
            agent_run.status = "completed"
            agent_run.completed_at = datetime.now(UTC)
            if current_state.plan:
                agent_run.plan_snapshot = [current_state.plan.model_dump(mode="json")]
            session.commit()

        # Emit final completion event
        append_event(
            session,
            org_id,
            run_id,
            kind="node_event",
            payload={
                "node": "final",
                "status": "completed",
                "ts": datetime.now(UTC).isoformat(),
                "message": "Run completed successfully",
            },
        )

    except Exception as e:
        # Handle errors
        agent_run = session.get(AgentRun, run_id)
        if agent_run:
            agent_run.status = "error"
            agent_run.completed_at = datetime.now(UTC)
            session.commit()

        append_event(
            session,
            org_id,
            run_id,
            kind="node_event",
            payload={
                "node": "error",
                "status": "error",
                "ts": datetime.now(UTC).isoformat(),
                "message": f"Error: {str(e)}",
            },
        )


def start_run(
    session: Session,
    org_id: UUID,
    user_id: UUID,
    intent: IntentV1,
    *,
    seed: int | None = None,
) -> UUID:
    """Start a new agent run.

    Creates an agent_run row, initializes the orchestrator state,
    and kicks off the LangGraph execution in a background thread.

    Args:
        session: Database session
        org_id: Organization ID for tenancy
        user_id: User ID who initiated this run
        intent: User's travel intent
        seed: Optional random seed for determinism

    Returns:
        UUID of the created agent run

    Note:
        The graph execution happens asynchronously in a background thread.
        Use the SSE endpoint to monitor progress.
    """
    # Generate seed if not provided
    if seed is None:
        seed = random.randint(0, 2**31 - 1)

    # Generate trace ID
    trace_id = str(uuid4())

    # Create agent run
    agent_run = AgentRun(
        run_id=uuid4(),
        org_id=org_id,
        user_id=user_id,
        intent=intent.model_dump(mode="json"),
        status="running",
        trace_id=trace_id,
        created_at=datetime.now(UTC),
    )
    session.add(agent_run)
    session.commit()
    session.refresh(agent_run)

    run_id = agent_run.run_id

    # Emit initial event
    append_event(
        session,
        org_id,
        run_id,
        kind="node_event",
        payload={
            "node": "init",
            "status": "running",
            "ts": datetime.now(UTC).isoformat(),
            "message": "Starting agent run...",
        },
    )

    # Start graph execution in background thread
    thread = threading.Thread(
        target=_execute_graph,
        args=(session, run_id, org_id, user_id, trace_id, intent, seed),
        daemon=True,
    )
    thread.start()

    return run_id
