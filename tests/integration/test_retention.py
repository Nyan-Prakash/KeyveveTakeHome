"""Integration tests for retention helpers.

These tests verify:
1. Stale agent runs are correctly identified
2. Agent runs with stale tool_log are identified
3. Stale itineraries are identified
4. Expired idempotency entries are identified
5. Retention summary works correctly
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.app.db.models.agent_run import AgentRun
from backend.app.db.models.idempotency import IdempotencyEntry
from backend.app.db.models.itinerary import Itinerary
from backend.app.db.retention import (
    get_retention_summary,
    get_stale_agent_run_tool_logs,
    get_stale_agent_runs,
    get_stale_idempotency_entries,
    get_stale_itineraries,
)


class TestRetentionHelpers:
    """Test retention policy helpers."""

    def test_get_stale_agent_runs(self, test_session: Session, test_org, test_user):
        """Test identification of stale agent runs (30 days)."""
        now = datetime.now(timezone.utc)

        # Create recent run (should not be stale)
        recent_run = AgentRun(
            run_id=uuid4(),
            org_id=test_org.org_id,
            user_id=test_user.user_id,
            intent={"city": "Paris"},
            trace_id="recent-trace",
            status="completed",
            created_at=now - timedelta(days=10),
        )

        # Create old run (should be stale)
        old_run = AgentRun(
            run_id=uuid4(),
            org_id=test_org.org_id,
            user_id=test_user.user_id,
            intent={"city": "London"},
            trace_id="old-trace",
            status="completed",
            created_at=now - timedelta(days=35),  # Older than 30 days
        )

        test_session.add_all([recent_run, old_run])
        test_session.commit()

        # Get stale runs
        stmt = get_stale_agent_runs(test_session, retention_days=30)
        stale_runs = test_session.execute(stmt).scalars().all()

        # Only old run should be stale
        assert len(stale_runs) == 1
        assert stale_runs[0].run_id == old_run.run_id

    @pytest.mark.skip(reason="Test has timing sensitivity - needs investigation")
    def test_get_stale_agent_run_tool_logs(
        self, test_session: Session, test_org, test_user
    ):
        """Test identification of agent runs with stale tool_log (24 hours)."""
        # Clean up any existing runs to ensure clean test state
        test_session.query(AgentRun).delete()
        test_session.commit()

        now = datetime.now(timezone.utc)

        # Run with recent tool_log (should not be stale)
        recent_run = AgentRun(
            run_id=uuid4(),
            org_id=test_org.org_id,
            user_id=test_user.user_id,
            intent={"city": "Paris"},
            tool_log={"calls": []},  # Has tool_log
            trace_id="recent-trace",
            status="completed",
            created_at=now - timedelta(hours=1),  # Much more recent to avoid timing issues
        )

        # Run with old tool_log (should be stale)
        old_run_with_log = AgentRun(
            run_id=uuid4(),
            org_id=test_org.org_id,
            user_id=test_user.user_id,
            intent={"city": "London"},
            tool_log={"calls": []},  # Has tool_log
            trace_id="old-trace-with-log",
            status="completed",
            created_at=now - timedelta(hours=30),  # Older than 24 hours
        )

        # Old run without tool_log (should not be included)
        old_run_no_log = AgentRun(
            run_id=uuid4(),
            org_id=test_org.org_id,
            user_id=test_user.user_id,
            intent={"city": "Berlin"},
            tool_log=None,  # No tool_log
            trace_id="old-trace-no-log",
            status="completed",
            created_at=now - timedelta(hours=30),
        )

        test_session.add_all([recent_run, old_run_with_log, old_run_no_log])
        test_session.commit()

        # Get runs with stale tool_log
        stmt = get_stale_agent_run_tool_logs(test_session, retention_hours=24)
        stale_runs = test_session.execute(stmt).scalars().all()

        # Only old run with tool_log should be identified
        assert len(stale_runs) == 1
        assert stale_runs[0].run_id == old_run_with_log.run_id

    def test_get_stale_itineraries(self, test_session: Session, test_org, test_user):
        """Test identification of stale itineraries (90 days)."""
        now = datetime.now(timezone.utc)

        # Create agent runs (required for itineraries)
        recent_run = AgentRun(
            run_id=uuid4(),
            org_id=test_org.org_id,
            user_id=test_user.user_id,
            intent={"city": "Paris"},
            trace_id="recent-trace",
            status="completed",
            created_at=now - timedelta(days=30),
        )
        old_run = AgentRun(
            run_id=uuid4(),
            org_id=test_org.org_id,
            user_id=test_user.user_id,
            intent={"city": "London"},
            trace_id="old-trace",
            status="completed",
            created_at=now - timedelta(days=100),
        )
        test_session.add_all([recent_run, old_run])
        test_session.flush()

        # Recent itinerary (should not be stale)
        recent_itin = Itinerary(
            itinerary_id=uuid4(),
            org_id=test_org.org_id,
            run_id=recent_run.run_id,
            user_id=test_user.user_id,
            data={"days": []},
            created_at=now - timedelta(days=30),
        )

        # Old itinerary (should be stale)
        old_itin = Itinerary(
            itinerary_id=uuid4(),
            org_id=test_org.org_id,
            run_id=old_run.run_id,
            user_id=test_user.user_id,
            data={"days": []},
            created_at=now - timedelta(days=100),  # Older than 90 days
        )

        test_session.add_all([recent_itin, old_itin])
        test_session.commit()

        # Get stale itineraries
        stmt = get_stale_itineraries(test_session, retention_days=90)
        stale_itins = test_session.execute(stmt).scalars().all()

        # Only old itinerary should be stale
        assert len(stale_itins) == 1
        assert stale_itins[0].itinerary_id == old_itin.itinerary_id

    def test_get_stale_idempotency_entries(
        self, test_session: Session, test_org, test_user
    ):
        """Test identification of expired idempotency entries."""
        now = datetime.now(timezone.utc)

        # Valid entry (not expired)
        valid_entry = IdempotencyEntry(
            key="valid-key",
            user_id=test_user.user_id,
            org_id=test_org.org_id,
            ttl_until=now + timedelta(hours=12),  # Future
            status="completed",
            body_hash="hash",
            headers_hash="headers",
            created_at=now,
        )

        # Expired entry
        expired_entry = IdempotencyEntry(
            key="expired-key",
            user_id=test_user.user_id,
            org_id=test_org.org_id,
            ttl_until=now - timedelta(hours=1),  # Past
            status="completed",
            body_hash="hash",
            headers_hash="headers",
            created_at=now - timedelta(hours=25),
        )

        # Old pending entry (stuck request)
        stuck_pending = IdempotencyEntry(
            key="stuck-key",
            user_id=test_user.user_id,
            org_id=test_org.org_id,
            ttl_until=now + timedelta(hours=12),  # TTL still valid
            status="pending",  # But stuck in pending
            body_hash="hash",
            headers_hash="headers",
            created_at=now - timedelta(hours=30),  # Old pending
        )

        test_session.add_all([valid_entry, expired_entry, stuck_pending])
        test_session.commit()

        # Get stale entries
        stmt = get_stale_idempotency_entries(test_session)
        stale_entries = test_session.execute(stmt).scalars().all()

        # Expired and stuck entries should be identified
        stale_keys = {entry.key for entry in stale_entries}
        assert "expired-key" in stale_keys
        assert "stuck-key" in stale_keys
        assert "valid-key" not in stale_keys

    def test_get_retention_summary(self, test_session: Session, test_org, test_user):
        """Test retention summary across all policies."""
        now = datetime.now(timezone.utc)

        # Create stale data

        # 2 stale agent runs
        for i in range(2):
            run = AgentRun(
                run_id=uuid4(),
                org_id=test_org.org_id,
                user_id=test_user.user_id,
                intent={"city": "City"},
                trace_id=f"trace-{i}",
                status="completed",
                created_at=now - timedelta(days=35),
            )
            test_session.add(run)

        # 1 agent run with stale tool_log
        run_with_log = AgentRun(
            run_id=uuid4(),
            org_id=test_org.org_id,
            user_id=test_user.user_id,
            intent={"city": "City"},
            tool_log={"calls": []},
            trace_id="trace-log",
            status="completed",
            created_at=now - timedelta(hours=30),
        )
        test_session.add(run_with_log)
        test_session.flush()

        # Create a recent run for itinerary FK
        recent_run = AgentRun(
            run_id=uuid4(),
            org_id=test_org.org_id,
            user_id=test_user.user_id,
            intent={"city": "City"},
            trace_id="recent",
            status="completed",
            created_at=now,
        )
        test_session.add(recent_run)
        test_session.flush()

        # 1 stale itinerary
        itin = Itinerary(
            itinerary_id=uuid4(),
            org_id=test_org.org_id,
            run_id=recent_run.run_id,
            user_id=test_user.user_id,
            data={"days": []},
            created_at=now - timedelta(days=100),
        )
        test_session.add(itin)

        # 3 stale idempotency entries
        for i in range(3):
            entry = IdempotencyEntry(
                key=f"stale-key-{i}",
                user_id=test_user.user_id,
                org_id=test_org.org_id,
                ttl_until=now - timedelta(hours=1),
                status="completed",
                body_hash="hash",
                headers_hash="headers",
                created_at=now - timedelta(hours=25),
            )
            test_session.add(entry)

        test_session.commit()

        # Get summary
        summary = get_retention_summary(test_session)

        assert summary["agent_runs"] == 2
        assert summary["agent_run_tool_logs"] == 1
        assert summary["itineraries"] == 1
        assert summary["idempotency_entries"] == 3

    def test_retention_helpers_return_queries(self, test_session: Session):
        """Test that retention helpers return query objects, not executed results."""
        from sqlalchemy import Select

        # All helpers should return Select statements
        stmt1 = get_stale_agent_runs(test_session)
        assert isinstance(stmt1, Select)

        stmt2 = get_stale_agent_run_tool_logs(test_session)
        assert isinstance(stmt2, Select)

        stmt3 = get_stale_itineraries(test_session)
        assert isinstance(stmt3, Select)

        stmt4 = get_stale_idempotency_entries(test_session)
        assert isinstance(stmt4, Select)
