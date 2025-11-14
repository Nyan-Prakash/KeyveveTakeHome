"""Preferences verification - SPEC §6.5.

Pure function that verifies user preferences are respected.
Distinguishes between must-have (blocking) and nice-to-have (advisory) preferences.
"""

from datetime import time

from backend.app.metrics.registry import MetricsClient
from backend.app.models.common import ViolationKind
from backend.app.models.intent import IntentV1
from backend.app.models.plan import PlanV1
from backend.app.models.tool_results import Attraction, FlightOption
from backend.app.models.violations import Violation

# Kid-friendly constraint: no activities past this time
KID_FRIENDLY_CUTOFF = time(20, 0)  # 8 PM


def verify_preferences(
    intent: IntentV1,
    plan: PlanV1,
    flights: dict[str, FlightOption],
    attractions: dict[str, Attraction],
    metrics: MetricsClient | None = None,
) -> list[Violation]:
    """Verify user preferences are respected.

    Args:
        intent: User's intent with preferences
        plan: Generated plan to verify
        flights: Mapping of option_ref -> FlightOption for overnight checks
        attractions: Mapping of option_ref -> Attraction for kid-friendly checks
        metrics: Optional metrics client for telemetry

    Returns:
        List of violations for preference issues

    Preference types per SPEC §6.5:
        - Must-haves (blocking):
            - avoid_overnight flights
            - kid_friendly (no late slots, kid-friendly venues only)
        - Nice-to-haves (advisory):
            - Theme coverage
            - Activity variety
    """
    violations: list[Violation] = []
    prefs = intent.prefs

    # Check avoid_overnight preference (must-have)
    if prefs.avoid_overnight:
        for day_plan in plan.days:
            for slot in day_plan.slots:
                if not slot.choices:
                    continue

                choice = slot.choices[0]
                if choice.kind.value == "flight":
                    option_ref = choice.option_ref
                    if option_ref in flights:
                        flight = flights[option_ref]
                        if flight.overnight:
                            # Emit preference violation metric
                            if metrics:
                                metrics.inc_pref_violation("avoid_overnight")

                            violations.append(
                                Violation(
                                    kind=ViolationKind.pref_violated,
                                    node_ref=option_ref,
                                    details={
                                        "preference": "avoid_overnight",
                                        "flight_id": flight.flight_id,
                                        "reason": "overnight_flight_selected",
                                    },
                                    blocking=True,
                                )
                            )

    # Check kid_friendly preferences (must-have)
    if prefs.kid_friendly:
        for day_plan in plan.days:
            for slot in day_plan.slots:
                if not slot.choices:
                    continue

                choice = slot.choices[0]

                # Check for late night activities
                if slot.window.end > KID_FRIENDLY_CUTOFF:
                    # Emit preference violation metric
                    if metrics:
                        metrics.inc_pref_violation("kid_friendly")

                    violations.append(
                        Violation(
                            kind=ViolationKind.pref_violated,
                            node_ref=choice.option_ref,
                            details={
                                "preference": "kid_friendly",
                                "slot_end": slot.window.end.isoformat(),
                                "cutoff": KID_FRIENDLY_CUTOFF.isoformat(),
                                "reason": "late_night_activity",
                            },
                            blocking=True,
                        )
                    )

                # Check if attraction is kid-friendly
                if choice.kind.value == "attraction":
                    option_ref = choice.option_ref
                    if option_ref in attractions:
                        attraction = attractions[option_ref]
                        # Only flag if explicitly NOT kid-friendly
                        # (None/unknown is acceptable with advisory)
                        if attraction.kid_friendly is False:
                            # Emit preference violation metric
                            if metrics:
                                metrics.inc_pref_violation("kid_friendly")

                            violations.append(
                                Violation(
                                    kind=ViolationKind.pref_violated,
                                    node_ref=option_ref,
                                    details={
                                        "preference": "kid_friendly",
                                        "venue_name": attraction.name,
                                        "kid_friendly": False,
                                        "reason": "not_kid_friendly",
                                    },
                                    blocking=False,  # Advisory since it's soft
                                )
                            )
                        elif attraction.kid_friendly is None:
                            # Unknown kid-friendliness - advisory
                            # Emit preference violation metric
                            if metrics:
                                metrics.inc_pref_violation("kid_friendly")

                            violations.append(
                                Violation(
                                    kind=ViolationKind.pref_violated,
                                    node_ref=option_ref,
                                    details={
                                        "preference": "kid_friendly",
                                        "venue_name": attraction.name,
                                        "kid_friendly": None,
                                        "reason": "unknown_kid_friendly",
                                    },
                                    blocking=False,
                                )
                            )

    # Check theme coverage (nice-to-have - advisory)
    if prefs.themes:
        # Count slots matching user themes
        matching_slots = 0
        total_attraction_slots = 0

        for day_plan in plan.days:
            for slot in day_plan.slots:
                if not slot.choices:
                    continue

                choice = slot.choices[0]
                if choice.kind.value == "attraction":
                    total_attraction_slots += 1
                    choice_themes = choice.features.themes or []
                    if any(theme in choice_themes for theme in prefs.themes):
                        matching_slots += 1

        # If less than 50% of attractions match themes, advisory
        if total_attraction_slots > 0:
            match_rate = matching_slots / total_attraction_slots
            if match_rate < 0.5:
                # Emit preference violation metric
                if metrics:
                    metrics.inc_pref_violation("themes")

                violations.append(
                    Violation(
                        kind=ViolationKind.pref_violated,
                        node_ref="theme_coverage",
                        details={
                            "preference": "themes",
                            "requested_themes": prefs.themes,
                            "matching_slots": matching_slots,
                            "total_slots": total_attraction_slots,
                            "match_rate": match_rate,
                            "reason": "low_theme_coverage",
                        },
                        blocking=False,  # Advisory
                    )
                )

    return violations
