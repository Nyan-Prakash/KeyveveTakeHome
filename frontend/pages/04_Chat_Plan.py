"""Chat-based travel planning with conversational interface."""

import json
import time
from typing import Any

import httpx
import streamlit as st

# Configuration
API_BASE_URL = "http://localhost:8000"
BEARER_TOKEN = "test-token"


def render_itinerary(itinerary_data: dict[str, Any]) -> None:
    """Render the itinerary in a formatted way."""
    if itinerary_data["status"] == "running":
        st.info("⏳ Your itinerary is still being generated...")
        return

    if itinerary_data["status"] == "error":
        st.error("❌ Plan generation failed. Please try again.")
        return

    if not itinerary_data.get("itinerary"):
        st.warning("No itinerary available yet.")
        return

    itin = itinerary_data["itinerary"]

    # Cost breakdown
    cost = itin.get("cost_breakdown", {})
    st.markdown("### 💰 Cost Breakdown")
    st.write(f"**Flights:** ${cost.get('flights_usd_cents', 0) / 100:,.2f}")
    st.write(f"**Lodging:** ${cost.get('lodging_usd_cents', 0) / 100:,.2f}")
    st.write(f"**Attractions:** ${cost.get('attractions_usd_cents', 0) / 100:,.2f}")
    st.write(f"**Transit:** ${cost.get('transit_usd_cents', 0) / 100:,.2f}")
    st.write(f"**Daily Spend:** ${cost.get('daily_spend_usd_cents', 0) / 100:,.2f}")
    st.write(f"**Total:** ${cost.get('total_usd_cents', 0) / 100:,.2f}")

    if cost.get("currency_disclaimer"):
        st.caption(cost["currency_disclaimer"])

    # Daily activities
    st.markdown("### 📅 Daily Plan")
    for day in itin.get("days", []):
        with st.expander(f"📍 {day.get('day_date')}", expanded=False):
            for act in day.get("activities", []):
                st.markdown(f"**{act['name']}** ({act['kind']})")
                st.caption(f"🕐 {act['window']['start']} - {act['window']['end']}")
                if act.get("notes"):
                    st.write(act["notes"])
                if act.get("locked"):
                    st.badge("🔒 Locked")

    # Show metrics
    violations = itinerary_data.get("violations", [])
    if violations:
        st.warning(f"⚠️ {len(violations)} constraint violations detected")
    else:
        st.success("✅ All constraints satisfied!")


def poll_itinerary(run_id: str) -> dict[str, Any] | None:
    """Poll for itinerary completion and return data when ready."""
    max_attempts = 60  # 60 seconds max
    attempt = 0

    while attempt < max_attempts:
        try:
            response = httpx.get(
                f"{API_BASE_URL}/plan/{run_id}",
                headers={"Authorization": f"Bearer {BEARER_TOKEN}"},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            if data["status"] in ("completed", "error"):
                return data

        except httpx.HTTPError:
            pass

        time.sleep(1)
        attempt += 1

    return None


def initialize_session_state():
    """Initialize session state for chat."""
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "chat_run_id" not in st.session_state:
        st.session_state.chat_run_id = None
    if "chat_itinerary" not in st.session_state:
        st.session_state.chat_itinerary = None
    if "is_generating" not in st.session_state:
        st.session_state.is_generating = False


def send_chat_message(user_message: str) -> None:
    """Send a chat message to the backend and handle response."""
    # Add user message to chat
    st.session_state.chat_messages.append({"role": "user", "content": user_message})

    # Build conversation history (exclude current message since we're sending it separately)
    conversation_history = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in st.session_state.chat_messages[:-1]
    ]

    # Call chat API
    try:
        response = httpx.post(
            f"{API_BASE_URL}/chat",
            json={
                "message": user_message,
                "conversation_history": conversation_history,
                "run_id": st.session_state.chat_run_id,
            },
            headers={"Authorization": f"Bearer {BEARER_TOKEN}"},
            timeout=30.0,
        )
        response.raise_for_status()
        result = response.json()

        # Add assistant response
        st.session_state.chat_messages.append(
            {"role": "assistant", "content": result["assistant_message"]}
        )

        # Check if we have a run_id (itinerary generation started)
        if result.get("run_id"):
            st.session_state.chat_run_id = result["run_id"]
            st.session_state.is_generating = True

    except httpx.HTTPError as e:
        st.session_state.chat_messages.append(
            {
                "role": "assistant",
                "content": f"Sorry, I encountered an error: {str(e)}. Please try again.",
            }
        )


def main():
    """Chat-based travel planning page."""
    st.title("💬 Chat Travel Planner")
    st.markdown("Plan your trip through conversation!")

    initialize_session_state()

    # Show example prompts if no messages yet
    if not st.session_state.chat_messages:
        st.markdown("### 👋 Welcome! Try saying:")
        st.info(
            "- 'I want to visit Madrid for 5 days in March with a $3000 budget'\n"
            "- 'Plan a kid-friendly trip to Denver this summer'\n"
            "- 'I need a cultural trip to Barcelona for a week'"
        )

    # Display chat messages
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Display itinerary if available and generation is complete
    if st.session_state.chat_run_id and st.session_state.is_generating:
        # Poll for completion
        with st.spinner("✨ Generating your personalized itinerary..."):
            itinerary_data = poll_itinerary(st.session_state.chat_run_id)

            if itinerary_data:
                st.session_state.chat_itinerary = itinerary_data
                st.session_state.is_generating = False
                st.rerun()

    # Display completed itinerary
    if st.session_state.chat_itinerary and not st.session_state.is_generating:
        with st.chat_message("assistant"):
            st.markdown("### ✅ Your Itinerary is Ready!")
            render_itinerary(st.session_state.chat_itinerary)
            st.markdown(
                "\n\n💡 **Want to make changes?** Just ask! For example:\n"
                "- 'Make it $300 cheaper'\n"
                "- 'Shift dates forward 2 days'\n"
                "- 'Make it more kid-friendly'"
            )

    # Chat input
    if prompt := st.chat_input("Tell me about your trip..."):
        send_chat_message(prompt)
        st.rerun()

    # Clear conversation button
    if st.session_state.chat_messages:
        if st.button("🔄 Start New Conversation"):
            st.session_state.chat_messages = []
            st.session_state.chat_run_id = None
            st.session_state.chat_itinerary = None
            st.session_state.is_generating = False
            st.rerun()


if __name__ == "__main__":
    main()
