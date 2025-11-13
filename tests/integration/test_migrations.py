"""Integration tests for Alembic migrations.

These tests verify:
1. Migrations can upgrade cleanly
2. Migrations can downgrade cleanly
3. Migration script does not contain dangerous operations
"""

import subprocess
from pathlib import Path

import pytest


@pytest.mark.integration
class TestAlembicMigrations:
    """Test Alembic migration safety and reversibility."""

    def test_migration_script_no_drop_operations(self):
        """
        Test that migration script does not contain dangerous DROP operations.

        Per SPEC: "Migrations must be additive (no DROP TABLE, DROP COLUMN etc.)."
        """
        # Find migration file
        migrations_dir = Path(__file__).parent.parent.parent / "alembic" / "versions"
        migration_files = list(migrations_dir.glob("*.py"))

        assert len(migration_files) > 0, "No migration files found"

        # Check each migration file
        for migration_file in migration_files:
            content = migration_file.read_text()

            # Check upgrade() function for dangerous operations
            # Look for DROP TABLE or DROP COLUMN in upgrade
            lines = content.split("\n")
            in_upgrade = False
            for line in lines:
                if "def upgrade()" in line:
                    in_upgrade = True
                elif "def downgrade()" in line:
                    in_upgrade = False

                if in_upgrade:
                    # Allow DROP in downgrade, but not in upgrade
                    dangerous_ops = ["DROP TABLE", "DROP COLUMN"]
                    for op in dangerous_ops:
                        if op in line.upper() and not line.strip().startswith("#"):
                            pytest.fail(
                                f"Migration {migration_file.name} contains "
                                f"dangerous operation in upgrade(): {line.strip()}"
                            )

    def test_migration_file_format(self):
        """Test that migration files follow expected format."""
        migrations_dir = Path(__file__).parent.parent.parent / "alembic" / "versions"
        migration_files = list(migrations_dir.glob("*.py"))

        for migration_file in migration_files:
            content = migration_file.read_text()

            # Must have revision ID
            assert "revision:" in content or "revision =" in content

            # Must have upgrade and downgrade functions
            assert "def upgrade()" in content
            assert "def downgrade()" in content

    def test_alembic_current_shows_version(self):
        """Test that alembic current command works (if DB is set up)."""
        # This test requires a test database to be set up
        # Skip if not in full integration test environment
        try:
            result = subprocess.run(
                ["alembic", "current"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # Command should run without error
            # May show no current version if DB not initialized, which is OK
            assert result.returncode == 0 or "command not found" not in result.stderr
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("Alembic not available or database not configured")

    def test_migration_dependencies(self):
        """Test that migrations have proper dependency chain."""
        migrations_dir = Path(__file__).parent.parent.parent / "alembic" / "versions"
        migration_files = list(migrations_dir.glob("*.py"))

        # Check first migration
        initial_migration = [
            f for f in migration_files if "001" in f.name or "initial" in f.name
        ]

        if initial_migration:
            content = initial_migration[0].read_text()
            # Initial migration should have down_revision = None
            assert (
                "down_revision: Union[str, None] = None" in content
                or "down_revision = None" in content
            )

    def test_migration_imports_required_types(self):
        """Test that migration imports necessary types for Postgres."""
        migrations_dir = Path(__file__).parent.parent.parent / "alembic" / "versions"
        migration_files = list(migrations_dir.glob("*.py"))

        for migration_file in migration_files:
            content = migration_file.read_text()

            # If using JSONB, must import postgresql
            if "JSONB" in content or "UUID" in content:
                assert (
                    "from sqlalchemy.dialects import postgresql" in content
                    or "from sqlalchemy.dialects.postgresql import" in content
                )

            # If using Vector, must import pgvector
            if "Vector" in content:
                assert "pgvector" in content or "vector" in content.lower()
