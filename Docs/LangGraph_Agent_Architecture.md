# LangGraph Agent Architecture

## Overview

The travel planning system uses a **LangGraph orchestrator** to coordinate multiple AI agents that work together to create personalized travel itineraries. This document explains how the system works, from receiving a user's travel request to delivering a complete itinerary.

## Codebase Structure

```
backend/app/
├── api/                          # API endpoints
│   ├── plan.py                   # POST /runs/start - Start agent run
│   ├── chat.py                   # GET /runs/{run_id}/events - SSE streaming
│   └── knowledge.py              # Knowledge base management
│
├── graph/                        # LangGraph orchestrator (THE CORE)
│   ├── runner.py                 # Graph execution engine + background thread
│   ├── nodes.py                  # All 10 node implementations
│   ├── state.py                  # OrchestratorState definition
│   └── rag.py                    # RAG retrieval logic
│
├── planning/                     # Planning algorithms
│   ├── planner.py                # build_candidate_plans()
│   ├── selector.py               # score_branches()
│   ├── budget_utils.py           # Budget calculation utilities
│   ├── simple_transit.py         # Transit injection between activities
│   └── types.py                  # Planning data structures
│
├── verify/                       # Constraint verifiers
│   ├── budget.py                 # Budget verification (10% slippage)
│   ├── feasibility.py            # Timing + venue hours + DST
│   ├── weather.py                # Weather constraint checking
│   └── preferences.py            # User preference matching
│
├── repair/                       # Repair engine
│   ├── engine.py                 # repair_plan() - bounded repair logic
│   └── models.py                 # RepairResult, PlanDiff
│
├── adapters/                     # External data adapters
│   ├── flights.py                # Flight data adapter
│   ├── lodging.py                # Lodging data adapter
│   ├── transit.py                # Transit data adapter
│   ├── weather.py                # Weather API adapter
│   ├── fx.py                     # Currency exchange adapter
│   └── mcp/                      # MCP (Model Context Protocol) adapters
│       ├── client.py             # MCP client implementation
│       └── weather.py            # MCP weather integration
│
├── models/                       # Pydantic data models
│   ├── intent.py                 # IntentV1 - user request
│   ├── plan.py                   # PlanV1, DayPlan, Slot, Choice
│   ├── itinerary.py              # ItineraryV1, Activity, Citation
│   ├── tool_results.py           # FlightOption, Lodging, Attraction
│   ├── violations.py             # Violation model
│   └── common.py                 # Shared types (Geo, Provenance, etc.)
│
└── db/                           # Database layer
    ├── models/                   # SQLAlchemy models
    │   ├── agent_run.py          # AgentRun table
    │   ├── itinerary.py          # Itinerary table
    │   ├── embedding.py          # Embedding table (RAG)
    │   └── agent_run_event.py    # Event streaming table
    └── agent_events.py           # append_event() - SSE event helper
```

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Request                             │
│              "Plan a 5-day trip to Munich"                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Start Run API                               │
│  - Creates AgentRun record in database                          │
│  - Generates unique trace_id                                    │
│  - Spawns background thread for execution                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   LangGraph Orchestrator                        │
│              (Sequential Node Execution)                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Node Flow Diagram

The LangGraph orchestrator executes **10 nodes** in sequence, each with a specific responsibility:

```
START
  │
  ▼
┌──────────────┐
│   1. INTENT  │  Parse and normalize user request
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   2. RAG     │  Retrieve knowledge about destination
└──────┬───────┘  (attractions, hotels, transit info)
       │
       ▼
┌──────────────┐
│  3. PLANNER  │  Generate 1-4 candidate plans
└──────┬───────┘  (uses RAG data to prevent hallucinations)
       │
       ▼
┌──────────────┐
│  4. SELECTOR │  Score and select best plan
└──────┬───────┘  (budget-aware scoring)
       │
       ▼
┌──────────────┐
│ 5. TOOL_EXEC │  Fetch real data (flights, weather, etc.)
└──────┬───────┘  (enriches plan with actual prices)
       │
       ▼
┌──────────────┐
│  6. RESOLVE  │  Map abstract choices to concrete options
└──────┬───────┘  (match planned items to fetched data)
       │
       ▼
┌──────────────┐
│ 7. VERIFIER  │  Check constraints (budget, timing, weather)
└──────┬───────┘  (identifies violations)
       │
       ▼
┌──────────────┐
│  8. REPAIR   │  Fix violations (≤2 moves/cycle, ≤3 cycles)
└──────┬───────┘  (automatic constraint repair)
       │
       ▼
┌──────────────┐
│   9. SYNTH   │  Build final itinerary with citations
└──────┬───────┘  ("no evidence, no claim" principle)
       │
       ▼
┌──────────────┐
│10.RESPONDER  │  Finalize and save to database
└──────┬───────┘
       │
       ▼
      END
```

