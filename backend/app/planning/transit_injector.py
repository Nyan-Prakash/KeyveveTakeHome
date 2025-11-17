"""Transit injection module for automatic transit between activities.

This module enhances the planner by automatically injecting transit events
between every pair of consecutive activities, using the RAG system for
location data and budget-conscious transit mode selection.
"""

from datetime import UTC, datetime, time, timedelta
from typing import Any
from uuid import UUID

from backend.app.adapters.transit import get_transit_leg
from backend.app.models.common import ChoiceKind, Geo, Provenance, TimeWindow, TransitMode
from backend.app.models.intent import IntentV1
from backend.app.models.plan import Choice, ChoiceFeatures, DayPlan, PlanV1, Slot

# Default city center coordinates (fallback if RAG doesn't provide locations)
DEFAULT_CITY_COORDS = {
    "paris": Geo(lat=48.8566, lon=2.3522),
    "london": Geo(lat=51.5074, lon=-0.1278),
    "madrid": Geo(lat=40.4168, lon=-3.7038),
    "denver": Geo(lat=39.7392, lon=-104.9903),
    "tokyo": Geo(lat=35.6762, lon=139.6503),
    "rio de janeiro": Geo(lat=-22.9068, lon=-43.1729),
    "reykjavik": Geo(lat=64.1466, lon=-21.9426),
}


def _select_budget_aware_transit_mode(
    intent: IntentV1, distance_km: float, available_modes: list[TransitMode] | None = None
) -> TransitMode:
    """Select appropriate transit mode based on budget and distance.
    
    Args:
        intent: User intent containing budget constraints
        distance_km: Distance to travel in kilometers
        available_modes: Available transit modes (if None, use all)
    
    Returns:
        Most appropriate transit mode for the budget
    """
    if available_modes is None:
        available_modes = [TransitMode.walk, TransitMode.metro, TransitMode.bus, TransitMode.taxi]
    
    # Calculate budget per day for transit decisions
    trip_days = max((intent.date_window.end - intent.date_window.start).days, 1)
    budget_per_day = intent.budget_usd_cents / trip_days
    
    # Distance thresholds for mode selection (in km)
    WALK_MAX_DISTANCE = 2.0  # Max 2km for walking
    
    # Budget thresholds (daily budget available)
    BUDGET_TIGHT = 15000    # Less than $150/day - prefer walking and public transit
    BUDGET_MODERATE = 30000 # $150-300/day - mix of public transit and occasional taxis
    # $300+/day - can afford taxis and convenience
    
    # For very short distances, always prefer walking if available
    if distance_km <= 0.5 and TransitMode.walk in available_modes:
        return TransitMode.walk
    
    # Budget-conscious mode selection
    if budget_per_day < BUDGET_TIGHT:
        # Very tight budget - prioritize walking and cheapest public transit
        if distance_km <= WALK_MAX_DISTANCE and TransitMode.walk in available_modes:
            return TransitMode.walk
        elif TransitMode.metro in available_modes:
            return TransitMode.metro
        elif TransitMode.bus in available_modes:
            return TransitMode.bus
        else:
            return TransitMode.walk  # Fallback to walking even if far
            
    elif budget_per_day < BUDGET_MODERATE:
        # Moderate budget - balance convenience and cost
        if distance_km <= 1.0 and TransitMode.walk in available_modes:
            return TransitMode.walk
        elif distance_km > 5.0 and TransitMode.taxi in available_modes:
            return TransitMode.taxi  # Long distances justify taxi
        elif TransitMode.metro in available_modes:
            return TransitMode.metro
        elif TransitMode.bus in available_modes:
            return TransitMode.bus
        else:
            return TransitMode.walk
            
    else:
        # Generous budget - prioritize convenience
        if distance_km <= 0.8 and TransitMode.walk in available_modes:
            return TransitMode.walk  # Still walk for very short distances
        elif TransitMode.taxi in available_modes:
            return TransitMode.taxi  # Prefer convenience
        elif TransitMode.metro in available_modes:
            return TransitMode.metro
        elif TransitMode.bus in available_modes:
            return TransitMode.bus
        else:
            return TransitMode.walk


