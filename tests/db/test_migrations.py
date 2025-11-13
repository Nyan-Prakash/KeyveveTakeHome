"""Tests for Alembic migrations."""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from backend.app.config import get_settings
from backend.app.db.base import get_engine


@pytest.mark.integration
class TestMigrations:
    """Tests for database migrations."""

    @pytest.fixture(scope="class")
    def alembic_config(self):
        """Create Alembic configuration."""
        config = Config("alembic.ini")
        settings = get_settings()
        config.set_main_option("sqlalchemy.url", settings.postgres_url)
        return config

    @pytest.fixture(scope="class")
    def engine(self):
        """Create a test database engine."""
        settings = get_settings()
        return get_engine(settings)

    def test_upgrade_creates_tables(self, alembic_config, engine):
        """Test that alembic upgrade head creates all tables."""
        # Downgrade to base first to ensure clean state
        try:
            command.downgrade(alembic_config, "base")
        except Exception:
            pass  # Ignore if already at base

        # Run upgrade
        command.upgrade(alembic_config, "head")

        # Verify tables exist
        inspector = inspect(engine)
        table_names = inspector.get_table_names()

        expected_tables = {
            "orgs",
            "users",
            "refresh_tokens",
            "destinations",
            "knowledge_items",
            "embeddings",
            "agent_runs",
            "itineraries",
            "idempotency_keys",
            "alembic_version",  # Alembic tracking table
        }

        for table in expected_tables:
            assert table in table_names, f"Table {table} not found after upgrade"

    def test_downgrade_removes_tables(self, alembic_config, engine):
        """Test that alembic downgrade base removes all tables."""
        # Ensure we're at head first
        command.upgrade(alembic_config, "head")

        # Run downgrade
        command.downgrade(alembic_config, "base")

        # Verify tables are gone (except alembic_version which Alembic keeps)
        inspector = inspect(engine)
        table_names = inspector.get_table_names()

        removed_tables = {
            "orgs",
            "users",
            "refresh_tokens",
            "destinations",
            "knowledge_items",
            "embeddings",
            "agent_runs",
            "itineraries",
            "idempotency_keys",
        }

        for table in removed_tables:
            assert table not in table_names, f"Table {table} still exists after downgrade"

    def test_upgrade_is_idempotent(self, alembic_config, engine):
        """Test that running upgrade multiple times is safe."""
        # Run upgrade to head
        command.upgrade(alembic_config, "head")

        # Run upgrade again - should not error
        command.upgrade(alembic_config, "head")

        # Verify tables still exist
        inspector = inspect(engine)
        table_names = inspector.get_table_names()

        assert "orgs" in table_names
        assert "users" in table_names
