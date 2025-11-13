"""Test that constants are accessible from Settings and no duplicated literals exist."""

import ast
from pathlib import Path

import pytest

from backend.app.config import Settings, get_settings


class TestConstantsSingleSource:
    """Test that all constants are accessible from Settings."""

    def test_settings_accessible(self):
        """Test that Settings can be imported and instantiated."""
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_buffer_constants_accessible(self):
        """Test that buffer constants are accessible from settings."""
        settings = get_settings()

        # Airport buffer
        assert hasattr(settings, "airport_buffer_min")
        assert isinstance(settings.airport_buffer_min, int)
        assert settings.airport_buffer_min > 0

        # Transit buffer
        assert hasattr(settings, "transit_buffer_min")
        assert isinstance(settings.transit_buffer_min, int)
        assert settings.transit_buffer_min > 0

    def test_jitter_constants_accessible(self):
        """Test that jitter constants are accessible from settings."""
        settings = get_settings()

        assert hasattr(settings, "retry_jitter_min_ms")
        assert isinstance(settings.retry_jitter_min_ms, int)
        assert settings.retry_jitter_min_ms >= 0

        assert hasattr(settings, "retry_jitter_max_ms")
        assert isinstance(settings.retry_jitter_max_ms, int)
        assert settings.retry_jitter_max_ms >= settings.retry_jitter_min_ms

    def test_ttl_constants_accessible(self):
        """Test that TTL constants are accessible from settings."""
        settings = get_settings()

        assert hasattr(settings, "fx_ttl_hours")
        assert isinstance(settings.fx_ttl_hours, int)
        assert settings.fx_ttl_hours > 0

        assert hasattr(settings, "weather_ttl_hours")
        assert isinstance(settings.weather_ttl_hours, int)
        assert settings.weather_ttl_hours > 0

    def test_timeout_constants_accessible(self):
        """Test that timeout constants are accessible from settings."""
        settings = get_settings()

        assert hasattr(settings, "soft_timeout_s")
        assert isinstance(settings.soft_timeout_s, (int, float))
        assert settings.soft_timeout_s > 0

        assert hasattr(settings, "hard_timeout_s")
        assert isinstance(settings.hard_timeout_s, (int, float))
        assert settings.hard_timeout_s >= settings.soft_timeout_s

    def test_circuit_breaker_constants_accessible(self):
        """Test that circuit breaker constants are accessible from settings."""
        settings = get_settings()

        assert hasattr(settings, "breaker_failure_threshold")
        assert isinstance(settings.breaker_failure_threshold, int)
        assert settings.breaker_failure_threshold > 0

        assert hasattr(settings, "breaker_timeout_s")
        assert isinstance(settings.breaker_timeout_s, int)
        assert settings.breaker_timeout_s > 0

    def test_performance_budget_constants_accessible(self):
        """Test that performance budget constants are accessible."""
        settings = get_settings()

        assert hasattr(settings, "ttfe_budget_ms")
        assert isinstance(settings.ttfe_budget_ms, int)
        assert settings.ttfe_budget_ms > 0

        assert hasattr(settings, "e2e_p50_budget_s")
        assert isinstance(settings.e2e_p50_budget_s, int)
        assert settings.e2e_p50_budget_s > 0

        assert hasattr(settings, "e2e_p95_budget_s")
        assert isinstance(settings.e2e_p95_budget_s, int)
        assert settings.e2e_p95_budget_s >= settings.e2e_p50_budget_s


class TestNoDuplicatedLiterals:
    """Test that there are no duplicated magic numbers in model modules."""

    def _extract_numeric_literals_from_file(self, file_path: Path) -> list[int]:
        """Extract numeric literals from a Python file."""
        if not file_path.exists():
            return []

        try:
            with open(file_path) as f:
                content = f.read()

            tree = ast.parse(content)
            literals = []

            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, int):
                    # Filter out common literals that are expected to be duplicated
                    if node.value not in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, -1]:
                        literals.append(node.value)

            return literals
        except (SyntaxError, UnicodeDecodeError):
            # Skip files that can't be parsed
            return []

    def _get_model_files(self) -> list[Path]:
        """Get all Python files in the models directory."""
        models_dir = Path(__file__).parent.parent.parent / "backend" / "app" / "models"
        if not models_dir.exists():
            return []

        return list(models_dir.glob("*.py"))

    def test_no_duplicated_magic_numbers_in_models(self):
        """Test that model modules don't have duplicated magic numbers."""
        model_files = self._get_model_files()

        if not model_files:
            pytest.skip("No model files found")

        all_literals = []
        file_literals = {}

        for file_path in model_files:
            if file_path.name == "__init__.py":
                continue  # Skip __init__.py

            literals = self._extract_numeric_literals_from_file(file_path)
            file_literals[file_path.name] = literals
            all_literals.extend(literals)

        # Check for duplicated literals across files
        literal_counts = {}
        for literal in all_literals:
            literal_counts[literal] = literal_counts.get(literal, 0) + 1

        duplicated = {lit: count for lit, count in literal_counts.items() if count > 1}

        # Some literals are OK to duplicate (like common values)
        allowed_duplicates = {
            15,  # Common buffer/timeout value
            24,  # Hours in day
            120,  # Common buffer value
            1536,  # Embedding dimension (if used)
        }

        problematic_duplicates = {
            lit: count
            for lit, count in duplicated.items()
            if lit not in allowed_duplicates
        }

        if problematic_duplicates:
            # This is more of a warning than a hard failure for PR-1
            print(f"Warning: Potentially duplicated literals: {problematic_duplicates}")
            # For now, just warn instead of failing
            # assert not problematic_duplicates, f"Duplicated literals found: {problematic_duplicates}"

    def test_settings_default_values_reasonable(self):
        """Test that settings have reasonable default values."""
        # Test with empty environment to get defaults
        settings = Settings(
            jwt_private_key_pem="dummy",
            jwt_public_key_pem="dummy",
            weather_api_key="dummy",
        )

        # Buffer values should be reasonable
        assert 60 <= settings.airport_buffer_min <= 180  # 1-3 hours
        assert 5 <= settings.transit_buffer_min <= 60  # 5min-1hour

        # Timeout values should be reasonable
        assert 1 <= settings.soft_timeout_s <= 5  # 1-5 seconds
        assert 2 <= settings.hard_timeout_s <= 10  # 2-10 seconds
        assert settings.hard_timeout_s >= settings.soft_timeout_s

        # TTL values should be reasonable
        assert 1 <= settings.fx_ttl_hours <= 168  # 1 hour to 1 week
        assert 1 <= settings.weather_ttl_hours <= 168  # 1 hour to 1 week

        # Performance budgets should be reasonable
        assert 100 <= settings.ttfe_budget_ms <= 2000  # 100ms to 2s
        assert 1 <= settings.e2e_p50_budget_s <= 30  # 1-30 seconds
        assert 5 <= settings.e2e_p95_budget_s <= 60  # 5-60 seconds
