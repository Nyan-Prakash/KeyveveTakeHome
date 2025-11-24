"""Unit tests for the PR6 selector module."""

from datetime import date, time, timedelta
from unittest.mock import patch

from backend.app.models.common import ChoiceKind, Provenance, TimeWindow
from backend.app.models.intent import DateWindow, IntentV1, Preferences
from backend.app.models.plan import (
    Assumptions,
    Choice,
    ChoiceFeatures,
    DayPlan,
    PlanV1,
    Slot,
)
from backend.app.planning.selector import (
    FROZEN_STATS,
    _aggregate_branch_features,
    _compute_weighted_score,
    _normalize_features,
    score_branches,
)
from backend.app.planning.types import BranchFeatures


def create_minimal_plan(features: ChoiceFeatures, plan_id: str = "test") -> PlanV1:
    """Helper to create a minimal valid plan with 4 days."""
    choice = Choice(
        kind=ChoiceKind.attraction,
        option_ref=plan_id,
        features=features,
        provenance=Provenance(source="test", fetched_at=date.today())
    )

    slot = Slot(
        window=TimeWindow(start=time(10, 0), end=time(12, 0)),
        choices=[choice]
    )

    # Create 4 days (minimum required by PlanV1)
    start_date = date.today()
    days = [
        DayPlan(date=start_date + timedelta(days=i), slots=[slot])
        for i in range(4)
    ]

    return PlanV1(
        days=days,
        assumptions=Assumptions(fx_rate_usd_eur=0.92, daily_spend_est_cents=8000),
        rng_seed=42
    )


def create_test_intent() -> IntentV1:
    """Helper to create a test intent for selector tests."""
    start_date = date.today()
    return IntentV1(
        city="Paris",
        date_window=DateWindow(
            start=start_date,
            end=start_date + timedelta(days=4),
            tz="Europe/Paris"
        ),
        budget_usd_cents=250_000,  # $2500
        airports=["CDG"],
        prefs=Preferences(
            kid_friendly=False,
            themes=["art"],
            avoid_overnight=False,
            locked_slots=[]
        )
    )


class TestSelectorFieldSafety:
    """Test that selector never references nonexistent fields."""

    def test_only_uses_choice_features(self):
        """Test that selector only accesses ChoiceFeatures fields."""
        # Create minimal branches with only ChoiceFeatures
        features = [
            ChoiceFeatures(
                cost_usd_cents=3000,
                travel_seconds=1800,
                indoor=True,
                themes=["art", "culture"]
            ),
            ChoiceFeatures(
                cost_usd_cents=4500,
                travel_seconds=2400,
                indoor=False,
                themes=["outdoor", "nature"]
            )
        ]

        plan = create_minimal_plan(features[0])
        branch = BranchFeatures(plan=plan, features=features)
        intent = create_test_intent()

        # This should work without accessing any raw model fields
        scored_plans = score_branches([branch], intent)

        assert len(scored_plans) == 1
        assert scored_plans[0].score is not None
        assert "cost" in scored_plans[0].feature_vector

    def test_aggregate_only_uses_choicefeatures_fields(self):
        """Test that _aggregate_branch_features only uses ChoiceFeatures fields."""
        features = [
            ChoiceFeatures(
                cost_usd_cents=2000,
                travel_seconds=1200,
                indoor=True,
                themes=["art"]
            ),
            ChoiceFeatures(
                cost_usd_cents=3000,
                travel_seconds=None,  # Test None handling
                indoor=None,
                themes=None
            )
        ]

        # This should work with just ChoiceFeatures
        result = _aggregate_branch_features(features)

        assert "cost" in result
        assert "travel_time" in result
        assert "theme_match" in result
        assert "indoor_pref" in result

        # Verify expected aggregations
        assert result["cost"] == 5000.0  # sum of costs
        assert result["travel_time"] == 1200.0  # avg of non-None values
        assert 0.0 <= result["theme_match"] <= 1.0  # normalized theme count
        assert -1.0 <= result["indoor_pref"] <= 1.0  # indoor preference score

    def test_empty_features_handling(self):
        """Test handling of empty feature sequences."""
        result = _aggregate_branch_features([])

        # Should return zero values for empty input
        assert result["cost"] == 0.0
        assert result["travel_time"] == 0.0
        assert result["theme_match"] == 0.0
        assert result["indoor_pref"] == 0.0


