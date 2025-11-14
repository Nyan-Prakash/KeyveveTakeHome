"""LangGraph state definition for orchestrator."""

from datetime import UTC, date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.intent import IntentV1
from backend.app.models.itinerary import ItineraryV1
from backend.app.models.plan import PlanV1
from backend.app.models.tool_results import Attraction, FlightOption, WeatherDay
from backend.app.models.violations import Violation


class OrchestratorState(BaseModel):
    """Typed state for LangGraph orchestrator.

    This state is passed through all nodes and contains the current
    planning context and intermediate results.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    trace_id: str = Field(description="Unique trace ID for this run")
    org_id: UUID = Field(description="Organization ID for tenancy")
    user_id: UUID = Field(description="User ID who initiated this run")
    seed: int = Field(description="Random seed for deterministic behavior")
    intent: IntentV1 = Field(description="Original user intent")
    plan: PlanV1 | None = Field(default=None, description="Generated plan")
    candidate_plans: list[PlanV1] = Field(
        default_factory=list, description="All candidate plans from planner"
    )
    itinerary: ItineraryV1 | None = Field(
        default=None, description="Final itinerary output"
    )
    messages: list[str] = Field(
        default_factory=list, description="Progress messages for SSE streaming"
    )
    violations: list[Violation] = Field(
        default_factory=list, description="Constraint violations detected"
    )
    done: bool = Field(default=False, description="Whether processing is complete")
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the run started",
    )
    last_event_ts: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp of last event",
    )

    # Tool results for verification (PR7)
    weather_by_date: dict[date, WeatherDay] = Field(
        default_factory=dict,
        description="Weather forecasts keyed by date",
    )
    attractions: dict[str, Attraction] = Field(
        default_factory=dict,
        description="Attractions keyed by option_ref",
    )
    flights: dict[str, FlightOption] = Field(
        default_factory=dict,
        description="Flight options keyed by option_ref",
    )
