#!/usr/bin/env python3
"""Simple integration test for LangGraph components."""

from datetime import date
from uuid import uuid4

from backend.app.graph.nodes import (
    intent_node,
    planner_node,
    selector_node,
    tool_exec_node,
    verifier_node,
    repair_node,
    synth_node,
    responder_node,
)
from backend.app.graph.state import OrchestratorState
from backend.app.models.intent import DateWindow, IntentV1, Preferences


def test_langgraph_nodes_integration():
    """Test that all LangGraph nodes work in sequence."""
    print("Testing LangGraph nodes integration...")
    
    # Create test intent
    intent = IntentV1(
        city="Paris",
        date_window=DateWindow(
            start=date(2025, 6, 1),
            end=date(2025, 6, 5),
            tz="Europe/Paris"
        ),
        budget_usd_cents=250_000,  # $2500
        airports=["CDG"],
        prefs=Preferences(
            kid_friendly=False,
            themes=["art"],
            avoid_overnight=False,
            locked_slots=[]
        )
    )
    
    # Initialize state
    state = OrchestratorState(
        trace_id=str(uuid4()),
        org_id=uuid4(),
        user_id=uuid4(),
        seed=42,
        intent=intent,
    )
    
    print(f"✓ Initial state created with trace_id: {state.trace_id}")
    
    # Test each node in sequence
    print("Running intent_node...")
    state = intent_node(state)
    print(f"✓ Intent processed. Messages: {len(state.messages)}")
    
    print("Running planner_node...")
    state = planner_node(state)
    print(f"✓ Planning completed. Plan has {len(state.plan.days) if state.plan else 0} days")
    
    print("Running selector_node...")
    state = selector_node(state)
    print(f"✓ Selection completed. Selected plan has {len(state.plan.days) if state.plan else 0} days")
    
    print("Running tool_exec_node...")
    state = tool_exec_node(state)
    print(f"✓ Tool execution completed. Tool call counts: {state.tool_call_counts}")
    
    print("Running verifier_node...")
    state = verifier_node(state)
    print(f"✓ Verification completed. Violations found: {len(state.violations)}")
    
    print("Running repair_node...")
    state = repair_node(state)
    print(f"✓ Repair completed. Repair applied: {'Yes' if hasattr(state, 'repair_log') and state.repair_log else 'No'}")
    
    print("Running synth_node...")
    state = synth_node(state)
    print(f"✓ Synthesis completed. Itinerary created: {'Yes' if state.itinerary else 'No'}")
    
    print("Running responder_node...")
    state = responder_node(state)
    print(f"✓ Response completed. Final message count: {len(state.messages)}")
    
    # Verify final state
    assert state.plan is not None, "Plan should be created"
    assert state.itinerary is not None, "Itinerary should be created"
    assert len(state.messages) > 0, "Messages should be logged"
    
    print("\n✅ All LangGraph nodes executed successfully!")
    print(f"Final itinerary has {len(state.itinerary.days)} days")
    print(f"Total messages logged: {len(state.messages)}")
    print(f"Node timings recorded: {list(state.node_timings.keys()) if state.node_timings else 'None'}")
    print(f"Tool call counts: {state.tool_call_counts}")
    print(f"Violations found: {len(state.violations)} - {[v.kind for v in state.violations]}")
    
    # Show sample activities from itinerary
    if state.itinerary and state.itinerary.days:
        first_day = state.itinerary.days[0]
        print(f"Sample day: {len(first_day.activities)} activities")
        if first_day.activities:
            activity = first_day.activities[0]
            print(f"  - {activity.name}: {activity.notes[:100]}...")
    
    return state


if __name__ == "__main__":
    test_langgraph_nodes_integration()
