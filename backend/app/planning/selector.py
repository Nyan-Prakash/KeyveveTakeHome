"""Plan scoring and selection with frozen statistics."""

import logging
from collections.abc import Mapping, Sequence

from backend.app.models.intent import IntentV1
from backend.app.models.plan import ChoiceFeatures

from .types import BranchFeatures, FeatureStats, ScoredPlan

# Setup logger
logger = logging.getLogger(__name__)

# Frozen statistics for feature normalization
# These values are derived from fixture data analysis and should not change
FROZEN_STATS: dict[str, FeatureStats] = {
    "cost": FeatureStats(mean=3500.0, std=1800.0),  # Cost in cents, ~$35 avg, $18 std
    "travel_time": FeatureStats(mean=1800.0, std=600.0),  # Travel in seconds, 30min avg, 10min std
    "theme_match": FeatureStats(mean=0.6, std=0.3),  # Theme compatibility 0-1 scale
    "indoor_pref": FeatureStats(mean=0.0, std=1.0),  # Indoor preference score (-1 to 1)
}

# Scoring weights for different features
SCORE_WEIGHTS = {
    "cost": -1.0,        # Lower cost is better
    "travel_time": -0.5, # Lower travel time is better
    "theme_match": 1.5,  # Higher theme match is better
    "indoor_pref": 0.3,  # Small preference for indoor/outdoor alignment
}


def _calculate_cost_weight(intent: IntentV1) -> float:
    """Calculate dynamic cost weight based on budget generosity."""
    baseline_per_day = 23000  # $230/day baseline
    # Get trip duration from intent's date_window
    trip_days = max((intent.date_window.end - intent.date_window.start).days, 1)
    budget_per_day = intent.budget_usd_cents / trip_days
    budget_ratio = budget_per_day / baseline_per_day

    # Adjust cost weight based on budget health
    if budget_ratio < 1.0:
        # Tight budget - strongly prefer cheaper
        cost_weight = -1.5
    elif budget_ratio < 1.5:
        # Normal budget - moderately prefer cheaper
        cost_weight = -1.0
    elif budget_ratio < 3.0:
        # Good budget - neutral on cost
        cost_weight = -0.3
    else:
        # Generous budget - actually prefer more expensive (better quality)
        cost_weight = 0.5

    # Log budget calculation for debugging
    logger.info(
        f"Budget calculation: budget=${intent.budget_usd_cents/100:.0f}, days={trip_days}, "
        f"per_day=${budget_per_day/100:.0f}, ratio={budget_ratio:.2f}, cost_weight={cost_weight}"
    )
    
    return cost_weight


def score_branches(
    branches: Sequence[BranchFeatures],
    intent: IntentV1,
    stats: Mapping[str, FeatureStats] = FROZEN_STATS,
) -> list[ScoredPlan]:
    """
    Score and rank plan branches using frozen feature statistics with budget-aware cost weighting.

    This function:
    1. Extracts aggregate features from each branch
    2. Normalizes features using z-scores with frozen stats
    3. Computes budget-aware cost weight based on intent
    4. Computes weighted scores
    5. Returns ranked list of scored plans
    6. Logs score vectors for chosen + top 2 discarded plans

    Args:
        branches: List of plan branches with extracted features
        intent: User intent with budget information for dynamic cost weighting
        stats: Feature statistics for normalization (frozen values)

    Returns:
        List of ScoredPlan objects sorted by descending score
    """
    # Calculate budget-aware cost weight
    cost_weight = _calculate_cost_weight(intent)

    scored_plans: list[ScoredPlan] = []

    for branch in branches:
        # Aggregate features across all choices in the plan
        feature_vector = _aggregate_branch_features(branch.features)

        # Normalize features using z-scores
        normalized_vector = _normalize_features(feature_vector, stats)

        # Compute weighted score with dynamic cost weight
        score = _compute_weighted_score(normalized_vector, cost_weight)

        scored_plans.append(ScoredPlan(
            plan=branch.plan,
            score=score,
            feature_vector={**feature_vector, **normalized_vector, "final_score": score, "cost_weight": cost_weight},
        ))

    # Sort by descending score (best first)
    scored_plans.sort(key=lambda x: x.score, reverse=True)

    # Log score vectors for chosen + top 2 discarded
    _log_score_vectors(scored_plans)

    return scored_plans


