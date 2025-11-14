"""Common test helpers for verifier unit tests."""

from datetime import UTC, date, datetime, time, timedelta

from backend.app.models.common import ChoiceKind, Provenance, TimeWindow
from backend.app.models.intent import DateWindow, IntentV1, Preferences
from backend.app.models.plan import Assumptions, Choice, ChoiceFeatures, DayPlan, PlanV1, Slot


def create_test_intent(
    budget_usd_cents: int = 100_000,
    tz: str = "Europe/Paris",
    prefs: Preferences | None = None,
) -> IntentV1:
    """Create a minimal test intent."""
    return IntentV1(
        city="Paris",
        date_window=DateWindow(
            start=date(2025, 6, 1),
            end=date(2025, 6, 7),
            tz=tz,
        ),
        budget_usd_cents=budget_usd_cents,
        airports=["CDG"],
        prefs=prefs or Preferences(),
    )


def create_test_slot(
    kind: ChoiceKind,
    option_ref: str,
    start: time = time(10, 0),
    end: time = time(12, 0),
    cost_usd_cents: int = 1000,
    indoor: bool | None = None,
    themes: list[str] | None = None,
) -> Slot:
    """Create a test slot with a single choice."""
    return Slot(
        window=TimeWindow(start=start, end=end),
        choices=[
            Choice(
                kind=kind,
                option_ref=option_ref,
                features=ChoiceFeatures(
                    cost_usd_cents=cost_usd_cents,
                    travel_seconds=1800,
                    indoor=indoor,
                    themes=themes or [],
                ),
                score=0.85,
                provenance=Provenance(
                    source="test",
                    fetched_at=datetime.now(UTC),
                    cache_hit=False,
                ),
            )
        ],
        locked=False,
    )


def pad_plan_to_min_days(days: list[DayPlan], min_days: int = 4) -> list[DayPlan]:
    """Pad a plan to meet minimum 4-day requirement.

    Adds filler days with a single attraction slot to meet PlanV1 requirements.
    """
    if len(days) >= min_days:
        return days

    result = list(days)
    last_date = days[-1].date if days else date(2025, 6, 1)

    for i in range(len(days), min_days):
        next_date = last_date + timedelta(days=(i - len(days) + 1))
        result.append(
            DayPlan(
                date=next_date,
                slots=[
                    create_test_slot(
                        ChoiceKind.attraction,
                        f"filler_{i}",
                        time(14, 0),
                        time(16, 0),
                    )
                ],
            )
        )

    return result


def create_test_plan(
    days: list[DayPlan],
    assumptions: Assumptions | None = None,
    pad_days: bool = True,
) -> PlanV1:
    """Create a test plan, optionally padding to 4 days minimum."""
    if pad_days:
        days = pad_plan_to_min_days(days)

    return PlanV1(
        days=days,
        assumptions=assumptions or Assumptions(
            fx_rate_usd_eur=0.92,
            daily_spend_est_cents=1000,
        ),
        rng_seed=42,
    )
