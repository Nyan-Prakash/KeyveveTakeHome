"""LangGraph nodes implementing PR6 planner and selector logic."""

import asyncio
import json
import random
import re
from datetime import UTC, datetime, time, timedelta

from openai import OpenAI

from backend.app.adapters.weather import get_weather_adapter
from backend.app.config import get_openai_api_key
from backend.app.models.common import ChoiceKind, Geo, Provenance, TimeWindow, TransitMode, compute_response_digest
from backend.app.models.tool_results import FlightOption, WeatherDay
from backend.app.models.itinerary import (
    Activity,
    Citation,
    CostBreakdown,
    DayItinerary,
    Decision,
    ItineraryV1,
)
from backend.app.models.plan import (
    Assumptions,
    Choice,
    ChoiceFeatures,
    DayPlan,
    PlanV1,
    Slot,
)
from backend.app.planning import build_candidate_plans, score_branches
from backend.app.planning.budget_utils import (
    BASELINE_DAILY_COST_CENTS,
    build_budget_profile,
    preferred_flight_tiers,
    preferred_lodging_tiers,
    target_flight_cost,
    target_lodging_cost,
)
from backend.app.planning.types import BranchFeatures
from backend.app.planning.simple_transit import simple_inject_transit

from .state import OrchestratorState


