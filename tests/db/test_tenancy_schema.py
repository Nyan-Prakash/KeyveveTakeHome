"""Tests for multi-tenancy schema enforcement."""

import pytest
from sqlalchemy import inspect

from backend.app.config import get_settings
from backend.app.db.base import Base, get_engine
from backend.app.db.models import (
    AgentRun,
    Destination,
    Embedding,
    Itinerary,
    KnowledgeItem,
    User,
)


@pytest.mark.integration
class TestTenancySchema:
    """Tests for multi-tenancy schema enforcement."""

    @pytest.fixture(scope="class")
    def engine(self):
        """Create a test database engine."""
        settings = get_settings()
        return get_engine(settings)

    def test_org_scoped_models_have_org_id(self, engine):
        """Test that org-scoped models have org_id column."""
        inspector = inspect(engine)
        org_scoped_models = [
            User,
            Destination,
            KnowledgeItem,
            Embedding,
            AgentRun,
            Itinerary,
        ]

        for model in org_scoped_models:
            table_name = model.__tablename__
            if table_name in inspector.get_table_names():
                columns = {col["name"]: col for col in inspector.get_columns(table_name)}

                # Assert org_id exists
                assert "org_id" in columns, f"{table_name} missing org_id column"

                # Assert org_id is NOT NULL
                assert (
                    columns["org_id"]["nullable"] is False
                ), f"{table_name}.org_id should be NOT NULL"

    def test_user_composite_unique_constraint(self, engine):
        """Test that User has composite unique constraint on (org_id, email)."""
        inspector = inspect(engine)
        table_name = User.__tablename__

        if table_name in inspector.get_table_names():
            constraints = inspector.get_unique_constraints(table_name)

            # Find the constraint with org_id and email
            found = False
            for constraint in constraints:
                if set(constraint["column_names"]) == {"org_id", "email"}:
                    found = True
                    break

            assert found, f"{table_name} missing unique constraint on (org_id, email)"

    def test_destination_composite_unique_constraint(self, engine):
        """Test that Destination has composite unique constraint on (org_id, slug)."""
        inspector = inspect(engine)
        table_name = Destination.__tablename__

        if table_name in inspector.get_table_names():
            constraints = inspector.get_unique_constraints(table_name)

            # Find the constraint with org_id and slug
            found = False
            for constraint in constraints:
                if set(constraint["column_names"]) == {"org_id", "slug"}:
                    found = True
                    break

            assert found, f"{table_name} missing unique constraint on (org_id, slug)"

    def test_org_scoped_models_have_org_id_index(self, engine):
        """Test that org-scoped models have index on org_id."""
        inspector = inspect(engine)
        org_scoped_models = [
            User,
            Destination,
            KnowledgeItem,
            Embedding,
            AgentRun,
            Itinerary,
        ]

        for model in org_scoped_models:
            table_name = model.__tablename__
            if table_name in inspector.get_table_names():
                indexes = inspector.get_indexes(table_name)

                # Check if any index includes org_id
                found = False
                for index in indexes:
                    if "org_id" in index["column_names"]:
                        found = True
                        break

                assert found, f"{table_name} missing index on org_id"
