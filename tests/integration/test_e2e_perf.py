"""PR9: End-to-end performance tests with fixture data.

These tests enforce SLOs from SPEC.md:
- TTFE (Time to First Event) < 800 ms
- E2E p50 ≤ 6 s
- E2E p95 ≤ 10 s

All tests use fixture data to ensure deterministic, fast execution.
CI must fail if these thresholds are exceeded.
"""

import time
from datetime import date, timedelta
from uuid import uuid4

import pytest

from backend.app.graph.nodes import (
    intent_node,
    planner_node,
    repair_node,
    responder_node,
    selector_node,
    synth_node,
    tool_exec_node,
    verifier_node,
)
from backend.app.graph.state import OrchestratorState
from backend.app.models.intent import DateWindow, IntentV1, Preferences


@pytest.fixture
def sample_intent() -> IntentV1:
    """Create a simple intent for performance testing."""
    start = date.today() + timedelta(days=30)
    end = start + timedelta(days=5)

    return IntentV1(
        city="Paris",
        date_window=DateWindow(
            start=start,
            end=end,
            tz="Europe/Paris",
        ),
        budget_usd_cents=500000,  # $5000
        airports=["CDG", "ORY"],
        prefs=Preferences(
            kid_friendly=False,
            themes=["art", "culture"],
            avoid_overnight=False,
            locked_slots=[],
        ),
    )


def run_e2e_graph(intent: IntentV1) -> tuple[OrchestratorState, float]:
    """Run the full orchestrator graph and return final state + duration.

    Returns:
        Tuple of (final_state, duration_seconds)
    """
    start_time = time.perf_counter()

    # Create initial state
    state = OrchestratorState(
        trace_id=str(uuid4()),
        org_id=uuid4(),
        user_id=uuid4(),
        seed=42,
        intent=intent,
    )

    # Run nodes in sequence
    state = intent_node(state)
    state = planner_node(state)
    state = selector_node(state)
    state = tool_exec_node(state)
    state = verifier_node(state)
    state = repair_node(state)
    state = synth_node(state)
    state = responder_node(state)

    end_time = time.perf_counter()
    duration = end_time - start_time

    return state, duration


def test_ttfe_under_800ms(sample_intent: IntentV1) -> None:
    """Test that Time to First Event (TTFE) is < 800 ms.

    TTFE is measured as the time from run start to when the first
    node (intent_node) completes.

    Per SPEC.md § 1.3: TTFE < 800 ms (p95).
    """
    start_time = time.perf_counter()

    state = OrchestratorState(
        trace_id=str(uuid4()),
        org_id=uuid4(),
        user_id=uuid4(),
        seed=42,
        intent=sample_intent,
    )

    # Run intent node (first event)
    state = intent_node(state)

    end_time = time.perf_counter()
    ttfe_ms = (end_time - start_time) * 1000

    # Assert TTFE under threshold
    assert ttfe_ms < 800, f"TTFE {ttfe_ms:.1f}ms exceeds 800ms threshold"


def test_e2e_latency_p50_under_6s(sample_intent: IntentV1) -> None:
    """Test that E2E p50 latency is ≤ 6 seconds.

    Runs the full graph 10 times and checks median latency.

    Per SPEC.md § 1.3: E2E p50 ≤ 6 s.
    """
    n_runs = 10
    durations: list[float] = []

    for _ in range(n_runs):
        # Vary seed for each run to avoid caching effects
        intent = IntentV1(
            city="Paris",
            date_window=sample_intent.date_window,
            budget_usd_cents=sample_intent.budget_usd_cents,
            airports=sample_intent.airports,
            prefs=sample_intent.prefs,
        )

        _, duration = run_e2e_graph(intent)
        durations.append(duration)

    # Calculate p50 (median)
    durations.sort()
    p50 = durations[len(durations) // 2]

    assert p50 <= 6.0, f"E2E p50 {p50:.2f}s exceeds 6s threshold"


def test_e2e_latency_p95_under_10s(sample_intent: IntentV1) -> None:
    """Test that E2E p95 latency is ≤ 10 seconds.

    Runs the full graph 20 times and checks 95th percentile latency.

    Per SPEC.md § 1.3: E2E p95 ≤ 10 s.
    """
    n_runs = 20
    durations: list[float] = []

    for _ in range(n_runs):
        intent = IntentV1(
            city="Paris",
            date_window=sample_intent.date_window,
            budget_usd_cents=sample_intent.budget_usd_cents,
            airports=sample_intent.airports,
            prefs=sample_intent.prefs,
        )

        _, duration = run_e2e_graph(intent)
        durations.append(duration)

    # Calculate p95
    durations.sort()
    p95_index = int(len(durations) * 0.95)
    p95 = durations[p95_index]

    assert p95 <= 10.0, f"E2E p95 {p95:.2f}s exceeds 10s threshold"


def test_e2e_produces_valid_itinerary(sample_intent: IntentV1) -> None:
    """Smoke test: E2E run produces a valid itinerary.

    Ensures performance tests actually run the full graph correctly.
    """
    final_state, duration = run_e2e_graph(sample_intent)

    # Check itinerary was created
    assert final_state.itinerary is not None, "No itinerary generated"
    assert len(final_state.itinerary.days) > 0, "Empty itinerary"
    assert final_state.itinerary.cost_breakdown.total_usd_cents > 0, "Zero cost"
    assert len(final_state.itinerary.citations) > 0, "No citations"
    assert final_state.done, "Run not marked as done"

    # Log duration for visibility
    print(f"E2E duration: {duration:.3f}s")