def _extract_venue_info_from_rag(chunks: list[str]) -> dict[int, dict[str, any]]:
    """Extract venue information from RAG chunks using LLM.

    Parses markdown-formatted RAG chunks to identify attraction names, types,
    costs, and characteristics.

    Args:
        chunks: List of knowledge chunk texts (markdown formatted)

    Returns:
        Dict mapping index to venue info dict with keys: name, type, indoor, cost_usd_cents
    """
    if not chunks:
        return {}

    # Combine chunks for LLM analysis (limit to prevent token overflow)
    combined_text = "\n\n".join(chunks[:20])  # Limit to first 20 chunks

    # Create prompt for LLM extraction
    prompt = f"""Extract attraction information from this travel guide text. Look for attractions, museums, parks, landmarks, etc.

For each attraction, extract:
- name: The full name of the attraction
- type: Category (museum, park, garden, palace, temple, restaurant, market, theater, beach, mountain, or attraction)
- indoor: Whether it's primarily indoor (true), outdoor (false), or unknown (null)
- price_usd: Price in USD (extract from text like "Attraction Name: 180" or "Attraction Name**: 400"). Return the exact number found.
Text:
{combined_text}

Return a JSON array of attractions. Example format:
[
  {{"name": "Prado Museum", "type": "museum", "indoor": true, "price_usd": 15.0}},
  {{"name": "Retiro Park", "type": "park", "indoor": false, "price_usd": null}}
]

IMPORTANT: Only extract entries that are clearly identifiable attractions with proper names, not general categories or descriptions."""

    max_retries = 2
    for attempt in range(max_retries):
        try:
            client = OpenAI(api_key=get_openai_api_key())

            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Use faster, cheaper model for extraction
                messages=[
                    {"role": "system", "content": "You are a precise data extractor. Return only valid JSON arrays."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,  # Deterministic extraction
                max_tokens=2000
            )

            content = response.choices[0].message.content
            # Extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            attractions = json.loads(content)

            # Validate that result is a list
            if not isinstance(attractions, list):
                raise ValueError(f"Expected list, got {type(attractions)}")

            # Convert to the expected format
            venue_info_map = {}
            indoor_by_type = {
                "temple": None,
                "garden": False,
                "museum": True,
                "restaurant": True,
                "market": None,
                "theater": True,
                "castle": None,
                "palace": None,
                "beach": False,
                "mountain": False,
                "park": False,
            }

            for idx, attr in enumerate(attractions):
                # Validate required fields
                if not isinstance(attr, dict):
                    continue
                if not attr.get("name"):
                    continue

                venue_type = attr.get("type", "attraction")
                indoor = attr.get("indoor")
                if indoor is None:
                    indoor = indoor_by_type.get(venue_type)

                # Convert cost to cents
                cost_usd_cents = None
                if attr.get("price_usd") is not None:
                    try:
                        cost_usd_cents = int(float(attr["price_usd"]) * 100)
                    except (ValueError, TypeError):
                        pass

                venue_info_map[idx] = {
                    "name": attr.get("name"),
                    "type": venue_type,
                    "indoor": indoor,
                    "cost_usd_cents": cost_usd_cents,
                }

            # Success - return results
            if venue_info_map:
                return venue_info_map
            elif attempt < max_retries - 1:
                print(f"Warning: LLM extraction returned empty results. Retrying ({attempt + 1}/{max_retries})...")
                continue
            else:
                print("Warning: LLM extraction returned no valid venues after retries.")
                return {}

        except json.JSONDecodeError as e:
            print(f"Warning: JSON parsing failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                continue
        except Exception as e:
            print(f"Warning: LLM extraction failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                continue

    # All retries exhausted - return empty dict
    print("Error: All RAG extraction attempts failed. Using empty venue map.")
    return {}

    # Log extraction results
    print("\n" + "="*60)
    print("RAG ATTRACTIONS/VENUES EXTRACTION RESULTS")
    print("="*60)
    print(f"Processed {len(chunks[:20])} RAG chunks")
    print(f"Extracted {len(venue_info_map)} attractions:")
    for idx, venue in venue_info_map.items():
        print(f"\n  Attraction {idx}:")
        print(f"    Name: {venue.get('name')}")
        print(f"    Type: {venue.get('type')}")
        print(f"    Indoor: {venue.get('indoor')}")
        cost = venue.get('cost_usd_cents')
        if cost:
            print(f"    Cost: ${cost / 100:.2f}")
        else:
            print(f"    Cost: Free/Unknown")
    print("="*60 + "\n")

    return venue_info_map


def _extract_flight_info_from_rag(chunks: list[str]) -> dict[int, dict[str, any]]:
    """Extract flight information from RAG chunks using LLM.

    Parses markdown-formatted RAG chunks to identify airline names, routes,
    pricing, and flight details.

    Args:
        chunks: List of knowledge chunk texts (markdown formatted)

    Returns:
        Dict mapping index to flight info dict with keys: airline, route, price_usd_cents, duration_hours
    """
    if not chunks:
        return {}

    # Combine chunks for LLM analysis (limit to prevent token overflow)
    combined_text = "\n\n".join(chunks[:20])  # Limit to first 20 chunks

    # Create prompt for LLM extraction
    prompt = f"""Extract flight and airline information from this travel guide text. Look for airlines, flight routes, pricing, and travel times.

For each flight/airline mentioned, extract:
- airline: The airline name (e.g., "LATAM", "American Airlines", "TAP Air Portugal")
- route: Flight route if specified (e.g., "JFK-GIG", "LAX-MAD")
- origin_airport: Origin airport code (e.g., "JFK", "LAX") if mentioned
- dest_airport: Destination airport code (e.g., "GIG", "MAD") if mentioned
- price_usd: Flight price in USD if mentioned (extract numbers like "$450", "$1,200"). If a range like "$400-600", use the lower value.

Text:
{combined_text}

Return a JSON array of flight information. Example format:
[
  {{"airline": "LATAM", "route": "JFK-GIG", "origin_airport": "JFK", "dest_airport": "GIG", "price_usd": 610.0, "duration_hours": 9.5}},
  {{"airline": "American Airlines", "route": "LAX-MAD", "origin_airport": "LAX", "dest_airport": "MAD", "price_usd": null, "duration_hours": 11.0}}
]

IMPORTANT: Only extract entries that are clearly identifiable airlines or flight information, not general travel descriptions."""

    try:
        client = OpenAI(api_key=get_openai_api_key())

        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Use faster, cheaper model for extraction
            messages=[
                {"role": "system", "content": "You are a precise data extractor. Return only valid JSON arrays."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,  # Deterministic extraction
            max_tokens=2000
        )

        content = response.choices[0].message.content
        # Extract JSON from markdown code blocks if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        flight_options = json.loads(content)

        # Convert to the expected format
        flight_info_map = {}
        for idx, flight in enumerate(flight_options):
            # Convert price to cents
            price_usd_cents = None
            if flight.get("price_usd") is not None:
                price_usd_cents = int(flight["price_usd"] * 100)

            flight_info_map[idx] = {
                "airline": flight.get("airline"),
                "route": flight.get("route"),
                "origin_airport": flight.get("origin_airport"),
                "dest_airport": flight.get("dest_airport"),
                "price_usd_cents": price_usd_cents,
                "duration_hours": flight.get("duration_hours"),
            }

        return flight_info_map

    except Exception as e:
        # Fallback to empty dict if LLM extraction fails
        print(f"Warning: Flight extraction failed: {e}. Using empty flight map.")
        return {}

    # Log extraction results
    print("\n" + "="*60)
    print("RAG FLIGHT EXTRACTION RESULTS")
    print("="*60)
    print(f"Processed {len(chunks[:20])} RAG chunks")
    print(f"Extracted {len(flight_info_map)} flights:")
    for idx, flight in flight_info_map.items():
        print(f"\n  Flight {idx}:")
        print(f"    Airline: {flight.get('airline')}")
        print(f"    Route: {flight.get('route')}")
        print(f"    Origin: {flight.get('origin_airport')}")
        print(f"    Dest: {flight.get('dest_airport')}")
        print(f"    Price: ${flight.get('price_usd_cents', 0) / 100:.2f}")
        print(f"    Duration: {flight.get('duration_hours')} hours")
    print("="*60 + "\n")

    return flight_info_map


def _match_rag_attraction_to_choice(
    choice: Choice,
    rag_attractions: list,
    used_attraction_ids: set[str],
) -> "Attraction | None":
    """Match a plan choice to the best RAG attraction using semantic scoring.

    Args:
        choice: The planner's Choice object with estimated cost and themes
        rag_attractions: List of Attraction objects from RAG database
        used_attraction_ids: Set of attraction IDs already assigned (to avoid duplicates)

    Returns:
        Best matching Attraction or None if no good match exists
    """
    if not rag_attractions or choice.kind != ChoiceKind.attraction:
        return None

    # If choice.option_ref already points to a RAG attraction ID, use it directly
    matching_attr = next(
        (attr for attr in rag_attractions if attr.id == choice.option_ref and attr.id not in used_attraction_ids),
        None
    )
    if matching_attr:
        return matching_attr

    # Otherwise, score available attractions
    target_cost = choice.features.cost_usd_cents
    target_indoor = choice.features.indoor
    target_themes = set(choice.features.themes or [])

    best_score = -1
    best_attraction = None

    for attraction in rag_attractions:
        # Skip already-used attractions
        if attraction.id in used_attraction_ids:
            continue

        score = 0.0

        # Cost compatibility (40% weight): Prefer attractions within ±30% of target
        if attraction.est_price_usd_cents is not None and target_cost > 0:
            cost_diff = abs(attraction.est_price_usd_cents - target_cost) / target_cost
            if cost_diff < 0.3:
                score += 0.4 * (1.0 - cost_diff / 0.3)
            elif cost_diff < 0.6:
                score += 0.2 * (1.0 - (cost_diff - 0.3) / 0.3)
        elif attraction.est_price_usd_cents == 0 and target_cost == 0:
            score += 0.4  # Both free

        # Indoor/outdoor match (20% weight)
        if target_indoor is not None and attraction.indoor is not None:
            if attraction.indoor == target_indoor:
                score += 0.2

        # Theme overlap (20% weight): Match attraction type to user themes
        if attraction.venue_type and target_themes:
            venue_type_lower = attraction.venue_type.lower()
            theme_matches = sum(
                1 for theme in target_themes
                if theme.lower() in venue_type_lower or venue_type_lower in theme.lower()
            )
            if theme_matches > 0:
                score += 0.2 * min(theme_matches / len(target_themes), 1.0)

        # Availability bonus (20% weight): Prefer attractions not yet used
        score += 0.2

        if score > best_score:
            best_score = score
            best_attraction = attraction

    # Return best match only if score is reasonable (>0.3)
    if best_score > 0.3:
        return best_attraction

    return None


def _normalize_transit_mode(mode: str | None) -> str | None:
    """Normalize transit mode strings from RAG to TransitMode enum values."""
    if not mode:
        return None

    normalized = mode.strip().lower()
    normalized = normalized.replace("-", " ")

    alias_map = {
        "subway": "metro",
        "underground": "metro",
        "tube": "metro",
        "tram": "metro",
        "light rail": "metro",
        "u bahn": "metro",
        "metro line": "metro",
        "rail": "train",
        "s bahn": "train",
        "railway": "train",
        "rideshare": "taxi",
        "uber": "taxi",
        "cab": "taxi",
    }
    normalized = alias_map.get(normalized, normalized)

    allowed = {"walk", "metro", "bus", "taxi", "train"}
    return normalized if normalized in allowed else None


def _extract_transit_info_from_rag(chunks: list[str]) -> dict[int, dict[str, any]]:
    """Extract transit information from RAG chunks using LLM.

    Parses markdown-formatted RAG chunks to identify transit modes, routes,
    neighborhoods served, and pricing.

    Args:
        chunks: List of knowledge chunk texts (markdown formatted)

    Returns:
        Dict mapping index to transit info dict with keys: mode, route_name, neighborhoods, price_usd_cents, duration_minutes
    """
    if not chunks:
        return {}

    # Combine chunks for LLM analysis (limit to prevent token overflow)
    combined_text = "\n\n".join(chunks[:20])  # Limit to first 20 chunks

    # Create prompt for LLM extraction
    prompt = f"""Extract public transportation information from this travel guide text. Look for metro lines, bus routes, taxi services, and transit details.

For each transit option mentioned, extract:
- mode: Transportation mode (metro, bus, taxi, walk, or train)
- route_name: Specific route name or line (e.g., "Line 1", "Metro Red Line", "Bus 150")
- neighborhoods: List of neighborhoods or areas served by this route
- price_usd: Transit cost in USD if mentioned (extract from text like "$2.50", "€1.50"). For monthly passes, divide by 30.
- duration_minutes: Typical journey time in minutes if mentioned

Text:
{combined_text}

Return a JSON array of transit options. Example format:
[
  {{"mode": "metro", "route_name": "Line 1", "neighborhoods": ["Downtown", "Copacabana"], "price_usd": 1.25, "duration_minutes": 15}},
  {{"mode": "bus", "route_name": "Bus 474", "neighborhoods": ["Ipanema", "Centro"], "price_usd": 1.00, "duration_minutes": 25}}
]

IMPORTANT: Only extract entries that are clearly identifiable transit routes or services, not general descriptions."""

    try:
        client = OpenAI(api_key=get_openai_api_key())

        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Use faster, cheaper model for extraction
            messages=[
                {"role": "system", "content": "You are a precise data extractor. Return only valid JSON arrays."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,  # Deterministic extraction
            max_tokens=2000
        )

        content = response.choices[0].message.content
        # Extract JSON from markdown code blocks if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        transit_options = json.loads(content)

        # Convert to the expected format
        transit_info_map = {}
        for idx, transit in enumerate(transit_options):
            # Convert price to cents
            price_usd_cents = None
            if transit.get("price_usd") is not None:
                price_usd_cents = int(transit["price_usd"] * 100)

            # Convert duration to seconds
            duration_seconds = None
            if transit.get("duration_minutes") is not None:
                duration_seconds = int(transit["duration_minutes"] * 60)

            # Normalize mode strings to supported enum values
            normalized_mode = _normalize_transit_mode(transit.get("mode"))

            transit_info_map[idx] = {
                "mode": normalized_mode or transit.get("mode"),
                "route_name": transit.get("route_name"),
                "neighborhoods": transit.get("neighborhoods", []),
                "price_usd_cents": price_usd_cents,
                "duration_seconds": duration_seconds,
            }

        return transit_info_map

    except Exception as e:
        # Fallback to empty dict if LLM extraction fails
        print(f"Warning: Transit extraction failed: {e}. Using empty transit map.")
        return {}

    # Log extraction results
    print("\n" + "="*60)
    print("RAG TRANSIT EXTRACTION RESULTS")
    print("="*60)
    print(f"Processed {len(chunks[:20])} RAG chunks")
    print(f"Extracted {len(transit_info_map)} transit options:")
    for idx, transit in transit_info_map.items():
        print(f"\n  Transit {idx}:")
        print(f"    Route: {transit.get('route_name')}")
        print(f"    Mode: {transit.get('mode')}")
        neighborhoods = transit.get('neighborhoods', [])
        if neighborhoods:
            print(f"    Areas: {', '.join(neighborhoods[:3])}")
        cost = transit.get('price_usd_cents')
        if cost:
            print(f"    Cost: ${cost / 100:.2f}")
        duration = transit.get('duration_seconds')
        if duration:
            print(f"    Duration: ~{duration // 60} min")
    print("="*60 + "\n")

    return transit_info_map


def _extract_lodging_info_from_rag(chunks: list[str]) -> dict[int, dict[str, any]]:
    """Extract lodging information from RAG chunks using LLM.

    Parses markdown-formatted RAG chunks to identify hotel names, tiers,
    and amenities.

    Args:
        chunks: List of knowledge chunk texts (markdown formatted)

    Returns:
        Dict mapping index to lodging info dict with keys: name, tier, amenities, price_per_night_usd_cents
    """
    if not chunks:
        return {}

    # Combine chunks for LLM analysis (limit to prevent token overflow)
    combined_text = "\n\n".join(chunks[:20])  # Limit to first 20 chunks

    # Create prompt for LLM extraction
    prompt = f"""Extract hotel/lodging information from this travel guide text. Look for hotels, hostels, accommodations, etc.

For each lodging option, extract:
- name: The full name of the hotel/lodging
- tier: Category (budget, mid, luxury, or boutique)
- amenities: List of notable features/amenities mentioned
- neighborhood: Location/district if mentioned
- price_usd: Price per night in USD (extract from text like "Hotel Name: 180" or "Hotel Name**: 400"). Return the exact number found.

Text:
{combined_text}

Return a JSON array of lodging options. Example format:
[
  {{"name": "Hotel Villa Magna", "tier": "luxury", "amenities": ["Rosewood", "Salamanca district"], "neighborhood": "Salamanca", "price_usd": 400}},
  {{"name": "The Hat Madrid", "tier": "budget", "amenities": ["hostel", "rooftop terrace"], "neighborhood": "city center", "price_usd": 65}}
]

IMPORTANT:
- Only extract entries that are clearly identifiable hotels/lodging with proper names
- Categorize tier based on context (luxury hotels, mid-range, budget-friendly, boutique)
- Extract price as the number that appears after the colon (e.g., "Hotel Name: 180" → 180)
- Do NOT invent information not in the text"""

    try:
        client = OpenAI(api_key=get_openai_api_key())

        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Use faster, cheaper model for extraction
            messages=[
                {"role": "system", "content": "You are a precise data extractor. Return only valid JSON arrays."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,  # Deterministic extraction
            max_tokens=2000
        )

        content = response.choices[0].message.content
        # Extract JSON from markdown code blocks if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        lodging_options = json.loads(content)

        # Convert to the expected format using RAG-extracted prices
        lodging_info_map = {}
        tier_pricing = {
            "budget": (6000, 9000),      # $60-90/night (fallback only)
            "mid": (12000, 18000),       # $120-180/night (fallback only)
            "luxury": (30000, 40000),    # $300-400/night (fallback only)
            "boutique": (15000, 25000),  # $150-250/night (fallback only)
        }

        for idx, lodging in enumerate(lodging_options):
            tier = lodging.get("tier", "mid").lower()

            # Use RAG-extracted price if available, otherwise estimate from tier
            if lodging.get("price_usd") is not None:
                # Convert extracted price to cents
                price_cents = int(lodging["price_usd"] * 100)
            elif tier in tier_pricing:
                # Fallback: estimate based on tier
                min_price, max_price = tier_pricing[tier]
                price_cents = (min_price + max_price) // 2
            else:
                # Default fallback
                price_cents = 15000  # $150/night

            lodging_info_map[idx] = {
                "name": lodging.get("name"),
                "tier": tier,
                "amenities": lodging.get("amenities", []),
                "neighborhood": lodging.get("neighborhood"),
                "price_per_night_usd_cents": price_cents,
            }

        return lodging_info_map

    except Exception as e:
        # Fallback to empty dict if LLM extraction fails
        print(f"Warning: Lodging extraction failed: {e}. Using empty lodging map.")
        return {}

    # Log extraction results
    print("\n" + "="*60)
    print("RAG LODGING EXTRACTION RESULTS")
    print("="*60)
    print(f"Processed {len(chunks[:20])} RAG chunks")
    print(f"Extracted {len(lodging_info_map)} lodging options:")
    for idx, lodging in lodging_info_map.items():
        print(f"\n  Lodging {idx}:")
        print(f"    Name: {lodging.get('name')}")
        print(f"    Tier: {lodging.get('tier')}")
        print(f"    Neighborhood: {lodging.get('neighborhood')}")
        print(f"    Price: ${lodging.get('price_per_night_usd_cents', 0) / 100:.2f}/night")
        amenities = lodging.get('amenities', [])
        if amenities:
            print(f"    Amenities: {', '.join(amenities[:3])}")
    print("="*60 + "\n")

    return lodging_info_map


def _await_sync(coro):
    """Run an async coroutine from synchronous context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()

    return asyncio.run(coro)


def _fallback_weather_day(city: str | None, target_date):
    """Create deterministic fixture weather when MCP/unified adapter is unavailable."""
    label = city or "Unknown"
    return WeatherDay(
        forecast_date=target_date,
        precip_prob=0.15,
        wind_kmh=15.0,
        temp_c_high=22.0,
        temp_c_low=12.0,
        city=label,
        temperature_celsius=18.0,
        conditions="clear",
        precipitation_mm=0.0,
        humidity_percent=55.0,
        wind_speed_ms=4.0,
        source="fixture",
        provenance=Provenance(
            source="fixture",
            ref_id=f"fixture:weather:{label}:{target_date.isoformat()}",
            source_url="fixture://weather",
            fetched_at=datetime.now(UTC),
            cache_hit=False,
            response_digest=None,
        ),
    )


def intent_node(state: OrchestratorState) -> OrchestratorState:
    """Process and normalize the user intent.

    In PR4, this is a simple pass-through that logs the intent.
    Real intent processing will be added in later PRs.
    """
    state.messages.append("Processing intent...")
    state.last_event_ts = datetime.now(UTC)
    return state


def planner_node(state: OrchestratorState) -> OrchestratorState:
    """Generate candidate plans based on the intent using PR6 planner.

    Replaces the PR4 stub implementation with real planning logic
    that generates 1-4 candidate plans with bounded fan-out.
    Now uses RAG attractions when available to prevent hallucinations.
    """
    state.messages.append("Planning itinerary...")
    state.last_event_ts = datetime.now(UTC)

    # Generate candidate plans using PR6 logic with RAG attractions
    candidate_plans = build_candidate_plans(state.intent, state.rag_attractions)

    # Inject transit between activities for all candidate plans
    state.messages.append("Injecting transit between activities...")
    enhanced_plans = []
    for plan in candidate_plans:
        try:
            enhanced_plan = simple_inject_transit(plan, state.intent)
            enhanced_plans.append(enhanced_plan)
            
            # Count added transit slots
            original_slots = sum(len(day.slots) for day in plan.days)
            enhanced_slots = sum(len(day.slots) for day in enhanced_plan.days)
            transit_added = enhanced_slots - original_slots
            state.messages.append(f"Added {transit_added} transit slots to plan")
            
        except Exception as e:
            # Fall back to original plan if transit injection fails
            state.messages.append(f"Warning: Transit injection failed, using basic plan: {e}")
            enhanced_plans.append(plan)

    # For now, take the first plan as our working plan
    # The selector will choose between alternatives in the next step
    if enhanced_plans:
        state.plan = enhanced_plans[0]
        state.messages.append(f"Generated {len(enhanced_plans)} candidate plans with transit")
        state.messages.append(f"Selected plan with {len(state.plan.days)} days")

        # Store all enhanced candidates in state for selector to use
        state.candidate_plans = list(enhanced_plans)
    else:
        state.messages.append("Failed to generate any candidate plans")
        # Fall back to stub plan
        rng = random.Random(state.seed)
        start_date = state.intent.date_window.start
        days: list[DayPlan] = []

        for day_offset in range(5):
            current_date = start_date + timedelta(days=day_offset)

            # Create 2 slots per day: morning and afternoon
            slots = [
                Slot(
                    window=TimeWindow(start=time(9, 0), end=time(12, 0)),
                    choices=[
                        Choice(
                            kind=ChoiceKind.attraction,
                            option_ref=f"fallback_attraction_{day_offset}_morning",
                            features=ChoiceFeatures(
                                cost_usd_cents=rng.randint(1000, 5000),
                                travel_seconds=1800,
                                indoor=rng.choice([True, False, None]),
                                themes=["culture", "art"],
                            ),
                            score=0.85,
                            provenance=Provenance(
                                source="fallback",
                                fetched_at=datetime.now(UTC),
                                cache_hit=False,
                            ),
                        )
                    ],
                    locked=False,
                ),
                Slot(
                    window=TimeWindow(start=time(14, 0), end=time(18, 0)),
                    choices=[
                        Choice(
                            kind=ChoiceKind.attraction,
                            option_ref=f"fallback_attraction_{day_offset}_afternoon",
                            features=ChoiceFeatures(
                                cost_usd_cents=rng.randint(1000, 5000),
                                travel_seconds=1800,
                                indoor=rng.choice([True, False, None]),
                                themes=["food", "nature"],
                            ),
                            score=0.80,
                            provenance=Provenance(
                                source="fallback",
                                fetched_at=datetime.now(UTC),
                                cache_hit=False,
                            ),
                        )
                    ],
                    locked=False,
                ),
            ]

            days.append(DayPlan(date=current_date, slots=slots))

        state.plan = PlanV1(
            days=days,
            assumptions=Assumptions(
                fx_rate_usd_eur=0.92,
                daily_spend_est_cents=10000,
                transit_buffer_minutes=15,
                airport_buffer_minutes=120,
            ),
            rng_seed=state.seed,
        )
        state.candidate_plans = [state.plan]

    state.last_event_ts = datetime.now(UTC)
    return state


def selector_node(state: OrchestratorState) -> OrchestratorState:
    """Select the best plan from candidates using PR6 selector logic.

    Uses feature-based scoring with frozen statistics to rank plans
    and logs score vectors for chosen + top 2 discarded plans.
    """
    state.messages.append("Selecting best plan...")
    state.last_event_ts = datetime.now(UTC)

    # Extract features from all candidate plans if available
    if hasattr(state, "candidate_plans") and state.candidate_plans:
        candidates = state.candidate_plans
    elif state.plan:
        candidates = [state.plan]
    else:
        state.messages.append("No plans available for selection")
        return state

    # Build BranchFeatures for each candidate plan
    branch_features: list[BranchFeatures] = []
    for plan in candidates:
        features = []
        for day in plan.days:
            for slot in day.slots:
                for choice in slot.choices:
                    features.append(choice.features)

        branch_features.append(BranchFeatures(plan=plan, features=features))

    # Score branches using PR6 selector with budget-aware scoring
    scored_plans = score_branches(branch_features, state.intent)

    if scored_plans:
        # Select the highest-scored plan
        best_plan = scored_plans[0]
        state.plan = best_plan.plan
        state.messages.append(f"Selected plan with score {best_plan.score:.3f}")
        state.messages.append(f"Evaluated {len(scored_plans)} alternatives")
    else:
        state.messages.append("No valid scored plans available")

    state.last_event_ts = datetime.now(UTC)
    return state


def rag_node(state: OrchestratorState) -> OrchestratorState:
    """Retrieve relevant knowledge chunks from RAG for the destination.

    This node queries the embedding table for knowledge chunks related to
    the destination city, parses attractions, and makes them available to the planner.
    Uses semantic search with targeted queries for different types of information.
    """
    from backend.app.graph.rag import retrieve_knowledge_for_destination
    from backend.app.models.common import Geo, Provenance

    state.messages.append("Retrieving local knowledge...")
    state.last_event_ts = datetime.now(UTC)

    # Retrieve knowledge chunks for the destination city
    city = state.intent.city
    org_id = state.org_id

    # Use semantic search with a focused query for travel planning
    # This helps retrieve the most relevant chunks about attractions, lodging, transit, etc.
    query = (
        f"popular tourist attractions museums hotels restaurants public transportation "
        f"getting around travel guide {city}"
    )

    chunks = retrieve_knowledge_for_destination(
        org_id=org_id,
        city=city,
        limit=20,
        query=query,  # Use semantic search
    )

    if chunks:
        state.rag_chunks = chunks
        state.messages.append(f"Retrieved {len(chunks)} knowledge chunks for {city}")
        state.tool_call_counts["rag"] = len(chunks)

        # Parse attractions from RAG chunks immediately for planner use
        venue_info_map = _extract_venue_info_from_rag(chunks)

        if venue_info_map:
            # Convert parsed venue data to Attraction objects
            from backend.app.models.tool_results import Attraction

            for idx, venue_info in venue_info_map.items():
                # Only include attractions with valid names
                if not venue_info.get("name"):
                    continue

                attraction = Attraction(
                    id=f"rag_attraction_{idx}",
                    name=venue_info["name"],
                    venue_type=venue_info.get("type", "attraction"),
                    indoor=venue_info.get("indoor"),
                    kid_friendly=False,  # Not extractable from RAG currently
                    opening_hours={
                        "0": [], "1": [], "2": [], "3": [], "4": [], "5": [], "6": []
                    },
                    location=Geo(lat=48.8566, lon=2.3522),  # Default, will be enriched later
                    est_price_usd_cents=venue_info.get("cost_usd_cents"),
                    provenance=Provenance(
                        source="rag",
                        ref_id=f"rag:attraction:{idx}",
                        source_url="rag://attractions",
                        fetched_at=datetime.now(UTC),
                        cache_hit=False,
                        response_digest=None,
                    ),
                )
                state.rag_attractions.append(attraction)

            state.messages.append(f"Parsed {len(state.rag_attractions)} attractions from RAG")

            # Validate sufficient attractions for trip planning
            # Estimate number of attraction slots needed: ~2 per day
            trip_days = (state.intent.date_window.end - state.intent.date_window.start).days
            estimated_attraction_slots = trip_days * 2

            if len(state.rag_attractions) < estimated_attraction_slots // 2:
                state.messages.append(
                    f"⚠️  WARNING: Only {len(state.rag_attractions)} attractions found, "
                    f"but trip needs ~{estimated_attraction_slots} slots. "
                    "Some attractions may be repeated or synthetic fallbacks may be used."
                )
        else:
            state.messages.append("Warning: Failed to extract attractions from RAG chunks")
            state.rag_attractions = []
    else:
        state.messages.append(f"No local knowledge found for {city}")
        state.rag_chunks = []
        state.rag_attractions = []

    # CRITICAL: Validate that we have SOME attractions from RAG
    # If empty, the planner will create abstract slots that may fail validation
    if not state.rag_attractions:
        state.messages.append(
            f"⚠️  CRITICAL: No attractions extracted from RAG for {city}. "
            "Planner will create abstract slots that may require manual fallback."
        )

    state.last_event_ts = datetime.now(UTC)
    return state


def tool_exec_node(state: OrchestratorState) -> OrchestratorState:
    """Execute tools to gather data.

    In PR4, this calls fake tools that return static data.
    Real tool execution will use the PR3 ToolExecutor in later PRs.

    For PR9, we populate state dictionaries and track realistic tool call counts
    to enable UI right-rail metrics display.
    """
    from backend.app.models.tool_results import Attraction, WeatherDay

    state.messages.append("Executing tools...")
    state.last_event_ts = datetime.now(UTC)

    if not state.plan:
        return state

    budget_profile = build_budget_profile(
        state.intent,
        baseline_per_day_cents=BASELINE_DAILY_COST_CENTS,
    )

    # Fetch real weather data via MCP/adapter
    weather_adapter = get_weather_adapter()
    weather_calls = 0

    for day_plan in state.plan.days:
        city = state.intent.city or "Unknown"
        try:
            if weather_adapter and city:
                weather_day = _await_sync(
                    weather_adapter.get_weather(city, day_plan.date)
                )
                weather_calls += 1
            else:
                raise RuntimeError("Weather adapter not available")
        except Exception as exc:  # noqa: BLE001
            state.messages.append(
                f"Weather lookup failed for {day_plan.date.isoformat()}, using fixture: {exc}"
            )
            weather_day = _fallback_weather_day(city, day_plan.date)

        # Ensure mandatory fields present for verifiers
        if weather_day.forecast_date != day_plan.date:
            weather_day.forecast_date = day_plan.date
        if weather_day.wind_kmh == 0 and weather_day.wind_speed_ms is not None:
            weather_day.wind_kmh = round(weather_day.wind_speed_ms * 3.6, 1)
        if weather_day.temp_c_high == 0 and weather_day.temperature_celsius is not None:
            weather_day.temp_c_high = weather_day.temperature_celsius
        if weather_day.temp_c_low == 0 and weather_day.temperature_celsius is not None:
            weather_day.temp_c_low = weather_day.temperature_celsius - 3

        state.weather_by_date[day_plan.date] = weather_day

    if state.plan.days:
        state.tool_call_counts["weather"] = (
            weather_calls if weather_calls else len(state.plan.days)
        )

    # Fetch real flight data using adapter with CONTINUOUS budget targeting
    from backend.app.adapters.flights import get_flights
    from backend.app.planning.budget_utils import compute_price_range

    # Calculate continuous target cost and price range for flights
    flight_target_cost = target_flight_cost(budget_profile)
    flight_price_range = compute_price_range(flight_target_cost, tolerance=0.3)

    flight_options = get_flights(
        origin=state.intent.airports[0] if state.intent.airports else "JFK",
        dest=state.intent.city or "Rio de Janeiro",  # Provide fallback destination
        date_window=(state.intent.date_window.start, state.intent.date_window.end),
        avoid_overnight=state.intent.prefs.avoid_overnight if state.intent.prefs else False,
        budget_usd_cents=state.intent.budget_usd_cents,
        target_price_cents=flight_target_cost,
        price_range=flight_price_range,
    )

    # Process flight choices from plan and enrich with RAG data
    flight_keywords = _extract_flight_info_from_rag(state.rag_chunks)
    flight_count = 0
    processed_flight_refs: set[str] = set()

    # Log RAG flight keywords availability
    print(f"\n📋 RAG Flight Keywords Available: {len(flight_keywords)} flights")
    if flight_keywords:
        print("Available RAG flights:")
        for idx, info in flight_keywords.items():
            print(f"  [{idx}] {info.get('airline') or 'Unknown Airline'} - ${info.get('price_usd_cents', 0)/100:.2f}")

    try:
        for day_plan in state.plan.days:
            for slot in day_plan.slots:
                for choice in slot.choices:
                    if (
                        choice.kind == ChoiceKind.flight
                        and choice.option_ref not in processed_flight_refs
                    ):
                        # Log flight processing
                        print(f"\n✈️  Processing flight choice: {choice.option_ref}")

                        # Try to extract flight info from RAG chunks
                        flight_info = None
                        if flight_keywords:
                            # Use round-robin assignment to distribute RAG data across flight choices
                            rag_idx = flight_count % len(flight_keywords)
                            flight_info = flight_keywords.get(rag_idx)
                            print(f"  → Matched to RAG flight {rag_idx}: {flight_info.get('airline') if flight_info else 'None'}")

                        # Try to find a matching fixture flight, or use RAG data to create new flight
                        matching_flight = None
                        if flight_options:
                            # Determine if this is outbound or return based on choice.option_ref
                            is_outbound = "outbound" in choice.option_ref.lower()
                            is_return = "return" in choice.option_ref.lower()

                            # Filter flights by direction
                            for flight in flight_options:
                                if is_outbound and state.intent.airports:
                                    # Outbound: from user's airport to destination
                                    if flight.origin.upper() in [a.upper() for a in state.intent.airports]:
                                        matching_flight = flight
                                        break
                                elif is_return and state.intent.airports:
                                    # Return: from destination to user's airport  
                                    if flight.dest.upper() in [a.upper() for a in state.intent.airports]:
                                        matching_flight = flight
                                        break

                        # Use RAG data if available, otherwise use fixture or fallback
                        if flight_info:
                            # Create flight primarily from RAG data
                            airline = flight_info.get("airline") or "Unknown Airline"
                            price_cents = flight_info.get("price_usd_cents") or choice.features.cost_usd_cents
                            duration_seconds = (
                                int(flight_info.get("duration_hours", 8) * 3600)
                                if flight_info.get("duration_hours")
                                else choice.features.travel_seconds
                            )

                            # Log RAG data usage
                            print(f"  ✓ Using RAG data: {airline} ${price_cents/100:.2f}")

                            # Use matching flight's details if available, otherwise create from RAG/choice
                            if matching_flight:
                                print(f"  ✓ Hybrid: RAG airline + Fixture details ({matching_flight.origin}->{matching_flight.dest})")
                                flight_id = f"{airline} {matching_flight.flight_id.split()[-1]}"
                                origin = matching_flight.origin
                                dest = matching_flight.dest
                                departure = matching_flight.departure
                                arrival = matching_flight.arrival
                                overnight = matching_flight.overnight
                            else:
                                # Create from scratch using RAG + choice data
                                print(f"  ⚠️  RAG-ONLY: Creating flight without fixture match")
                                flight_id = f"{airline} {choice.option_ref}"
                                origin = flight_info.get("origin_airport") or (state.intent.airports[0] if state.intent.airports else "JFK")
                                dest = flight_info.get("dest_airport") or "GIG"  # Default destination

                                # Create reasonable departure/arrival times based on choice window
                                departure = datetime.combine(
                                    day_plan.date,
                                    slot.window.start,
                                    tzinfo=UTC
                                )
                                arrival = departure + timedelta(seconds=duration_seconds)
                                overnight = arrival.date() > departure.date()

                            flight = FlightOption(
                                flight_id=flight_id,
                                origin=origin,
                                dest=dest,
                                departure=departure,
                                arrival=arrival,
                                duration_seconds=duration_seconds,
                                price_usd_cents=price_cents,
                                overnight=overnight,
                                provenance=Provenance(
                                    source="rag",
                                    ref_id=f"rag:flight:{choice.option_ref}",
                                    source_url="rag://flights",
                                    fetched_at=datetime.now(UTC),
                                    cache_hit=False,
                                    response_digest=None,
                                ),
                            )

                        elif matching_flight:
                            # Use fixture flight data
                            print(f"  ✓ Fixture-only: {matching_flight.flight_id} ${matching_flight.price_usd_cents/100:.2f}")
                            flight = matching_flight
                            flight.provenance.source = "fixture"

                        else:
                            # Fallback: create basic flight from choice features
                            print(f"  ⚠️  FALLBACK: Creating flight from planner estimates")
                            flight = FlightOption(
                                flight_id=f"Fallback {choice.option_ref}",
                                origin=state.intent.airports[0] if state.intent.airports else "JFK",
                                dest="GIG",  # Default destination
                                departure=datetime.combine(day_plan.date, slot.window.start, tzinfo=UTC),
                                arrival=datetime.combine(day_plan.date, slot.window.start, tzinfo=UTC) + timedelta(seconds=choice.features.travel_seconds),
                                duration_seconds=choice.features.travel_seconds,
                                price_usd_cents=choice.features.cost_usd_cents,
                                overnight=False,
                                provenance=Provenance(
                                    source="fallback",
                                    ref_id=f"fallback:flight:{choice.option_ref}",
                                    source_url="fallback://flights",
                                    fetched_at=datetime.now(UTC),
                                    cache_hit=False,
                                    response_digest=None,
                                ),
                            )

                        # Compute and set response digest
                        flight_data = flight.model_dump(mode="json")
                        flight.provenance.response_digest = compute_response_digest(flight_data)

                        state.flights[flight.flight_id] = flight
                        processed_flight_refs.add(choice.option_ref)
                        flight_count += 1

    except Exception as e:
        # Log error but don't fail the entire tool execution
        print(f"Warning: Error processing flights: {e}")
        state.messages.append(f"Warning: Flight processing encountered an error: {e}")

    state.tool_call_counts["flights"] = flight_count

    # Log final flight inventory
    print(f"\n" + "="*60)
    print(f"FINAL FLIGHT INVENTORY: {len(state.flights)} flights")
    print("="*60)
    for flight_id, flight in state.flights.items():
        print(f"  {flight_id}")
        print(f"    Route: {flight.origin} → {flight.dest}")
        print(f"    Price: ${flight.price_usd_cents / 100:.2f}")
        print(f"    Source: {flight.provenance.source}")
    print("="*60 + "\n")

    # Extract lodging info from RAG chunks FIRST
    lodging_keywords = _extract_lodging_info_from_rag(state.rag_chunks)

    # Fetch lodging data using adapter with CONTINUOUS budget targeting
    # Pass RAG data to generate lodging directly from RAG instead of fixtures
    from backend.app.adapters.lodging import get_lodging

    # Calculate continuous target cost and price range for lodging
    lodging_target_cost = target_lodging_cost(budget_profile)
    lodging_price_range = compute_price_range(lodging_target_cost, tolerance=0.3)

    lodging_options = get_lodging(
        city=state.intent.city,
        checkin=state.intent.date_window.start,
        checkout=state.intent.date_window.end,
        budget_usd_cents=state.intent.budget_usd_cents,
        rag_lodging_data=lodging_keywords,  # Pass RAG data to adapter
        target_price_cents=lodging_target_cost,
        price_range=lodging_price_range,
    )

    # Log RAG lodging keywords availability
    print(f"\n🏨 RAG Lodging Keywords Available: {len(lodging_keywords)} options")
    if lodging_keywords:
        print("Available RAG lodging:")
        for idx, info in lodging_keywords.items():
            print(f"  [{idx}] {info.get('name')} ({info.get('tier')}) - ${info.get('price_per_night_usd_cents', 0)/100:.2f}/night")

    # Populate state.lodgings dictionary directly from RAG-generated options
    # No enrichment needed since lodging was created from RAG data
    for idx, lodging in enumerate(lodging_options):
        tier_display = lodging.tier.value if hasattr(lodging.tier, 'value') else str(lodging.tier)
        print(f"\n🏨 Processing lodging option {idx}: {lodging.name} ({tier_display})")
        print(f"  ✓ RAG-based lodging: ${lodging.price_per_night_usd_cents/100:.2f}/night")
        print(f"  Source: {lodging.provenance.source}")

        state.lodgings[lodging.lodging_id] = lodging
    state.tool_call_counts["lodging"] = len(lodging_options)

    # Log final lodging inventory
    print(f"\n" + "="*60)
    print(f"FINAL LODGING INVENTORY: {len(state.lodgings)} options")
    print("="*60)
    for lodging_id, lodging in state.lodgings.items():
        tier = lodging.tier.value if hasattr(lodging.tier, 'value') else str(lodging.tier)
        print(f"  {lodging.name} ({tier})")
        print(f"    Price: ${lodging.price_per_night_usd_cents / 100:.2f}/night")
        print(f"    Location: {lodging.geo.lat:.4f}, {lodging.geo.lon:.4f}" if lodging.geo else "    Location: N/A")
        print(f"    Source: {lodging.provenance.source}")
    print("="*60 + "\n")

    # Simulate FX tool call
    state.tool_call_counts["fx"] = 1

    # Populate attractions from plan using state.rag_attractions (already parsed)
    # Use semantic matching instead of round-robin
    attraction_count = 0
    used_attraction_ids: set[str] = set()

    # Log RAG attractions availability
    print(f"\n🎭 RAG Attractions Available: {len(state.rag_attractions)} venues")
    if state.rag_attractions:
        print("Available RAG attractions:")
        for attr in state.rag_attractions:
            cost_display = f"${attr.est_price_usd_cents/100:.2f}" if attr.est_price_usd_cents else "Free"
            print(f"  {attr.id}: {attr.name} ({attr.venue_type}) - {cost_display}")

    for day_plan in state.plan.days:
        for slot in day_plan.slots:
            for choice in slot.choices:
                if choice.kind == ChoiceKind.attraction:
                    print(f"\n🎭 Processing attraction slot: {choice.option_ref}")

                    # Check if choice already references a RAG attraction from planner
                    if choice.option_ref in [attr.id for attr in state.rag_attractions]:
                        # Planner already selected RAG attraction - use it directly
                        matched_attraction = next(
                            attr for attr in state.rag_attractions if attr.id == choice.option_ref
                        )
                        print(f"  ✓ Planner selected: {matched_attraction.name}")

                        # Synchronize cost: Update choice.features with actual RAG cost
                        if matched_attraction.est_price_usd_cents is not None:
                            choice.features.cost_usd_cents = matched_attraction.est_price_usd_cents

                        # Store in state.attractions
                        state.attractions[choice.option_ref] = matched_attraction
                        used_attraction_ids.add(choice.option_ref)
                        attraction_count += 1

                    elif choice.option_ref not in state.attractions:
                        # Planner created abstract slot - try semantic matching
                        matched_attraction = _match_rag_attraction_to_choice(
                            choice,
                            state.rag_attractions,
                            used_attraction_ids,
                        )

                        if matched_attraction:
                            print(f"  ✓ Semantic match: {matched_attraction.name}")
                            print(f"    Score: Cost ${matched_attraction.est_price_usd_cents/100:.2f} vs target ${choice.features.cost_usd_cents/100:.2f}")

                            # Synchronize cost: Update choice.features with actual RAG cost
                            if matched_attraction.est_price_usd_cents is not None:
                                choice.features.cost_usd_cents = matched_attraction.est_price_usd_cents

                            # Store using matched attraction's ID
                            state.attractions[matched_attraction.id] = matched_attraction
                            # Update choice.option_ref to point to actual attraction
                            choice.option_ref = matched_attraction.id
                            used_attraction_ids.add(matched_attraction.id)
                            attraction_count += 1
                        else:
                            # No suitable RAG match - this should fail validation
                            print(f"  ⚠️  No suitable RAG attraction found for {choice.option_ref}")
                            print(f"    Target cost: ${choice.features.cost_usd_cents/100:.2f}")
                            print(f"    This plan will likely fail validation")

                            # Create stub attraction to avoid crashing (will be caught by validation)
                            stub_attraction = Attraction(
                                id=choice.option_ref,
                                name=f"[Missing] {choice.option_ref}",
                                venue_type="attraction",
                                indoor=choice.features.indoor,
                                kid_friendly=False,
                                opening_hours={
                                    "0": [], "1": [], "2": [], "3": [], "4": [], "5": [], "6": []
                                },
                                location=Geo(lat=48.8566, lon=2.3522),
                                est_price_usd_cents=choice.features.cost_usd_cents,
                                provenance=Provenance(
                                    source="fallback",
                                    ref_id=f"fallback:{choice.option_ref}",
                                    fetched_at=datetime.now(UTC),
                                    cache_hit=False,
                                ),
                            )
                            state.attractions[choice.option_ref] = stub_attraction
                            attraction_count += 1

    state.tool_call_counts["attractions"] = attraction_count

    # Log final attractions inventory
    print(f"\n" + "="*60)
    print(f"FINAL ATTRACTIONS INVENTORY: {len(state.attractions)} venues")
    print("="*60)
    for attr_id, attr in state.attractions.items():
        cost_display = f"${attr.est_price_usd_cents/100:.2f}" if attr.est_price_usd_cents else "Free"
        print(f"  {attr.name} ({attr.venue_type})")
        print(f"    Cost: {cost_display}")
        print(f"    Indoor: {attr.indoor}")
    print("="*60 + "\n")

    # Populate transit legs and enrich with RAG data
    transit_keywords = _extract_transit_info_from_rag(state.rag_chunks)
    transit_keyword_items = list(transit_keywords.items())
    transit_count = 0

    # Log RAG transit availability
    print(f"\n🚇 RAG Transit Keywords Available: {len(transit_keywords)} options")
    if transit_keywords:
        print("Available RAG transit:")
        for idx, info in transit_keywords.items():
            route = info.get('route_name', 'Unknown route')
            mode = info.get('mode', 'unknown')
            cost_display = f"${info.get('price_usd_cents', 0)/100:.2f}" if info.get('price_usd_cents') else "N/A"
            print(f"  [{idx}] {route} ({mode}) - {cost_display}")

    for day_plan in state.plan.days:
        for slot in day_plan.slots:
            for choice in slot.choices:
                if (
                    choice.kind == ChoiceKind.transit
                    and choice.option_ref not in state.transit_legs
                ):
                    print(f"\n🚇 Processing transit: {choice.option_ref}")

                    from backend.app.adapters.transit import get_transit_leg

                    # Extract location data from the choice
                    from_geo = Geo(lat=48.8566, lon=2.3522)  # Default Paris center
                    to_geo = Geo(lat=48.8566 + 0.01, lon=2.3522 + 0.01)  # Slightly offset

                    # Extract transit mode from choice.option_ref as fallback
                    mode_str = choice.option_ref.split("_")[-1] if "_" in choice.option_ref else "metro"
                    try:
                        mode = TransitMode(mode_str)
                    except ValueError:
                        mode = TransitMode.metro

                    matching_rag_idx: int | None = None
                    matching_rag: dict[str, any] | None = None

                    if transit_keyword_items:
                        preferred_mode = mode.value
                        for rag_idx, rag_info in transit_keyword_items:
                            rag_mode = rag_info.get("mode")
                            if rag_mode and preferred_mode and rag_mode == preferred_mode:
                                matching_rag_idx = rag_idx
                                matching_rag = rag_info
                                break

                        if matching_rag is None:
                            matching_rag_idx, matching_rag = transit_keyword_items[
                                transit_count % len(transit_keyword_items)
                            ]

                    if matching_rag:
                        print(f"  → Matched to RAG transit: {matching_rag.get('route_name')} ({matching_rag.get('mode')})")

                    # Override mode with RAG data if available
                    if matching_rag and matching_rag.get("mode"):
                        normalized_mode = _normalize_transit_mode(matching_rag.get("mode"))
                        if normalized_mode:
                            try:
                                mode = TransitMode(normalized_mode)
                            except ValueError:
                                pass

                    transit_leg = get_transit_leg(
                        from_geo=from_geo,
                        to_geo=to_geo,
                        mode_prefs=[mode],
                    )

                    # Enrich transit leg and slot features with RAG data if available
                    if matching_rag:
                        print(f"  ✓ Enriching with RAG data:")
                        price_cents = matching_rag.get("price_usd_cents")
                        duration_seconds = matching_rag.get("duration_seconds")
                        route_name = matching_rag.get("route_name")
                        neighborhoods = matching_rag.get("neighborhoods") or []

                        if price_cents is not None:
                            transit_leg.price_usd_cents = price_cents
                            if choice.features:
                                choice.features.cost_usd_cents = price_cents
                            print(f"    Price: ${price_cents/100:.2f}")

                        if duration_seconds is not None:
                            transit_leg.duration_seconds = duration_seconds
                            if choice.features:
                                choice.features.travel_seconds = duration_seconds
                            print(f"    Duration: ~{duration_seconds // 60} min")

                        if route_name:
                            transit_leg.route_name = route_name
                            print(f"    Route: {route_name}")
                        if neighborhoods:
                            if isinstance(neighborhoods, list):
                                transit_leg.neighborhoods = neighborhoods
                            else:
                                transit_leg.neighborhoods = [str(neighborhoods)]
                            print(f"    Areas: {', '.join(neighborhoods[:2]) if isinstance(neighborhoods, list) else neighborhoods}")

                        transit_leg.provenance.source = "fixture+rag"
                        if matching_rag_idx is not None:
                            transit_leg.provenance.ref_id = (
                                f"enriched:{transit_leg.provenance.ref_id}:{matching_rag_idx}"
                            )
                    else:
                        print(f"  ✓ Using fixture-only transit")

                    state.transit_legs[choice.option_ref] = transit_leg
                    transit_count += 1

    state.tool_call_counts["transit"] = transit_count

    # Log final transit inventory
    print(f"\n" + "="*60)
    print(f"FINAL TRANSIT INVENTORY: {len(state.transit_legs)} legs")
    print("="*60)
    for leg_id, leg in state.transit_legs.items():
        route_display = getattr(leg, 'route_name', 'Unknown route')
        print(f"  {route_display} ({leg.mode.value})")
        cost_display = f"${leg.price_usd_cents/100:.2f}" if hasattr(leg, 'price_usd_cents') and leg.price_usd_cents else "N/A"
        print(f"    Cost: {cost_display}")
        print(f"    Duration: ~{leg.duration_seconds // 60} min")
        print(f"    Source: {leg.provenance.source}")
    print("="*60 + "\n")

    state.messages.append(f"Executed {sum(state.tool_call_counts.values())} tool calls")
    state.last_event_ts = datetime.now(UTC)

    return state


def _find_best_flight(
    available_flights: list, desired_features, time_window, day_index: int = 0, trip_days: int = 5
):
    """Find best matching flight based on cost preferences and direction.

    Args:
        available_flights: List of FlightOption objects
        desired_features: ChoiceFeatures with target cost
        time_window: TimeWindow for the slot
        day_index: Day index in trip (0 = first day, trip_days-1 = last day)
        trip_days: Total number of days in trip

    Returns:
        Best matching FlightOption or None
    """
    if not available_flights:
        return None

    # Determine if this is outbound or return based on day
    is_outbound = day_index == 0
    is_return = day_index == trip_days - 1

    # Filter flights by direction if we can determine origin/destination
    direction_filtered = []
    if available_flights:
        for flight in available_flights:
            if is_outbound:
                # For outbound, we want flights FROM departure airport TO destination
                # Assuming JFK -> GIG pattern for outbound
                if any(airport in flight.origin for airport in ['JFK', 'LGA', 'EWR']) and 'GIG' in flight.dest:
                    direction_filtered.append(flight)
            elif is_return:
                # For return, we want flights FROM destination TO departure airport  
                # Assuming GIG -> JFK pattern for return
                if 'GIG' in flight.origin and any(airport in flight.dest for airport in ['JFK', 'LGA', 'EWR']):
                    direction_filtered.append(flight)
    
    # Use direction filtered flights if available, otherwise use all
    candidate_flights = direction_filtered if direction_filtered else available_flights

    # Filter by rough cost match (within 50% of desired to be more flexible)
    target_cost = desired_features.cost_usd_cents if desired_features else 50000
    candidates = [
        f for f in candidate_flights
        if abs(f.price_usd_cents - target_cost) / max(target_cost, 1) < 0.5
    ]

    # Return cheapest if we have matches, otherwise cheapest overall
    candidates = candidates if candidates else candidate_flights
    return min(candidates, key=lambda f: f.price_usd_cents) if candidates else None


def _find_best_lodging(available_lodging: list, desired_features):
    """Find best matching lodging based on cost preferences.

    Args:
        available_lodging: List of Lodging objects
        desired_features: ChoiceFeatures with target cost

    Returns:
        Best matching Lodging or None
    """
    if not available_lodging:
        return None

    target_cost = desired_features.cost_usd_cents if desired_features else 15000
    
    # Find lodging closest to target cost (not always cheapest!)
    # This respects the budget-aware planning that sets target costs
    best_lodging = min(
        available_lodging,
        key=lambda l: abs(l.price_per_night_usd_cents - target_cost)
    )
    
    return best_lodging


def resolve_node(state: OrchestratorState) -> OrchestratorState:
    """Resolve abstract plan choices to concrete tool results with real pricing.

    Maps the planner's abstract choices (with estimated costs) to actual
    flights/lodging/attractions that were fetched by tool_exec_node.
    This ensures the final itinerary uses real pricing data.
    """
    state.messages.append("Resolving plan to actual options with real pricing...")
    state.last_event_ts = datetime.now(UTC)

    if not state.plan:
        state.messages.append("No plan to resolve")
        return state

    resolved_count = 0
    trip_days = len(state.plan.days)

    for day_index, day_plan in enumerate(state.plan.days):
        for slot in day_plan.slots:
            # Get the top choice for this slot
            if not slot.choices:
                continue

            choice = slot.choices[0]

            if choice.kind == ChoiceKind.flight:
                # Find best matching flight from available options with direction awareness
                best_flight = _find_best_flight(
                    available_flights=list(state.flights.values()),
                    desired_features=choice.features,
                    time_window=slot.window,
                    day_index=day_index,
                    trip_days=trip_days,
                )
                if best_flight:
                    # Update choice to reference real flight with real price
                    choice.option_ref = best_flight.flight_id
                    if choice.features:
                        choice.features.cost_usd_cents = best_flight.price_usd_cents
                    choice.provenance = Provenance(
                        source="flights_adapter",
                        fetched_at=datetime.now(UTC),
                        cache_hit=False,
                    )
                    resolved_count += 1

            elif choice.kind == ChoiceKind.lodging:
                # Find best matching lodging based on tier preference
                best_lodging = _find_best_lodging(
                    available_lodging=list(state.lodgings.values()),
                    desired_features=choice.features,
                )
                if best_lodging:
                    # Update choice to reference real lodging with real price
                    choice.option_ref = best_lodging.lodging_id
                    if choice.features:
                        choice.features.cost_usd_cents = best_lodging.price_per_night_usd_cents
                    choice.provenance = Provenance(
                        source="lodging_adapter",
                        fetched_at=datetime.now(UTC),
                        cache_hit=False,
                    )
                    resolved_count += 1

    state.messages.append(f"Resolved {resolved_count} choices to real options with accurate pricing")
    state.last_event_ts = datetime.now(UTC)

    return state


def verifier_node(state: OrchestratorState) -> OrchestratorState:
    """Verify plan constraints using PR7 verifiers.

    Runs all four verifiers:
    - Budget (with 10% slippage)
    - Feasibility (timing + venue hours + DST + last train)
    - Weather (tri-state logic)
    - Preferences (must-have vs nice-to-have)

    Emits metrics and updates state.violations.
    """
    from backend.app.metrics import MetricsClient
    from backend.app.verify import (
        verify_budget,
        verify_feasibility,
        verify_preferences,
        verify_weather,
    )

    state.messages.append("Verifying plan constraints...")
    state.last_event_ts = datetime.now(UTC)

    if not state.plan:
        state.messages.append("No plan to verify")
        return state

    # Initialize metrics client
    metrics = MetricsClient()

    # Clear previous violations
    state.violations = []

    # Run budget verifier
    budget_violations = verify_budget(state.intent, state.plan)
    state.violations.extend(budget_violations)

    # Emit budget metrics
    total_cost = 0
    for day_plan in state.plan.days:
        for slot in day_plan.slots:
            if slot.choices:
                total_cost += slot.choices[0].features.cost_usd_cents
    total_cost += state.plan.assumptions.daily_spend_est_cents * len(state.plan.days)

    metrics.observe_budget_delta(state.intent.budget_usd_cents, total_cost)

    if budget_violations:
        for violation in budget_violations:
            metrics.inc_violation(violation.kind.value)

    # Run feasibility verifier
    feasibility_violations = verify_feasibility(
        state.intent,
        state.plan,
        state.attractions,
    )
    state.violations.extend(feasibility_violations)

    if feasibility_violations:
        for violation in feasibility_violations:
            metrics.inc_violation(violation.kind.value)
            if violation.kind.value == "timing_infeasible":
                reason = violation.details.get("reason", "timing")
                metrics.inc_feasibility_violation(reason)
            elif violation.kind.value == "venue_closed":
                metrics.inc_feasibility_violation("venue_closed")

    # Run weather verifier
    weather_violations = verify_weather(state.plan, state.weather_by_date)
    state.violations.extend(weather_violations)

    if weather_violations:
        for violation in weather_violations:
            metrics.inc_violation(violation.kind.value)
            if violation.blocking:
                metrics.inc_weather_blocking()
            else:
                metrics.inc_weather_advisory()

    # Run preferences verifier
    pref_violations = verify_preferences(
        state.intent,
        state.plan,
        state.flights,
        state.attractions,
    )
    state.violations.extend(pref_violations)

    if pref_violations:
        for violation in pref_violations:
            metrics.inc_violation(violation.kind.value)
            pref = violation.details.get("preference", "unknown")
            metrics.inc_pref_violation(pref)

    # Log results
    blocking_count = sum(1 for v in state.violations if v.blocking)
    advisory_count = len(state.violations) - blocking_count

    if state.violations:
        state.messages.append(
            f"Found {len(state.violations)} violations "
            f"({blocking_count} blocking, {advisory_count} advisory)"
        )
    else:
        state.messages.append("No violations detected")

    state.last_event_ts = datetime.now(UTC)
    return state


def repair_node(state: OrchestratorState) -> OrchestratorState:
    """Repair plan violations using PR8 repair engine.

    Applies bounded repair moves to fix violations:
    - ≤2 moves per cycle
    - ≤3 cycles total
    - Partial recompute with reuse tracking
    - Streams repair decisions as events
    """
    from backend.app.metrics import MetricsClient
    from backend.app.repair import repair_plan

    state.messages.append("Checking for repairs...")
    state.last_event_ts = datetime.now(UTC)

    # Check if we have blocking violations to repair
    blocking_violations = [v for v in state.violations if v.blocking]

    if not blocking_violations:
        state.messages.append("No blocking violations - no repairs needed")
        state.last_event_ts = datetime.now(UTC)
        return state

    if not state.plan:
        state.messages.append("No plan to repair")
        state.last_event_ts = datetime.now(UTC)
        return state

    # Initialize metrics client
    metrics = MetricsClient()

    # Store plan before repair
    state.plan_before_repair = state.plan

    # Log repair attempt
    state.messages.append(
        f"Attempting to repair {len(blocking_violations)} blocking violations"
    )
    metrics.inc_repair_attempt()

    # Run repair engine
    result = repair_plan(
        plan=state.plan,
        violations=state.violations,
        metrics=metrics,
    )

    # Update state with repair results
    state.plan = result.plan_after
    state.violations = result.remaining_violations
    state.repair_cycles_run = result.cycles_run
    state.repair_moves_applied = result.moves_applied
    state.repair_reuse_ratio = result.reuse_ratio

    # Stream repair decision events
    for diff in result.diffs:
        state.messages.append(
            f"Repair move: {diff.move_type.value} on day {diff.day_index} - {diff.reason}"
        )

    # Log final results
    if result.success:
        state.messages.append(
            f"Repair successful: {result.moves_applied} moves in {result.cycles_run} cycles, "
            f"{result.reuse_ratio:.0%} reuse"
        )
    else:
        state.messages.append(
            f"Repair incomplete: {len(result.remaining_violations)} violations remain after "
            f"{result.cycles_run} cycles"
        )

    state.last_event_ts = datetime.now(UTC)
    return state


def synth_node(state: OrchestratorState) -> OrchestratorState:
    """Synthesize final itinerary from plan with full provenance tracking.

    PR9: Implements "no evidence, no claim" by generating citations for all
    claims, tracking decisions, and building a complete ItineraryV1 with
    cost breakdown. Emits synthesis metrics.
    """
    from backend.app.metrics import MetricsClient

    start_time = datetime.now(UTC)
    state.messages.append("Synthesizing itinerary...")
    state.last_event_ts = start_time

    if not state.plan:
        state.messages.append("No plan to synthesize")
        return state

    metrics = MetricsClient()

    # Build itinerary from plan with proper tool result lookups
    days: list[DayItinerary] = []
    citations: list[Citation] = []
    decisions: list[Decision] = []

    # Track costs by category
    flights_cost = 0
    lodging_cost = 0
    attractions_cost = 0
    transit_cost = 0

    # Track lodging stays to properly calculate multi-night costs
    # Maps lodging_id -> number of consecutive nights
    lodging_nights: dict[str, int] = {}
    processed_lodging_ids: set[str] = set()

    for day_plan in state.plan.days:
        activities: list[Activity] = []

        for slot in day_plan.slots:
            choice = slot.choices[0]  # Selected choice is first

            # Look up the actual tool result to get name, geo, provenance
            name = f"{choice.kind.value.title()}"
            geo: Geo | None = None
            notes_parts: list[str] = []
            activity_cost: int | None = None  # Track individual activity cost

            # Resolve tool results based on kind
            if choice.kind == ChoiceKind.flight and choice.option_ref in state.flights:
                flight = state.flights[choice.option_ref]
                name = f"{flight.origin} → {flight.dest}"
                notes_parts.append(f"Departure: {flight.departure.strftime('%H:%M')}")
                activity_cost = flight.price_usd_cents
                flights_cost += flight.price_usd_cents

                # Create citation for flight details
                citations.append(
                    Citation(
                        claim=f"Flight {flight.origin} to {flight.dest}",
                        provenance=flight.provenance,
                    )
                )

            elif (
                choice.kind == ChoiceKind.lodging
                and choice.option_ref in state.lodgings
            ):
                lodging = state.lodgings[choice.option_ref]
                name = lodging.name
                geo = lodging.geo
                notes_parts.append(f"{lodging.tier.value.title()} tier")
                if lodging.kid_friendly:
                    notes_parts.append("Kid-friendly")

                # Track per-night cost for display (total lodging cost calculated later)
                activity_cost = lodging.price_per_night_usd_cents

                # Track lodging nights (each day with lodging = 1 night)
                lodging_nights[choice.option_ref] = lodging_nights.get(choice.option_ref, 0) + 1

                # Citation for lodging (only add once per unique lodging)
                if choice.option_ref not in processed_lodging_ids:
                    citations.append(
                        Citation(
                            claim=f"Lodging: {lodging.name}",
                            provenance=lodging.provenance,
                        )
                    )
                    processed_lodging_ids.add(choice.option_ref)

            elif (
                choice.kind == ChoiceKind.attraction
                and choice.option_ref in state.attractions
            ):
                attr = state.attractions[choice.option_ref]
                name = attr.name
                geo = attr.location

                # Only add claims if we have evidence
                if attr.indoor is not None:
                    indoor_str = "Indoor" if attr.indoor else "Outdoor"
                    notes_parts.append(indoor_str)

                if attr.kid_friendly is True:
                    notes_parts.append("Kid-friendly")

                if attr.venue_type:
                    notes_parts.append(attr.venue_type.title())

                if attr.est_price_usd_cents is not None:
                    activity_cost = attr.est_price_usd_cents
                    attractions_cost += attr.est_price_usd_cents

                # Citation for attraction
                citations.append(
                    Citation(
                        claim=f"{attr.name} ({attr.venue_type})",
                        provenance=attr.provenance,
                    )
                )

            elif (
                choice.kind == ChoiceKind.transit
                and choice.option_ref in state.transit_legs
            ):
                leg = state.transit_legs[choice.option_ref]
                route_display = getattr(leg, "route_name", None)
                name = (
                    f"{route_display} ({leg.mode.value.title()})"
                    if route_display
                    else f"{leg.mode.value.title()} transit"
                )
                notes_parts.append(f"~{leg.duration_seconds // 60} minutes")

                if getattr(leg, "neighborhoods", None):
                    neighborhoods = ", ".join(leg.neighborhoods)
                    notes_parts.append(neighborhoods)

                # Prefer enriched costs, fall back to leg price if present
                if choice.features and choice.features.cost_usd_cents is not None:
                    activity_cost = choice.features.cost_usd_cents
                else:
                    activity_cost = getattr(leg, "price_usd_cents", None)

                if activity_cost is not None:
                    transit_cost += activity_cost

                # Citation for transit
                citations.append(
                    Citation(
                        claim=f"Transit via {leg.mode.value}",
                        provenance=leg.provenance,
                    )
                )
            else:
                # Fallback: use features but no detailed tool result
                # "No evidence, no claim" - be generic
                state.messages.append(
                    f"Warning: Using estimated cost for {choice.kind.value} {choice.option_ref} "
                    f"(tool result not found)"
                )
                activity_cost = choice.features.cost_usd_cents
                notes_parts.append(f"Estimated cost: ${choice.features.cost_usd_cents / 100:.2f}")

                # Still count cost by type using estimated values
                if choice.kind == ChoiceKind.flight:
                    flights_cost += choice.features.cost_usd_cents
                elif choice.kind == ChoiceKind.lodging:
                    lodging_cost += choice.features.cost_usd_cents
                elif choice.kind == ChoiceKind.attraction:
                    attractions_cost += choice.features.cost_usd_cents
                elif choice.kind == ChoiceKind.transit:
                    transit_cost += choice.features.cost_usd_cents

            # Build notes from collected parts
            notes = "; ".join(notes_parts) if notes_parts else "Details not available"

            activities.append(
                Activity(
                    window=slot.window,
                    kind=choice.kind,
                    name=name,
                    geo=geo,
                    notes=notes,
                    locked=slot.locked,
                    cost_usd_cents=activity_cost,
                )
            )

        days.append(DayItinerary(day_date=day_plan.date, activities=activities))

    # Calculate total lodging cost (price_per_night * number of nights)
    for lodging_id, num_nights in lodging_nights.items():
        if lodging_id in state.lodgings:
            lodging = state.lodgings[lodging_id]
            lodging_cost += lodging.price_per_night_usd_cents * num_nights

    # Add weather citations
    for day_date, weather in state.weather_by_date.items():
        citations.append(
            Citation(
                claim=f"Weather forecast for {day_date}",
                provenance=weather.provenance,
            )
        )

    # Build decisions from selector and repair
    # Always create at least one decision for UI display (PR9)
    if hasattr(state, "candidate_plans") and len(state.candidate_plans) > 1:
        decisions.append(
            Decision(
                node="selector",
                rationale="Selected plan based on cost, travel time, and preference fit",
                alternatives_considered=len(state.candidate_plans),
                selected=str(state.plan.rng_seed) if state.plan else "0",
            )
        )
    else:
        # Fallback: create planner decision if no selector ran
        decisions.append(
            Decision(
                node="planner",
                rationale="Generated initial itinerary based on user preferences and constraints",
                alternatives_considered=1,
                selected="initial_plan",
            )
        )

    if state.repair_cycles_run > 0:
        decisions.append(
            Decision(
                node="repair",
                rationale=f"Applied {state.repair_moves_applied} repair moves in {state.repair_cycles_run} cycles",
                alternatives_considered=state.repair_moves_applied,
                selected="repaired_plan",
            )
        )

    # Calculate total cost with daily spend
    daily_spend_total = state.plan.assumptions.daily_spend_est_cents * len(days)
    total_cost = (
        flights_cost
        + lodging_cost
        + attractions_cost
        + transit_cost
        + daily_spend_total
    )

    # Build FX disclaimer
    fx_date = state.intent.date_window.start
    currency_disclaimer = (
        f"FX as-of {fx_date.isoformat()}; "
        f"prices are estimates; verify before booking."
    )

    state.itinerary = ItineraryV1(
        itinerary_id=state.trace_id,
        intent=state.intent,
        days=days,
        cost_breakdown=CostBreakdown(
            flights_usd_cents=flights_cost,
            lodging_usd_cents=lodging_cost,
            attractions_usd_cents=attractions_cost,
            transit_usd_cents=transit_cost,
            daily_spend_usd_cents=daily_spend_total,
            total_usd_cents=total_cost,
            currency_disclaimer=currency_disclaimer,
        ),
        decisions=decisions,
        citations=citations,
        created_at=start_time,
        trace_id=state.trace_id,
    )

    # Emit metrics
    end_time = datetime.now(UTC)
    latency_ms = int((end_time - start_time).total_seconds() * 1000)
    metrics.observe_synthesis_latency(latency_ms)

    # Count claims as number of activities + weather days + decisions
    total_claims = (
        sum(len(day.activities) for day in days)
        + len(state.weather_by_date)
        + len(decisions)
    )
    metrics.observe_citation_coverage(len(citations), total_claims)

    state.messages.append(
        f"Itinerary synthesized: {len(days)} days, {len(citations)} citations"
    )
    state.last_event_ts = end_time
    return state


def responder_node(state: OrchestratorState) -> OrchestratorState:
    """Finalize and mark run as complete.

    This is the terminal node that marks the run as done.
    """
    state.messages.append("Finalizing itinerary...")
    state.last_event_ts = datetime.now(UTC)

    state.done = True
    state.messages.append("Run completed successfully")
    state.last_event_ts = datetime.now(UTC)

    return state