def _extract_location_from_rag(chunks: list[str], activity_name: str) -> Geo | None:
    """Extract geographic coordinates from RAG chunks for a specific activity.
    
    Args:
        chunks: RAG knowledge chunks 
        activity_name: Name of the activity to find location for
        
    Returns:
        Geographic coordinates if found, None otherwise
    """
    # This is a simplified implementation. In a production system,
    # you would use more sophisticated NLP to extract coordinates
    # or location names that could be geocoded.
    
    # For now, return None to use default locations
    # TODO: Implement actual location extraction from RAG chunks
    # This could involve:
    # 1. Searching for the activity name in chunks
    # 2. Finding nearby coordinate mentions
    # 3. Using NLP to extract addresses/landmarks
    # 4. Geocoding addresses to coordinates
    
    return None


def _get_activity_location(
    activity_ref: str, 
    city: str, 
    rag_chunks: list[str],
    activity_kind: ChoiceKind
) -> Geo:
    """Get the geographic location for an activity.
    
    Args:
        activity_ref: Reference ID for the activity
        city: City name for default coordinates
        rag_chunks: RAG knowledge chunks for location lookup
        activity_kind: Type of activity (flight, lodging, attraction, etc.)
        
    Returns:
        Geographic coordinates for the activity
    """
    # Try to extract location from RAG first
    rag_location = _extract_location_from_rag(rag_chunks, activity_ref)
    if rag_location:
        return rag_location
    
    # Fall back to city-appropriate defaults based on activity type
    city_lower = city.lower()
    base_coords = DEFAULT_CITY_COORDS.get(city_lower, Geo(lat=48.8566, lon=2.3522))
    
    # Different location strategies based on activity type
    import random
    
    if activity_kind == ChoiceKind.flight:
        # Flights happen at airports - use airport-specific offsets
        if city_lower == "rio de janeiro":
            # GIG airport location
            return Geo(lat=-22.8100, lon=-43.2505)
        elif city_lower == "paris":
            # CDG airport location  
            return Geo(lat=49.0097, lon=2.5479)
        else:
            # Generic airport offset from city center
            offset_lat = random.uniform(-0.05, 0.05)  # ~5km variation for airports
            offset_lon = random.uniform(-0.05, 0.05)
            return Geo(lat=base_coords.lat + offset_lat, lon=base_coords.lon + offset_lon)
    
    elif activity_kind == ChoiceKind.lodging:
        # Hotels are typically in city center or tourist areas
        offset_lat = random.uniform(-0.01, 0.01)  # ~1km variation for hotels
        offset_lon = random.uniform(-0.01, 0.01)
        return Geo(lat=base_coords.lat + offset_lat, lon=base_coords.lon + offset_lon)
    
    else:
        # Attractions can be more spread out
        offset_lat = random.uniform(-0.03, 0.03)  # ~3km variation for attractions
        offset_lon = random.uniform(-0.03, 0.03)
        return Geo(lat=base_coords.lat + offset_lat, lon=base_coords.lon + offset_lon)


def _create_transit_slot(
    from_location: Geo,
    to_location: Geo,
    transit_mode: TransitMode,
    start_time: time,
    duration_minutes: int,
    day_offset: int,
    slot_index: int
) -> Slot:
    """Create a transit slot between two locations.
    
    Args:
        from_location: Starting location
        to_location: Destination location  
        transit_mode: Mode of transportation
        start_time: When transit begins
        duration_minutes: How long transit takes
        day_offset: Day number in itinerary
        slot_index: Index within the day for unique reference
        
    Returns:
        Slot containing the transit choice
    """
    # Get the transit leg data
    transit_leg = get_transit_leg(from_location, to_location, [transit_mode])
    
    # Calculate end time
    end_time_dt = datetime.combine(datetime.today(), start_time) + timedelta(minutes=duration_minutes)
    end_time = end_time_dt.time()
    
    # Create transit choice
    transit_choice = Choice(
        kind=ChoiceKind.transit,
        option_ref=f"transit_{day_offset}_{slot_index}_{transit_mode.value}",
        features=ChoiceFeatures(
            cost_usd_cents=_get_transit_cost(transit_mode, duration_minutes),
            travel_seconds=duration_minutes * 60,
            indoor=None,  # Transit doesn't have indoor/outdoor classification
            themes=None,
        ),
        score=0.8,
        provenance=Provenance(
            source="planner_transit",
            ref_id=f"auto_transit_{day_offset}_{slot_index}",
            fetched_at=datetime.now(UTC),
        ),
    )
    
    return Slot(
        window=TimeWindow(start=start_time, end=end_time),
        choices=[transit_choice],
        locked=False,
    )