class TestSelectorUseFrozenStats:
    """Test that selector uses frozen statistics."""

    def test_uses_frozen_stats_by_default(self):
        """Test that score_branches uses FROZEN_STATS by default."""
        features = [
            ChoiceFeatures(
                cost_usd_cents=3500,  # Should be near mean
                travel_seconds=1800,
                indoor=True,
                themes=["art"]
            )
        ]

        plan = create_minimal_plan(features[0])
        branch = BranchFeatures(plan=plan, features=features)
        intent = create_test_intent()

        # Should use frozen stats
        scored = score_branches([branch], intent)

        assert len(scored) == 1
        # Score should be computed using frozen normalization
        assert isinstance(scored[0].score, float)

    def test_normalization_uses_frozen_values(self):
        """Test that normalization uses the exact frozen statistics."""
        feature_vector = {
            "cost": 3500.0,      # Should normalize to 0.0 (at mean)
            "travel_time": 1800.0, # Should normalize to 0.0 (at mean)
        }

        normalized = _normalize_features(feature_vector, FROZEN_STATS)

        # Cost should be normalized using frozen mean/std
        expected_cost_z = (3500.0 - FROZEN_STATS["cost"].mean) / FROZEN_STATS["cost"].std
        assert abs(normalized["norm_cost"] - expected_cost_z) < 0.001

        # Travel time should be normalized using frozen mean/std
        expected_travel_z = (1800.0 - FROZEN_STATS["travel_time"].mean) / FROZEN_STATS["travel_time"].std
        assert abs(normalized["norm_travel_time"] - expected_travel_z) < 0.001

    def test_no_dynamic_stat_computation(self):
        """Test that stats are not computed from input data."""
        # Create features with very different values than frozen stats
        high_cost_features = [
            ChoiceFeatures(cost_usd_cents=50000, travel_seconds=10000)
            for _ in range(10)
        ]

        low_cost_features = [
            ChoiceFeatures(cost_usd_cents=1000, travel_seconds=300)
            for _ in range(10)
        ]

        # If stats were computed dynamically, these would normalize very differently
        # But with frozen stats, they should use the same normalization parameters

        high_agg = _aggregate_branch_features(high_cost_features)
        low_agg = _aggregate_branch_features(low_cost_features)

        high_norm = _normalize_features(high_agg, FROZEN_STATS)
        low_norm = _normalize_features(low_agg, FROZEN_STATS)

        # Both should use same frozen mean/std for normalization
        # High cost should have positive z-score, low cost negative
        assert high_norm["norm_cost"] > low_norm["norm_cost"]

        # But the normalization parameters themselves come from FROZEN_STATS
        cost_stat = FROZEN_STATS["cost"]
        expected_high_z = (high_agg["cost"] - cost_stat.mean) / cost_stat.std
        expected_low_z = (low_agg["cost"] - cost_stat.mean) / cost_stat.std

        assert abs(high_norm["norm_cost"] - expected_high_z) < 0.001
        assert abs(low_norm["norm_cost"] - expected_low_z) < 0.001


