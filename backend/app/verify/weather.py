"""Weather suitability verification - SPEC §6.4.

Pure function that verifies weather constraints against activity indoor/outdoor status.
Uses tri-state logic: indoor=True (safe), indoor=False (blocks if bad weather),
indoor=None (advisory warning).
"""

from datetime import date

from backend.app.metrics.registry import MetricsClient
from backend.app.models.common import ViolationKind
from backend.app.models.plan import PlanV1
from backend.app.models.tool_results import WeatherDay
from backend.app.models.violations import Violation

# Weather thresholds from SPEC §6.4
PRECIP_THRESHOLD = 0.60  # 60% precipitation probability
WIND_THRESHOLD_KMH = 30.0  # 30 km/h wind speed


def verify_weather(
    plan: PlanV1,
    weather_by_date: dict[date, WeatherDay],
    metrics: MetricsClient | None = None,
) -> list[Violation]:
    """Verify weather suitability for outdoor activities.

    Args:
        plan: Generated plan to verify
        weather_by_date: Weather forecasts keyed by date
        metrics: Optional metrics client for telemetry

    Returns:
        List of violations for weather issues

    Tri-state logic per SPEC §6.4:
        - If bad weather (precip >= 0.60 OR wind >= 30 km/h):
            - indoor == False (explicit outdoor) → BLOCKING violation
            - indoor == None (unknown) → ADVISORY violation
            - indoor == True → no violation (safe indoors)
        - If good weather → no violations
    """
    violations: list[Violation] = []

    for day_plan in plan.days:
        # Get weather for this day
        weather = weather_by_date.get(day_plan.date)
        if not weather:
            # No weather data - can't verify, skip
            continue

        # Check if weather is unsuitable
        bad_weather = (
            weather.precip_prob >= PRECIP_THRESHOLD
            or weather.wind_kmh >= WIND_THRESHOLD_KMH
        )

        if not bad_weather:
            # Good weather, no concerns
            continue

        # Bad weather - check each slot's indoor/outdoor status
        for slot in day_plan.slots:
            if not slot.choices:
                continue

            choice = slot.choices[0]
            indoor_status = choice.features.indoor

            if indoor_status is False:
                # Explicit outdoor activity in bad weather → BLOCKING
                # Emit blocking weather violation metric
                if metrics:
                    metrics.inc_weather_blocking()

                violations.append(
                    Violation(
                        kind=ViolationKind.weather_unsuitable,
                        node_ref=choice.option_ref,
                        details={
                            "date": day_plan.date.isoformat(),
                            "precip_prob": weather.precip_prob,
                            "wind_kmh": weather.wind_kmh,
                            "indoor": False,
                            "severity": "blocking",
                            "reason": "outdoor_activity_bad_weather",
                        },
                        blocking=True,
                    )
                )
            elif indoor_status is None:
                # Unknown indoor/outdoor status in bad weather → ADVISORY
                # Emit advisory weather violation metric
                if metrics:
                    metrics.inc_weather_advisory()

                violations.append(
                    Violation(
                        kind=ViolationKind.weather_unsuitable,
                        node_ref=choice.option_ref,
                        details={
                            "date": day_plan.date.isoformat(),
                            "precip_prob": weather.precip_prob,
                            "wind_kmh": weather.wind_kmh,
                            "indoor": None,
                            "severity": "advisory",
                            "reason": "uncertain_weather",
                        },
                        blocking=False,
                    )
                )
            # indoor_status == True → no violation, safe indoors

    return violations
