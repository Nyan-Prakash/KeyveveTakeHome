"""Convenient imports for all model types."""

# Common types and enums
from .common import (
    ChoiceKind,
    Geo,
    Money,
    Provenance,
    Tier,
    TimeWindow,
    TransitMode,
    ViolationKind,
)

# Intent models
from .intent import DateWindow, IntentV1, LockedSlot, Preferences

# Itinerary models
from .itinerary import (
    Activity,
    Citation,
    CostBreakdown,
    DayItinerary,
    Decision,
    ItineraryV1,
)

# Plan models
from .plan import Assumptions, Choice, ChoiceFeatures, DayPlan, PlanV1, Slot

# Tool result models
from .tool_results import (
    Attraction,
    FlightOption,
    Lodging,
    TransitLeg,
    WeatherDay,
    Window,
)

# Violation models
from .violations import Violation

__all__ = [
    # Common
    "ChoiceKind",
    "Geo",
    "Money",
    "Provenance",
    "Tier",
    "TimeWindow",
    "TransitMode",
    "ViolationKind",
    # Intent
    "DateWindow",
    "IntentV1",
    "LockedSlot",
    "Preferences",
    # Plan
    "Assumptions",
    "Choice",
    "ChoiceFeatures",
    "DayPlan",
    "PlanV1",
    "Slot",
    # Tool Results
    "Attraction",
    "FlightOption",
    "Lodging",
    "TransitLeg",
    "WeatherDay",
    "Window",
    # Violations
    "Violation",
    # Itinerary
    "Activity",
    "Citation",
    "CostBreakdown",
    "DayItinerary",
    "Decision",
    "ItineraryV1",
]
