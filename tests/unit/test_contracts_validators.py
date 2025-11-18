"""Test contract validators and model constraints."""

from datetime import date, datetime, time

import pytest
from pydantic import ValidationError

from backend.app.models import (
    Assumptions,
    Choice,
    ChoiceFeatures,
    ChoiceKind,
    DateWin    def test_minimal_day_count_passes(self):
        """Plan with 1 day should pass validation."""
        assumptions = Assumptions(
            fx_rate_usd_eur=1.1,
            daily_spend_est_cents=5000,
        )

        # Test with 1 day
        days = [
            self._create_minimal_day_plan(date(2025, 6, 1))
        ]

        try:
            plan = PlanV1(
                days=days,
                assumptions=assumptions,
                rng_seed=42,
            )
            assert len(plan.days) == 1
        except ValidationError:
            pytest.fail("Single day plan should not raise ValidationError")    IntentV1,
    PlanV1,
    Preferences,
    Provenance,
    Slot,
    TimeWindow,
)


class TestDateWindowValidation:
    """Test DateWindow validation logic."""

    def test_valid_date_window(self):
        """Valid date window should pass validation."""
        window = DateWindow(
            start=date(2025, 6, 1),
            end=date(2025, 6, 5),
            tz="Europe/Paris",
        )
        assert window.start == date(2025, 6, 1)
        assert window.end == date(2025, 6, 5)

    def test_reversed_date_window_fails(self):
        """Reversed date window should raise validation error."""
        with pytest.raises(
            ValidationError, match="End date must be on or after start date"
        ):
            DateWindow(
                start=date(2025, 6, 5),
                end=date(2025, 6, 1),  # Before start
                tz="Europe/Paris",
            )


class TestIntentV1Validation:
    """Test IntentV1 validation logic."""

    def test_valid_intent(self):
        """Valid intent should pass validation."""
        intent = IntentV1(
            city="Paris",
            date_window=DateWindow(
                start=date(2025, 6, 1),
                end=date(2025, 6, 5),
                tz="Europe/Paris",
            ),
            budget_usd_cents=250000,
            airports=["CDG", "ORY"],
            prefs=Preferences(),
        )
        assert intent.city == "Paris"
        assert len(intent.airports) == 2

    def test_empty_airports_fails(self):
        """Empty airports list should raise validation error."""
        with pytest.raises(
            ValidationError, match="At least one airport must be provided"
        ):
            IntentV1(
                city="Paris",
                date_window=DateWindow(
                    start=date(2025, 6, 1),
                    end=date(2025, 6, 5),
                    tz="Europe/Paris",
                ),
                budget_usd_cents=250000,
                airports=[],  # Empty list
                prefs=Preferences(),
            )

    def test_negative_budget_fails(self):
        """Negative budget should raise validation error."""
        with pytest.raises(ValidationError, match="Budget must be positive"):
            IntentV1(
                city="Paris",
                date_window=DateWindow(
                    start=date(2025, 6, 1),
                    end=date(2025, 6, 5),
                    tz="Europe/Paris",
                ),
                budget_usd_cents=-1000,  # Negative
                airports=["CDG"],
                prefs=Preferences(),
            )

    def test_zero_budget_fails(self):
        """Zero budget should raise validation error."""
        with pytest.raises(ValidationError, match="Budget must be positive"):
            IntentV1(
                city="Paris",
                date_window=DateWindow(
                    start=date(2025, 6, 1),
                    end=date(2025, 6, 5),
                    tz="Europe/Paris",
                ),
                budget_usd_cents=0,  # Zero
                airports=["CDG"],
                prefs=Preferences(),
            )


class TestSlotValidation:
    """Test Slot validation logic."""

    def test_valid_slot(self):
        """Valid slot should pass validation."""
        choice = Choice(
            kind=ChoiceKind.attraction,
            option_ref="attraction_001",
            features=ChoiceFeatures(cost_usd_cents=5000),
            provenance=Provenance(
                source="tool",
                fetched_at=datetime(2025, 6, 1, 12, 0, 0),
            ),
        )
        slot = Slot(
            window=TimeWindow(start=time(10, 0), end=time(12, 0)),
            choices=[choice],
        )
        assert len(slot.choices) == 1

    def test_empty_choices_fails(self):
        """Empty choices list should raise validation error."""
        with pytest.raises(
            ValidationError, match="At least one choice must be provided"
        ):
            Slot(
                window=TimeWindow(start=time(10, 0), end=time(12, 0)),
                choices=[],  # Empty
            )


