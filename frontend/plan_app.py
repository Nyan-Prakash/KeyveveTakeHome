"""Minimal Streamlit UI for travel planning."""

import json
import os
from datetime import date

import httpx
import streamlit as st
from auth import auth

# Configuration
API_BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Require authentication
auth.require_auth()
# Removed hardcoded token


def main():
    """Main Streamlit application."""
    st.title("Travel Planner")
    st.markdown("Generate AI-powered travel itineraries")

    # Intent form
    st.header("Trip Details")

    col1, col2 = st.columns(2)

    with col1:
        city = st.text_input("Destination City", value="Paris")
        budget = st.number_input(
            "Budget (USD)", min_value=100, max_value=100000, value=5000, step=100
        )

    with col2:
        start_date = st.date_input("Start Date", value=date.today())
        end_date = st.date_input(
            "End Date", value=date.today().replace(day=date.today().day + 7)
        )

    airports = st.text_input("Airports (comma-separated IATA codes)", value="JFK,EWR")
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
        if not city or not airports_list:
            st.error("Please provide a destination city and at least one airport.")
            return

        # Build intent
        intent = {
            "city": city,
            "date_window": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "tz": "America/New_York",  # Default TZ for PR4
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
                    headers=auth.get_auth_headers(),
                    timeout=10.0,
                )
                response.raise_for_status()
                result = response.json()
                run_id = result["run_id"]

                st.success(f"Plan started! Run ID: {run_id}")

                # Stream events
                st.header("Progress")
                progress_container = st.container()
                event_log = []

                with httpx.stream(
                    "GET",
                    f"{API_BASE_URL}/plan/{run_id}/stream",
                    headers=auth.get_auth_headers(),
                    timeout=60.0,
                ) as stream_response:
                    stream_response.raise_for_status()

                    for line in stream_response.iter_lines():
                        if not line:
                            continue

                        # Parse SSE format
                        if line.startswith("event:"):
                            event_type = line.split(":", 1)[1].strip()
                        elif line.startswith("data:"):
                            data_str = line.split(":", 1)[1].strip()
                            try:
                                data = json.loads(data_str)

                                if event_type == "heartbeat":
                                    # Show heartbeat (optional)
                                    with progress_container:
                                        st.caption(f"Heartbeat at {data.get('ts', '')}")
                                else:
                                    # Show event
                                    event_log.append(data)
                                    with progress_container:
                                        payload = data.get("payload", {})
                                        message = payload.get(
                                            "message", "Processing..."
                                        )
                                        node = payload.get("node", "")
                                        event_status = payload.get("status", "")

                                        st.write(
                                            f"**{node}** ({event_status}): {message}"
                                        )

                                        # Check if final
                                        if (
                                            node == "final"
                                            and event_status == "completed"
                                        ):
                                            st.success("Itinerary completed!")
                                            break

                            except json.JSONDecodeError:
                                pass

                # Fetch final itinerary details
                try:
                    itinerary_response = httpx.get(
                        f"{API_BASE_URL}/plan/{run_id}",
                        headers=auth.get_auth_headers(),
                        timeout=10.0,
                    )
                    itinerary_response.raise_for_status()
                    itinerary_data = itinerary_response.json()

                    # Main itinerary + Right rail layout
                    col_main, col_rail = st.columns([2, 1])

                    with col_main:
                        st.header("Itinerary Summary")
                        st.markdown(
                            f"""
                            **Destination:** {city}
                            **Dates:** {start_date} to {end_date}
                            **Budget:** ${budget}
                            """
                        )

                        # Show itinerary details if available
                        if itinerary_data.get("itinerary"):
                            itin = itinerary_data["itinerary"]

                            # Cost breakdown
                            cost = itin.get("cost_breakdown", {})
                            st.subheader("Cost Breakdown")
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
                            st.write(
                                f"**Total: ${cost.get('total_usd_cents', 0) / 100:.2f}**"
                            )

                            if cost.get("currency_disclaimer"):
                                st.caption(cost["currency_disclaimer"])

                            # Daily activities
                            st.subheader("Daily Plan")
                            for day in itin.get("days", []):
                                with st.expander(
                                    f"Day {day.get('day_date')}", expanded=False
                                ):
                                    for act in day.get("activities", []):
                                        st.markdown(
                                            f"**{act['name']}** ({act['kind']})"
                                        )
                                        st.caption(
                                            f"{act['window']['start']} - {act['window']['end']}"
                                        )
                                        if act.get("notes"):
                                            st.write(act["notes"])
                                        if act.get("locked"):
                                            st.badge("🔒 Locked")
                        else:
                            st.info("Itinerary details not yet available")

                    with col_rail:
                        st.header("System Info")

                        # Tools & Timings
                        st.subheader("Tools Used")
                        if itinerary_data.get("tool_call_counts"):
                            for tool, count in itinerary_data[
                                "tool_call_counts"
                            ].items():
                                st.write(f"- {tool}: {count} calls")
                        else:
                            st.caption("No tool metrics available")

                        # Node timings
                        st.subheader("Node Timings")
                        if itinerary_data.get("node_timings"):
                            for node, timing_ms in itinerary_data[
                                "node_timings"
                            ].items():
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
                                st.write(
                                    f"**{dec['node']}**: {dec['rationale'][:60]}..."
                                )
                                st.caption(
                                    f"{dec['alternatives_considered']} alternatives"
                                )
                        else:
                            st.caption("No decisions recorded")

                        # Citations
                        st.subheader("Citations")
                        if itinerary_data.get("itinerary", {}).get("citations"):
                            citations = itinerary_data["itinerary"]["citations"]
                            st.metric("Total Citations", len(citations))
                            with st.expander("View Citations", expanded=False):
                                for i, cite in enumerate(
                                    citations[:10], 1
                                ):  # Show first 10
                                    st.caption(f"{i}. {cite['claim'][:50]}...")
                                    prov = cite.get("provenance", {})
                                    st.caption(
                                        f"   Source: {prov.get('source')} @ {prov.get('fetched_at', 'N/A')[:10]}"
                                    )
                        else:
                            st.caption("No citations available")

                except httpx.HTTPError as e:
                    st.error(f"Error fetching itinerary: {e}")
                    st.markdown(
                        f"""
                        **Destination:** {city}
                        **Dates:** {start_date} to {end_date}
                        **Budget:** ${budget}

                        Your itinerary has been generated! Check the progress log above for details.
                        """
                    )

            except httpx.HTTPError as e:
                st.error(f"Error: {e}")


if __name__ == "__main__":
    main()
