"""Shared budget helpers for planner, selector, and adapters."""

from __future__ import annotations

import math
from dataclasses import dataclass
from backend.app.models.common import Tier
from backend.app.models.intent import IntentV1

# Baseline estimates used to translate user budgets into planner knobs.
BASELINE_DAILY_COST_CENTS = 31_000  # Lodging + attractions + meals per day
BASE_FLIGHT_COST_CENTS = 75_000     # One-way flight estimate

# Reference costs for tier selection (in cents)
FLIGHT_TIER_BASE = {
    "budget": 55_000,
    "mid": 85_000,
    "premium": 125_000,
}

LODGING_TIER_BASE = {
    Tier.budget: 8_000,
    Tier.mid: 16_000,
    Tier.luxury: 36_000,
}

_MIN_RATIO = 0.15
_MAX_RATIO = 5.0


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp value between low/high."""
    return max(low, min(high, value))


def _rank_by_target(target: float, mapping: dict) -> list:
    """Return mapping keys sorted by closeness to target value."""
    return [
        key
        for key, _ in sorted(mapping.items(), key=lambda item: abs(item[1] - target))
    ]


@dataclass(frozen=True)
class BudgetProfile:
    """Precomputed budget characteristics for a given intent."""

    trip_days: int
    total_budget_cents: int
    budget_per_day_cents: float
    baseline_per_day_cents: int
    baseline_trip_cost_cents: int

    @property
    def per_day_ratio(self) -> float:
        """Budget-per-day vs baseline ratio."""
        if self.baseline_per_day_cents == 0:
            return 1.0
        return self.budget_per_day_cents / self.baseline_per_day_cents

    @property
    def trip_ratio(self) -> float:
        """Total budget vs baseline trip ratio."""
        if self.baseline_trip_cost_cents == 0:
            return 1.0
        return self.total_budget_cents / self.baseline_trip_cost_cents

    @property
    def normalized_pressure(self) -> float:
        """Pressure signal (-1 tight budget, +1 generous) with smooth response."""
        ratio = _clamp(self.trip_ratio, _MIN_RATIO, _MAX_RATIO)
        return math.tanh(math.log(ratio))


def build_budget_profile(
    intent: IntentV1,
    baseline_per_day_cents: int = BASELINE_DAILY_COST_CENTS,
    *,
    flight_cost_cents: int = BASE_FLIGHT_COST_CENTS,
) -> BudgetProfile:
    """Create a reusable profile summarizing the user's budget."""
    trip_days = max((intent.date_window.end - intent.date_window.start).days, 1)
    budget_per_day = intent.budget_usd_cents / trip_days
    baseline_trip = (2 * flight_cost_cents) + baseline_per_day_cents * trip_days

    return BudgetProfile(
        trip_days=trip_days,
        total_budget_cents=intent.budget_usd_cents,
        budget_per_day_cents=budget_per_day,
        baseline_per_day_cents=baseline_per_day_cents,
        baseline_trip_cost_cents=baseline_trip,
    )


def scale_cost_multiplier(
    base_multiplier: float,
    profile: BudgetProfile,
    *,
    min_multiplier: float = 0.45,
    max_multiplier: float = 1.55,
) -> float:
    """
    Scale a variant's base multiplier using the profile's pressure signal.

    Ensures smooth adjustments when budgets change without jumping between bands.
    """
    adjustment = 1.0 + profile.normalized_pressure * 0.65  # Allow ~65% swing
    return _clamp(base_multiplier * adjustment, min_multiplier, max_multiplier)


def compute_cost_weight(
    profile: BudgetProfile,
    *,
    tight_weight: float = -1.8,
    neutral_weight: float = -0.9,
    luxury_weight: float = 0.6,
) -> float:
    """Map budget pressure to selector cost weight smoothly."""
    normalized = profile.normalized_pressure

    if normalized >= 0:
        return neutral_weight + normalized * (luxury_weight - neutral_weight)

    return neutral_weight + normalized * (neutral_weight - tight_weight)


def target_flight_cost(profile: BudgetProfile) -> int:
    """Target per-leg flight spend based on total budget."""
    flights_total = profile.total_budget_cents * 0.34  # ~34% of trip budget
    per_leg = flights_total / 2
    return int(_clamp(per_leg, 40_000, 160_000))


