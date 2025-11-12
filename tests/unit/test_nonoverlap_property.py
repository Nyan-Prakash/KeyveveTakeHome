"""Property-based tests for non-overlapping slot generation."""

from datetime import date, datetime, time

from hypothesis import given
from hypothesis import strategies as st

from backend.app.config import get_settings
from backend.app.models import (
    Choice,
    ChoiceFeatures,
    ChoiceKind,
    DayPlan,
    Provenance,
    Slot,
    TimeWindow,
)


def generate_non_overlapping_slots(
    num_slots: int, seed: int | None = None
) -> list[Slot]:
    """Generate non-overlapping slots with fixed seed for reproducibility."""
    if seed is not None:
        import random
        random.seed(seed)

    slots = []
    current_time = time(9, 0)  # Start at 9 AM

    for i in range(num_slots):
        # Duration between 1-3 hours
        duration_minutes = 60 + (i * 30) % 120  # Vary duration

        # Calculate end time
        end_minutes = current_time.hour * 60 + current_time.minute + duration_minutes
        if end_minutes >= 24 * 60:  # Don't go past midnight
            break

        end_hour = (end_minutes // 60) % 24
        end_minute = end_minutes % 60
        end_time = time(end_hour, end_minute)

        # Create choice
        choice = Choice(
            kind=ChoiceKind.attraction,
            option_ref=f"option_{i}",
            features=ChoiceFeatures(cost_usd_cents=5000 + i * 1000),
            provenance=Provenance(
                source="tool",
                fetched_at=datetime(2025, 6, 1, 12, 0, 0),
            ),
        )

        # Create slot
        slot = Slot(
            window=TimeWindow(start=current_time, end=end_time),
            choices=[choice],
        )
        slots.append(slot)

        # Next slot starts 30 minutes after this one ends
        next_minutes = end_minutes + 30
        if next_minutes >= 24 * 60:
            break
        next_hour = (next_minutes // 60) % 24
        next_minute = next_minutes % 60
        current_time = time(next_hour, next_minute)

    return slots


class TestNonOverlapProperty:
    """Property-based tests for non-overlapping slot validation."""

    def test_generated_slots_are_non_overlapping(self):
        """Test that generated slots are indeed non-overlapping."""
        settings = get_settings()
        slots = generate_non_overlapping_slots(5, seed=settings.eval_rng_seed)

        # Verify no overlaps
        sorted_slots = sorted(slots, key=lambda s: s.window.start)
        for i in range(len(sorted_slots) - 1):
            current = sorted_slots[i]
            next_slot = sorted_slots[i + 1]

            # Current end time should be <= next start time
            assert current.window.end <= next_slot.window.start, (
                f"Overlap detected: slot {i} ends at {current.window.end}, "
                f"slot {i+1} starts at {next_slot.window.start}"
            )

    def test_non_overlapping_slots_create_valid_day_plan(self):
        """Test that non-overlapping slots can create a valid DayPlan."""
        settings = get_settings()
        slots = generate_non_overlapping_slots(4, seed=settings.eval_rng_seed)

        # Should be able to create a valid DayPlan
        day_plan = DayPlan(
            date=date(2025, 6, 1),
            slots=slots,
        )

        assert len(day_plan.slots) == len(slots)
        assert day_plan.date == date(2025, 6, 1)

    def test_serialization_preserves_non_overlap(self):
        """Test that serialization and deserialization preserves non-overlap property."""
        settings = get_settings()
        slots = generate_non_overlapping_slots(3, seed=settings.eval_rng_seed)

        day_plan = DayPlan(
            date=date(2025, 6, 1),
            slots=slots,
        )

        # Serialize to dict
        day_plan_dict = day_plan.model_dump()

        # Deserialize
        restored_plan = DayPlan.model_validate(day_plan_dict)

        # Verify still non-overlapping
        sorted_slots = sorted(restored_plan.slots, key=lambda s: s.window.start)
        for i in range(len(sorted_slots) - 1):
            current = sorted_slots[i]
            next_slot = sorted_slots[i + 1]
            assert current.window.end <= next_slot.window.start

    def test_fixed_seed_produces_deterministic_slots(self):
        """Test that fixed seed produces deterministic slot generation."""
        seed = 42

        slots1 = generate_non_overlapping_slots(4, seed=seed)
        slots2 = generate_non_overlapping_slots(4, seed=seed)

        # Should be identical
        assert len(slots1) == len(slots2)
        for s1, s2 in zip(slots1, slots2, strict=True):
            assert s1.window.start == s2.window.start
            assert s1.window.end == s2.window.end
            assert s1.choices[0].option_ref == s2.choices[0].option_ref

    @given(st.integers(min_value=1, max_value=8))
    def test_property_various_slot_counts(self, num_slots: int):
        """Property test: various numbers of slots should maintain non-overlap."""
        slots = generate_non_overlapping_slots(num_slots, seed=42)

        if not slots:  # Empty list is trivially non-overlapping
            return

        # Verify non-overlapping property
        sorted_slots = sorted(slots, key=lambda s: s.window.start)
        for i in range(len(sorted_slots) - 1):
            current = sorted_slots[i]
            next_slot = sorted_slots[i + 1]
            assert current.window.end <= next_slot.window.start

    def test_edge_case_single_slot(self):
        """Test edge case with single slot."""
        slots = generate_non_overlapping_slots(1, seed=42)

        assert len(slots) == 1

        # Single slot is trivially non-overlapping
        day_plan = DayPlan(
            date=date(2025, 6, 1),
            slots=slots,
        )
        assert len(day_plan.slots) == 1

    def test_edge_case_empty_slots(self):
        """Test edge case with empty slot list."""
        slots = generate_non_overlapping_slots(0, seed=42)

        assert len(slots) == 0

        # Empty slots list should be valid
        day_plan = DayPlan(
            date=date(2025, 6, 1),
            slots=slots,
        )
        assert len(day_plan.slots) == 0

    def test_time_boundary_handling(self):
        """Test that slot generation handles time boundaries correctly."""
        # Generate many slots to test boundary conditions
        slots = generate_non_overlapping_slots(20, seed=42)

        # All slots should be within a single day
        for slot in slots:
            assert slot.window.start < slot.window.end
            assert slot.window.start >= time(0, 0)
            assert slot.window.end <= time(23, 59)

    def test_consistent_gap_between_slots(self):
        """Test that there's consistent gap between generated slots."""
        slots = generate_non_overlapping_slots(5, seed=42)

        if len(slots) < 2:
            return

        sorted_slots = sorted(slots, key=lambda s: s.window.start)

        # Calculate gaps between slots
        gaps = []
        for i in range(len(sorted_slots) - 1):
            current = sorted_slots[i]
            next_slot = sorted_slots[i + 1]

            current_end_minutes = current.window.end.hour * 60 + current.window.end.minute
            next_start_minutes = next_slot.window.start.hour * 60 + next_slot.window.start.minute

            gap_minutes = next_start_minutes - current_end_minutes
            gaps.append(gap_minutes)

        # All gaps should be non-negative (non-overlapping)
        for gap in gaps:
            assert gap >= 0, f"Negative gap detected: {gap} minutes"