class TestSelectorScoreLogging:
    """Test score logging functionality."""

    @patch('backend.app.planning.selector.logger')
    def test_logs_chosen_plan(self, mock_logger):
        """Test that chosen plan score vector is logged."""
        features = [
            ChoiceFeatures(
                cost_usd_cents=2000,
                travel_seconds=1500,
                indoor=True,
                themes=["art"]
            )
        ]

        plan = create_minimal_plan(features[0])
        branch = BranchFeatures(plan=plan, features=features)
        intent = create_test_intent()

        score_branches([branch], intent)

        # Should log chosen plan
        mock_logger.info.assert_called()

        # Check that one of the log calls was for chosen plan
        log_calls = mock_logger.info.call_args_list
        chosen_logged = any(
            "Chosen plan score vector" in str(call)
            for call in log_calls
        )
        assert chosen_logged

    @patch('backend.app.planning.selector.logger')
    def test_logs_top_discarded_plans(self, mock_logger):
        """Test that top 2 discarded plans are logged when available."""
        # Create 3 different branches
        branches = []
        for i in range(3):
            features = [
                ChoiceFeatures(
                    cost_usd_cents=2000 + i * 1000,  # Different costs for different scores
                    travel_seconds=1500,
                    indoor=True,
                    themes=["art"]
                )
            ]

            plan = create_minimal_plan(features[0], f"test_{i}")
            branches.append(BranchFeatures(plan=plan, features=features))

        intent = create_test_intent()
        score_branches(branches, intent)

        # Should log chosen + 2 discarded plans
        mock_logger.info.assert_called()

        log_calls = [str(call) for call in mock_logger.info.call_args_list]

        # Check for chosen plan log
        chosen_logged = any("Chosen plan score vector" in call for call in log_calls)
        assert chosen_logged

        # Check for discarded plans logs
        discarded_logged = sum("Discarded plan" in call for call in log_calls)
        assert discarded_logged >= 2  # Should log top 2 discarded

    @patch('backend.app.planning.selector.logger')
    def test_handles_empty_plans(self, mock_logger):
        """Test logging handles empty plan list gracefully."""
        intent = create_test_intent()
        score_branches([], intent)

        # Should log warning for empty plans
        warning_calls = [call for call in mock_logger.warning.call_args_list
                        if "No plans to log score vectors" in str(call)]
        assert len(warning_calls) > 0


class TestSelectorScoring:
    """Test scoring computation."""

    def test_weighted_score_computation(self):
        """Test that weighted score is computed correctly with dynamic cost weight."""
        normalized_vector = {
            "norm_cost": -0.5,      # Good (low cost)
            "norm_travel_time": 0.0,  # Average
            "norm_theme_match": 1.0,  # Good (high theme match)
            "norm_indoor_pref": 0.2,  # Slight indoor preference
        }

        # Use a known cost weight
        cost_weight = -1.0
        score = _compute_weighted_score(normalized_vector, cost_weight)

        # Score should be: cost_weight*(-0.5) + -0.5*(0.0) + 1.5*(1.0) + 0.3*(0.2)
        expected = cost_weight * (-0.5) + (-0.5) * 0.0 + 1.5 * 1.0 + 0.3 * 0.2
        assert abs(score - expected) < 0.01

    def test_score_ordering(self):
        """Test that better plans get higher scores."""
        # Create low-cost, theme-matching plan
        good_features = [
            ChoiceFeatures(
                cost_usd_cents=1000,  # Low cost (good)
                travel_seconds=1200,   # Short travel (good)
                indoor=True,
                themes=["art", "culture", "museums"]  # Many themes (good)
            )
        ]

        # Create high-cost, no-theme plan
        bad_features = [
            ChoiceFeatures(
                cost_usd_cents=8000,  # High cost (bad)
                travel_seconds=3600,  # Long travel (bad)
                indoor=None,
                themes=None  # No themes (bad)
            )
        ]

        # Create plans
        plans = []
        for i, features in enumerate([good_features, bad_features]):
            plan = create_minimal_plan(features[0], f"test_{i}")
            plans.append(BranchFeatures(plan=plan, features=features))

        intent = create_test_intent()
        scored = score_branches(plans, intent)

        # Good plan should score higher than bad plan
        assert scored[0].score > scored[1].score