def target_lodging_cost(profile: BudgetProfile) -> int:
    """Target per-night lodging spend based on trip budget."""
    lodging_total = profile.total_budget_cents * 0.38
    per_night = lodging_total / profile.trip_days
    return int(_clamp(per_night, 6_000, 45_000))


def target_activity_cost(profile: BudgetProfile) -> int:
    """Target spend for daytime activities (per slot)."""
    return int(_clamp(profile.budget_per_day_cents * 0.18, 0, 12_000))


def target_meal_cost(profile: BudgetProfile) -> int:
    """Target spend for evening meal slots."""
    return int(_clamp(profile.budget_per_day_cents * 0.12, 1_000, 9_000))


def preferred_flight_tiers(profile: BudgetProfile, max_tiers: int = 3) -> list[str]:
    """
    [DEPRECATED] Return flight tier order closest to the target budget.

    This function is deprecated in favor of continuous budget targeting using
    target_flight_cost() + compute_price_range(). Kept for backward compatibility only.

    Use instead:
        target = target_flight_cost(profile)
        price_range = compute_price_range(target)
    """
    tier_order = _rank_by_target(target_flight_cost(profile), FLIGHT_TIER_BASE)
    # Always include budget tier for fallback
    ordered = []
    for tier in tier_order:
        if tier not in ordered:
            ordered.append(tier)
        if len(ordered) >= max_tiers:
            break
    if "budget" not in ordered:
        ordered.append("budget")
    return ordered[:max_tiers]


def preferred_lodging_tiers(profile: BudgetProfile, max_tiers: int = 3) -> list[Tier]:
    """
    [DEPRECATED] Return lodging tiers sorted by closeness to the target per-night spend.

    This function is deprecated in favor of continuous budget targeting using
    target_lodging_cost() + compute_price_range(). Kept for backward compatibility only.

    Use instead:
        target = target_lodging_cost(profile)
        price_range = compute_price_range(target)
    """
    tier_order = _rank_by_target(target_lodging_cost(profile), LODGING_TIER_BASE)
    ordered: list[Tier] = []
    for tier in tier_order:
        if tier not in ordered:
            ordered.append(tier)
        if len(ordered) >= max_tiers:
            break
    if Tier.budget not in ordered:
        ordered.append(Tier.budget)
    return ordered[:max_tiers]


def cap_daily_spend(
    base_daily_spend_cents: int,
    profile: BudgetProfile,
    *,
    min_daily_spend_cents: int = 2_000,
    max_daily_fraction: float = 0.45,
) -> int:
    """Clamp daily discretionary spend so total trip cost stays under budget."""
    allowed = int(profile.budget_per_day_cents * max_daily_fraction)
    return max(min_daily_spend_cents, min(base_daily_spend_cents, allowed))


def compute_price_range(
    target_cents: int,
    tolerance: float = 0.3,
    *,
    min_price: int | None = None,
    max_price: int | None = None,
) -> tuple[int, int]:
    """
    Compute a continuous price range around a target cost.

    Args:
        target_cents: Target price in cents
        tolerance: Fractional tolerance (0.3 = ±30% of target)
        min_price: Optional absolute minimum price
        max_price: Optional absolute maximum price

    Returns:
        Tuple of (min_cents, max_cents) for filtering

    Example:
        target=$100, tolerance=0.3 → ($70, $130)
    """
    lower = int(target_cents * (1 - tolerance))
    upper = int(target_cents * (1 + tolerance))

    if min_price is not None:
        lower = max(lower, min_price)
    if max_price is not None:
        upper = min(upper, max_price)

    return (lower, upper)


def infer_display_tier_from_flight_price(price_cents: int) -> str:
    """
    Infer display tier label from continuous flight price for UI purposes.

    Maps price to nearest tier label without affecting selection logic.
    Used only for display/logging, not for filtering.
    """
    distances = {
        tier: abs(price_cents - base_price)
        for tier, base_price in FLIGHT_TIER_BASE.items()
    }
    return min(distances, key=distances.get)


def infer_display_tier_from_lodging_price(price_cents: int) -> Tier:
    """
    Infer display tier label from continuous lodging price for UI purposes.

    Maps price to nearest tier enum without affecting selection logic.
    Used only for display/logging, not for filtering.
    """
    distances = {
        tier: abs(price_cents - base_price)
        for tier, base_price in LODGING_TIER_BASE.items()
    }
    return min(distances, key=distances.get)
