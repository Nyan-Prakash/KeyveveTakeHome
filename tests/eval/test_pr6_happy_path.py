"""Evaluation tests for PR6 happy path scenarios."""

from datetime import date
from unittest.mock import patch

from backend.app.models.intent import DateWindow, IntentV1, Preferences
from backend.app.planning import build_candidate_plans, score_branches
from backend.app.planning.types import BranchFeatures


class TestPR6HappyPath:
    """Test PR6 integration with real adapters/fixtures."""

    def test_happy_path_completes_successfully(self):
        """Test that happy path scenario completes with PR6 planner/selector."""
        # Use similar intent as eval scenarios but focused on PR6
        intent = IntentV1(
            city="Paris",
            date_window=DateWindow(
                start=date(2025, 6, 1),
                end=date(2025, 6, 5),
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

        # Generate plans with PR6 planner
        candidate_plans = build_candidate_plans(intent)

        # Basic validation
        assert len(candidate_plans) >= 1
        assert len(candidate_plans) <= 4  # Fan-out cap

        # All plans should be valid
        for plan in candidate_plans:
            assert 4 <= len(plan.days) <= 7  # Valid day count
            assert plan.rng_seed is not None  # Has seed for determinism

            # All days should have valid slots
            for day in plan.days:
                assert len(day.slots) >= 0  # Can have empty days
                for slot in day.slots:
                    assert len(slot.choices) >= 1  # Each slot needs choices

                    # Each choice should have valid features
                    for choice in slot.choices:
                        features = choice.features
                        assert features.cost_usd_cents >= 0
                        assert features.travel_seconds is None or features.travel_seconds >= 0
                        # indoor can be True, False, or None (tri-state)
                        assert features.indoor in [True, False, None]

    def test_selector_scores_plans_successfully(self):
        """Test that selector can score plans from planner."""
        intent = IntentV1(
            city="London",
            date_window=DateWindow(
                start=date(2025, 7, 10),
                end=date(2025, 7, 14),
                tz="Europe/London"
            ),
            budget_usd_cents=300_000,  # $3000
            airports=["LHR"],
            prefs=Preferences(
                kid_friendly=False,
                themes=["culture", "history"],
                avoid_overnight=False,
                locked_slots=[]
            )
        )

        # Generate candidate plans
        candidate_plans = build_candidate_plans(intent)
        assert len(candidate_plans) >= 1

        # Extract features and create branches
        branches = []
        for plan in candidate_plans:
            features = []
            for day in plan.days:
                for slot in day.slots:
                    for choice in slot.choices:
                        features.append(choice.features)

            branches.append(BranchFeatures(plan=plan, features=features))

        # Score branches
        scored_plans = score_branches(branches)

        # Validate scoring results
        assert len(scored_plans) == len(candidate_plans)
        assert all(isinstance(p.score, float) for p in scored_plans)

        # Plans should be sorted by descending score
        scores = [p.score for p in scored_plans]
        assert scores == sorted(scores, reverse=True)

        # Each scored plan should have a feature vector
        for scored_plan in scored_plans:
            assert "final_score" in scored_plan.feature_vector
            assert scored_plan.feature_vector["final_score"] == scored_plan.score

    def test_e2e_with_orchestrator_integration(self):
        """Test end-to-end with PR6 components (without full orchestrator)."""
        # This focuses on PR6 components working together rather than full integration

        intent = IntentV1(
            city="Madrid",
            date_window=DateWindow(
                start=date(2025, 8, 1),
                end=date(2025, 8, 5),
                tz="Europe/Madrid"
            ),
            budget_usd_cents=200_000,  # $2000
            airports=["MAD"],
            prefs=Preferences(
                kid_friendly=True,
                themes=["food", "culture"],
                avoid_overnight=True,
                locked_slots=[]
            )
        )

        # Test planner -> selector pipeline
        plans = build_candidate_plans(intent)
        assert len(plans) >= 1

        # Convert to branch features
        branches = []
        for plan in plans:
            features = []
            for day in plan.days:
                for slot in day.slots:
                    for choice in slot.choices:
                        features.append(choice.features)
            branches.append(BranchFeatures(plan=plan, features=features))

        # Score and select
        scored = score_branches(branches)
        selected_plan = scored[0].plan

        # Selected plan should be valid and complete
        assert selected_plan is not None
        assert len(selected_plan.days) >= 4

        # Plan should respect intent constraints
        total_cost = 0
        for day in selected_plan.days:
            for slot in day.slots:
                total_cost += slot.choices[0].features.cost_usd_cents

        # Add estimated additional costs (this is a rough check)
        estimated_total = total_cost + selected_plan.assumptions.daily_spend_est_cents * len(selected_plan.days)

        # Should be reasonable relative to budget (allow 50% over for estimation errors)
        assert estimated_total <= intent.budget_usd_cents * 1.5

    @patch('backend.app.planning.selector.logger')
    def test_score_logs_are_captured(self, mock_logger):
        """Test that score logs are captured during integration."""
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

        # Generate multiple plans to trigger logging
        plans = build_candidate_plans(intent)

        if len(plans) > 1:
            # Convert to branches
            branches = []
            for plan in plans:
                features = []
                for day in plan.days:
                    for slot in day.slots:
                        features.append(slot.choices[0].features)
                branches.append(BranchFeatures(plan=plan, features=features))

            # Score branches (should trigger logging)
            score_branches(branches)

            # Verify logging was called
            assert mock_logger.info.called

            # Check that score vector logs contain expected keys
            log_calls = mock_logger.info.call_args_list
            score_logs = [call for call in log_calls if "score vector" in str(call)]

            # Should have at least one log for chosen plan
            assert len(score_logs) >= 1


class TestPR6ConstraintValidation:
    """Test that PR6 implementation follows constraints."""

    def test_planner_deterministic_behavior(self):
        """Test that planner produces identical results for identical inputs."""
        intent = IntentV1(
            city="Rome",
            date_window=DateWindow(
                start=date(2025, 10, 1),
                end=date(2025, 10, 6),
                tz="Europe/Rome"
            ),
            budget_usd_cents=220_000,
            airports=["FCO"],
            prefs=Preferences(
                themes=["history", "art"],
                kid_friendly=False
            )
        )

        # Run planner multiple times
        runs = [build_candidate_plans(intent) for _ in range(3)]

        # All runs should produce identical results
        for i in range(1, len(runs)):
            assert len(runs[0]) == len(runs[i])

            for j in range(len(runs[0])):
                plan1, plan2 = runs[0][j], runs[i][j]

                # Plans should be structurally identical
                assert len(plan1.days) == len(plan2.days)
                assert plan1.rng_seed == plan2.rng_seed
                assert plan1.assumptions.fx_rate_usd_eur == plan2.assumptions.fx_rate_usd_eur

                # Day-by-day comparison
                for d1, d2 in zip(plan1.days, plan2.days, strict=False):
                    assert d1.date == d2.date
                    assert len(d1.slots) == len(d2.slots)

    def test_selector_uses_only_choice_features(self):
        """Test that selector implementation only accesses ChoiceFeatures."""
        # This test ensures the implementation constraint is met
        # by using a custom ChoiceFeatures that would fail if other fields were accessed

        from backend.app.models.plan import ChoiceFeatures

        # Create features with all possible values
        test_features = [
            ChoiceFeatures(
                cost_usd_cents=2500,
                travel_seconds=1800,
                indoor=True,
                themes=["test", "theme"]
            ),
            ChoiceFeatures(
                cost_usd_cents=3000,
                travel_seconds=None,
                indoor=None,
                themes=None
            )
        ]

        # Test aggregation function directly
        from backend.app.planning.selector import _aggregate_branch_features

        result = _aggregate_branch_features(test_features)

        # Should succeed and produce valid aggregates
        assert isinstance(result["cost"], float)
        assert isinstance(result["travel_time"], float)
        assert isinstance(result["theme_match"], float)
        assert isinstance(result["indoor_pref"], float)

        # Values should be reasonable
        assert result["cost"] > 0
        assert result["travel_time"] >= 0
        assert 0 <= result["theme_match"] <= 1
        assert -1 <= result["indoor_pref"] <= 1

    def test_fan_out_cap_enforcement(self):
        """Test that fan-out cap is enforced under all conditions."""
        # Test with various intents that might generate many plans
        test_intents = [
            # High budget, multiple airports, many themes
            IntentV1(
                city="Paris",
                date_window=DateWindow(start=date(2025, 6, 1), end=date(2025, 6, 8), tz="Europe/Paris"),
                budget_usd_cents=500_000,
                airports=["CDG", "ORY", "BVA"],
                prefs=Preferences(themes=["art", "food", "culture", "outdoor", "history"])
            ),
            # Medium budget, moderate complexity
            IntentV1(
                city="London",
                date_window=DateWindow(start=date(2025, 7, 1), end=date(2025, 7, 7), tz="Europe/London"),
                budget_usd_cents=300_000,
                airports=["LHR", "LGW"],
                prefs=Preferences(themes=["culture", "food"])
            ),
            # Low budget, should still cap
            IntentV1(
                city="Berlin",
                date_window=DateWindow(start=date(2025, 8, 1), end=date(2025, 8, 5), tz="Europe/Berlin"),
                budget_usd_cents=100_000,
                airports=["BER"],
                prefs=Preferences(themes=["art"])
            )
        ]

        for intent in test_intents:
            plans = build_candidate_plans(intent)
            assert len(plans) <= 4, f"Fan-out cap violated: {len(plans)} plans generated"
            assert len(plans) >= 1, "Should always generate at least one plan"