def _get_transit_cost(mode: TransitMode, duration_minutes: int) -> int:
    """Calculate transit cost based on mode and duration.
    
    Args:
        mode: Transportation mode
        duration_minutes: Duration in minutes
        
    Returns:
        Cost in USD cents
    """
    # Base costs per mode (in cents)
    base_costs = {
        TransitMode.walk: 0,          # Free
        TransitMode.metro: 200,       # $2 per ride
        TransitMode.bus: 150,         # $1.50 per ride
        TransitMode.taxi: 300,        # $3 base + distance
    }
    
    base_cost = base_costs.get(mode, 200)
    
    # For taxi, add distance-based cost
    if mode == TransitMode.taxi:
        # Rough estimate: $1.50 per minute for taxi
        distance_cost = int(duration_minutes * 150)
        return base_cost + distance_cost
    
    return base_cost


def inject_transit_between_activities(
    plan: PlanV1, 
    intent: IntentV1, 
    org_id: UUID
) -> tuple[PlanV1, list[str]]:
    """Inject transit slots between consecutive activities in a plan.
    
    This function enhances the travel plan by automatically adding transit
    events between every pair of consecutive activities. It uses the RAG
    system to determine activity locations and selects budget-appropriate
    transit modes.
    
    Args:
        plan: Original travel plan
        intent: User intent with budget and preferences
        org_id: Organization ID for RAG lookup
        
    Returns:
        Tuple of (enhanced plan with transit slots inserted, list of info messages)
    """
    # Import RAG retrieval locally to avoid circular imports
    try:
        from backend.app.graph.rag import retrieve_knowledge_for_destination
        rag_chunks = retrieve_knowledge_for_destination(org_id, intent.city, limit=30)
    except ImportError:
        # Fall back to empty chunks if RAG system is not available
        rag_chunks = []
    
    enhanced_days: list[DayPlan] = []
    messages: list[str] = []
    
    for day_plan in plan.days:
        if not day_plan.slots:
            enhanced_days.append(day_plan)
            continue
            
        # Group all slots (activities including lodging) for transit injection
        # We want transit between consecutive activities, including to/from lodging
        all_slots = [slot for slot in day_plan.slots if slot.choices]
        
        # Sort by start time 
        all_slots.sort(key=lambda s: s.window.start)
        
        # Build new slot list with transit between activities
        enhanced_slots: list[Slot] = []
        
        for i, slot in enumerate(all_slots):
            # Add the activity slot
            enhanced_slots.append(slot)
            
            # Add transit to next activity (if there is one and it's not the same type)
            if i < len(all_slots) - 1:
                current_slot = slot
                next_slot = all_slots[i + 1]
                
                # Skip if both are lodging (no need for lodging-to-lodging transit)
                current_kind = current_slot.choices[0].kind
                next_kind = next_slot.choices[0].kind
                if current_kind == ChoiceKind.lodging and next_kind == ChoiceKind.lodging:
                    continue
                
                # Get locations for current and next activities
                current_location = _get_activity_location(
                    current_slot.choices[0].option_ref,
                    intent.city,
                    rag_chunks,
                    current_kind
                )
                next_location = _get_activity_location(
                    next_slot.choices[0].option_ref,
                    intent.city, 
                    rag_chunks,
                    next_kind
                )
                
                # Calculate distance for transit mode selection
                distance_km = _calculate_distance(current_location, next_location)
                
                # Select appropriate transit mode based on budget
                transit_mode = _select_budget_aware_transit_mode(intent, distance_km)
                
                # Calculate transit timing
                # Transit starts after buffer time from when previous activity ends
                buffer_minutes = plan.assumptions.transit_buffer_minutes
                
                transit_start_dt = datetime.combine(datetime.today(), current_slot.window.end) + timedelta(minutes=buffer_minutes)
                transit_start = transit_start_dt.time()
                
                # Estimate transit duration based on mode and distance
                mode_speeds = {
                    TransitMode.walk: 5,      # 5 km/h
                    TransitMode.metro: 30,    # 30 km/h
                    TransitMode.bus: 20,      # 20 km/h  
                    TransitMode.taxi: 25,     # 25 km/h
                }
                
                speed_kmh = mode_speeds.get(transit_mode, 20)
                transit_duration = max(
                    int((distance_km / speed_kmh) * 60),  # Convert to minutes
                    5  # Minimum 5 minutes
                )
                
                # Ensure transit doesn't conflict with next activity
                # Transit must end with buffer before next activity starts
                max_available_time = _time_diff_minutes(transit_start, next_slot.window.start) - buffer_minutes
                
                if max_available_time > 5:  # Need at least 5 minutes for transit
                    # Adjust transit duration to fit available time
                    if transit_duration > max_available_time:
                        transit_duration = max_available_time
                        # If we need to shorten transit, prefer faster modes
                        if transit_duration < 15 and transit_mode == TransitMode.walk and distance_km > 1.0:
                            # Switch to faster transit for longer distances when time is tight
                            transit_mode = _select_budget_aware_transit_mode(
                                intent, distance_km, [TransitMode.metro, TransitMode.bus, TransitMode.taxi]
                            )
                            speed_kmh = mode_speeds.get(transit_mode, 20)
                            transit_duration = max(
                                int((distance_km / speed_kmh) * 60),
                                5
                            )
                    
                    # Create and add transit slot
                    transit_slot = _create_transit_slot(
                        current_location,
                        next_location,
                        transit_mode,
                        transit_start,
                        transit_duration,
                        day_offset=(plan.days.index(day_plan)),
                        slot_index=len(enhanced_slots)
                    )
                    
                    enhanced_slots.append(transit_slot)
                    messages.append(f"Added {transit_mode.value} transit between activities (${_get_transit_cost(transit_mode, transit_duration)/100:.2f})")
                else:
                    # Not enough time for transit - activities are too close together
                    messages.append(
                        f"Skipped transit - insufficient time between activities"
                    )
        
        # Create enhanced day plan
        enhanced_day = DayPlan(
            date=day_plan.date,
            slots=enhanced_slots
        )
        enhanced_days.append(enhanced_day)
    
    # Return enhanced plan and messages
    enhanced_plan = PlanV1(
        days=enhanced_days,
        assumptions=plan.assumptions,
        rng_seed=plan.rng_seed
    )
    
    return enhanced_plan, messages


def _calculate_distance(geo1: Geo, geo2: Geo) -> float:
    """Calculate haversine distance between two points.
    
    Args:
        geo1: First coordinate
        geo2: Second coordinate
        
    Returns:
        Distance in kilometers
    """
    import math
    
    # Earth radius in km
    R = 6371.0

    # Convert to radians
    lat1 = math.radians(geo1.lat)
    lon1 = math.radians(geo1.lon)
    lat2 = math.radians(geo2.lat)
    lon2 = math.radians(geo2.lon)

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance


def _time_diff_minutes(start_time: time, end_time: time) -> int:
    """Calculate difference between two times in minutes.
    
    Args:
        start_time: Starting time
        end_time: Ending time
        
    Returns:
        Difference in minutes
    """
    start_dt = datetime.combine(datetime.today(), start_time)
    end_dt = datetime.combine(datetime.today(), end_time)
    
    # Handle day boundary crossing
    if end_dt < start_dt:
        end_dt += timedelta(days=1)
    
    diff = end_dt - start_dt
    return int(diff.total_seconds() / 60)
