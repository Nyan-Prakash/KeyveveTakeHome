"""Plan page for creating and refining travel itineraries with what-if flows."""

import json
from datetime import date

import httpx
import streamlit as st

# Configuration
API_BASE_URL = "http://localhost:8000"
BEARER_TOKEN = "test-token"


def render_right_rail(itinerary_data: dict) -> None:
    """Render the right rail with system info, tools, decisions, and citations."""
    st.header("System Info")

    # Tools & Timings
    st.subheader("Tools Used")
    if itinerary_data.get("tool_call_counts"):
        for tool, count in itinerary_data["tool_call_counts"].items():
            st.write(f"- {tool}: {count} calls")
    else:
        st.caption("No tool metrics available")

    # Node timings
    st.subheader("Node Timings")
    if itinerary_data.get("node_timings"):
        for node, timing_ms in itinerary_data["node_timings"].items():
            st.write(f"- {node}: {timing_ms}ms")
    else:
        st.caption("No timing metrics available")

    # Checks & Violations
    st.subheader("Constraint Checks")
    violations = itinerary_data.get("violations", [])
    if violations:
        st.warning(f"{len(violations)} violations detected")
        for v in violations[:3]:  # Show first 3
            st.write(f"- {v.get('kind')}: {v.get('details')}")
    else:
        st.success("All constraints satisfied")

    # Decisions
    st.subheader("Key Decisions")
    if itinerary_data.get("itinerary", {}).get("decisions"):
        decisions = itinerary_data["itinerary"]["decisions"]
        for dec in decisions[:3]:  # Show first 3
            st.write(f"**{dec['node']}**: {dec['rationale'][:60]}...")
            st.caption(f"{dec['alternatives_considered']} alternatives")
    else:
        st.caption("No decisions recorded")

    # Citations
    st.subheader("Citations")
    if itinerary_data.get("itinerary", {}).get("citations"):
        citations = itinerary_data["itinerary"]["citations"]
        st.metric("Total Citations", len(citations))

        # Count RAG citations
        rag_citations = [
            c for c in citations if c.get("provenance", {}).get("source") == "rag"
        ]
        if rag_citations:
            st.info(f"📚 {len(rag_citations)} citations from knowledge base (RAG)")

        with st.expander("View Citations", expanded=False):
            for i, cite in enumerate(citations[:10], 1):  # Show first 10
                st.caption(f"{i}. {cite['claim'][:50]}...")
                prov = cite.get("provenance", {})
                source = prov.get("source", "unknown")
                if source == "rag":
                    st.caption(f"   📚 Source: RAG (chunk {prov.get('ref_id', 'N/A')})")
                else:
                    st.caption(
                        f"   Source: {source} @ {prov.get('fetched_at', 'N/A')[:10]}"
                    )
    else:
        st.caption("No citations available")


