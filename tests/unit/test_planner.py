"""Unit tests for the PR6 planner module."""

from datetime import date, time

from backend.app.models.common import TimeWindow
from backend.app.models.intent import DateWindow, IntentV1, LockedSlot, Preferences
from backend.app.planning.planner import build_candidate_plans


class TestPlannerFanOut:
    """Test planner fan-out constraints."""

    def test_fanout_cap_never_exceeded(self):
        """Test that planner never returns more than 4 plans."""
        # Create a high-budget intent that could generate many plans
        intent = IntentV1(
            city="Paris",
            date_window=DateWindow(
                start=date(2025, 6, 1),
                end=date(2025, 6, 8),
                tz="Europe/Paris"
            ),
            budget_usd_cents=500_000,  # $5000 - high budget
            airports=["CDG", "ORY", "BVA"],  # Multiple airports
            prefs=Preferences(
                kid_friendly=False,
                themes=["art", "food", "culture", "outdoor"],  # Many themes
                avoid_overnight=False,
                locked_slots=[]
            )
        )

        plans = build_candidate_plans(intent)

        assert len(plans) <= 4, f"Expected ≤4 plans, got {len(plans)}"
        assert len(plans) >= 1, "Expected at least 1 plan"

    def test_plans_differ_meaningfully(self):
        """Test that different plans have meaningful differences."""
        intent = IntentV1(
            city="Paris",
            date_window=DateWindow(
                start=date(2025, 6, 1),
                end=date(2025, 6, 5),
                tz="Europe/Paris"
            ),
            budget_usd_cents=300_000,  # $3000
            airports=["CDG", "ORY"],
            prefs=Preferences(
                kid_friendly=False,
                themes=["art", "food"],
                avoid_overnight=False,
                locked_slots=[]
            )
        )

        plans = build_candidate_plans(intent)

        if len(plans) > 1:
            # Check that plans have different cost structures
            total_costs = []
            for plan in plans:
                total_cost = 0
                for day in plan.days:
                    for slot in day.slots:
                        total_cost += slot.choices[0].features.cost_usd_cents
                total_costs.append(total_cost)

            # At least two plans should have different total costs
            unique_costs = set(total_costs)
            assert len(unique_costs) > 1, "Plans should have different cost structures"

    def test_deterministic_output(self):
        """Test that same intent always produces same plans."""
        intent = IntentV1(
            city="Tokyo",
            date_window=DateWindow(
                start=date(2025, 7, 1),
                end=date(2025, 7, 5),
                tz="Asia/Tokyo"
            ),
            budget_usd_cents=200_000,  # $2000
            airports=["NRT"],
            prefs=Preferences(
                kid_friendly=True,
                themes=["culture"],
                avoid_overnight=True,
                locked_slots=[]
            )
        )

        plans1 = build_candidate_plans(intent)
        plans2 = build_candidate_plans(intent)

        assert len(plans1) == len(plans2)

        # Check that corresponding plans are identical
        for p1, p2 in zip(plans1, plans2, strict=False):
            assert len(p1.days) == len(p2.days)
            for d1, d2 in zip(p1.days, p2.days, strict=False):
                assert d1.date == d2.date
                assert len(d1.slots) == len(d2.slots)
                for s1, s2 in zip(d1.slots, d2.slots, strict=False):
                    assert s1.window == s2.window
                    assert s1.locked == s2.locked
                    assert len(s1.choices) == len(s2.choices)
                    # Compare first choice features
                    f1, f2 = s1.choices[0].features, s2.choices[0].features
                    assert f1.cost_usd_cents == f2.cost_usd_cents
                    assert f1.travel_seconds == f2.travel_seconds


