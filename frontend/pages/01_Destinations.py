"""Destinations page for managing travel destinations."""

import httpx
import streamlit as st

# Configuration
API_BASE_URL = "http://localhost:8000"
BEARER_TOKEN = "test-token"


def main():
    """Destinations management page."""
    st.title("Destinations")
    st.markdown("Manage your travel destinations and view planning history")

    # Search bar
    search = st.text_input("🔍 Search destinations", placeholder="City or country name")

    # Fetch destinations
    try:
        params = {}
        if search:
            params["search"] = search

        response = httpx.get(
            f"{API_BASE_URL}/destinations",
            headers={"Authorization": f"Bearer {BEARER_TOKEN}"},
            params=params,
            timeout=10.0,
        )
        response.raise_for_status()
        destinations = response.json()

        # Display destinations
        if not destinations:
            st.info("No destinations found. Create your first destination below!")
        else:
            st.subheader(f"Your Destinations ({len(destinations)})")

            for dest in destinations:
                with st.expander(
                    f"📍 {dest['city']}, {dest['country']}", expanded=False
                ):
                    col1, col2 = st.columns([2, 1])

                    with col1:
                        st.write(
                            f"**Location:** {dest['geo']['lat']:.4f}, {dest['geo']['lon']:.4f}"
                        )
                        if dest.get("fixture_path"):
                            st.caption(f"Fixture: {dest['fixture_path']}")

                        # Last run summary
                        last_run = dest.get("last_run")
                        if last_run and last_run.get("run_id"):
                            st.write("**Last Planning Run:**")
                            st.write(f"- Status: {last_run['status']}")
                            if last_run.get("total_cost_usd_cents"):
                                cost_usd = last_run["total_cost_usd_cents"] / 100
                                st.write(f"- Cost: ${cost_usd:.2f}")
                            if last_run.get("created_at"):
                                st.caption(f"Created: {last_run['created_at'][:10]}")

                            # Button to go to plan
                            if st.button(f"View Plan", key=f"view_{dest['dest_id']}"):
                                st.session_state["selected_destination"] = dest
                                st.switch_page("pages/03_Plan.py")
                        else:
                            st.caption("No planning runs yet")

                    with col2:
                        # Edit button
                        if st.button("✏️ Edit", key=f"edit_{dest['dest_id']}"):
                            st.session_state["editing_dest"] = dest

                        # Delete button
                        if st.button("🗑️ Delete", key=f"delete_{dest['dest_id']}"):
                            if st.session_state.get(
                                f"confirm_delete_{dest['dest_id']}"
                            ):
                                # Actually delete
                                try:
                                    del_response = httpx.delete(
                                        f"{API_BASE_URL}/destinations/{dest['dest_id']}",
                                        headers={
                                            "Authorization": f"Bearer {BEARER_TOKEN}"
                                        },
                                        timeout=10.0,
                                    )
                                    del_response.raise_for_status()
                                    st.success("Destination deleted!")
                                    st.rerun()
                                except httpx.HTTPError as e:
                                    st.error(f"Delete failed: {e}")
                            else:
                                # First click: ask for confirmation
                                st.session_state[
                                    f"confirm_delete_{dest['dest_id']}"
                                ] = True
                                st.warning("Click delete again to confirm")

    except httpx.HTTPError as e:
        st.error(f"Failed to load destinations: {e}")

    # Add new destination section
    st.divider()
    st.subheader("Add New Destination")

    # Check if editing
    editing_dest = st.session_state.get("editing_dest")

    with st.form("destination_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            city = st.text_input(
                "City *",
                value=editing_dest["city"] if editing_dest else "",
                placeholder="e.g., Paris",
            )
            lat = st.number_input(
                "Latitude *",
                min_value=-90.0,
                max_value=90.0,
                value=float(editing_dest["geo"]["lat"]) if editing_dest else 0.0,
                format="%.6f",
            )

        with col2:
            country = st.text_input(
                "Country *",
                value=editing_dest["country"] if editing_dest else "",
                placeholder="e.g., France",
            )
            lon = st.number_input(
                "Longitude *",
                min_value=-180.0,
                max_value=180.0,
                value=float(editing_dest["geo"]["lon"]) if editing_dest else 0.0,
                format="%.6f",
            )

        fixture_path = st.text_input(
            "Fixture Path (optional)",
            value=editing_dest.get("fixture_path", "") if editing_dest else "",
            placeholder="e.g., fixtures/paris_data.json",
        )

        submit_label = "Update Destination" if editing_dest else "Create Destination"
        submitted = st.form_submit_button(submit_label, type="primary")

        if submitted:
            if not city or not country:
                st.error("City and country are required")
            else:
                payload = {
                    "city": city,
                    "country": country,
                    "geo": {"lat": lat, "lon": lon},
                    "fixture_path": fixture_path if fixture_path else None,
                }

                try:
                    if editing_dest:
                        # Update existing
                        response = httpx.patch(
                            f"{API_BASE_URL}/destinations/{editing_dest['dest_id']}",
                            json=payload,
                            headers={"Authorization": f"Bearer {BEARER_TOKEN}"},
                            timeout=10.0,
                        )
                    else:
                        # Create new
                        response = httpx.post(
                            f"{API_BASE_URL}/destinations",
                            json=payload,
                            headers={"Authorization": f"Bearer {BEARER_TOKEN}"},
                            timeout=10.0,
                        )

                    response.raise_for_status()
                    st.success(
                        f"Destination {'updated' if editing_dest else 'created'} successfully!"
                    )

                    # Clear editing state
                    if "editing_dest" in st.session_state:
                        del st.session_state["editing_dest"]

                    st.rerun()

                except httpx.HTTPError as e:
                    if e.response and e.response.status_code == 409:
                        st.error(
                            "This destination already exists for your organization"
                        )
                    else:
                        st.error(f"Failed to save destination: {e}")

    if editing_dest:
        if st.button("Cancel Edit"):
            del st.session_state["editing_dest"]
            st.rerun()


if __name__ == "__main__":
    main()