def main():
    """Plan page with destination-awareness and what-if flows."""
    st.title("Travel Planner")
    st.markdown("Generate and refine AI-powered travel itineraries")

    # Destination selector
    try:
        response = httpx.get(
            f"{API_BASE_URL}/destinations",
            headers={"Authorization": f"Bearer {BEARER_TOKEN}"},
            timeout=10.0,
        )
        response.raise_for_status()
        destinations = response.json()

        if not destinations:
            st.warning("No destinations found. Please create a destination first.")
            if st.button("Go to Destinations"):
                st.switch_page("pages/01_Destinations.py")
            return

        # Build destination options
        dest_options = {f"{d['city']}, {d['country']}": d for d in destinations}

        # Check if destination was pre-selected from another page
        preselected_dest = st.session_state.get("selected_destination")
        default_index = 0
        if preselected_dest:
            for i, (name, dest) in enumerate(dest_options.items()):
                if dest["dest_id"] == preselected_dest["dest_id"]:
                    default_index = i
                    break

        selected_dest_name = st.selectbox(
            "Destination",
            options=list(dest_options.keys()),
            index=default_index,
        )
        selected_dest = dest_options[selected_dest_name]
        city = selected_dest["city"]

    except httpx.HTTPError as e:
        st.error(f"Failed to load destinations: {e}")
        return

    st.divider()

    # Check if we have an active run
    active_run_id = st.session_state.get(f"active_run_{city}")

    if active_run_id:
        # Show what-if interface
        st.header(f"Itinerary for {city}")

        # What-if controls
        with st.expander("🔄 What-If Controls", expanded=True):
            st.caption("Refine your itinerary with quick adjustments")

            col1, col2 = st.columns(2)

            with col1:
                budget_change = st.number_input(
                    "Budget Change (USD)",
                    min_value=-5000,
                    max_value=5000,
                    value=0,
                    step=100,
                    help="Negative values reduce budget, positive values increase it",
                )

                if st.button("💰 Apply Budget Change", disabled=(budget_change == 0)):
                    try:
                        edit_response = httpx.post(
                            f"{API_BASE_URL}/plan/{active_run_id}/edit",
                            json={"delta_budget_usd_cents": budget_change * 100},
                            headers={"Authorization": f"Bearer {BEARER_TOKEN}"},
                            timeout=10.0,
                        )
                        edit_response.raise_for_status()
                        result = edit_response.json()
                        new_run_id = result["run_id"]

                        st.session_state[f"active_run_{city}"] = new_run_id
                        st.success(
                            f"Creating new plan with ${abs(budget_change)} {'less' if budget_change < 0 else 'more'} budget..."
                        )
                        st.rerun()

                    except httpx.HTTPError as e:
                        st.error(f"Failed to apply change: {e}")

            with col2:
                date_shift = st.number_input(
                    "Shift Dates (days)",
                    min_value=-30,
                    max_value=30,
                    value=0,
                    step=1,
                    help="Shift all dates forward (+) or backward (-)",
                )

                if st.button("📅 Shift Dates", disabled=(date_shift == 0)):
                    try:
                        edit_response = httpx.post(
                            f"{API_BASE_URL}/plan/{active_run_id}/edit",
                            json={"shift_dates_days": date_shift},
                            headers={"Authorization": f"Bearer {BEARER_TOKEN}"},
                            timeout=10.0,
                        )
                        edit_response.raise_for_status()
                        result = edit_response.json()
                        new_run_id = result["run_id"]

                        st.session_state[f"active_run_{city}"] = new_run_id
                        st.success(f"Shifting dates by {date_shift} days...")
                        st.rerun()

                    except httpx.HTTPError as e:
                        st.error(f"Failed to apply change: {e}")

            # Quick what-if buttons
            st.caption("Quick Actions:")
            col_a, col_b, col_c = st.columns(3)

            with col_a:
                if st.button("💸 $300 cheaper"):
                    try:
                        edit_response = httpx.post(
                            f"{API_BASE_URL}/plan/{active_run_id}/edit",
                            json={"delta_budget_usd_cents": -30000},
                            headers={"Authorization": f"Bearer {BEARER_TOKEN}"},
                            timeout=10.0,
                        )
                        edit_response.raise_for_status()
                        result = edit_response.json()
                        st.session_state[f"active_run_{city}"] = result["run_id"]
                        st.rerun()
                    except httpx.HTTPError as e:
                        st.error(f"Failed: {e}")

            with col_b:
                if st.button("👶 More kid-friendly"):
                    try:
                        edit_response = httpx.post(
                            f"{API_BASE_URL}/plan/{active_run_id}/edit",
                            json={"new_prefs": {"kid_friendly": True}},
                            headers={"Authorization": f"Bearer {BEARER_TOKEN}"},
                            timeout=10.0,
                        )
                        edit_response.raise_for_status()
                        result = edit_response.json()
                        st.session_state[f"active_run_{city}"] = result["run_id"]
                        st.rerun()
                    except httpx.HTTPError as e:
                        st.error(f"Failed: {e}")

            with col_c:
                if st.button("➡️ Shift +1 day"):
                    try:
                        edit_response = httpx.post(
                            f"{API_BASE_URL}/plan/{active_run_id}/edit",
                            json={"shift_dates_days": 1},
                            headers={"Authorization": f"Bearer {BEARER_TOKEN}"},
                            timeout=10.0,
                        )
                        edit_response.raise_for_status()
                        result = edit_response.json()
                        st.session_state[f"active_run_{city}"] = result["run_id"]
                        st.rerun()
                    except httpx.HTTPError as e:
                        st.error(f"Failed: {e}")

        # Fetch and display itinerary
        try:
            itinerary_response = httpx.get(
                f"{API_BASE_URL}/plan/{active_run_id}",
                headers={"Authorization": f"Bearer {BEARER_TOKEN}"},
                timeout=10.0,
            )
            itinerary_response.raise_for_status()
            itinerary_data = itinerary_response.json()

            # Main itinerary + Right rail layout
            col_main, col_rail = st.columns([2, 1])

            with col_main:
                st.subheader("Current Itinerary")

                if itinerary_data["status"] == "running":
                    st.info("⏳ Plan is still being generated...")
                elif itinerary_data["status"] == "error":
                    st.error("❌ Plan generation failed")
                elif itinerary_data.get("itinerary"):
                    itin = itinerary_data["itinerary"]

                    # Cost breakdown
                    cost = itin.get("cost_breakdown", {})
                    st.write("**Cost Breakdown**")
                    st.write(
                        f"- Flights: ${cost.get('flights_usd_cents', 0) / 100:.2f}"
                    )
                    st.write(
                        f"- Lodging: ${cost.get('lodging_usd_cents', 0) / 100:.2f}"
                    )
                    st.write(
                        f"- Attractions: ${cost.get('attractions_usd_cents', 0) / 100:.2f}"
                    )
                    st.write(
                        f"- Transit: ${cost.get('transit_usd_cents', 0) / 100:.2f}"
                    )
                    st.write(
                        f"- Daily Spend: ${cost.get('daily_spend_usd_cents', 0) / 100:.2f}"
                    )
                    st.write(f"**Total: ${cost.get('total_usd_cents', 0) / 100:.2f}**")

                    if cost.get("currency_disclaimer"):
                        st.caption(cost["currency_disclaimer"])

                    # Daily activities
                    st.subheader("Daily Plan")
                    for day in itin.get("days", []):
                        with st.expander(f"Day {day.get('day_date')}", expanded=False):
                            for act in day.get("activities", []):
                                st.markdown(f"**{act['name']}** ({act['kind']})")
                                st.caption(
                                    f"{act['window']['start']} - {act['window']['end']}"
                                )
                                if act.get("notes"):
                                    st.write(act["notes"])
                                if act.get("locked"):
                                    st.badge("🔒 Locked")

            with col_rail:
                render_right_rail(itinerary_data)

        except httpx.HTTPError as e:
            st.error(f"Failed to load itinerary: {e}")

        # Start new plan button
        if st.button("🔄 Start New Plan"):
            if f"active_run_{city}" in st.session_state:
                del st.session_state[f"active_run_{city}"]
            st.rerun()

    else:
        # Initial plan creation form
        st.header("Create New Plan")

        col1, col2 = st.columns(2)

        with col1:
            budget = st.number_input(
                "Budget (USD)", min_value=100, max_value=100000, value=5000, step=100
            )
            start_date = st.date_input("Start Date", value=date.today())

        with col2:
            airports = st.text_input(
                "Airports (comma-separated IATA codes)", value="JFK,EWR"
            )
            end_date = st.date_input(
                "End Date", value=date.today().replace(day=date.today().day + 7)
            )

        airports_list = [a.strip() for a in airports.split(",") if a.strip()]

        # Preferences
        st.subheader("Preferences")
        col3, col4 = st.columns(2)

        with col3:
            kid_friendly = st.checkbox("Kid Friendly")
            avoid_overnight = st.checkbox("Avoid Red-Eye Flights")

        with col4:
            themes = st.multiselect(
                "Themes",
                ["art", "food", "culture", "nature", "history", "adventure"],
                default=["culture"],
            )

        # Submit button
        if st.button("Generate Itinerary", type="primary"):
            if not airports_list:
                st.error("Please provide at least one airport.")
                return

            # Build intent
            intent = {
                "city": city,
                "date_window": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "tz": "America/New_York",  # Default TZ
                },
                "budget_usd_cents": budget * 100,
                "airports": airports_list,
                "prefs": {
                    "kid_friendly": kid_friendly,
                    "themes": themes,
                    "avoid_overnight": avoid_overnight,
                    "locked_slots": [],
                },
            }

            # Start the plan
            with st.spinner("Starting plan generation..."):
                try:
                    response = httpx.post(
                        f"{API_BASE_URL}/plan",
                        json=intent,
                        headers={"Authorization": f"Bearer {BEARER_TOKEN}"},
                        timeout=10.0,
                    )
                    response.raise_for_status()
                    result = response.json()
                    run_id = result["run_id"]

                    st.session_state[f"active_run_{city}"] = run_id
                    st.success(f"Plan started! Run ID: {run_id}")
                    st.rerun()

                except httpx.HTTPError as e:
                    st.error(f"Error: {e}")


if __name__ == "__main__":
    main()
