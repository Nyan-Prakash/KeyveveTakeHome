# Triply Travel Planner - Interview Preparation Guide

> **Last Updated**: 2025-11-23
> **Branch**: ImplementRag
> **Purpose**: Comprehensive technical overview for interview preparation

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Tech Stack Summary](#tech-stack-summary)
3. [System Architecture](#system-architecture)
4. [LangGraph Orchestration](#langgraph-orchestration)
5. [Data Models & Schemas](#data-models--schemas)
6. [Database Schema](#database-schema)
7. [API Endpoints](#api-endpoints)
8. [Planning Algorithm](#planning-algorithm)
9. [Verification System](#verification-system)
10. [Repair Engine](#repair-engine)
11. [RAG System](#rag-system)
12. [Security Architecture](#security-architecture)
13. [Frontend Structure](#frontend-structure)
14. [MCP Integration](#mcp-integration)
15. [Key Design Decisions](#key-design-decisions)
16. [Interview Talking Points](#interview-talking-points)

---

## Project Overview

**Triply Travel Planner** is an AI-powered travel planning system that generates personalized 4-7 day itineraries with:

- **Real-time constraint verification** (budget, weather, timing, preferences)
- **Multi-step agentic orchestration** using LangGraph
- **RAG-enhanced knowledge base** for local insights
- **Deterministic repair loops** to fix constraint violations
- **Streaming progress updates** via Server-Sent Events

### Core Capabilities

```
User Input → AI Planning → Verification → Repair → Final Itinerary
     ↓           ↓             ↓           ↓            ↓
  Intent    Candidates    Constraints   Fixes      Bookable Plan
```

### Key Features

- **Multi-Plan Generation**: 1-4 candidate plans (cost-conscious, convenience, experience, relaxed)
- **Budget-Aware**: Allocates flights, lodging, activities within user budget
- **Weather-Conscious**: Avoids outdoor activities in bad weather
- **RAG-Enhanced**: Uses uploaded PDFs/docs for local recommendations
- **Multi-Tenant**: Org-scoped data with user isolation
- **Secure**: JWT RS256, Argon2 password hashing, rate limiting

---

## Tech Stack Summary

### Backend Core

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.11+ | Primary language |
| **FastAPI** | 0.115.0 | REST API framework |
| **LangGraph** | 0.2.0 | Agentic workflow orchestration |
| **OpenAI GPT-4** | Latest | Intent extraction, planning LLM |
| **PostgreSQL** | 16+ with pgvector | Relational DB + vector search |
| **SQLAlchemy** | 2.0 | Type-safe ORM |
| **Redis** | 7.x | Caching, rate limiting |
| **PyJWT** | Latest | RS256 token auth |
| **Argon2** | Latest | Password hashing |

### Frontend

| Technology | Version | Purpose |
|------------|---------|---------|
| **Streamlit** | 1.39.0 | Multi-page web UI |
| **Python** | 3.11+ | Page logic |
| **Server-Sent Events** | Native | Real-time updates |

### External Services

| Service | Purpose |
|---------|---------|
| **OpenWeatherMap** | Weather forecasting |
| **MCP Weather Server** | Node.js-based weather tool (port 3001) |
| **Flight Search API** | Mock/real flight data |
| **Lodging Search API** | Mock/real hotel data |
| **Attraction Search API** | POI lookup |
| **Transit Routing API** | Local transportation |
| **Currency Exchange API** | FX rates |

### Development Tools

- **Pytest**: Testing framework with coverage
- **Ruff**: Fast Python linter
- **Black**: Code formatter
- **MyPy**: Type checking
- **Pre-commit**: Git hooks
- **Docker Compose**: Full-stack deployment
- **Alembic**: Database migrations

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    STREAMLIT FRONTEND (8501)                    │
│  ├─ Home.py (Landing page)                                      │
│  ├─ pages/00_Login.py & 00_Signup.py (Auth)                    │
│  ├─ pages/01_Destinations.py (Destination CRUD)                 │
│  ├─ pages/02_Knowledge_Base.py (PDF/MD upload & chunks)         │
│  ├─ pages/04_Chat_Plan.py (Conversational planning)             │
│  └─ auth.py (JWT token management)                              │
└─────────────────┬──────────────────────────────────────────────┘
                  │ HTTP/REST (Bearer Auth)
┌─────────────────▼──────────────────────────────────────────────┐
│               FASTAPI BACKEND (8000)                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ API ROUTERS                                              │  │
│  │  ├─ /auth (login, signup, refresh)                      │  │
│  │  ├─ /plan (create_plan, stream progress)                │  │
│  │  ├─ /chat (chat_plan, intent extraction)                │  │
│  │  ├─ /destinations (CRUD destinations)                   │  │
│  │  └─ /destinations/{id}/knowledge (upload docs, chunks)  │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ LANGGRAPH ORCHESTRATOR (10-step workflow)                │  │
│  │  1. Intent: Parse user requirements                      │  │
│  │  2. RAG: Retrieve local knowledge                        │  │
│  │  3. Planner: Generate 1-4 candidate plans               │  │
│  │  4. Selector: Choose optimal plan                        │  │
│  │  5. ToolExec: Fetch flights, hotels, weather           │  │
│  │  6. Resolve: Merge tool data into plan                  │  │
│  │  7. Verifier: Check budget/weather/timing               │  │
│  │  8. Repair: Fix violations (≤3 cycles, ≤2 moves/cycle)  │  │
│  │  9. Synth: Compile final structured itinerary           │  │
│  │  10. Responder: Format response with citations          │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ ADAPTERS (External Tool Integration)                     │  │
│  │  ├─ flights.py (Tier selection, price calculation)      │  │
│  │  ├─ lodging.py (Hotel search, check-in/out times)       │  │
│  │  ├─ weather.py (MCP-based with fallback fixtures)       │  │
│  │  ├─ transit.py (Local transportation routing)           │  │
│  │  ├─ fx.py (Currency exchange caching)                   │  │
│  │  └─ mcp/ (MCP protocol client implementation)           │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ PLANNING & VERIFICATION                                  │  │
│  │  ├─ planning/planner.py (Candidate gen, budget-aware)   │  │
│  │  ├─ planning/selector.py (Plan scoring)                 │  │
│  │  ├─ planning/budget_utils.py (Cost estimation)          │  │
│  │  ├─ verify/budget.py (10% slippage check)               │  │
│  │  ├─ verify/weather.py (Rain/temp constraints)           │  │
│  │  ├─ verify/feasibility.py (Timing/distance)             │  │
│  │  └─ repair/engine.py (Deterministic constraint fixing)  │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ RAG & KNOWLEDGE BASE                                     │  │
│  │  ├─ graph/rag.py (Semantic search, fallback retrieval)  │  │
│  │  ├─ graph/embedding_utils.py (OpenAI embeddings)        │  │
│  │  ├─ utils/pdf_parser.py (PDF extraction + OCR)          │  │
│  │  └─ api/knowledge.py (Upload, chunking, embedding)      │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ SECURITY & AUTHENTICATION                                │  │
│  │  ├─ security/jwt.py (RS256 tokens, 15min/7day TTL)      │  │
│  │  ├─ security/passwords.py (Argon2 hashing)              │  │
│  │  ├─ security/lockout.py (Failed attempt tracking)       │  │
│  │  └─ security/middleware.py (Rate limiting, security hdrs)│  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────┬───────────────────────────────────────────┬─┘
                   │                                           │
        ┌──────────▼─────────────┐              ┌─────────────▼──┐
        │  POSTGRESQL + PGVECTOR │              │ REDIS CLUSTER  │
        │  ├─ users              │              ├─ auth tokens   │
        │  ├─ org                │              ├─ rate limits   │
        │  ├─ destinations       │              ├─ sessions      │
        │  ├─ agent_runs         │              └─ cache         │
        │  ├─ itineraries        │                               │
        │  ├─ knowledge_items    │              ┌─────────────────┐
        │  ├─ embeddings (vector)│              │ MCP WEATHER SRV │
        │  └─ refresh_tokens     │              │ (Node.js, 3001) │
        │                        │              │ └─ get_weather  │
        │  Indexes:              │              │    (fallbacks)  │
        │  - pgvector cosine     │              └─────────────────┘
        └────────────────────────┘
```

### Request Flow Example

```
1. User clicks "Generate Plan" in Streamlit
   ↓
2. Frontend sends POST /plan with IntentV1 (JWT bearer token)
   ↓
3. Backend validates token, extracts user_id + org_id
   ↓
4. Creates agent_run record in database
   ↓
5. Spawns background thread with LangGraph execution
   ↓
6. Returns run_id to frontend
   ↓
7. Frontend opens SSE connection: GET /plan/{run_id}/stream
   ↓
8. Backend streams progress events (heartbeat + node updates)
   ↓
9. LangGraph executes 10 nodes sequentially:
   Intent → RAG → Planner → Selector → ToolExec → Resolve → Verifier → Repair → Synth → Responder
   ↓
10. Final itinerary saved to database
    ↓
11. Frontend displays result with cost breakdown + decisions
```

---

## LangGraph Orchestration

### Workflow Diagram

```
User Input (IntentV1)
    ↓
┌───────────────────┐
│  INTENT NODE      │ Parse structured intent from natural language
│  (intent.py)      │ Output: Validated IntentV1 with budget, dates, prefs
└────────┬──────────┘
         ↓
┌───────────────────┐
│  RAG NODE         │ Semantic search in knowledge base
│  (rag.py)         │ Output: Top 20 relevant chunks (pgvector cosine)
└────────┬──────────┘
         ↓
┌───────────────────┐
│  PLANNER NODE     │ Generate 1-4 candidate plans
│  (planner.py)     │ Variants: cost-conscious, convenience, experience, relaxed
└────────┬──────────┘ Output: List[PlanV1] with budget profiles
         ↓
┌───────────────────┐
│  SELECTOR NODE    │ Score and select optimal plan
│  (selector.py)    │ Criteria: budget fit, distribution, feasibility, prefs
└────────┬──────────┘ Output: Single best PlanV1
         ↓
┌───────────────────┐
│  TOOLEXEC NODE    │ Parallel tool execution
│  (nodes.py)       │ - Flights (tier selection)
│                   │ - Lodging (check-in/out windows)
│                   │ - Weather (MCP + fallback)
│                   │ - Attractions (theme filtering)
│                   │ - Transit (mode selection)
└────────┬──────────┘ Output: Tool results in state
         ↓
┌───────────────────┐
│  RESOLVE NODE     │ Merge tool results into plan slots
│  (nodes.py)       │ Replace placeholders with real data
└────────┬──────────┘ Output: Updated PlanV1 with real costs
         ↓
┌───────────────────┐
│  VERIFIER NODE    │ Check constraints
│  (verify/)        │ - Budget (10% slippage allowed)
│                   │ - Weather (outdoor activities in rain)
│                   │ - Timing (overlaps, closed venues)
│                   │ - Preferences (kid-friendly, themes)
└────────┬──────────┘ Output: List[Violation]
         ↓
    Violations?
    ├─ NO ──────────────────────────┐
    │                               ↓
    └─ YES                      ┌───────────────────┐
       ↓                        │  SYNTH NODE       │
   ┌───────────────────┐        │  (nodes.py)       │
   │  REPAIR NODE      │        │  Compile final    │
   │  (engine.py)      │        │  ItineraryV1      │
   │  Apply ≤2 fixes   │        │  with cost        │
   │  per cycle (≤3)   │        │  breakdown        │
   │  - Budget: tier↓  │        └────────┬──────────┘
   │  - Weather: move  │                 ↓
   │  - Timing: reorder│        ┌───────────────────┐
   │  - Venue: replace │        │  RESPONDER NODE   │
   └────────┬──────────┘        │  (nodes.py)       │
            ↓                   │  Format response  │
        Re-verify               │  Save to DB       │
            ↓                   │  Return citations │
        (loop or timeout)       └────────┬──────────┘
            ↓                            ↓
    (continue to synth)         Final Output (saved)
```

### State Management (OrchestratorState)

```python
class OrchestratorState(TypedDict):
    # Identifiers
    trace_id: str
    org_id: str
    user_id: str
    seed: int  # Deterministic RNG seed

    # Core data
    intent: IntentV1 | None
    candidate_plans: list[PlanV1]
    plan: PlanV1 | None
    itinerary: ItineraryV1 | None

    # Verification
    violations: list[Violation]

    # RAG
    rag_chunks: list[str]

    # Tool results
    weather_by_date: dict[str, WeatherDay]
    flights: list[FlightOption]
    lodgings: list[Lodging]
    attractions: list[Attraction]
    transit_legs: list[TransitLeg]

    # Repair tracking
    repair_cycles_run: int
    repair_moves_applied: int
    repair_reuse_ratio: float

    # Metrics
    node_timings: dict[str, float]
    tool_call_counts: dict[str, int]
```

### Node Execution Times (Typical)

| Node | P50 | P95 | Purpose |
|------|-----|-----|---------|
| Intent | <500ms | <1s | LLM parsing |
| RAG | <500ms | <1s | Vector search |
| Planner | 1-2s | 3-4s | Candidate generation |
| Selector | <100ms | <200ms | Scoring |
| ToolExec | 1-3s | 4-5s | Parallel API calls |
| Resolve | <100ms | <200ms | Data merging |
| Verifier | <500ms | <1s | Constraint checks |
| Repair | <1s | <2s | Fix application |
| Synth | <100ms | <200ms | Final assembly |
| Responder | <100ms | <200ms | DB save |

**Total E2E**: 4-8s (P50), 9-11s (P95), Budget: 10s

---

## Data Models & Schemas

### Intent Models (User Input)

```python
class DateWindow(BaseModel):
    start: datetime  # Trip start date (UTC)
    end: datetime    # Trip end date (UTC)
    tz: str          # IANA timezone (e.g., "America/New_York")

class LockedSlot(BaseModel):
    """User-pinned activity that cannot be moved/removed"""
    window: TimeWindow
    choice: Choice
    rationale: str

class Preferences(BaseModel):
    kid_friendly: bool = False
    themes: list[str] = []  # "art", "food", "history", "nature", etc.
    avoid_overnight: bool = False  # For flights
    locked_slots: list[LockedSlot] = []

class IntentV1(BaseModel):
    city: str  # Destination city
    date_window: DateWindow
    budget_usd_cents: int  # MUST be positive (stored as cents)
    airports: list[str]    # IATA codes, ≥1 required
    prefs: Preferences
```

### Plan Models (Intermediate Representation)

```python
class TimeWindow(BaseModel):
    start: datetime  # UTC
    end: datetime    # UTC

class ChoiceFeatures(BaseModel):
    """Standardized attributes for plan choices"""
    cost_usd_cents: int | None = None
    travel_time_seconds: int | None = None
    indoor: bool | None = None
    kid_friendly: bool | None = None
    themes: list[str] = []
    tier: str | None = None  # "budget" | "mid" | "luxury"

class Provenance(BaseModel):
    """Track where data came from"""
    source: str  # "tool" | "rag" | "user" | "fixture"
    source_url: str | None = None
    fetched_at: datetime | None = None
    response_digest: str | None = None  # SHA256 for dedup

class Choice(BaseModel):
    kind: ChoiceKind  # flight | lodging | attraction | transit | meal
    features: ChoiceFeatures
    score: float  # Selection score
    provenance: Provenance

class Slot(BaseModel):
    """Time slot with ranked alternatives"""
    window: TimeWindow
    choices: list[Choice]  # Ranked by score (desc)
    locked: bool = False   # User-pinned

class DayPlan(BaseModel):
    slots: list[Slot]

class Assumptions(BaseModel):
    """Planning assumptions for transparency"""
    fx_rate: float | None = None
    daily_spend_usd_cents: int
    airport_buffer_min: int = 120
    transit_buffer_min: int = 15

class PlanV1(BaseModel):
    days: list[DayPlan]
    assumptions: Assumptions
```

### Itinerary Models (Final Output)

```python
class Activity(BaseModel):
    """Single activity in final itinerary"""
    window: TimeWindow
    kind: ChoiceKind
    name: str
    geo: dict | None = None  # {"lat": ..., "lon": ...}
    notes: str | None = None
    cost_usd_cents: int | None = None

class DayItinerary(BaseModel):
    activities: list[Activity]

class CostBreakdown(BaseModel):
    """Transparent cost accounting"""
    flights_usd_cents: int
    lodging_usd_cents: int
    attractions_usd_cents: int
    transit_usd_cents: int
    daily_spend_usd_cents: int  # Meals, misc
    total_usd_cents: int
    currency_disclaimer: str | None = None

class Decision(BaseModel):
    """Explain why a choice was made"""
    claim: str
    rationale: str

class Citation(BaseModel):
    """Provenance for claims"""
    claim: str
    provenance: Provenance

class ItineraryV1(BaseModel):
    days: list[DayItinerary]
    cost_breakdown: CostBreakdown
    decisions: list[Decision]
    citations: list[Citation]
    metadata: dict  # {trace_id, created_at, etc.}
```

### Violation Models

```python
class ViolationKind(str, Enum):
    BUDGET_EXCEEDED = "budget_exceeded"
    TIMING_INFEASIBLE = "timing_infeasible"
    VENUE_CLOSED = "venue_closed"
    WEATHER_UNSUITABLE = "weather_unsuitable"
    PREF_VIOLATED = "pref_violated"

class Violation(BaseModel):
    kind: ViolationKind
    node_ref: str  # Which verifier found it
    details: dict  # Specific violation data
    blocking: bool = True  # Can be fixed by repair?
```

---

## Database Schema

### Entity Relationship Diagram

```
┌─────────────┐
│     org     │
│ (org_id PK) │
└──────┬──────┘
       │ 1
       │
       │ N
┌──────▼──────────────┐
│       user          │
│ (user_id PK)        │
│  org_id FK          │
│  email              │
│  password_hash      │
│  locked_until       │
└──────┬──────────────┘
       │ 1
       │
       ├───────────────┬────────────────┬──────────────────┐
       │ N             │ N              │ N                │ N
┌──────▼──────┐  ┌────▼────────┐  ┌────▼──────────┐  ┌───▼──────────┐
│  agent_run  │  │ destination │  │ refresh_token │  │  itinerary   │
│ (run_id PK) │  │(dest_id PK) │  │  (jti PK)     │  │(itin_id PK)  │
│  intent     │  │  city       │  │  expires_at   │  │  data JSONB  │
│  plan_snap  │  │  tz         │  └───────────────┘  └──────────────┘
│  tool_log   │  │  last_run   │
│  status     │  └──────┬──────┘
└──────┬──────┘         │ 1
       │ 1              │
       │                │ N
       │ N         ┌────▼──────────────┐
┌──────▼──────┐   │  knowledge_item   │
│ agent_run   │   │  (item_id PK)     │
│   _event    │   │   doc_name        │
│(event_id PK)│   │   status          │
│  kind       │   └────┬──────────────┘
│  payload    │        │ 1
└─────────────┘        │
                       │ N
                  ┌────▼──────────────┐
                  │    embedding      │
                  │(embedding_id PK)  │
                  │  chunk_text       │
                  │  vector(1536)     │
                  │  page_number      │
                  └───────────────────┘
```

### Table Definitions

#### org (Multi-tenancy)
```sql
CREATE TABLE org (
    org_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### user (Accounts)
```sql
CREATE TABLE "user" (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES org(org_id) ON DELETE CASCADE,
    email VARCHAR NOT NULL,
    password_hash VARCHAR NOT NULL,  -- Argon2id
    locked_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(org_id, email)
);
CREATE INDEX idx_user_org ON "user"(org_id, email);
```

#### agent_run (LangGraph Execution)
```sql
CREATE TABLE agent_run (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES org(org_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
    intent JSONB NOT NULL,  -- IntentV1 serialized
    plan_snapshot JSONB,    -- PlanV1 before repair
    tool_log JSONB,         -- {node_timings, tool_call_counts}
    trace_id VARCHAR NOT NULL,
    status VARCHAR,         -- "running" | "completed" | "error"
    cost_usd NUMERIC(10,6),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX idx_run_org_user ON agent_run(org_id, user_id, created_at DESC);
```

#### itinerary (Final Outputs)
```sql
CREATE TABLE itinerary (
    itinerary_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES org(org_id) ON DELETE CASCADE,
    run_id UUID NOT NULL REFERENCES agent_run(run_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
    data JSONB NOT NULL,  -- ItineraryV1 serialized
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_itinerary_run ON itinerary(run_id);
```

#### destination (Travel Destinations)
```sql
CREATE TABLE destination (
    dest_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES org(org_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
    city VARCHAR NOT NULL,
    tz VARCHAR,  -- IANA timezone
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_run_id UUID REFERENCES agent_run(run_id) ON DELETE SET NULL,
    last_run_cost_usd NUMERIC(10,2),
    UNIQUE(org_id, city)
);
CREATE INDEX idx_dest_org ON destination(org_id, user_id);
```

#### knowledge_item (Documents)
```sql
CREATE TABLE knowledge_item (
    item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES org(org_id) ON DELETE CASCADE,
    dest_id UUID NOT NULL REFERENCES destination(dest_id) ON DELETE CASCADE,
    doc_name VARCHAR,
    status VARCHAR DEFAULT 'queued',  -- "queued" | "processing" | "done"
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_knowledge_dest ON knowledge_item(dest_id);
```

#### embedding (RAG Vectors - pgvector)
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE embedding (
    embedding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id UUID NOT NULL REFERENCES knowledge_item(item_id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    vector vector(1536),  -- OpenAI text-embedding-3-small dimension
    page_number INT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_embedding_item ON embedding(item_id);
CREATE INDEX idx_embedding_vector ON embedding
  USING ivfflat (vector vector_cosine_ops);
```

#### refresh_token (Token Rotation)
```sql
CREATE TABLE refresh_token (
    jti VARCHAR PRIMARY KEY,  -- JWT ID
    user_id UUID NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE INDEX idx_refresh_user ON refresh_token(user_id);
```

#### agent_run_event (Event Log)
```sql
CREATE TABLE agent_run_event (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES agent_run(run_id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES org(org_id) ON DELETE CASCADE,
    kind VARCHAR NOT NULL,  -- "node_event" | "message" | "error"
    payload JSONB NOT NULL,
    ts TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_event_run_ts ON agent_run_event(run_id, ts);
```

---

## API Endpoints

### Authentication (`/auth`)

#### POST /auth/signup
```json
// Request
{
  "email": "user@example.com",
  "password": "securepassword"
}

// Response (201 Created)
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "expires_in": 900,  // 15 minutes
  "token_type": "Bearer"
}
```

#### POST /auth/login
```json
// Request
{
  "email": "user@example.com",
  "password": "securepassword"
}

// Response (200 OK)
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "expires_in": 900
}

// Error: Account Locked (423 Locked)
{
  "detail": "Account locked until 2025-11-23T15:30:00Z"
}
```

#### POST /auth/refresh
```json
// Request
{
  "refresh_token": "eyJhbGc..."
}

// Response (200 OK)
{
  "access_token": "eyJhbGc...",  // New token
  "refresh_token": "eyJhbGc...", // Rotated
  "expires_in": 900
}
```

### Planning (`/plan`)

#### POST /plan
```json
// Request (Authorization: Bearer <access_token>)
{
  "city": "Paris",
  "date_window": {
    "start": "2025-06-01T00:00:00Z",
    "end": "2025-06-07T23:59:59Z",
    "tz": "Europe/Paris"
  },
  "budget_usd_cents": 250000,  // $2500
  "airports": ["CDG", "ORY"],
  "prefs": {
    "kid_friendly": false,
    "themes": ["art", "food", "history"],
    "avoid_overnight": true,
    "locked_slots": []
  }
}

// Response (202 Accepted)
{
  "run_id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d"
}
```

#### GET /plan/{run_id}/stream
```
// Server-Sent Events (SSE) stream
// Query params: ?last_ts=2025-11-23T14:00:00Z (optional, for resume)

event: heartbeat
data: {"ts": "2025-11-23T14:23:45Z"}

event: node_event
data: {"node": "intent", "status": "started", "ts": "2025-11-23T14:23:45.100Z"}

event: node_event
data: {"node": "intent", "status": "completed", "latency_ms": 450, "ts": "2025-11-23T14:23:45.550Z"}

event: node_event
data: {"node": "planner", "status": "started", "ts": "2025-11-23T14:23:46Z"}

event: message
data: {"message": "Generated 3 candidate plans", "ts": "2025-11-23T14:23:48Z"}

event: node_event
data: {"node": "responder", "status": "completed", "ts": "2025-11-23T14:23:52Z"}

event: done
data: {"itinerary_id": "...", "run_id": "...", "ts": "2025-11-23T14:23:52.500Z"}
```

### Chat Planning (`/chat`)

#### POST /chat
```json
// Request (Authorization: Bearer <access_token>)
{
  "message": "I want to visit Tokyo for 5 days with a budget of $3000",
  "conversation_history": [
    {"role": "user", "content": "I'm planning a trip"},
    {"role": "assistant", "content": "Great! Where would you like to go?"}
  ],
  "run_id": null  // Optional: for editing existing plans
}

// Response (200 OK)
{
  "assistant_message": "I understand you want to visit Tokyo for 5 days with a $3000 budget. What dates are you considering?",
  "intent": null,  // Not yet complete
  "run_id": null,
  "is_complete": false,
  "is_generating": false
}

// When intent is complete:
{
  "assistant_message": "Perfect! I'll generate your Tokyo itinerary now.",
  "intent": {
    "city": "Tokyo",
    "date_window": {...},
    "budget_usd_cents": 300000,
    "airports": ["NRT", "HND"],
    "prefs": {...}
  },
  "run_id": "a1b2c3d4...",
  "is_complete": true,
  "is_generating": true
}
```

### Knowledge Base (`/destinations/{dest_id}/knowledge`)

#### POST /destinations/{dest_id}/knowledge/upload
```
// Request (Content-Type: multipart/form-data)
Authorization: Bearer <access_token>
Content-Type: multipart/form-data

file: paris_guide.pdf (binary)

// Response (201 Created)
{
  "item_id": "f1e2d3c4-b5a6-4d5e-8f9a-0b1c2d3e4f5a",
  "status": "queued",
  "doc_name": "paris_guide.pdf"
}
```

#### GET /destinations/{dest_id}/knowledge/items
```json
// Response (200 OK)
[
  {
    "item_id": "f1e2d3c4...",
    "doc_name": "paris_guide.pdf",
    "status": "done",
    "created_at": "2025-11-23T14:00:00Z"
  },
  {
    "item_id": "a2b3c4d5...",
    "doc_name": "local_tips.md",
    "status": "processing",
    "created_at": "2025-11-23T14:05:00Z"
  }
]
```

#### GET /destinations/{dest_id}/knowledge/chunks
```json
// Query params: ?limit=20
// Response (200 OK)
[
  {
    "chunk_id": "e1f2a3b4...",
    "snippet": "The Eiffel Tower is best visited at sunset...",
    "doc_name": "paris_guide.pdf",
    "page_number": 12
  },
  {
    "chunk_id": "b2c3d4e5...",
    "snippet": "For authentic croissants, try Maison Landemaine...",
    "doc_name": "paris_guide.pdf",
    "page_number": 45
  }
]
```

### Destinations (`/destinations`)

#### GET /destinations
```json
// Response (200 OK)
[
  {
    "dest_id": "a1b2c3d4...",
    "city": "Paris",
    "tz": "Europe/Paris",
    "last_run_id": "f1e2d3c4...",
    "last_run_cost_usd": 2345.67,
    "created_at": "2025-11-20T10:00:00Z"
  }
]
```

#### POST /destinations
```json
// Request
{
  "city": "Tokyo",
  "tz": "Asia/Tokyo"
}

// Response (201 Created)
{
  "dest_id": "b2c3d4e5...",
  "city": "Tokyo",
  "tz": "Asia/Tokyo",
  "created_at": "2025-11-23T14:00:00Z"
}
```

---

## Planning Algorithm

### Candidate Generation Flow

```
IntentV1 (user input)
    ↓
Calculate Budget Profile
    ├─ Flight budget: 25-35% of total
    ├─ Lodging budget: 30-40% of total
    ├─ Daily spend: $100-150/day
    └─ Activity budget: remainder
    ↓
Generate Plan Variants (1-4 candidates)
    ↓
┌─────────────────────────────────────────────┐
│ 1. COST-CONSCIOUS (0.7x multiplier)         │
│    - Budget-tier flights & lodging          │
│    - Free/cheap attractions                 │
│    - Always generated                       │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│ 2. CONVENIENCE (1.0x, if budget > $1000)    │
│    - Mid-tier flights & lodging             │
│    - Central locations                      │
│    - Balanced cost vs. time                 │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│ 3. EXPERIENCE (1.2x, if budget > $2000)     │
│    - Luxury accommodations                  │
│    - Premium attractions                    │
│    - Quality over cost                      │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│ 4. RELAXED (0.9x, if budget > $2000 + themes)│
│    - More free time, fewer activities       │
│    - Flexible scheduling                    │
│    - Balanced approach                      │
└─────────────────────────────────────────────┘
    ↓
Inject Transit Slots
    - Walk: <15min
    - Metro/Bus: 15-45min
    - Taxi: 30-60min
    - Train: 60-120min
    ↓
Output: List[PlanV1] (1-4 plans)
```

### Budget Allocation Example ($2500 budget)

```
Total Budget: $2500

Cost-Conscious Plan (0.7x = $1750 target):
├─ Flights: $500 (budget tier)
├─ Lodging: $600 (4 nights × $150)
├─ Daily Spend: $400 (4 days × $100)
├─ Activities: $250 (free + cheap)
└─ Total: $1750 (70% of budget)

Convenience Plan (1.0x = $2500 target):
├─ Flights: $750 (mid tier)
├─ Lodging: $800 (4 nights × $200)
├─ Daily Spend: $500 (4 days × $125)
├─ Activities: $450 (mix of paid)
└─ Total: $2500 (100% of budget)

Experience Plan (1.2x = $3000 target, capped at $2750):
├─ Flights: $900 (mid-premium tier)
├─ Lodging: $1000 (4 nights × $250)
├─ Daily Spend: $600 (4 days × $150)
├─ Activities: $250 (premium experiences)
└─ Total: $2750 (110% of budget, max slippage)
```

### Plan Selection Scoring

```python
def score_plan(plan: PlanV1, intent: IntentV1) -> float:
    score = 0.0

    # 1. Budget compliance (40% weight)
    budget_usage = plan.total_cost / intent.budget_usd_cents
    if budget_usage <= 1.0:
        score += 40 * (1.0 - abs(1.0 - budget_usage))
    elif budget_usage <= 1.1:  # Allow 10% slippage
        score += 40 * (1.0 - (budget_usage - 1.0) * 5)
    else:
        score -= 100  # Hard penalty for >10% over

    # 2. Cost distribution (20% weight)
    flight_ratio = plan.flights_cost / plan.total_cost
    lodging_ratio = plan.lodging_cost / plan.total_cost
    activity_ratio = plan.activity_cost / plan.total_cost

    # Target: 25-35% flights, 30-40% lodging, 20-30% activities
    if 0.25 <= flight_ratio <= 0.35:
        score += 7
    if 0.30 <= lodging_ratio <= 0.40:
        score += 7
    if 0.20 <= activity_ratio <= 0.30:
        score += 6

    # 3. Schedule feasibility (20% weight)
    if no_timing_overlaps(plan):
        score += 10
    if adequate_buffers(plan):
        score += 10

    # 4. Preference alignment (20% weight)
    theme_coverage = len(set(plan.themes) & set(intent.prefs.themes))
    score += theme_coverage * 5  # 5 points per matched theme

    if intent.prefs.kid_friendly:
        kid_friendly_ratio = count_kid_activities(plan) / total_activities(plan)
        score += kid_friendly_ratio * 10

    return score
```

---

## Verification System

### Budget Verification

```python
def verify_budget(intent: IntentV1, plan: PlanV1) -> list[Violation]:
    violations = []

    total_cost = (
        sum(flight.price_usd_cents for flight in plan.flights) +
        sum(lodging.price_usd_cents for lodging in plan.lodgings) +
        sum(activity.price_usd_cents for activity in plan.activities) +
        sum(transit.price_usd_cents for transit in plan.transit_legs) +
        plan.daily_spend_usd_cents * plan.num_days
    )

    # Allow 10% slippage
    max_allowed = intent.budget_usd_cents * 1.10

    if total_cost > max_allowed:
        violations.append(Violation(
            kind=ViolationKind.BUDGET_EXCEEDED,
            node_ref="verify.budget",
            details={
                "total_cost": total_cost,
                "budget": intent.budget_usd_cents,
                "overage": total_cost - intent.budget_usd_cents,
                "overage_pct": (total_cost / intent.budget_usd_cents - 1.0) * 100
            },
            blocking=True
        ))

    return violations
```

### Weather Verification

```python
def verify_weather(plan: PlanV1, weather_by_date: dict[str, WeatherDay]) -> list[Violation]:
    violations = []

    for day in plan.days:
        date_str = day.date.isoformat()
        weather = weather_by_date.get(date_str)

        if not weather:
            continue

        for slot in day.slots:
            for choice in slot.choices:
                # Skip indoor activities
                if choice.features.indoor:
                    continue

                # Check precipitation
                if weather.precip_prob > 70:
                    violations.append(Violation(
                        kind=ViolationKind.WEATHER_UNSUITABLE,
                        node_ref="verify.weather",
                        details={
                            "date": date_str,
                            "activity": choice.name,
                            "precip_prob": weather.precip_prob,
                            "reason": "High rain probability for outdoor activity"
                        },
                        blocking=True
                    ))

                # Check temperature extremes
                if weather.temp_c_high > 35 or weather.temp_c_low < 5:
                    violations.append(Violation(
                        kind=ViolationKind.WEATHER_UNSUITABLE,
                        node_ref="verify.weather",
                        details={
                            "date": date_str,
                            "activity": choice.name,
                            "temp_high": weather.temp_c_high,
                            "temp_low": weather.temp_c_low,
                            "reason": "Extreme temperature"
                        },
                        blocking=False  # Warning only
                    ))

    return violations
```

### Feasibility Verification

```python
def verify_feasibility(plan: PlanV1) -> list[Violation]:
    violations = []

    for day in plan.days:
        for i, slot in enumerate(day.slots):
            # Check for overlaps
            if i > 0:
                prev_end = day.slots[i-1].window.end
                curr_start = slot.window.start

                if curr_start < prev_end:
                    violations.append(Violation(
                        kind=ViolationKind.TIMING_INFEASIBLE,
                        node_ref="verify.feasibility",
                        details={
                            "day": day.date,
                            "overlap_minutes": (prev_end - curr_start).total_seconds() / 60,
                            "slot_index": i
                        },
                        blocking=True
                    ))

            # Check venue hours
            for choice in slot.choices:
                if choice.kind == ChoiceKind.ATTRACTION:
                    if not is_open_during(choice, slot.window):
                        violations.append(Violation(
                            kind=ViolationKind.VENUE_CLOSED,
                            node_ref="verify.feasibility",
                            details={
                                "venue": choice.name,
                                "scheduled_time": slot.window.start,
                                "opening_hours": choice.features.opening_hours
                            },
                            blocking=True
                        ))

    return violations
```

### Preference Verification

```python
def verify_preferences(intent: IntentV1, plan: PlanV1) -> list[Violation]:
    violations = []

    # Check kid-friendly requirement
    if intent.prefs.kid_friendly:
        for day in plan.days:
            for slot in day.slots:
                for choice in slot.choices:
                    if choice.features.kid_friendly == False:
                        violations.append(Violation(
                            kind=ViolationKind.PREF_VIOLATED,
                            node_ref="verify.preferences",
                            details={
                                "activity": choice.name,
                                "issue": "Not kid-friendly",
                                "day": day.date
                            },
                            blocking=False  # Soft violation
                        ))

    # Check theme coverage
    requested_themes = set(intent.prefs.themes)
    covered_themes = set()
    for day in plan.days:
        for slot in day.slots:
            for choice in slot.choices:
                covered_themes.update(choice.features.themes)

    missing_themes = requested_themes - covered_themes
    if missing_themes:
        violations.append(Violation(
            kind=ViolationKind.PREF_VIOLATED,
            node_ref="verify.preferences",
            details={
                "missing_themes": list(missing_themes),
                "covered_themes": list(covered_themes)
            },
            blocking=False  # Informational
        ))

    return violations
```

---

## Repair Engine

### Repair Loop Architecture

```
Violations from Verifier
    ↓
┌─────────────────────────────────────────┐
│ Repair Engine (≤3 cycles)               │
│                                         │
│  For each cycle:                        │
│    1. Select ≤2 highest priority        │
│       violations                        │
│    2. Apply appropriate fix move        │
│    3. Re-verify plan                    │
│    4. If no violations or max cycles,   │
│       exit                              │
│                                         │
│  Constraint: ≤2 moves per cycle         │
│  Constraint: ≤3 cycles total            │
│  Deterministic: No LLM calls            │
└─────────────────────────────────────────┘
    ↓
Repaired Plan (or timeout)
```

### Move Types

```python
class MoveType(str, Enum):
    DOWNGRADE_TIER = "downgrade_tier"        # Budget fix
    RESCHEDULE_ACTIVITY = "reschedule_activity"  # Weather/timing fix
    REPLACE_ACTIVITY = "replace_activity"    # Venue closed/pref violation
    REMOVE_ACTIVITY = "remove_activity"      # Last resort
    REORDER_ACTIVITIES = "reorder_activities"  # Timing optimization

class RepairMove(BaseModel):
    move_type: MoveType
    target_ref: str  # e.g., "day_2_slot_3"
    params: dict     # Move-specific parameters
    rationale: str
```

### Budget Repair (Downgrade Tier)

```python
def apply_budget_fix(plan: PlanV1, violation: Violation) -> RepairMove | None:
    """Downgrade expensive choices to reduce cost"""

    # Find most expensive downgradeable item
    candidates = []

    # Check flights
    for flight in plan.flights:
        if flight.tier in ["luxury", "mid"]:
            next_tier = "mid" if flight.tier == "luxury" else "budget"
            savings = flight.price - get_tier_price(next_tier, flight)
            candidates.append({
                "type": "flight",
                "item": flight,
                "savings": savings,
                "next_tier": next_tier
            })

    # Check lodging
    for lodging in plan.lodgings:
        if lodging.tier in ["luxury", "mid"]:
            next_tier = "mid" if lodging.tier == "luxury" else "budget"
            savings = lodging.price - get_tier_price(next_tier, lodging)
            candidates.append({
                "type": "lodging",
                "item": lodging,
                "savings": savings,
                "next_tier": next_tier
            })

    # Pick highest savings
    if not candidates:
        return None

    best = max(candidates, key=lambda c: c["savings"])

    return RepairMove(
        move_type=MoveType.DOWNGRADE_TIER,
        target_ref=f"{best['type']}_{best['item'].id}",
        params={"new_tier": best["next_tier"]},
        rationale=f"Downgrade {best['type']} from {best['item'].tier} to {best['next_tier']} to save ${best['savings']/100:.2f}"
    )
```

### Weather Repair (Reschedule)

```python
def apply_weather_fix(plan: PlanV1, violation: Violation, weather_by_date: dict) -> RepairMove | None:
    """Move outdoor activity to day with better weather"""

    activity_date = violation.details["date"]
    activity_ref = violation.details["activity_ref"]

    # Find days with better weather (precip_prob < 30%)
    good_weather_days = [
        date for date, weather in weather_by_date.items()
        if weather.precip_prob < 30 and date != activity_date
    ]

    if not good_weather_days:
        # No better weather, try replace with indoor activity
        return apply_activity_replacement(plan, activity_ref, indoor_only=True)

    # Pick closest day with good weather
    target_date = min(good_weather_days, key=lambda d: abs(parse_date(d) - parse_date(activity_date)))

    return RepairMove(
        move_type=MoveType.RESCHEDULE_ACTIVITY,
        target_ref=activity_ref,
        params={"new_date": target_date},
        rationale=f"Reschedule outdoor activity to {target_date} (better weather)"
    )
```

### Timing Repair (Reorder)

```python
def apply_timing_fix(plan: PlanV1, violation: Violation) -> RepairMove | None:
    """Reorder activities to eliminate overlaps"""

    day_idx = violation.details["day_index"]
    day = plan.days[day_idx]

    # Sort slots by start time (simple heuristic)
    sorted_slots = sorted(day.slots, key=lambda s: s.window.start)

    # Adjust durations if still overlapping
    for i in range(1, len(sorted_slots)):
        prev_end = sorted_slots[i-1].window.end
        curr_start = sorted_slots[i].window.start

        if curr_start < prev_end:
            # Shorten previous activity or delay current
            gap_needed = (prev_end - curr_start).total_seconds() / 60
            sorted_slots[i].window.start = prev_end + timedelta(minutes=15)  # Add buffer

    return RepairMove(
        move_type=MoveType.REORDER_ACTIVITIES,
        target_ref=f"day_{day_idx}",
        params={"new_order": [s.id for s in sorted_slots]},
        rationale="Reorder activities to eliminate timing conflicts"
    )
```

### Repair Tracking

```python
class RepairResult(BaseModel):
    """Track repair outcomes for observability"""
    cycles_run: int
    moves_applied: list[RepairMove]
    violations_fixed: list[Violation]
    remaining_violations: list[Violation]
    reuse_ratio: float  # % of original plan retained
    timeout: bool = False
```

---

## RAG System

### RAG Architecture

```
Document Upload (PDF/MD/TXT)
    ↓
┌─────────────────────────────────────┐
│ INGESTION PIPELINE                  │
│                                     │
│ 1. File Type Detection              │
│    ├─ PDF → PyMuPDF extraction      │
│    ├─ PDF (scanned) → Tesseract OCR │
│    ├─ MD → Markdown parser          │
│    └─ TXT → UTF-8 decoder           │
│                                     │
│ 2. Text Chunking (TikToken)         │
│    ├─ Chunk size: 800 tokens        │
│    ├─ Overlap: 100 tokens           │
│    └─ Preserve page boundaries      │
│                                     │
│ 3. Embedding Generation             │
│    └─ OpenAI text-embedding-3-small │
│       (1536 dimensions)             │
│                                     │
│ 4. Vector Storage (pgvector)        │
│    ├─ Cosine distance index         │
│    └─ Org + dest scoping            │
└─────────────────────────────────────┘
    ↓
Queryable Knowledge Base
    ↓
┌─────────────────────────────────────┐
│ RETRIEVAL PIPELINE                  │
│                                     │
│ 1. Query Embedding                  │
│    └─ Embed search query (1536d)   │
│                                     │
│ 2. Semantic Search (pgvector)       │
│    ├─ Cosine similarity             │
│    ├─ Org-scoped filtering          │
│    ├─ Dest-scoped filtering         │
│    └─ Top 20 results                │
│                                     │
│ 3. Fallback: Recency-based          │
│    └─ If no embeddings, use latest  │
│                                     │
│ 4. Citation Tracking                │
│    └─ Provenance metadata attached  │
└─────────────────────────────────────┘
    ↓
Retrieved Chunks (used in RAG node)
```

### PDF Processing Pipeline

```python
def extract_pdf_text(pdf_path: str, enable_ocr: bool = True) -> list[dict]:
    """Extract text from PDF with OCR fallback"""

    doc = fitz.open(pdf_path)
    pages = []

    for page_num, page in enumerate(doc):
        # Try native text extraction
        text = page.get_text()

        # OCR fallback for scanned pages
        if enable_ocr and len(text.strip()) < 50:  # Threshold
            pix = page.get_pixmap(dpi=144)  # 2x scaling
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(img)

        pages.append({
            "page_number": page_num + 1,
            "text": text,
            "char_count": len(text)
        })

    return pages
```

### Token-Aware Chunking

```python
import tiktoken

def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks by token count"""

    encoding = tiktoken.encoding_for_model("gpt-4")
    tokens = encoding.encode(text)
    chunks = []

    start = 0
    while start < len(tokens):
        end = start + chunk_size
        chunk_tokens = tokens[start:end]
        chunk_text = encoding.decode(chunk_tokens)
        chunks.append(chunk_text)

        start += (chunk_size - overlap)  # Move forward with overlap

    return chunks
```

### Semantic Search Query

```sql
-- Retrieve top 20 similar chunks
SELECT
    e.embedding_id,
    e.chunk_text,
    e.page_number,
    k.doc_name,
    1 - (e.vector <=> $1::vector) AS similarity  -- Cosine similarity
FROM embedding e
JOIN knowledge_item k ON e.item_id = k.item_id
JOIN destination d ON k.dest_id = d.dest_id
WHERE d.org_id = $2  -- Org scoping
  AND d.dest_id = $3  -- Destination scoping
ORDER BY e.vector <=> $1::vector  -- Cosine distance (ascending)
LIMIT 20;
```

### Citation Tracking

```python
class Citation(BaseModel):
    claim: str
    provenance: Provenance

class Provenance(BaseModel):
    source: str  # "tool" | "rag" | "user" | "fixture"
    source_url: str | None = None
    fetched_at: datetime | None = None
    response_digest: str | None = None  # SHA256 for dedup
    doc_name: str | None = None  # For RAG sources
    page_number: int | None = None

# Example citation
Citation(
    claim="The Louvre is closed on Tuesdays",
    provenance=Provenance(
        source="rag",
        doc_name="paris_guide.pdf",
        page_number=12,
        fetched_at=datetime.now(),
        response_digest="a1b2c3d4..."
    )
)
```

### RAG Integration in Planning

```python
async def rag_node(state: OrchestratorState) -> OrchestratorState:
    """Retrieve relevant knowledge chunks"""

    intent = state["intent"]

    # Build search query from intent
    query = f"{intent.city} {' '.join(intent.prefs.themes)} attractions activities"

    # Embed query
    query_embedding = await openai_embed(query)

    # Semantic search
    chunks = await pgvector_search(
        org_id=state["org_id"],
        dest_id=get_dest_id(intent.city, state["org_id"]),
        query_vector=query_embedding,
        limit=20
    )

    # Fallback to recency if no results
    if not chunks:
        chunks = await get_recent_chunks(
            org_id=state["org_id"],
            dest_id=get_dest_id(intent.city, state["org_id"]),
            limit=20
        )

    state["rag_chunks"] = [c.chunk_text for c in chunks]
    return state
```

---

## Security Architecture

### Authentication Flow

```
User Login Request
    ↓
┌─────────────────────────────────────┐
│ 1. Validate Email/Password          │
│    ├─ Check account lockout         │
│    ├─ Verify password (Argon2)      │
│    └─ Increment failed attempts     │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 2. Generate JWT Tokens (RS256)      │
│    ├─ Access Token (15min TTL)      │
│    │   Payload: {user_id, org_id,   │
│    │            token_type, exp, jti}│
│    │   Sign with RSA-4096 private key│
│    │                                 │
│    └─ Refresh Token (7day TTL)      │
│        Payload: {user_id, token_type,│
│                  exp, jti}           │
│        Store JTI in database         │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 3. Return Tokens to Client          │
│    {access_token, refresh_token,    │
│     expires_in: 900}                │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 4. Client Stores Tokens             │
│    ├─ Access token in memory        │
│    └─ Refresh token in httpOnly     │
│       cookie (secure)               │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 5. Authenticated Requests           │
│    Authorization: Bearer <access>   │
│    ├─ Verify signature (RSA public) │
│    ├─ Check expiry                  │
│    ├─ Extract user_id + org_id      │
│    └─ Proceed with request          │
└─────────────────────────────────────┘
    ↓
Token Expired?
    ├─ NO → Continue request
    └─ YES → Refresh flow
        ↓
    ┌─────────────────────────────────┐
    │ 6. Token Refresh                │
    │    POST /auth/refresh           │
    │    {refresh_token}              │
    │    ├─ Verify refresh token      │
    │    ├─ Check JTI in database     │
    │    ├─ Revoke old refresh token  │
    │    ├─ Issue new access token    │
    │    └─ Issue new refresh token   │
    └─────────────────────────────────┘
```

### Password Security

```python
from argon2 import PasswordHasher

ph = PasswordHasher(
    time_cost=2,      # Number of iterations
    memory_cost=65536,  # 64 MB memory
    parallelism=1,
    hash_len=32,
    salt_len=16
)

# Hash password on signup
password_hash = ph.hash("user_password")
# Stored: $argon2id$v=19$m=65536,t=2,p=1$...

# Verify password on login
try:
    ph.verify(stored_hash, input_password)
    # Success - proceed with login
except:
    # Failed - increment failed attempts
    increment_failed_login(user_id)
    if get_failed_attempts(user_id) >= 5:
        lock_account(user_id, duration_minutes=5)
```

### Account Lockout

```python
class AccountLockout:
    THRESHOLD = 5  # Failed attempts before lockout
    DURATION_MINUTES = 5

    @staticmethod
    def check_and_lock(user: User) -> bool:
        """Check if account should be locked"""

        # Count recent failed attempts (last 15 minutes)
        recent_failures = count_failed_logins(
            user.user_id,
            since=datetime.now() - timedelta(minutes=15)
        )

        if recent_failures >= AccountLockout.THRESHOLD:
            user.locked_until = datetime.now() + timedelta(minutes=AccountLockout.DURATION_MINUTES)
            db.commit()
            return True

        return False

    @staticmethod
    def is_locked(user: User) -> bool:
        """Check if account is currently locked"""
        if user.locked_until and user.locked_until > datetime.now():
            return True
        return False
```

### Rate Limiting (Redis Token Bucket)

```python
class RateLimiter:
    """Token bucket rate limiter with Redis"""

    async def check_rate_limit(self, key: str, limit: int, window_seconds: int) -> bool:
        """
        key: "ip:192.168.1.1" or "user:a1b2c3d4"
        limit: Max requests in window
        window_seconds: Time window
        """

        current = await redis.get(f"ratelimit:{key}")

        if current is None:
            # First request in window
            await redis.setex(f"ratelimit:{key}", window_seconds, 1)
            return True

        if int(current) >= limit:
            return False  # Rate limit exceeded

        await redis.incr(f"ratelimit:{key}")
        return True

# Usage
if not await rate_limiter.check_rate_limit(f"user:{user_id}", limit=10, window_seconds=3600):
    raise HTTPException(429, "Rate limit exceeded. Try again in 1 hour.")
```

### Security Headers Middleware

```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    # Content Security Policy
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:;"
    )

    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"

    # Prevent MIME sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # HTTPS only (in production)
    if settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response
```

### Multi-Tenancy Enforcement

```python
def get_current_user_org(token: str = Depends(oauth2_scheme)) -> tuple[str, str]:
    """Extract and verify user_id + org_id from JWT"""

    try:
        payload = jwt.decode(token, settings.JWT_PUBLIC_KEY_PEM, algorithms=["RS256"])
        user_id = payload.get("user_id")
        org_id = payload.get("org_id")

        if not user_id or not org_id:
            raise HTTPException(401, "Invalid token")

        return user_id, org_id
    except JWTError:
        raise HTTPException(401, "Invalid token")

# Usage in endpoints
@app.get("/destinations")
async def get_destinations(user_org: tuple = Depends(get_current_user_org)):
    user_id, org_id = user_org

    # All queries automatically scoped to org
    destinations = db.query(Destination).filter(
        Destination.org_id == org_id,
        Destination.user_id == user_id
    ).all()

    return destinations
```

---

## Frontend Structure

### Streamlit Pages Architecture

```
frontend/
├── Home.py                    # Landing page (entry point)
├── auth.py                    # Auth utilities (JWT management)
├── plan_app.py                # Shared planning logic
└── pages/
    ├── 00_Login.py            # Login page
    ├── 00_Signup.py           # Signup page
    ├── 01_Destinations.py     # Destination CRUD
    ├── 02_Knowledge_Base.py   # PDF/MD upload
    └── 04_Chat_Plan.py        # Conversational planning
```

### Session State Management

```python
# auth.py - Token management
import streamlit as st

def init_session_state():
    """Initialize session state variables"""
    if "access_token" not in st.session_state:
        st.session_state.access_token = None
    if "refresh_token" not in st.session_state:
        st.session_state.refresh_token = None
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "org_id" not in st.session_state:
        st.session_state.org_id = None

def is_authenticated() -> bool:
    """Check if user is logged in"""
    return st.session_state.access_token is not None

def logout():
    """Clear session state"""
    st.session_state.access_token = None
    st.session_state.refresh_token = None
    st.session_state.user_id = None
    st.session_state.org_id = None
    st.rerun()
```

### Authentication Guard

```python
# pages/01_Destinations.py
import streamlit as st
from auth import is_authenticated, init_session_state

init_session_state()

if not is_authenticated():
    st.warning("Please log in to access this page")
    st.stop()

# Authenticated page content
st.title("Destinations")
# ...
```

### SSE Streaming Integration

```python
# plan_app.py - Real-time progress updates
import sseclient
import requests

def stream_plan_progress(run_id: str, access_token: str):
    """Stream planning progress via SSE"""

    url = f"{BACKEND_URL}/plan/{run_id}/stream"
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.get(url, headers=headers, stream=True)
    client = sseclient.SSEClient(response)

    progress_container = st.empty()
    message_container = st.empty()

    for event in client.events():
        if event.event == "heartbeat":
            continue

        elif event.event == "node_event":
            data = json.loads(event.data)
            progress_container.info(f"Step: {data['node']} - {data['status']}")

        elif event.event == "message":
            data = json.loads(event.data)
            message_container.write(data["message"])

        elif event.event == "done":
            data = json.loads(event.data)
            st.success("Plan generated successfully!")
            return data["itinerary_id"]

        elif event.event == "error":
            data = json.loads(event.data)
            st.error(f"Error: {data['message']}")
            return None
```

### Chat Interface

```python
# pages/04_Chat_Plan.py
import streamlit as st

st.title("Chat Planning")

# Conversation history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# User input
if prompt := st.chat_input("Describe your travel plans"):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Call chat endpoint
    response = requests.post(
        f"{BACKEND_URL}/chat",
        headers={"Authorization": f"Bearer {st.session_state.access_token}"},
        json={
            "message": prompt,
            "conversation_history": st.session_state.messages
        }
    )

    data = response.json()

    # Add assistant message
    st.session_state.messages.append({
        "role": "assistant",
        "content": data["assistant_message"]
    })

    # If intent is complete, start plan generation
    if data["is_complete"] and data["run_id"]:
        st.info("Generating your itinerary...")
        itinerary_id = stream_plan_progress(data["run_id"], st.session_state.access_token)

        if itinerary_id:
            # Display final itinerary
            display_itinerary(itinerary_id)

    st.rerun()
```

---

## MCP Integration

### MCP Architecture

```
Backend (Python)
    ↓
┌─────────────────────────────────────┐
│ MCP Client (adapters/mcp/client.py) │
│  └─ HTTP requests to MCP server     │
└──────────────┬──────────────────────┘
               │ HTTP (port 3001)
               ↓
┌─────────────────────────────────────┐
│ MCP Server (Node.js)                │
│  ├─ server.js (entry point)         │
│  ├─ weather-tool.js (implementation)│
│  └─ mcp-protocol.js (utilities)     │
└─────────────────────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ External APIs                       │
│  ├─ OpenWeatherMap (primary)        │
│  └─ Fixtures (fallback)             │
└─────────────────────────────────────┘
```

### MCP Client (Python)

```python
# backend/app/adapters/mcp/client.py
import httpx

class MCPClient:
    def __init__(self, base_url: str = "http://localhost:3001", timeout: float = 3.0):
        self.base_url = base_url
        self.timeout = timeout

    async def call_tool(self, tool_name: str, params: dict) -> dict:
        """Call MCP tool with timeout and fallback"""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/tools/{tool_name}",
                    json=params,
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()

        except (httpx.TimeoutException, httpx.HTTPError) as e:
            logger.warning(f"MCP call failed: {e}, using fallback")
            return None  # Caller handles fallback

# Usage in weather adapter
async def get_weather_mcp(city: str, date: str) -> WeatherDay | None:
    client = MCPClient()
    result = await client.call_tool("get_weather", {"city": city, "date": date})

    if not result:
        return None  # Fallback to fixtures

    return WeatherDay(
        temp_c_high=result["temp_high"],
        temp_c_low=result["temp_low"],
        precip_prob=result["precip_prob"],
        wind_kmh=result["wind_speed"],
        conditions=result["conditions"]
    )
```

### MCP Server (Node.js)

```javascript
// mcp-server/src/server.js
const express = require('express');
const { getWeather } = require('./weather-tool');

const app = express();
app.use(express.json());

app.post('/tools/get_weather', async (req, res) => {
  try {
    const { city, date } = req.body;

    // Validate inputs
    if (!city || !date) {
      return res.status(400).json({ error: 'Missing city or date' });
    }

    // Call weather API
    const weather = await getWeather(city, date);

    res.json(weather);
  } catch (error) {
    console.error('Weather tool error:', error);
    res.status(500).json({ error: 'Weather fetch failed' });
  }
});

app.listen(3001, () => {
  console.log('MCP server listening on port 3001');
});
```

```javascript
// mcp-server/src/weather-tool.js
const axios = require('axios');

const OPENWEATHER_API_KEY = process.env.WEATHER_API_KEY;
const FIXTURES = require('./fixtures/weather.json');

async function getWeather(city, date) {
  try {
    // Call OpenWeatherMap API
    const response = await axios.get(
      `https://api.openweathermap.org/data/2.5/forecast`,
      {
        params: {
          q: city,
          appid: OPENWEATHER_API_KEY,
          units: 'metric'
        },
        timeout: 2000
      }
    );

    // Find forecast for target date
    const forecast = response.data.list.find(item =>
      item.dt_txt.startsWith(date)
    );

    if (!forecast) {
      throw new Error('No forecast for date');
    }

    return {
      temp_high: forecast.main.temp_max,
      temp_low: forecast.main.temp_min,
      precip_prob: forecast.pop * 100,
      wind_speed: forecast.wind.speed * 3.6,  // m/s to km/h
      conditions: forecast.weather[0].description
    };

  } catch (error) {
    console.warn('OpenWeather API failed, using fixture:', error.message);

    // Fallback to fixture data
    return FIXTURES[city] || FIXTURES['default'];
  }
}

module.exports = { getWeather };
```

### Fallback Fixtures

```json
// mcp-server/src/fixtures/weather.json
{
  "Paris": {
    "temp_high": 22,
    "temp_low": 15,
    "precip_prob": 20,
    "wind_speed": 15,
    "conditions": "partly cloudy"
  },
  "Tokyo": {
    "temp_high": 28,
    "temp_low": 22,
    "precip_prob": 30,
    "wind_speed": 10,
    "conditions": "sunny"
  },
  "default": {
    "temp_high": 20,
    "temp_low": 12,
    "precip_prob": 40,
    "wind_speed": 12,
    "conditions": "cloudy"
  }
}
```

---

## Key Design Decisions

### ADR-001: Money as Integer Cents

**Decision**: Store all monetary values as integer cents, not float dollars

**Rationale**:
- Eliminates floating-point precision errors (0.1 + 0.2 != 0.3)
- Financial accuracy for budget calculations
- Lossless arithmetic operations

**Trade-offs**:
- Must convert for display ($25.00 vs 2500 cents)
- Slightly less intuitive in code
- **Winner**: Financial correctness outweighs convenience

**Implementation**:
```python
class IntentV1(BaseModel):
    budget_usd_cents: int  # 250000 = $2500.00

def display_cost(cents: int) -> str:
    return f"${cents / 100:.2f}"
```

---

### ADR-002: Tri-State Booleans

**Decision**: Use `Optional[bool]` instead of custom enums for unknown values

**Rationale**:
- JSON serialization compatibility
- Pydantic native support
- Represents "unknown" state cleanly

**Trade-offs**:
- Less explicit than `enum State { Yes, No, Unknown }`
- Requires documentation of None meaning

**Implementation**:
```python
class ChoiceFeatures(BaseModel):
    indoor: bool | None = None  # True, False, or None (unknown)
    kid_friendly: bool | None = None
```

---

### ADR-003: UTC + IANA Timezone

**Decision**: Store datetime in UTC with separate timezone string

**Rationale**:
- Handles DST transitions correctly
- Historical accuracy (timezone rules change)
- Easy conversion to local time

**Trade-offs**:
- Two fields to maintain (datetime + tz string)
- More complex than naive datetime

**Implementation**:
```python
class DateWindow(BaseModel):
    start: datetime  # Always UTC
    end: datetime    # Always UTC
    tz: str          # "America/New_York"

def to_local(dt: datetime, tz: str) -> datetime:
    return dt.astimezone(ZoneInfo(tz))
```

---

### ADR-004: LangGraph vs Custom Orchestrator

**Decision**: Use LangGraph for workflow management

**Rationale**:
- Typed state management (TypedDict)
- Built-in checkpointing for resumability
- Graph visualization for debugging
- Community support and updates

**Trade-offs**:
- Framework dependency
- Learning curve for team
- Less control over execution

**Winner**: Productivity and maintainability outweigh control

---

### ADR-005: SSE for Streaming

**Decision**: Server-Sent Events for real-time updates, not WebSocket

**Rationale**:
- Simpler protocol (HTTP-based)
- Native browser support
- No need for bidirectional communication
- Easy to implement with FastAPI

**Trade-offs**:
- Unidirectional only (server→client)
- No request multiplexing
- Reconnection overhead

**Winner**: Simplicity for our use case (progress updates only)

---

### ADR-006: Deterministic Repair

**Decision**: Repair engine without LLM calls

**Rationale**:
- Bounded execution time (≤3 cycles)
- Predictable behavior (no hallucinations)
- Lower cost (no extra LLM API calls)
- Easier to debug and test

**Trade-offs**:
- Less intelligent fixes
- May miss creative solutions
- Requires hand-coded heuristics

**Winner**: Reliability and cost over creativity

---

### ADR-007: pgvector for RAG

**Decision**: Use PostgreSQL + pgvector extension instead of dedicated vector DB

**Rationale**:
- Single database for relational + vector data
- Simplifies infrastructure (no Pinecone/Weaviate)
- ACID guarantees for embeddings
- Org-scoped filtering in SQL

**Trade-offs**:
- Slower than specialized vector DBs at massive scale
- Fewer vector-specific features (quantization, ANN algorithms)

**Winner**: Simplicity for MVP scale (<1M vectors)

---

## Interview Talking Points

### 1. Architecture Highlights

**Talking Points**:
- "We use a 10-step LangGraph orchestration with typed state management for planning"
- "Multi-constraint verification with bounded deterministic repair (≤3 cycles, ≤2 moves)"
- "RAG-enhanced knowledge base with pgvector semantic search and PDF OCR"
- "Real-time streaming via SSE with heartbeat and resumption support"
- "Enterprise security: JWT RS256, Argon2 password hashing, org-scoped multi-tenancy"

**Deep Dive Questions to Expect**:
- Q: "Why LangGraph over a custom orchestrator?"
  - A: "Typed state management with TypedDict ensures type safety, built-in checkpointing allows resumability, and graph visualization aids debugging. While we lose some control, the productivity gains and community support outweigh this."

- Q: "How do you handle tool failures gracefully?"
  - A: "We use a multi-layered fallback strategy: MCP primary → fixture fallbacks → graceful degradation. For example, weather API failures fall back to seasonal averages. We also use circuit breakers (5 failures → 60s pause)."

- Q: "Explain your repair engine constraints"
  - A: "We enforce ≤2 moves per cycle and ≤3 cycles total to bound execution time. The repair is deterministic (no LLM calls) for predictability. We track reuse ratio to ensure minimal plan changes."

---

### 2. Technical Achievements

**Talking Points**:
- "Deterministic planning with seed-based RNG for reproducible results"
- "Token-aware chunking with 800-token chunks and 100-token overlap for optimal embeddings"
- "P95 latency: 9-11s end-to-end with 10-second budget"
- "Comprehensive testing: unit, integration, and evaluation scenarios"
- "Money stored as integer cents to eliminate floating-point errors"

**Deep Dive Questions to Expect**:
- Q: "How do you ensure budget accuracy?"
  - A: "We store all monetary values as integer cents (not float dollars) to eliminate floating-point precision errors. We also allow 10% budget slippage during verification to account for real-world variability."

- Q: "What's your testing strategy?"
  - A: "We have three layers: (1) Unit tests for models, utilities, and security functions. (2) Integration tests for full API flows and database operations. (3) Evaluation scenarios for end-to-end planning with real constraints."

---

### 3. Scalability & Performance

**Talking Points**:
- "Stateless backend design allows horizontal scaling"
- "Connection pooling with read replicas for database scaling"
- "Redis-based rate limiting (1000 req/hr per IP, 10 plans/hr per user)"
- "Parallel tool execution (flights, hotels, weather) saves 2-3 seconds"
- "pgvector cosine distance index for sub-second RAG retrieval"

**Deep Dive Questions to Expect**:
- Q: "How would you scale to 1M users?"
  - A: "Backend is stateless (no session affinity), so we can horizontally scale with load balancers. Database uses connection pooling and could add read replicas. Redis cluster for distributed rate limiting. For vector search at scale, we'd consider migrating to dedicated vector DB (Pinecone/Weaviate)."

- Q: "What are your performance bottlenecks?"
  - A: "Tool execution is the biggest bottleneck (1-3s P50). We mitigate with parallel execution and caching (FX rates, weather). Database queries are optimized with indexes (pgvector, run_org_user, etc.). LLM calls are unavoidable but we minimize them."

---

### 4. Security & Compliance

**Talking Points**:
- "JWT RS256 with 4096-bit RSA keys (not HS256 shared secrets)"
- "Argon2id password hashing with time-cost=2, memory-cost=64MB"
- "Account lockout after 5 failed attempts for 5 minutes"
- "Org-scoped multi-tenancy with database-level isolation"
- "Security headers: CSP, HSTS, X-Frame-Options, X-Content-Type-Options"

**Deep Dive Questions to Expect**:
- Q: "Why RS256 over HS256 for JWT?"
  - A: "RS256 uses asymmetric keys (public for verification, private for signing). This allows services to verify tokens without storing the private key, reducing attack surface. HS256 uses a shared secret, which must be distributed to all services."

- Q: "How do you prevent account enumeration attacks?"
  - A: "We use generic error messages ('Invalid email or password') to avoid revealing whether an email exists. We also rate-limit login attempts globally (1000/hr per IP) and per-user (5 attempts → lockout)."

---

### 5. RAG System Details

**Talking Points**:
- "PDF processing with PyMuPDF native extraction + Tesseract OCR fallback"
- "Token-aware chunking (800 tokens, 100 overlap) using TikToken"
- "OpenAI text-embedding-3-small (1536 dimensions)"
- "pgvector cosine distance search with org + destination scoping"
- "Citation tracking with provenance metadata (source, page, fetched_at)"

**Deep Dive Questions to Expect**:
- Q: "Why 800-token chunks with 100-token overlap?"
  - A: "800 tokens balances semantic coherence (enough context) with embedding quality (not too diluted). 100-token overlap ensures concepts near chunk boundaries aren't split, improving recall."

- Q: "How do you handle scanned PDFs?"
  - A: "We try native text extraction first (PyMuPDF). If a page has <50 characters (configurable threshold), we fall back to Tesseract OCR with 2x DPI scaling (144 DPI). We also OCR embedded images."

---

### 6. Multi-Constraint Verification

**Talking Points**:
- "Four verifiers: budget (10% slippage), weather (outdoor activities), feasibility (timing/hours), preferences (themes/kid-friendly)"
- "Budget verifier checks total cost including flights, lodging, activities, transit, and daily spend"
- "Weather verifier flags outdoor activities with >70% precipitation probability"
- "Feasibility verifier checks venue hours, overlaps, and connection buffers (120min airport, 15min transit)"
- "Violations are blocking or informational, guiding repair priority"

**Deep Dive Questions to Expect**:
- Q: "Why allow 10% budget slippage?"
  - A: "Real-world travel costs are variable (price fluctuations, taxes, tips). Strict enforcement would reject too many valid plans. 10% is a reasonable buffer while still providing budget discipline."

- Q: "How do you prioritize violations for repair?"
  - A: "We prioritize blocking violations first (budget exceeded, timing infeasible, venue closed). Within blocking violations, we sort by impact (budget overage amount, number of affected activities). We apply ≤2 fixes per cycle to avoid cascading changes."

---

### 7. User Experience

**Talking Points**:
- "Conversational planning with intent extraction (no forms)"
- "Real-time progress updates via SSE (node-level granularity)"
- "What-if scenario editing (budget, dates, preferences)"
- "Transparent cost breakdown (flights, lodging, activities, daily spend)"
- "Citations for all claims (RAG sources, tool responses)"

**Deep Dive Questions to Expect**:
- Q: "How does the chat interface extract intent?"
  - A: "We use a structured LLM prompt that parses natural language into IntentV1 schema (city, dates, budget, airports, preferences). The LLM asks clarifying questions if information is incomplete. Once all fields are populated, we validate and start planning."

- Q: "How do you handle user edits to existing plans?"
  - A: "We parse the edit message to identify what changed (e.g., 'increase budget to $3000'). We create a new intent with the modification and re-run the planner. We preserve locked_slots (user-pinned activities) during re-planning."

---

## Conclusion

**Key Strengths to Emphasize**:
1. **Production-Ready Architecture**: Full-stack, type-safe, tested, documented
2. **Agentic AI Orchestration**: LangGraph-based multi-step workflow
3. **Multi-Constraint Solving**: Verification + deterministic repair
4. **RAG Enhancement**: Semantic search with PDF OCR
5. **Enterprise Security**: JWT, Argon2, multi-tenancy, rate limiting
6. **Real-Time UX**: SSE streaming, conversational planning
7. **Scalable Design**: Stateless backend, horizontal scaling, caching

**Areas for Improvement (Be Honest)**:
- "RAG retrieval could use re-ranking for better precision"
- "Repair engine is deterministic but could benefit from LLM-guided fixes in future iterations"
- "Weather API has limited forecast horizon (7 days), constraining planning window"
- "Frontend is Streamlit (rapid prototyping) but could be migrated to React for richer UX"

**Closing Statement**:
"Triply demonstrates end-to-end AI-powered travel planning with real-world constraints, production-grade security, and a scalable architecture. It showcases my ability to design complex systems, integrate LLMs effectively, and balance technical correctness with user experience."

---

## Quick Reference

### File Locations

| Component | Path |
|-----------|------|
| LangGraph Nodes | `backend/app/graph/nodes.py` |
| Planning Algorithm | `backend/app/planning/planner.py` |
| Verification | `backend/app/verify/*.py` |
| Repair Engine | `backend/app/repair/engine.py` |
| RAG System | `backend/app/graph/rag.py` |
| PDF Parsing | `backend/app/utils/pdf_parser.py` |
| Security | `backend/app/security/*.py` |
| API Routes | `backend/app/api/*.py` |
| Database Models | `backend/app/db/models/*.py` |
| Frontend Pages | `frontend/pages/*.py` |
| MCP Server | `mcp-server/src/server.js` |

### Environment Variables (Critical)

```bash
# Database
POSTGRES_URL=postgresql://user:pass@localhost:5432/triply_dev

# Auth
JWT_PRIVATE_KEY_PEM="-----BEGIN RSA PRIVATE KEY-----\n..."
JWT_PUBLIC_KEY_PEM="-----BEGIN PUBLIC KEY-----\n..."

# LLM
OPENAI_API_KEY=sk-...

# External APIs
WEATHER_API_KEY=...

# MCP
MCP_WEATHER_ENDPOINT=http://localhost:3001
MCP_ENABLED=true

# Security
PASSWORD_MIN_LENGTH=8
LOCKOUT_THRESHOLD=5
```

### Docker Commands

```bash
# Start full stack
docker-compose up -d

# View logs
docker-compose logs -f backend

# Restart service
docker-compose restart backend

# Stop all
docker-compose down

# Rebuild
docker-compose up -d --build
```

### Database Commands

```bash
# Run migrations
alembic upgrade head

# Create migration
alembic revision --autogenerate -m "description"

# Seed database
python scripts/seed_db.py

# Connect to DB
psql -h localhost -U triply_user -d triply_dev
```

### Testing Commands

```bash
# All tests
pytest -v

# Unit only
pytest -m unit

# Integration only
pytest -m integration

# With coverage
pytest --cov=backend --cov-report=html

# Specific test
pytest tests/unit/test_budget.py::test_budget_verification
```

---

**Good luck with your interview! You've got this! 🚀**