---

## Detailed Node Explanations

### 1. Intent Node

📂 **Code:** [`backend/app/graph/nodes.py:692-700`](../backend/app/graph/nodes.py) - `intent_node()`

**Purpose:** Normalize and validate the user's travel request.

**Key Operations:**
- Pass-through processing (currently minimal)
- Logs the intent for downstream nodes
- Future: Will add intent classification and validation

**Input:** `state.intent` (user's travel preferences)
**Output:** Validated `OrchestratorState`

---

### 2. RAG Node (Retrieval-Augmented Generation)

📂 **Code:**
- Node: [`backend/app/graph/nodes.py:865-952`](../backend/app/graph/nodes.py) - `rag_node()`
- Retrieval: [`backend/app/graph/rag.py`](../backend/app/graph/rag.py) - `retrieve_knowledge_for_destination()`
- Extraction helpers: [`backend/app/graph/nodes.py:46-649`](../backend/app/graph/nodes.py):
  - `_extract_venue_info_from_rag()` (lines 46-196)
  - `_extract_flight_info_from_rag()` (lines 198-299)
  - `_extract_lodging_info_from_rag()` (lines 527-648)
  - `_extract_transit_info_from_rag()` (lines 411-524)

**Purpose:** Retrieve local knowledge about the destination to ground the planner in real data.

**Key Operations:**
```python
# 1. Query embedding database for destination knowledge
chunks = retrieve_knowledge_for_destination(org_id, city, limit=20)

# 2. Extract structured data using LLM
venue_info = _extract_venue_info_from_rag(chunks)
flight_info = _extract_flight_info_from_rag(chunks)
lodging_info = _extract_lodging_info_from_rag(chunks)
transit_info = _extract_transit_info_from_rag(chunks)

# 3. Convert to Attraction objects for planner
state.rag_attractions = [...]
```

**Why It Matters:**
- **Prevents hallucinations:** Planner uses real attractions instead of inventing fake ones
- **Local knowledge:** Leverages organization-specific travel data
- **Cost accuracy:** Extracts actual prices from knowledge base

**Data Extracted:**
- **Attractions:** Name, type, indoor/outdoor, cost
- **Flights:** Airlines, routes, prices
- **Lodging:** Hotels, tiers, amenities, prices
- **Transit:** Metro lines, bus routes, costs

---

### 3. Planner Node

📂 **Code:**
- Node: [`backend/app/graph/nodes.py:703-817`](../backend/app/graph/nodes.py) - `planner_node()`
- Planning logic: [`backend/app/planning/planner.py`](../backend/app/planning/planner.py) - `build_candidate_plans()`
- Budget utils: [`backend/app/planning/budget_utils.py`](../backend/app/planning/budget_utils.py)
- Transit injection: [`backend/app/planning/simple_transit.py`](../backend/app/planning/simple_transit.py) - `simple_inject_transit()`

**Purpose:** Generate multiple candidate itineraries based on user preferences.

**Algorithm:**
```
FOR each budget tier (preferred tiers based on user budget):
    1. Calculate daily spend allocations
    2. Create day-by-day schedule with slots
    3. Populate slots with RAG attractions (not hallucinated!)
    4. Inject transit between activities

    IF valid plan created:
        Add to candidate_plans

LIMIT: Generate 1-4 candidate plans (bounded fan-out)
```

**Key Features:**
- **Budget-aware:** Uses `build_budget_profile()` to determine flight/lodging tiers
- **RAG-grounded:** Only uses attractions from `state.rag_attractions`
- **Transit injection:** Automatically adds travel time between activities
- **Multiple candidates:** Creates alternatives for selector to choose from

**Example Output:**
```python
PlanV1(
    days=[
        DayPlan(
            date=2025-06-01,
            slots=[
                Slot(window=09:00-12:00, choices=[attraction_choice]),
                Slot(window=12:00-12:30, choices=[transit_choice]),
                Slot(window=12:30-15:00, choices=[attraction_choice]),
                ...
            ]
        ),
        ...
    ]
)
```

---

### 4. Selector Node

📂 **Code:**
- Node: [`backend/app/graph/nodes.py:820-862`](../backend/app/graph/nodes.py) - `selector_node()`
- Scoring logic: [`backend/app/planning/selector.py`](../backend/app/planning/selector.py) - `score_branches()`
- Types: [`backend/app/planning/types.py`](../backend/app/planning/types.py) - `BranchFeatures`

**Purpose:** Choose the best plan from candidates using feature-based scoring.

**Scoring Algorithm:**
```python
# Extract features from each candidate
for plan in candidates:
    features = [choice.features for choice in plan]
    branch_features.append(BranchFeatures(plan, features))

# Score using frozen statistics (PR6 selector)
scored_plans = score_branches(branch_features, intent)

# Select highest-scoring plan
best_plan = scored_plans[0]
```

**Scoring Factors:**
- **Budget fit:** How well does cost match user's budget?
- **Travel efficiency:** Minimize transit time
- **Preference alignment:** Match themes, indoor/outdoor, etc.
- **Diversity:** Balance different activity types

---

### 5. Tool Execution Node

📂 **Code:**
- Node: [`backend/app/graph/nodes.py:955-1479`](../backend/app/graph/nodes.py) - `tool_exec_node()`
- Adapters:
  - Weather: [`backend/app/adapters/weather.py`](../backend/app/adapters/weather.py) + [`backend/app/adapters/mcp/weather.py`](../backend/app/adapters/mcp/weather.py)
  - Flights: [`backend/app/adapters/flights.py`](../backend/app/adapters/flights.py)
  - Lodging: [`backend/app/adapters/lodging.py`](../backend/app/adapters/lodging.py)
  - Transit: [`backend/app/adapters/transit.py`](../backend/app/adapters/transit.py)
  - FX: [`backend/app/adapters/fx.py`](../backend/app/adapters/fx.py)

**Purpose:** Fetch real-world data to enrich the plan with actual prices and details.

**Data Sources:**

```
┌─────────────────────────────────────────────────────────────┐
│                      TOOL EXECUTION                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐      ┌──────────────┐                    │
│  │   Weather    │      │   Flights    │                    │
│  │   Adapter    │      │   Adapter    │                    │
│  │  (MCP/API)   │      │  (Fixtures)  │                    │
│  └──────┬───────┘      └──────┬───────┘                    │
│         │                      │                            │
│         ▼                      ▼                            │
│  state.weather_by_date   state.flights                     │
│                                                              │
│  ┌──────────────┐      ┌──────────────┐                    │
│  │   Lodging    │      │ Attractions  │                    │
│  │   Adapter    │      │  (from RAG)  │                    │
│  │  (RAG-based) │      │              │                    │
│  └──────┬───────┘      └──────┬───────┘                    │
│         │                      │                            │
│         ▼                      ▼                            │
│  state.lodgings          state.attractions                 │
│                                                              │
│  ┌──────────────┐                                          │
│  │   Transit    │                                          │
│  │   Adapter    │                                          │
│  │ (RAG-enriched)│                                         │
│  └──────┬───────┘                                          │
│         │                                                   │
│         ▼                                                   │
│  state.transit_legs                                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**RAG Enrichment Process:**
```python
# Example: Enriching flights with RAG data
for flight_choice in plan:
    # 1. Extract RAG keywords
    rag_flight_info = flight_keywords[index]

    # 2. Match to fixture flights
    matching_flight = find_flight_by_route(...)

    # 3. Create hybrid result
    flight = FlightOption(
        airline=rag_flight_info["airline"],      # From RAG
        route=matching_flight.route,             # From fixture
        price=rag_flight_info["price"],          # From RAG (actual!)
        provenance={"source": "rag+fixture"}
    )
```

**Tool Call Tracking:**
```python
state.tool_call_counts = {
    "weather": 5,      # 5 days of weather
    "flights": 2,      # Outbound + return
    "lodging": 3,      # 3 hotel options
    "attractions": 12, # 12 activities
    "transit": 8,      # 8 transit legs
    "fx": 1            # Currency exchange
}
```

---

### 6. Resolve Node

📂 **Code:**
- Node: [`backend/app/graph/nodes.py:1559-1626`](../backend/app/graph/nodes.py) - `resolve_node()`
- Helpers:
  - `_find_best_flight()` (lines 1482-1531)
  - `_find_best_lodging()` (lines 1534-1556)

**Purpose:** Map abstract plan choices to concrete tool results with real pricing.

**Problem:** Planner creates estimates, but tool_exec fetches real data. Resolve bridges the gap.

**Algorithm:**
```python
for day in plan.days:
    for slot in day.slots:
        choice = slot.choices[0]

        if choice.kind == FLIGHT:
            # Find best matching flight from available options
            best_flight = find_best_flight(
                state.flights,
                desired_cost=choice.features.cost_usd_cents,
                time_window=slot.window,
                day_index=day_index  # Determines outbound vs return
            )

            # Update choice to reference real flight
            choice.option_ref = best_flight.flight_id
            choice.features.cost_usd_cents = best_flight.price_usd_cents

        elif choice.kind == LODGING:
            # Match to lodging closest to target cost
            best_lodging = find_best_lodging(
                state.lodgings,
                desired_cost=choice.features.cost_usd_cents
            )
            choice.option_ref = best_lodging.lodging_id
            choice.features.cost_usd_cents = best_lodging.price_per_night
```

**Result:** Plan now references actual fetched data with real prices.

---

### 7. Verifier Node

📂 **Code:**
- Node: [`backend/app/graph/nodes.py:1629-1736`](../backend/app/graph/nodes.py) - `verifier_node()`
- Verifiers:
  - Budget: [`backend/app/verify/budget.py`](../backend/app/verify/budget.py) - `verify_budget()`
  - Feasibility: [`backend/app/verify/feasibility.py`](../backend/app/verify/feasibility.py) - `verify_feasibility()`
  - Weather: [`backend/app/verify/weather.py`](../backend/app/verify/weather.py) - `verify_weather()`
  - Preferences: [`backend/app/verify/preferences.py`](../backend/app/verify/preferences.py) - `verify_preferences()`
- Models: [`backend/app/models/violations.py`](../backend/app/models/violations.py) - `Violation`

**Purpose:** Check if the plan satisfies all constraints.

**Four Verification Types:**

```
┌─────────────────────────────────────────────────────────────┐
│                        VERIFIERS                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. BUDGET VERIFIER                                         │
│     ✓ Total cost ≤ budget + 10% slippage                   │
│     ✓ Tracks cost by category (flights, lodging, etc.)     │
│                                                              │
│  2. FEASIBILITY VERIFIER                                    │
│     ✓ Transit time between activities is realistic         │
│     ✓ Venues are open during scheduled times               │
│     ✓ Airport buffer times (2 hours)                       │
│     ✓ DST transitions handled correctly                    │
│                                                              │
│  3. WEATHER VERIFIER (tri-state logic)                      │
│     ✓ Outdoor activities not scheduled during bad weather  │
│     ✓ Advisory (warning) vs Blocking (must fix)            │
│     ✓ Checks rain, wind, temperature                       │
│                                                              │
│  4. PREFERENCES VERIFIER                                    │
│     ✓ Must-have preferences satisfied                      │
│     ✓ Nice-to-have preferences tracked                     │
│     ✓ Theme matching (art, food, nature, etc.)            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Output:**
```python
state.violations = [
    Violation(
        kind="budget_exceeded",
        blocking=True,
        details={"overage": 5000, "category": "flights"}
    ),
    Violation(
        kind="weather_rain",
        blocking=False,  # Advisory only
        details={"day": 2, "precip_prob": 0.7}
    ),
    ...
]
```

---

### 8. Repair Node

📂 **Code:**
- Node: [`backend/app/graph/nodes.py:1739-1812`](../backend/app/graph/nodes.py) - `repair_node()`
- Repair engine: [`backend/app/repair/engine.py`](../backend/app/repair/engine.py) - `repair_plan()`
- Models: [`backend/app/repair/models.py`](../backend/app/repair/models.py) - `RepairResult`, `PlanDiff`

**Purpose:** Automatically fix constraint violations with bounded repair cycles.

**Repair Algorithm:**
```
MAX_CYCLES = 3
MAX_MOVES_PER_CYCLE = 2

for cycle in range(MAX_CYCLES):
    if no blocking_violations:
        break

    # Identify repair moves
    moves = []
    for violation in blocking_violations:
        move = choose_repair_move(violation)
        moves.append(move)

        if len(moves) >= MAX_MOVES_PER_CYCLE:
            break

    # Apply moves
    for move in moves:
        if move.type == "swap_attraction":
            swap_activities(day, slot, new_attraction)
        elif move.type == "shift_time":
            shift_slot_window(slot, delta_minutes)
        elif move.type == "change_flight":
            replace_flight(slot, cheaper_flight)

    # Re-verify after repairs
    violations = verify_all(plan)
```

**Repair Move Types:**
1. **Swap Attraction:** Replace expensive attraction with cheaper one
2. **Shift Time:** Adjust slot timing to avoid closed venues
3. **Change Flight:** Select cheaper flight option
4. **Skip Activity:** Remove non-essential activity to reduce cost

**Partial Recompute:**
- Only re-verifies affected days (not entire plan)
- Tracks reuse ratio for metrics

---

### 9. Synthesis Node

📂 **Code:**
- Node: [`backend/app/graph/nodes.py:1815-2106`](../backend/app/graph/nodes.py) - `synth_node()`
- Models: [`backend/app/models/itinerary.py`](../backend/app/models/itinerary.py) - `ItineraryV1`, `Activity`, `Citation`, `CostBreakdown`

**Purpose:** Build the final itinerary with complete provenance tracking.

**"No Evidence, No Claim" Principle:**
Every claim in the itinerary must be backed by a citation.

```python
# Example synthesis flow
for day in plan.days:
    for slot in day.slots:
        choice = slot.choices[0]

        # Look up actual tool result
        if choice.kind == ATTRACTION:
            attraction = state.attractions[choice.option_ref]

            # Create activity with evidence
            activity = Activity(
                name=attraction.name,
                geo=attraction.location,
                notes=f"{attraction.venue_type}, {indoor_str}",
                cost=attraction.est_price_usd_cents
            )

            # Create citation for this claim
            citations.append(Citation(
                claim=f"{attraction.name} ({attraction.venue_type})",
                provenance=attraction.provenance  # Where data came from
            ))
```

**Cost Breakdown:**
```python
CostBreakdown(
    flights_usd_cents=122000,      # $1,220
    lodging_usd_cents=60000,       # $600 (3 nights × $200)
    attractions_usd_cents=15000,   # $150
    transit_usd_cents=2500,        # $25
    daily_spend_usd_cents=25000,   # $250 (meals, misc)
    total_usd_cents=224500,        # $2,245
    currency_disclaimer="FX as-of 2025-06-01; prices are estimates"
)
```

**Output:** `ItineraryV1` object with:
- Day-by-day activities
- Cost breakdown
- Citations for all claims
- Decision rationale
- Provenance tracking

---

### 10. Responder Node

📂 **Code:**
- Node: [`backend/app/graph/nodes.py:2109-2121`](../backend/app/graph/nodes.py) - `responder_node()`
- Database: [`backend/app/db/models/itinerary.py`](../backend/app/db/models/itinerary.py)

**Purpose:** Finalize the run and save results to database.

**Operations:**
1. Mark `state.done = True`
2. Save itinerary to database
3. Update `AgentRun` with final status
4. Emit completion event

---

## State Management

📂 **Code:** [`backend/app/graph/state.py`](../backend/app/graph/state.py) - `OrchestratorState`

The `OrchestratorState` object flows through all nodes, accumulating data:

```python
@dataclass
class OrchestratorState:
    # Identity
    trace_id: str
    org_id: UUID
    user_id: UUID
    seed: int

    # Input
    intent: IntentV1

    # RAG data
    rag_chunks: list[str]
    rag_attractions: list[Attraction]

    # Planning
    candidate_plans: list[PlanV1]
    plan: PlanV1 | None

    # Tool results
    weather_by_date: dict[date, WeatherDay]
    flights: dict[str, FlightOption]
    lodgings: dict[str, Lodging]
    attractions: dict[str, Attraction]
    transit_legs: dict[str, TransitLeg]

    # Verification & Repair
    violations: list[Violation]
    repair_cycles_run: int
    repair_moves_applied: int

    # Final output
    itinerary: ItineraryV1 | None

    # Tracking
    messages: list[str]
    tool_call_counts: dict[str, int]
    node_timings: dict[str, int]
    last_event_ts: datetime
    done: bool
```

---

## Execution Flow

📂 **Code:** [`backend/app/graph/runner.py`](../backend/app/graph/runner.py)
- Main entry point: `start_run()` (lines 259-333)
- Graph builder: `_build_graph()` (lines 46-83)
- Background executor: `_execute_graph()` (lines 86-256)

### Background Thread Execution

```python
def start_run(session, org_id, user_id, intent):
    # 1. Create database record
    agent_run = AgentRun(
        run_id=uuid4(),
        org_id=org_id,
        status="running"
    )
    session.add(agent_run)
    session.commit()

    # 2. Start background thread
    thread = threading.Thread(
        target=_execute_graph,
        args=(run_id, org_id, user_id, trace_id, intent, seed),
        daemon=True
    )
    thread.start()

    # 3. Return immediately (non-blocking)
    return run_id
```

### Node Execution with Events

```python
def _execute_graph(run_id, org_id, user_id, trace_id, intent, seed):
    # Initialize state
    state = OrchestratorState(
        trace_id=trace_id,
        org_id=org_id,
        user_id=user_id,
        intent=intent,
        seed=seed
    )

    # Execute nodes sequentially
    node_sequence = ["intent", "rag", "planner", "selector",
                     "tool_exec", "resolve", "verifier", "repair",
                     "synth", "responder"]

    for node_name in node_sequence:
        # Emit start event (for SSE streaming)
        append_event(session, org_id, run_id,
                    kind="node_event",
                    payload={"node": node_name, "status": "running"})

        # Execute node and track timing
        start = datetime.now(UTC)
        node_fn = NODE_FUNCTIONS[node_name]
        state = node_fn(state)
        end = datetime.now(UTC)

        latency_ms = int((end - start).total_seconds() * 1000)
        state.node_timings[node_name] = latency_ms

        # Emit completion event
        append_event(session, org_id, run_id,
                    kind="node_event",
                    payload={"node": node_name, "status": "completed"})

    # Save final results
    agent_run.status = "completed"
    agent_run.plan_snapshot = [state.plan.model_dump()]
    agent_run.tool_log = {
        "node_timings": state.node_timings,
        "tool_call_counts": state.tool_call_counts,
        "weather_by_date": state.weather_by_date
    }

    # Save itinerary
    itinerary_record = Itinerary(
        org_id=org_id,
        run_id=run_id,
        data=state.itinerary.model_dump()
    )
    session.add(itinerary_record)
    session.commit()
```

---

## Key Design Decisions

### 1. Sequential vs Parallel Execution

**Choice:** Sequential node execution
**Rationale:**
- Simpler to debug and reason about
- Each node depends on previous node's output
- State accumulates linearly

### 2. RAG-Grounded Planning

**Choice:** Extract attractions from RAG before planning
**Rationale:**
- Prevents AI hallucinations
- Ensures only real attractions are suggested
- Enables accurate cost estimation

### 3. Bounded Repair

**Choice:** Max 3 cycles, 2 moves per cycle
**Rationale:**
- Prevents infinite repair loops
- Ensures reasonable latency
- Balances perfection vs speed

### 4. Provenance Tracking

**Choice:** Every data point has `Provenance` object
**Rationale:**
- Enables "no evidence, no claim" principle
- Allows users to verify sources
- Supports debugging and auditing

### 5. Background Thread Execution

**Choice:** Run graph in daemon thread
**Rationale:**
- Non-blocking API response
- User can poll status via SSE
- Enables long-running operations

---

## Event Streaming (SSE)

📂 **Code:**
- Event emission: [`backend/app/db/agent_events.py`](../backend/app/db/agent_events.py) - `append_event()`
- SSE endpoint: [`backend/app/api/chat.py`](../backend/app/api/chat.py)
- Event model: [`backend/app/db/models/agent_run_event.py`](../backend/app/db/models/agent_run_event.py)

Users monitor progress via Server-Sent Events:

```
Client                          Server
  │                               │
  ├─ POST /runs/start ───────────>│
  │<─ 201 {run_id: "abc123"} ─────┤
  │                               │
  ├─ GET /runs/abc123/events ────>│
  │<─ SSE Stream ─────────────────┤
  │  event: node_event            │
  │  data: {"node": "rag",        │
  │         "status": "running"}  │
  │                               │
  │<─ SSE Stream ─────────────────┤
  │  event: node_event            │
  │  data: {"node": "rag",        │
  │         "status": "completed"}│
  │                               │
  │  ... (more events) ...        │
  │                               │
  │<─ SSE Stream ─────────────────┤
  │  event: node_event            │
  │  data: {"node": "final",      │
  │         "status": "completed"}│
  │                               │
  ├─ GET /runs/abc123/itinerary ─>│
  │<─ 200 {itinerary: {...}} ─────┤
```

---

## Performance Characteristics

### Typical Latencies (5-day trip)

| Node | Latency | Operations |
|------|---------|------------|
| Intent | 10ms | Pass-through |
| RAG | 2000ms | DB query + LLM extraction |
| Planner | 500ms | Generate 2-4 candidates |
| Selector | 100ms | Score branches |
| Tool Exec | 3000ms | Fetch flights, weather, lodging |
| Resolve | 200ms | Match choices to results |
| Verifier | 300ms | Run 4 verifiers |
| Repair | 500ms | 1-2 repair cycles (if needed) |
| Synth | 400ms | Build final itinerary |
| Responder | 50ms | Save to database |

**Total:** ~7 seconds (no repair) to ~10 seconds (with repair)

### Tool Call Counts

Typical 5-day trip to Munich:
- Weather: 5 calls (1 per day)
- Flights: 2 calls (outbound + return)
- Lodging: 3 options fetched
- Attractions: 10-12 activities
- Transit: 8-10 legs
- FX: 1 call

**Total:** ~30 tool calls

---

## Error Handling

```python
try:
    # Execute graph
    for node_name in node_sequence:
        state = node_fn(state)

except Exception as e:
    # Update run status
    agent_run.status = "error"
    agent_run.completed_at = datetime.now(UTC)
    session.commit()

    # Emit error event
    append_event(session, org_id, run_id,
                kind="node_event",
                payload={
                    "node": "error",
                    "status": "error",
                    "message": str(e)
                })
```

---

## Future Enhancements

1. **Parallel Tool Execution:** Fetch flights, weather, lodging concurrently
2. **Streaming LLM Responses:** Stream itinerary generation in real-time
3. **Multi-destination Support:** Plan trips with multiple cities
4. **User Feedback Loop:** Learn from user edits to improve future plans
5. **Cost Optimization:** Automatically find cheaper alternatives
6. **Real-time Availability:** Check actual hotel/flight availability

---

## Quick Reference: Code Location Map

| Component | File Path | Key Functions |
|-----------|-----------|---------------|
| **Graph Runner** | [`backend/app/graph/runner.py`](../backend/app/graph/runner.py) | `start_run()`, `_execute_graph()`, `_build_graph()` |
| **All Node Implementations** | [`backend/app/graph/nodes.py`](../backend/app/graph/nodes.py) | `intent_node()`, `rag_node()`, `planner_node()`, etc. |
| **State Definition** | [`backend/app/graph/state.py`](../backend/app/graph/state.py) | `OrchestratorState` |
| **RAG Retrieval** | [`backend/app/graph/rag.py`](../backend/app/graph/rag.py) | `retrieve_knowledge_for_destination()` |
| **Planning Logic** | [`backend/app/planning/planner.py`](../backend/app/planning/planner.py) | `build_candidate_plans()` |
| **Selector Logic** | [`backend/app/planning/selector.py`](../backend/app/planning/selector.py) | `score_branches()` |
| **Budget Utilities** | [`backend/app/planning/budget_utils.py`](../backend/app/planning/budget_utils.py) | `build_budget_profile()`, `target_flight_cost()` |
| **Transit Injection** | [`backend/app/planning/simple_transit.py`](../backend/app/planning/simple_transit.py) | `simple_inject_transit()` |
| **Budget Verifier** | [`backend/app/verify/budget.py`](../backend/app/verify/budget.py) | `verify_budget()` |
| **Feasibility Verifier** | [`backend/app/verify/feasibility.py`](../backend/app/verify/feasibility.py) | `verify_feasibility()` |
| **Weather Verifier** | [`backend/app/verify/weather.py`](../backend/app/verify/weather.py) | `verify_weather()` |
| **Preferences Verifier** | [`backend/app/verify/preferences.py`](../backend/app/verify/preferences.py) | `verify_preferences()` |
| **Repair Engine** | [`backend/app/repair/engine.py`](../backend/app/repair/engine.py) | `repair_plan()` |
| **Repair Models** | [`backend/app/repair/models.py`](../backend/app/repair/models.py) | `RepairResult`, `PlanDiff` |
| **Weather Adapter** | [`backend/app/adapters/weather.py`](../backend/app/adapters/weather.py) | `get_weather_adapter()` |
| **Flights Adapter** | [`backend/app/adapters/flights.py`](../backend/app/adapters/flights.py) | `get_flights()` |
| **Lodging Adapter** | [`backend/app/adapters/lodging.py`](../backend/app/adapters/lodging.py) | `get_lodging()` |
| **Transit Adapter** | [`backend/app/adapters/transit.py`](../backend/app/adapters/transit.py) | `get_transit_leg()` |
| **FX Adapter** | [`backend/app/adapters/fx.py`](../backend/app/adapters/fx.py) | `get_fx_rate()` |
| **Intent Model** | [`backend/app/models/intent.py`](../backend/app/models/intent.py) | `IntentV1` |
| **Plan Model** | [`backend/app/models/plan.py`](../backend/app/models/plan.py) | `PlanV1`, `DayPlan`, `Slot`, `Choice` |
| **Itinerary Model** | [`backend/app/models/itinerary.py`](../backend/app/models/itinerary.py) | `ItineraryV1`, `Activity`, `Citation` |
| **Tool Results** | [`backend/app/models/tool_results.py`](../backend/app/models/tool_results.py) | `FlightOption`, `Lodging`, `Attraction`, `WeatherDay` |
| **Violations Model** | [`backend/app/models/violations.py`](../backend/app/models/violations.py) | `Violation` |
| **Common Models** | [`backend/app/models/common.py`](../backend/app/models/common.py) | `Geo`, `Provenance`, `TimeWindow` |
| **API: Start Run** | [`backend/app/api/plan.py`](../backend/app/api/plan.py) | `POST /runs/start` |
| **API: SSE Events** | [`backend/app/api/chat.py`](../backend/app/api/chat.py) | `GET /runs/{run_id}/events` |
| **API: Knowledge** | [`backend/app/api/knowledge.py`](../backend/app/api/knowledge.py) | Knowledge base endpoints |
| **Event Helper** | [`backend/app/db/agent_events.py`](../backend/app/db/agent_events.py) | `append_event()` |
| **DB: AgentRun** | [`backend/app/db/models/agent_run.py`](../backend/app/db/models/agent_run.py) | `AgentRun` table model |
| **DB: Itinerary** | [`backend/app/db/models/itinerary.py`](../backend/app/db/models/itinerary.py) | `Itinerary` table model |
| **DB: Embeddings** | [`backend/app/db/models/embedding.py`](../backend/app/db/models/embedding.py) | `Embedding` table model (RAG) |
| **DB: Events** | [`backend/app/db/models/agent_run_event.py`](../backend/app/db/models/agent_run_event.py) | `AgentRunEvent` table model |

---

## Conclusion

The LangGraph agent architecture provides a **modular, debuggable, and extensible** system for AI-powered travel planning. By breaking the problem into distinct nodes with clear responsibilities, the system achieves:

- ✅ **Grounded AI:** RAG prevents hallucinations
- ✅ **Budget Compliance:** Multi-stage verification and repair
- ✅ **Provenance Tracking:** Every claim is backed by evidence
- ✅ **Observable:** SSE events enable real-time monitoring
- ✅ **Maintainable:** Clear separation of concerns

The sequential node execution, combined with RAG grounding and bounded repair, ensures both **quality** and **performance** for real-world travel planning.

---

## Where to Start Reading

**For understanding the overall flow:**
1. Start with [`backend/app/graph/runner.py`](../backend/app/graph/runner.py) to see how the graph is built and executed
2. Read [`backend/app/graph/nodes.py`](../backend/app/graph/nodes.py) to understand each node's implementation

**For understanding specific features:**
- **Planning:** [`backend/app/planning/planner.py`](../backend/app/planning/planner.py) + [`backend/app/planning/selector.py`](../backend/app/planning/selector.py)
- **RAG System:** [`backend/app/graph/rag.py`](../backend/app/graph/rag.py) + extraction functions in [`backend/app/graph/nodes.py`](../backend/app/graph/nodes.py)
- **Verification:** All files in [`backend/app/verify/`](../backend/app/verify/)
- **Repair:** [`backend/app/repair/engine.py`](../backend/app/repair/engine.py)
- **Data Models:** All files in [`backend/app/models/`](../backend/app/models/)
- **API Endpoints:** All files in [`backend/app/api/`](../backend/app/api/)

**For debugging:**
- Check [`backend/app/db/agent_events.py`](../backend/app/db/agent_events.py) for event logging
- Inspect [`backend/app/graph/state.py`](../backend/app/graph/state.py) to understand state transitions
- Review node implementations in [`backend/app/graph/nodes.py`](../backend/app/graph/nodes.py) for detailed execution logic