class TestDayPlanValidation:
    """Test DayPlan validation for overlapping slots."""

    def _create_choice(self, ref: str = "test_choice") -> Choice:
        """Helper to create a valid choice."""
        return Choice(
            kind=ChoiceKind.attraction,
            option_ref=ref,
            features=ChoiceFeatures(cost_usd_cents=5000),
            provenance=Provenance(
                source="tool",
                fetched_at=datetime(2025, 6, 1, 12, 0, 0),
            ),
        )

    def test_non_overlapping_slots_pass(self):
        """Non-overlapping slots should pass validation."""
        slot1 = Slot(
            window=TimeWindow(start=time(10, 0), end=time(12, 0)),
            choices=[self._create_choice("choice1")],
        )
        slot2 = Slot(
            window=TimeWindow(start=time(14, 0), end=time(16, 0)),
            choices=[self._create_choice("choice2")],
        )

        day_plan = DayPlan(
            date=date(2025, 6, 1),
            slots=[slot1, slot2],
        )
        assert len(day_plan.slots) == 2

    def test_overlapping_slots_fail(self):
        """Overlapping slots should raise validation error."""
        slot1 = Slot(
            window=TimeWindow(start=time(10, 0), end=time(13, 0)),  # Ends at 13:00
            choices=[self._create_choice("choice1")],
        )
        slot2 = Slot(
            window=TimeWindow(
                start=time(12, 0), end=time(14, 0)
            ),  # Starts at 12:00 - overlap!
            choices=[self._create_choice("choice2")],
        )

        with pytest.raises(ValidationError, match="Overlapping slots"):
            DayPlan(
                date=date(2025, 6, 1),
                slots=[slot1, slot2],
            )

    def test_adjacent_slots_pass(self):
        """Adjacent slots (touching but not overlapping) should pass."""
        slot1 = Slot(
            window=TimeWindow(start=time(10, 0), end=time(12, 0)),
            choices=[self._create_choice("choice1")],
        )
        slot2 = Slot(
            window=TimeWindow(
                start=time(12, 0), end=time(14, 0)
            ),  # Starts when first ends
            choices=[self._create_choice("choice2")],
        )

        day_plan = DayPlan(
            date=date(2025, 6, 1),
            slots=[slot1, slot2],
        )
        assert len(day_plan.slots) == 2


class TestPlanV1Validation:
    """Test PlanV1 validation logic."""

    def _create_minimal_day_plan(self, day_date: date) -> DayPlan:
        """Helper to create a minimal valid day plan."""
        choice = Choice(
            kind=ChoiceKind.attraction,
            option_ref="test_choice",
            features=ChoiceFeatures(cost_usd_cents=5000),
            provenance=Provenance(
                source="tool",
                fetched_at=datetime(2025, 6, 1, 12, 0, 0),
            ),
        )
        slot = Slot(
            window=TimeWindow(start=time(10, 0), end=time(12, 0)),
            choices=[choice],
        )
        return DayPlan(date=day_date, slots=[slot])

    def test_valid_day_count_passes(self):
        """Plan with any number of days should pass validation."""
        assumptions = Assumptions(
            fx_rate_usd_eur=1.1,
            daily_spend_est_cents=5000,
        )

        # Test with 5 days
        days = [
            self._create_minimal_day_plan(date(2025, 6, day)) for day in range(1, 6)
        ]

        try:
            plan = PlanV1(
                days=days,
                assumptions=assumptions,
                rng_seed=42,
            )
            assert len(plan.days) == 5
        except ValidationError:
            pytest.fail("Valid plan should not raise ValidationError")

    def test_short_trip_passes(self):
        """Plan with few days should pass validation."""
        assumptions = Assumptions(
            fx_rate_usd_eur=1.1,
            daily_spend_est_cents=5000,
        )

        # Test with 2 days
        days = [
            self._create_minimal_day_plan(date(2025, 6, day)) for day in range(1, 3)
        ]

        try:
            plan = PlanV1(
                days=days,
                assumptions=assumptions,
                rng_seed=42,
            )
            assert len(plan.days) == 2
        except ValidationError:
            pytest.fail("Short plan should not raise ValidationError")

    def test_many_days_passes(self):
        """Plan with many days should pass validation."""
        assumptions = Assumptions(
            fx_rate_usd_eur=1.1,
            daily_spend_est_cents=5000,
        )

        # Test with 10 days
        days = [
            self._create_minimal_day_plan(date(2025, 6, day)) for day in range(1, 11)
        ]

        try:
            plan = PlanV1(
                days=days,
                assumptions=assumptions,
                rng_seed=42,
            )
            assert len(plan.days) == 10
        except ValidationError:
            pytest.fail("Extended plan should not raise ValidationError")
