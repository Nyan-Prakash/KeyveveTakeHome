"""Minimal Streamlit UI for travel planning."""

import json
from datetime import date

import httpx
import streamlit as st

# Configuration
API_BASE_URL = "http://localhost:8000"
BEARER_TOKEN = "test-token"  # Stub token for PR4


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
                    headers={"Authorization": f"Bearer {BEARER_TOKEN}"},
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
                    headers={"Authorization": f"Bearer {BEARER_TOKEN}"},
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

                # Show final itinerary summary
                st.header("Itinerary Summary")
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