def _aggregate_branch_features(features: Sequence[ChoiceFeatures]) -> dict[str, float]:
    """
    Aggregate ChoiceFeatures into branch-level feature vector.

    This function only accesses ChoiceFeatures fields and computes
    aggregate statistics like total cost, average travel time, etc.

    Args:
        features: Sequence of ChoiceFeatures from all choices in the branch

    Returns:
        Dictionary with aggregated feature values
    """
    if not features:
        return {
            "cost": 0.0,
            "travel_time": 0.0,
            "theme_match": 0.0,
            "indoor_pref": 0.0,
        }

    # Aggregate cost (total)
    total_cost = sum(f.cost_usd_cents for f in features)

    # Aggregate travel time (average, excluding None values)
    travel_times = [f.travel_seconds for f in features if f.travel_seconds is not None]
    avg_travel_time = sum(travel_times) / len(travel_times) if travel_times else 0.0

    # Compute theme diversity (how many unique themes are covered)
    all_themes = set()
    for f in features:
        if f.themes:
            all_themes.update(f.themes)
    theme_diversity = len(all_themes) / 5.0  # Normalize by max expected themes

    # Compute indoor preference score (1=all indoor, -1=all outdoor, 0=mixed/unknown)
    indoor_scores = []
    for f in features:
        if f.indoor is True:
            indoor_scores.append(1.0)
        elif f.indoor is False:
            indoor_scores.append(-1.0)
        else:
            indoor_scores.append(0.0)

    avg_indoor_score = sum(indoor_scores) / len(indoor_scores) if indoor_scores else 0.0

    return {
        "cost": float(total_cost),
        "travel_time": avg_travel_time,
        "theme_match": theme_diversity,
        "indoor_pref": avg_indoor_score,
    }


def _normalize_features(
    feature_vector: dict[str, float],
    stats: Mapping[str, FeatureStats],
) -> dict[str, float]:
    """
    Normalize features using z-score normalization with frozen statistics.

    Args:
        feature_vector: Raw feature values
        stats: Frozen statistics for normalization

    Returns:
        Dictionary with z-score normalized features (prefixed with 'norm_')
    """
    normalized = {}

    for feature_name, value in feature_vector.items():
        if feature_name in stats:
            stat = stats[feature_name]
            if stat.std > 0:
                z_score = (value - stat.mean) / stat.std
            else:
                z_score = 0.0
            normalized[f"norm_{feature_name}"] = z_score
        else:
            # If no stats available, pass through unchanged
            normalized[f"norm_{feature_name}"] = value

    return normalized


def _compute_weighted_score(normalized_vector: dict[str, float], cost_weight: float) -> float:
    """
    Compute final weighted score from normalized features.

    Args:
        normalized_vector: Dictionary with normalized feature values
        cost_weight: Dynamic cost weight based on budget

    Returns:
        Final scalar score for the plan
    """
    score = 0.0

    for feature_name, weight in SCORE_WEIGHTS.items():
        norm_key = f"norm_{feature_name}"
        if norm_key in normalized_vector:
            if feature_name == "cost":
                # Use dynamic cost weight for cost feature
                score += cost_weight * normalized_vector[norm_key]
            else:
                score += weight * normalized_vector[norm_key]

    return score


def _log_score_vectors(scored_plans: list[ScoredPlan]) -> None:
    """
    Log score vectors for chosen plan and top 2 discarded plans.

    Args:
        scored_plans: List of scored plans sorted by score (descending)
    """
    if not scored_plans:
        logger.warning("No plans to log score vectors for")
        return

    # Log chosen plan (highest score)
    chosen = scored_plans[0]
    logger.info(
        "Chosen plan score vector",
        extra={
            "plan_rank": 1,
            "plan_id": f"chosen_{id(chosen.plan)}",
            "final_score": chosen.score,
            "feature_vector": chosen.feature_vector,
        }
    )

    # Log top 2 discarded plans if they exist
    for i in range(1, min(3, len(scored_plans))):
        discarded = scored_plans[i]
        logger.info(
            f"Discarded plan {i} score vector",
            extra={
                "plan_rank": i + 1,
                "plan_id": f"discarded_{i}_{id(discarded.plan)}",
                "final_score": discarded.score,
                "feature_vector": discarded.feature_vector,
            }
        )

    # Log summary statistics
    logger.info(
        "Plan scoring summary",
        extra={
            "total_plans": len(scored_plans),
            "score_range": {
                "min": min(p.score for p in scored_plans),
                "max": max(p.score for p in scored_plans),
                "spread": max(p.score for p in scored_plans) - min(p.score for p in scored_plans),
            }
        }
    )
