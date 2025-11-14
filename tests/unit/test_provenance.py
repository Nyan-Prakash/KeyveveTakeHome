"""Tests for provenance helper functions and validation."""

from datetime import UTC, datetime

import pytest

from backend.app.models.common import (
    Provenance,
    compute_response_digest,
    create_provenance,
)


def test_compute_response_digest_deterministic() -> None:
    """Test that compute_response_digest is deterministic."""
    data = {"foo": "bar", "baz": [1, 2, 3], "nested": {"key": "value"}}

    digest1 = compute_response_digest(data)
    digest2 = compute_response_digest(data)

    assert digest1 == digest2
    assert isinstance(digest1, str)
    assert len(digest1) == 64  # SHA256 hex digest length


def test_compute_response_digest_order_independent() -> None:
    """Test that key order doesn't affect digest (sorted keys)."""
    data1 = {"a": 1, "b": 2, "c": 3}
    data2 = {"c": 3, "a": 1, "b": 2}

    digest1 = compute_response_digest(data1)
    digest2 = compute_response_digest(data2)

    assert digest1 == digest2


def test_compute_response_digest_different_data() -> None:
    """Test that different data produces different digests."""
    data1 = {"foo": "bar"}
    data2 = {"foo": "baz"}

    digest1 = compute_response_digest(data1)
    digest2 = compute_response_digest(data2)

    assert digest1 != digest2


def test_compute_response_digest_complex_types() -> None:
    """Test that compute_response_digest handles complex types."""
    from datetime import date

    data = {
        "string": "test",
        "int": 42,
        "float": 3.14,
        "bool": True,
        "none": None,
        "list": [1, 2, 3],
        "dict": {"nested": "value"},
        "date": date(2025, 6, 1),  # Non-JSON-serializable, uses default=str
    }

    digest = compute_response_digest(data)

    assert isinstance(digest, str)
    assert len(digest) == 64


def test_create_provenance_minimal() -> None:
    """Test creating provenance with minimal required fields."""
    prov = create_provenance(source="fixture")

    assert prov.source == "fixture"
    assert prov.ref_id is None
    assert prov.source_url is None
    assert isinstance(prov.fetched_at, datetime)
    assert prov.cache_hit is None
    assert prov.response_digest is None


def test_create_provenance_full() -> None:
    """Test creating provenance with all fields."""
    fetched_at = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    response_data = {"test": "data"}

    prov = create_provenance(
        source="tool",
        ref_id="test-ref-123",
        source_url="https://api.example.com",
        fetched_at=fetched_at,
        cache_hit=True,
        response_data=response_data,
    )

    assert prov.source == "tool"
    assert prov.ref_id == "test-ref-123"
    assert prov.source_url == "https://api.example.com"
    assert prov.fetched_at == fetched_at
    assert prov.cache_hit is True
    assert prov.response_digest is not None
    assert isinstance(prov.response_digest, str)
    assert len(prov.response_digest) == 64


def test_create_provenance_auto_timestamp() -> None:
    """Test that create_provenance auto-generates timestamp if not provided."""
    before = datetime.now(UTC)
    prov = create_provenance(source="fixture")
    after = datetime.now(UTC)

    assert before <= prov.fetched_at <= after


def test_create_provenance_response_digest() -> None:
    """Test that response_digest is computed from response_data."""
    data = {"foo": "bar", "baz": 123}

    prov = create_provenance(source="fixture", response_data=data)

    expected_digest = compute_response_digest(data)
    assert prov.response_digest == expected_digest


def test_provenance_model_validation() -> None:
    """Test that Provenance model validates required fields."""
    from pydantic import ValidationError

    # This should work
    prov = Provenance(
        source="fixture",
        fetched_at=datetime.now(UTC),
    )
    assert prov.source == "fixture"

    # Missing required field should raise
    with pytest.raises(ValidationError):
        Provenance(source="fixture")  # Missing fetched_at  # type: ignore[call-arg]


def test_provenance_all_fields_populated() -> None:
    """Test that a fully populated provenance has all expected fields."""
    prov = Provenance(
        source="tool",
        ref_id="ref-123",
        source_url="https://example.com",
        fetched_at=datetime.now(UTC),
        cache_hit=False,
        response_digest="abc123def456",
    )

    assert prov.source == "tool"
    assert prov.ref_id == "ref-123"
    assert prov.source_url == "https://example.com"
    assert isinstance(prov.fetched_at, datetime)
    assert prov.cache_hit is False
    assert prov.response_digest == "abc123def456"


def test_provenance_fixture_source_convention() -> None:
    """Test that fixture sources use 'fixture' as source type."""
    prov = create_provenance(
        source="fixture",
        ref_id="fixture:flights:CDG-JFK-2025-06-01",
    )

    assert prov.source == "fixture"
    assert prov.ref_id is not None
    assert "fixture:" in prov.ref_id


def test_provenance_tri_state_cache_hit() -> None:
    """Test that cache_hit supports tri-state (True/False/None)."""
    # Explicit True
    prov1 = create_provenance(source="tool", cache_hit=True)
    assert prov1.cache_hit is True

    # Explicit False
    prov2 = create_provenance(source="tool", cache_hit=False)
    assert prov2.cache_hit is False

    # None (unknown)
    prov3 = create_provenance(source="tool", cache_hit=None)
    assert prov3.cache_hit is None

    # Default (not provided)
    prov4 = create_provenance(source="tool")
    assert prov4.cache_hit is None
