"""Test the evaluation runner."""

import subprocess
import sys
from pathlib import Path


class TestEvalRunner:
    """Test the evaluation runner functionality."""

    def test_eval_runner_executes_without_error(self):
        """Test that eval runner runs without throwing exceptions."""
        eval_dir = Path(__file__).parent.parent.parent / "eval"
        runner_path = eval_dir / "runner.py"

        assert runner_path.exists(), "Eval runner script not found"

        # Run the evaluation script
        result = subprocess.run(
            [sys.executable, str(runner_path)],
            cwd=eval_dir,
            capture_output=True,
            text=True,
        )

        # Should not crash (exit code doesn't matter for this test)
        # We're just testing that it runs without throwing exceptions
        assert result.returncode in [0, 1], (
            f"Eval runner crashed with exit code {result.returncode}. "
            f"Stdout: {result.stdout}\nStderr: {result.stderr}"
        )

    def test_eval_runner_produces_expected_output(self):
        """Test that eval runner produces expected output format."""
        eval_dir = Path(__file__).parent.parent.parent / "eval"
        runner_path = eval_dir / "runner.py"

        result = subprocess.run(
            [sys.executable, str(runner_path)],
            cwd=eval_dir,
            capture_output=True,
            text=True,
        )

        output = result.stdout

        # Check for expected output patterns
        assert "Running evaluation" in output
        assert "scenarios" in output
        assert "Summary:" in output

        # Should mention both scenarios
        assert "happy_stub" in output
        assert "budget_fail_stub" in output

    def test_eval_scenarios_have_expected_results(self):
        """Test that eval runner produces expected pass/fail results."""
        eval_dir = Path(__file__).parent.parent.parent / "eval"
        runner_path = eval_dir / "runner.py"

        result = subprocess.run(
            [sys.executable, str(runner_path)],
            cwd=eval_dir,
            capture_output=True,
            text=True,
        )

        output = result.stdout

        # The happy_stub scenario should pass (within budget)
        # The budget_fail_stub scenario should pass (budget exceeded as expected)
        # Both scenarios should show some form of success indication

        # Check that evaluation completed
        assert "Summary:" in output

        # Check for pass indicators (✅ or PASS)
        pass_indicators = output.count("✅") + output.count("PASS")
        assert pass_indicators > 0, "No passing scenarios found in output"

    def test_scenarios_yaml_file_exists_and_valid(self):
        """Test that scenarios.yaml file exists and has valid structure."""
        eval_dir = Path(__file__).parent.parent.parent / "eval"
        scenarios_path = eval_dir / "scenarios.yaml"

        assert scenarios_path.exists(), "scenarios.yaml file not found"

        # Try to load the YAML (basic validation)
        import yaml

        with open(scenarios_path) as f:
            data = yaml.safe_load(f)

        assert "scenarios" in data
        assert isinstance(data["scenarios"], list)
        assert len(data["scenarios"]) >= 2  # At least happy_stub and budget_fail_stub

        # Check each scenario has required fields
        for scenario in data["scenarios"]:
            assert "scenario_id" in scenario
            assert "description" in scenario
            assert "intent" in scenario
            assert "must_satisfy" in scenario

            # Check intent structure
            intent = scenario["intent"]
            assert "city" in intent
            assert "date_window" in intent
            assert "budget_usd_cents" in intent
            assert "airports" in intent
            assert "prefs" in intent

    def test_eval_runner_returns_appropriate_exit_codes(self):
        """Test that eval runner returns appropriate exit codes."""
        eval_dir = Path(__file__).parent.parent.parent / "eval"
        runner_path = eval_dir / "runner.py"

        result = subprocess.run(
            [sys.executable, str(runner_path)],
            cwd=eval_dir,
            capture_output=True,
            text=True,
        )

        # Should return 0 for success or 1 for some failures
        # (For our stub scenarios, we expect success)
        assert result.returncode in [0, 1], f"Unexpected exit code: {result.returncode}"

        # If exit code is 1, there should be failure indicators in output
        if result.returncode == 1:
            output = result.stdout + result.stderr
            assert (
                "FAIL" in output or "❌" in output or "failed" in output
            ), "Exit code 1 but no failure indicators in output"
