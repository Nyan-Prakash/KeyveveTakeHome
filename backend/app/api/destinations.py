"""Destinations API endpoints for managing travel destinations."""

from collections.abc import Generator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.auth import CurrentUser, get_current_user
from backend.app.db.models.agent_run import AgentRun
from backend.app.db.models.destination import Destination
from backend.app.db.session import get_session_factory

router = APIRouter(prefix="/destinations", tags=["destinations"])


class GeoModel(BaseModel):
    """Geographic coordinates."""

    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class LastRunSummary(BaseModel):
    """Summary of the last agent run for a destination."""

    run_id: UUID | None = None
    status: str | None = None
    total_cost_usd_cents: int | None = None
    created_at: str | None = None


class DestinationResponse(BaseModel):
    """Destination response model."""

    dest_id: UUID
    city: str
    country: str
    geo: GeoModel
    fixture_path: str | None = None
    created_at: str
    last_run: LastRunSummary | None = None


class CreateDestinationRequest(BaseModel):
    """Request to create a new destination."""

    city: str = Field(..., min_length=1, max_length=200)
    country: str = Field(..., min_length=1, max_length=200)
    geo: GeoModel
    fixture_path: str | None = None


class UpdateDestinationRequest(BaseModel):
    """Request to update a destination."""

    city: str | None = Field(None, min_length=1, max_length=200)
    country: str | None = Field(None, min_length=1, max_length=200)
    geo: GeoModel | None = None
    fixture_path: str | None = None


def get_db_session() -> Generator[Session, None, None]:
    """Dependency to get a database session."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


def get_last_run_for_destination(
    session: Session, org_id: UUID, city: str
) -> LastRunSummary:
    """Get the last run summary for a destination based on intent city."""
    stmt = (
        select(AgentRun)
        .where(AgentRun.org_id == org_id)
        .order_by(AgentRun.created_at.desc())
    )
    runs = session.execute(stmt).scalars().all()

    # Find the most recent run matching this city
    for run in runs:
        intent = run.intent
        if isinstance(intent, dict) and intent.get("city", "").lower() == city.lower():
            # Extract cost from tool_log or plan_snapshot
            cost_cents = None
            if run.cost_usd is not None:
                cost_cents = int(run.cost_usd * 100)

            return LastRunSummary(
                run_id=run.run_id,
                status=run.status,
                total_cost_usd_cents=cost_cents,
                created_at=run.created_at.isoformat() if run.created_at else None,
            )

    return LastRunSummary()


@router.get("", response_model=list[DestinationResponse])
def list_destinations(
    search: str | None = Query(None, description="Search by city or country"),
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> list[DestinationResponse]:
    """List all destinations for the current org with optional search."""
    stmt = select(Destination).where(Destination.org_id == current_user.org_id)

    if search:
        search_lower = f"%{search.lower()}%"
        stmt = stmt.where(
            (func.lower(Destination.city).like(search_lower))
            | (func.lower(Destination.country).like(search_lower))
        )

    stmt = stmt.order_by(Destination.created_at.desc())
    destinations = session.execute(stmt).scalars().all()

    results = []
    for dest in destinations:
        last_run = get_last_run_for_destination(session, current_user.org_id, dest.city)
        results.append(
            DestinationResponse(
                dest_id=dest.dest_id,
                city=dest.city,
                country=dest.country,
                geo=GeoModel(lat=dest.geo["lat"], lon=dest.geo["lon"]),
                fixture_path=dest.fixture_path,
                created_at=dest.created_at.isoformat(),
                last_run=last_run,
            )
        )

    return results


@router.post(
    "", response_model=DestinationResponse, status_code=status.HTTP_201_CREATED
)
def create_destination(
    request: CreateDestinationRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> DestinationResponse:
    """Create a new destination (org-scoped)."""
    # Check if destination already exists for this org
    stmt = select(Destination).where(
        Destination.org_id == current_user.org_id,
        Destination.city == request.city,
        Destination.country == request.country,
    )
    existing = session.execute(stmt).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Destination already exists for this organization",
        )

    # Create new destination
    destination = Destination(
        org_id=current_user.org_id,
        city=request.city,
        country=request.country,
        geo={"lat": request.geo.lat, "lon": request.geo.lon},
        fixture_path=request.fixture_path,
    )

    session.add(destination)
    session.commit()
    session.refresh(destination)

    return DestinationResponse(
        dest_id=destination.dest_id,
        city=destination.city,
        country=destination.country,
        geo=GeoModel(lat=destination.geo["lat"], lon=destination.geo["lon"]),
        fixture_path=destination.fixture_path,
        created_at=destination.created_at.isoformat(),
        last_run=LastRunSummary(),
    )


@router.patch("/{dest_id}", response_model=DestinationResponse)
def update_destination(
    dest_id: UUID,
    request: UpdateDestinationRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> DestinationResponse:
    """Update a destination (org-scoped)."""
    stmt = select(Destination).where(Destination.dest_id == dest_id)
    destination = session.execute(stmt).scalar_one_or_none()

    if not destination:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Destination not found",
        )

    if destination.org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this destination",
        )

    # Update fields if provided
    if request.city is not None:
        destination.city = request.city
    if request.country is not None:
        destination.country = request.country
    if request.geo is not None:
        destination.geo = {"lat": request.geo.lat, "lon": request.geo.lon}
    if request.fixture_path is not None:
        destination.fixture_path = request.fixture_path

    session.commit()
    session.refresh(destination)

    last_run = get_last_run_for_destination(
        session, current_user.org_id, destination.city
    )

    return DestinationResponse(
        dest_id=destination.dest_id,
        city=destination.city,
        country=destination.country,
        geo=GeoModel(lat=destination.geo["lat"], lon=destination.geo["lon"]),
        fixture_path=destination.fixture_path,
        created_at=destination.created_at.isoformat(),
        last_run=last_run,
    )


@router.delete("/{dest_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_destination(
    dest_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> None:
    """Soft delete a destination (org-scoped).

    For PR11, we're doing a hard delete for simplicity.
    In production, this would set a deleted_at timestamp.
    """
    stmt = select(Destination).where(Destination.dest_id == dest_id)
    destination = session.execute(stmt).scalar_one_or_none()

    if not destination:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Destination not found",
        )

    if destination.org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this destination",
        )

    session.delete(destination)
    session.commit()
