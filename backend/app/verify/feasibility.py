"""Feasibility verification - SPEC §6.2–6.3.

Pure functions that verify:
- Timing gaps between slots meet buffer requirements
- Venue hours accommodate slot windows
- DST transitions don't cause false violations
- Last train cutoff constraints
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from backend.app.metrics.registry import MetricsClient
from backend.app.models.common import ViolationKind
from backend.app.models.intent import IntentV1
from backend.app.models.plan import PlanV1
from backend.app.models.tool_results import Attraction
from backend.app.models.violations import Violation


def verify_feasibility(
    intent: IntentV1,
    plan: PlanV1,
    attractions: dict[str, Attraction],
    last_train_cutoff: time = time(23, 30),
    metrics: MetricsClient | None = None,
) -> list[Violation]:
    """Verify timing and venue feasibility constraints.

    Args:
        intent: User's intent with timezone
        plan: Generated plan to verify
        attractions: Mapping of option_ref -> Attraction for venue hour checks
        last_train_cutoff: Local time of last public transit (default 23:30)
        metrics: Optional metrics client for telemetry

    Returns:
        List of violations for timing gaps, venue closures, and last train issues

    Checks per SPEC §6.2–6.3:
        - Adjacent slot timing with appropriate buffers
        - Venue opening hours coverage (any window must fully contain slot)
        - DST transitions handled via zoneinfo
        - Last train cutoff for final activities
    """
    violations: list[Violation] = []
    tz = ZoneInfo(intent.date_window.tz)

    # Museum buffer constant per SPEC
    MUSEUM_BUFFER_MINUTES = 20

    for day_plan in plan.days:
        # Sort slots by start time for timing checks
        sorted_slots = sorted(day_plan.slots, key=lambda s: s.window.start)

        # Check timing gaps between adjacent slots
        for i in range(len(sorted_slots) - 1):
            current_slot = sorted_slots[i]
            next_slot = sorted_slots[i + 1]

            # Determine appropriate buffer based on current slot type
            if not current_slot.choices:
                continue

            current_choice = current_slot.choices[0]

            # Choose buffer based on choice kind and context
            if current_choice.kind.value == "flight":
                buffer_minutes = plan.assumptions.airport_buffer_minutes
                buffer_name = "airport"
            elif (
                current_choice.kind.value == "attraction"
                and current_choice.option_ref in attractions
            ):
                attraction = attractions[current_choice.option_ref]
                if attraction.venue_type == "museum":
                    buffer_minutes = MUSEUM_BUFFER_MINUTES
                    buffer_name = "museum"
                else:
                    buffer_minutes = plan.assumptions.transit_buffer_minutes
                    buffer_name = "in-city transit"
            else:
                buffer_minutes = plan.assumptions.transit_buffer_minutes
                buffer_name = "in-city transit"

            # Calculate gap using timezone-aware datetimes for DST safety
            current_end_dt = datetime.combine(
                day_plan.date, current_slot.window.end, tzinfo=tz
            )
            next_start_dt = datetime.combine(
                day_plan.date, next_slot.window.start, tzinfo=tz
            )

            # Handle DST edge case: if times cross DST boundary, adjust
            gap_delta = next_start_dt - current_end_dt
            gap_minutes = gap_delta.total_seconds() / 60

            if gap_minutes < buffer_minutes:
                # Emit timing feasibility violation metric
                if metrics:
                    metrics.inc_feasibility_violation("timing")

                violations.append(
                    Violation(
                        kind=ViolationKind.timing_infeasible,
                        node_ref=current_choice.option_ref,
                        details={
                            "gap_minutes": gap_minutes,
                            "required_minutes": buffer_minutes,
                            "buffer_type": buffer_name,
                            "current_end": current_slot.window.end.isoformat(),
                            "next_start": next_slot.window.start.isoformat(),
                        },
                        blocking=True,
                    )
                )

        # Check venue hours for attractions
        for slot in day_plan.slots:
            if not slot.choices:
                continue

            choice = slot.choices[0]
            if choice.kind.value != "attraction":
                continue

            option_ref = choice.option_ref
            if option_ref not in attractions:
                continue

            attraction = attractions[option_ref]

            # Get day of week (0=Monday, 6=Sunday)
            day_of_week = day_plan.date.weekday()
            day_key = str(day_of_week)

            # Check if venue has opening hours for this day
            if day_key not in attraction.opening_hours:
                # No hours specified = closed
                # Emit venue closed metric
                if metrics:
                    metrics.inc_violation("venue_closed")

                violations.append(
                    Violation(
                        kind=ViolationKind.venue_closed,
                        node_ref=option_ref,
                        details={
                            "venue_name": attraction.name,
                            "date": day_plan.date.isoformat(),
                            "day_of_week": day_of_week,
                            "reason": "no_opening_hours",
                        },
                        blocking=True,
                    )
                )
                continue

            windows = attraction.opening_hours[day_key]
            if not windows:
                # Empty list = closed
                # Emit venue closed metric
                if metrics:
                    metrics.inc_violation("venue_closed")

                violations.append(
                    Violation(
                        kind=ViolationKind.venue_closed,
                        node_ref=option_ref,
                        details={
                            "venue_name": attraction.name,
                            "date": day_plan.date.isoformat(),
                            "day_of_week": day_of_week,
                            "reason": "closed_all_day",
                        },
                        blocking=True,
                    )
                )
                continue

            # Check if ANY window fully covers the slot (SPEC §6.3)
            slot_covered = False
            for window in windows:
                # Convert to comparable times in same timezone
                # Windows are datetime with timezone info
                window_start_time = window.start.astimezone(tz).time()
                window_end_time = window.end.astimezone(tz).time()

                if (
                    window_start_time <= slot.window.start
                    and slot.window.end <= window_end_time
                ):
                    slot_covered = True
                    break

            if not slot_covered:
                # Emit venue closed metric
                if metrics:
                    metrics.inc_violation("venue_closed")

                violations.append(
                    Violation(
                        kind=ViolationKind.venue_closed,
                        node_ref=option_ref,
                        details={
                            "venue_name": attraction.name,
                            "date": day_plan.date.isoformat(),
                            "slot_start": slot.window.start.isoformat(),
                            "slot_end": slot.window.end.isoformat(),
                            "available_windows": [
                                {
                                    "start": w.start.astimezone(tz).time().isoformat(),
                                    "end": w.end.astimezone(tz).time().isoformat(),
                                }
                                for w in windows
                            ],
                            "reason": "outside_opening_hours",
                        },
                        blocking=True,
                    )
                )

        # Check last train cutoff for final activities
        if sorted_slots:
            last_slot = sorted_slots[-1]
            if last_slot.choices:
                last_choice = last_slot.choices[0]
                # If last activity ends after last train minus buffer, violation
                last_activity_end = last_slot.window.end

                # Calculate latest acceptable end time
                # (last_train_cutoff - transit_buffer)
                buffer_delta = timedelta(
                    minutes=plan.assumptions.transit_buffer_minutes
                )
                last_train_dt = datetime.combine(
                    day_plan.date, last_train_cutoff, tzinfo=tz
                )
                latest_end_dt = last_train_dt - buffer_delta
                latest_end_time = latest_end_dt.time()

                if last_activity_end > latest_end_time:
                    # Emit timing feasibility violation metric (last train is timing issue)
                    if metrics:
                        metrics.inc_feasibility_violation("timing")

                    violations.append(
                        Violation(
                            kind=ViolationKind.timing_infeasible,
                            node_ref=last_choice.option_ref,
                            details={
                                "activity_end": last_activity_end.isoformat(),
                                "last_train": last_train_cutoff.isoformat(),
                                "latest_end": latest_end_time.isoformat(),
                                "buffer_minutes": plan.assumptions.transit_buffer_minutes,
                                "reason": "last_train_missed",
                            },
                            blocking=True,
                        )
                    )

    return violations