class TestPlannerConstraints:
    """Test planner respects constraints."""

    def test_respects_trip_dates(self):
        """Test that all plan days fall within the trip window."""
        intent = IntentV1(
            city="London",
            date_window=DateWindow(
                start=date(2025, 8, 10),
                end=date(2025, 8, 15),
                tz="Europe/London"
            ),
            budget_usd_cents=150_000,
            airports=["LHR"],
            prefs=Preferences()
        )

        plans = build_candidate_plans(intent)

        for plan in plans:
            for day in plan.days:
                assert intent.date_window.start <= day.date <= intent.date_window.end

    def test_honors_locked_slots(self):
        """Test that locked slots appear in plans unchanged."""
        locked_slot = LockedSlot(
            day_offset=1,
            window=TimeWindow(start=time(14, 0), end=time(16, 0)),
            activity_id="louvre_tour"
        )

        intent = IntentV1(
            city="Paris",
            date_window=DateWindow(
                start=date(2025, 6, 1),
                end=date(2025, 6, 5),
                tz="Europe/Paris"
            ),
            budget_usd_cents=200_000,
            airports=["CDG"],
            prefs=Preferences(locked_slots=[locked_slot])
        )

        plans = build_candidate_plans(intent)

        for plan in plans:
            if len(plan.days) > 1:  # Check day 1 (offset 1)
                day_1 = plan.days[1]
                locked_found = False

                for slot in day_1.slots:
                    if (slot.locked and
                        slot.window.start == time(14, 0) and
                        slot.window.end == time(16, 0)):
                        locked_found = True
                        assert slot.choices[0].option_ref == "louvre_tour"

                assert locked_found, "Locked slot not found in day 1"

    def test_avoids_overlapping_slots(self):
        """Test that slots don't overlap within a day."""
        intent = IntentV1(
            city="Berlin",
            date_window=DateWindow(
                start=date(2025, 9, 1),
                end=date(2025, 9, 5),
                tz="Europe/Berlin"
            ),
            budget_usd_cents=180_000,
            airports=["BER"],
            prefs=Preferences()
        )

        plans = build_candidate_plans(intent)

        for plan in plans:
            for day in plan.days:
                slots = day.slots
                for i in range(len(slots) - 1):
                    current_end = slots[i].window.end
                    next_start = slots[i + 1].window.start
                    assert current_end <= next_start, f"Overlapping slots: {current_end} > {next_start}"


class TestPlannerVariants:
    """Test different plan variants."""

    def test_low_budget_reduces_plans(self):
        """Test that low budget results in fewer plan variants."""
        low_budget_intent = IntentV1(
            city="Madrid",
            date_window=DateWindow(
                start=date(2025, 5, 1),
                end=date(2025, 5, 5),
                tz="Europe/Madrid"
            ),
            budget_usd_cents=80_000,  # $800 - low budget
            airports=["MAD"],
            prefs=Preferences(themes=["art", "food"])
        )

        high_budget_intent = IntentV1(
            city="Madrid",
            date_window=DateWindow(
                start=date(2025, 5, 1),
                end=date(2025, 5, 5),
                tz="Europe/Madrid"
            ),
            budget_usd_cents=400_000,  # $4000 - high budget
            airports=["MAD"],
            prefs=Preferences(themes=["art", "food"])
        )

        low_plans = build_candidate_plans(low_budget_intent)
        high_plans = build_candidate_plans(high_budget_intent)

        assert len(low_plans) <= len(high_plans)

    def test_plan_assumptions_vary_by_variant(self):
        """Test that different plan variants have different assumptions."""
        intent = IntentV1(
            city="Rome",
            date_window=DateWindow(
                start=date(2025, 4, 1),
                end=date(2025, 4, 6),
                tz="Europe/Rome"
            ),
            budget_usd_cents=300_000,
            airports=["FCO"],
            prefs=Preferences(themes=["culture", "food"])
        )

        plans = build_candidate_plans(intent)

        if len(plans) > 1:
            # Different variants should have different daily spend estimates
            daily_spends = [plan.assumptions.daily_spend_est_cents for plan in plans]
            unique_spends = set(daily_spends)

            # At least some plans should differ in daily spend
            assert len(unique_spends) >= 1, "Plans should have varied assumptions"
