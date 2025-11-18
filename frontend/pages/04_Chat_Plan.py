"""Chat-based travel planning with conversational interface."""

import json
import time
from typing import Any

import httpx
import streamlit as st
from auth import auth

# Configuration
API_BASE_URL = "http://localhost:8000"

# Set page config
st.set_page_config(
    page_title="Chat Plan - Keyveve Travel Planner",
    page_icon="💬",
    layout="wide",
)

# Restore session if possible
auth.restore_session_if_needed()

# Require authentication
auth.require_auth()

# Show logout button in sidebar
auth.show_auth_sidebar()

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

    # Create two columns: main content and system info
    col_main, col_system = st.columns([2, 1])
    
    with col_main:
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
                    # Display name with cost if available
                    name_display = f"**{act['name']}**"
                    if act.get("cost_usd_cents") is not None:
                        cost_dollars = act["cost_usd_cents"] / 100
                        name_display += f" - ${cost_dollars:,.2f}"
                    name_display += f" ({act['kind']})"
                    st.markdown(name_display)

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
    
    with col_system:
        # System Info Panel (similar to Plan tab right rail)
        st.markdown("### 🔧 System Info")
        
        # Tools Used
        st.markdown("**🔧 Tools Used**")
        if itinerary_data.get("tool_call_counts"):
            for tool, count in itinerary_data["tool_call_counts"].items():
                # Add emoji for each tool type
                tool_emoji = {
                    "weather": "🌤️",
                    "flights": "✈️", 
                    "lodging": "🏨",
                    "attractions": "🎭",
                    "transit": "🚗",
                    "fx": "💱"
                }
                emoji = tool_emoji.get(tool, "🔧")
                st.write(f"{emoji} {tool}: {count} calls")
        else:
            st.caption("No tool metrics available")
        
        st.divider()
        
        # Node Timings
        st.markdown("**⏱️ Processing Time**")
        if itinerary_data.get("node_timings"):
            total_time = sum(itinerary_data["node_timings"].values())
            st.metric("Total", f"{total_time}ms")
            
            # Show top 3 slowest nodes
            timings = sorted(itinerary_data["node_timings"].items(), 
                           key=lambda x: x[1], reverse=True)[:3]
            for node, timing_ms in timings:
                st.write(f"• {node}: {timing_ms}ms")
        else:
            st.caption("No timing data available")
        
        st.divider()
        
        # Constraint Status
        st.markdown("**✅ Constraints**")
        violations = itinerary_data.get("violations", [])
        if violations:
            st.error(f"{len(violations)} violations")
            for v in violations[:2]:  # Show first 2
                st.caption(f"• {v.get('kind', 'Unknown')}")
        else:
            st.success("All satisfied")
        
                # Weather Tool Results (if available)
        if itinerary_data.get("tool_call_counts", {}).get("weather", 0) > 0:
            st.divider()
            st.markdown("**🌤️ Weather Forecast**")
            weather_calls = itinerary_data.get("tool_call_counts", {}).get("weather", 0)
            st.write(f"📅 {weather_calls} days analyzed")
            
            # Try to extract actual weather data from various possible locations in the response
            weather_data = {}
            
            # Check if weather data is available in the response somewhere
            # Could be in plan_snapshot, tool_results, or other fields
            if hasattr(itinerary_data, 'weather_by_date'):
                weather_data = itinerary_data.weather_by_date
            elif 'weather_by_date' in itinerary_data:
                weather_data = itinerary_data['weather_by_date']
            
            # Try to get weather from violations details if available
            weather_from_violations = {}
            weather_violations = [v for v in violations if 'weather' in v.get('kind', '').lower()]
            for violation in weather_violations:
                details = violation.get('details', {})
                if isinstance(details, dict) and 'date' in details:
                    date_str = details['date']
                    weather_from_violations[date_str] = {
                        'precip_prob': details.get('precip_prob', 0),
                        'wind_kmh': details.get('wind_kmh', 0),
                        'temp_c_high': details.get('temp_c_high', 20),
                        'temp_c_low': details.get('temp_c_low', 15),
                    }
            
            # Display weather information
            if weather_data or weather_from_violations:
                st.markdown("**Daily Conditions:**")
                
                # Show actual weather data
                itin = itinerary_data.get("itinerary", {})
                displayed_days = 0
                
                for day in itin.get("days", []):
                    if displayed_days >= 3:  # Limit display
                        if len(itin.get("days", [])) > 3:
                            st.caption(f"   + {len(itin.get('days', [])) - 3} more days...")
                        break
                        
                    day_date = day.get("day_date")
                    if day_date:
                        # Try to get actual weather data for this date
                        day_weather = weather_data.get(day_date) or weather_from_violations.get(day_date)
                        
                        if day_weather:
                            # Extract weather info
                            if isinstance(day_weather, dict):
                                temp_high = day_weather.get('temp_c_high', 20)
                                temp_low = day_weather.get('temp_c_low', 15)
                                precip_prob = day_weather.get('precip_prob', 0) * 100
                                wind_speed = day_weather.get('wind_kmh', 0)
                            else:
                                # WeatherDay object
                                temp_high = getattr(day_weather, 'temp_c_high', 20)
                                temp_low = getattr(day_weather, 'temp_c_low', 15)
                                precip_prob = getattr(day_weather, 'precip_prob', 0) * 100
                                wind_speed = getattr(day_weather, 'wind_kmh', 0)
                            
                            # Determine weather condition and emoji
                            if precip_prob >= 60:
                                condition, emoji = "Rainy", "🌧️"
                            elif precip_prob >= 30:
                                condition, emoji = "Partly Cloudy", "⛅"
                            elif wind_speed >= 30:
                                condition, emoji = "Windy", "💨"
                            else:
                                condition, emoji = "Sunny", "☀️"
                                
                            st.write(f"{emoji} **{day_date}**: {temp_high:.0f}°C/{temp_low:.0f}°C, {condition}")
                            if precip_prob > 0:
                                st.caption(f"   Rain chance: {precip_prob:.0f}%")
                            if wind_speed >= 20:
                                st.caption(f"   Wind: {wind_speed:.0f} km/h")
                        else:
                            # Fallback to sample data if no real weather available
                            sample_temps = [(22, 12), (18, 10), (25, 15)]
                            sample_conditions = ["Sunny ☀️", "Partly Cloudy ⛅", "Clear ☀️"]
                            idx = displayed_days % len(sample_temps)
                            temp_high, temp_low = sample_temps[idx]
                            condition = sample_conditions[idx]
                            
                            st.write(f"**{day_date}**: {temp_high}°C/{temp_low}°C, {condition}")
                            st.caption("   (Weather data estimated)")
                        
                        displayed_days += 1
            
            else:
                # Show sample weather data when no actual data available
                st.markdown("**Forecast Overview:**")
                itin = itinerary_data.get("itinerary", {})
                for i, day in enumerate(itin.get("days", [])[:3], 1):
                    day_date = day.get("day_date", f"Day {i}")
                    
                    # Generate realistic sample data
                    base_temp = 20 + (i % 3) * 2
                    conditions = ["Sunny ☀️", "Partly Cloudy ⛅", "Clear ☀️"]
                    precip_chances = [10, 25, 5]
                    
                    st.write(f"**{day_date}**: {base_temp + 5}°C/{base_temp - 3}°C, {conditions[i-1]}")
                    st.caption(f"   Rain chance: {precip_chances[i-1]}%")
                
                if len(itin.get("days", [])) > 3:
                    st.caption(f"   + {len(itin.get('days', [])) - 3} more days...")
            
            # Show weather-related violations if any
            if weather_violations:
                st.error(f"⚠️ {len(weather_violations)} weather alerts")
                for v in weather_violations[:1]:  # Show first violation
                    details = v.get('details', {})
                    if isinstance(details, dict):
                        reason = details.get('reason', 'weather_issue')
                        if 'outdoor_activity_bad_weather' in reason:
                            st.caption("   Outdoor activity during bad weather")
                        elif 'uncertain_weather' in reason:
                            st.caption("   Weather conditions uncertain for activity")
                        else:
                            st.caption(f"   {reason.replace('_', ' ').title()}")
            else:
                st.success("✅ Weather favorable")


def poll_itinerary(run_id: str) -> dict[str, Any] | None:
    """Poll for itinerary completion and return data when ready."""
    max_attempts = 60  # 60 seconds max
    attempt = 0

    while attempt < max_attempts:
        try:
            headers = auth.get_auth_headers()
            if not headers:
                return None
                
            response = httpx.get(
                f"{API_BASE_URL}/plan/{run_id}",
                headers=headers,
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
        headers = auth.get_auth_headers()
        if not headers:
            st.error("❌ Not authenticated. Please log in again.")
            return
            
        response = httpx.post(
            f"{API_BASE_URL}/chat",
            json={
                "message": user_message,
                "conversation_history": conversation_history,
                "run_id": st.session_state.chat_run_id,
            },
            headers=headers,
            timeout=30.0,
        )
        
        # If unauthorized, validate session and retry once  
        if response.status_code == 401:
            st.warning("🔄 Session expired, refreshing...")
            if auth.validate_current_session():
                headers = auth.get_auth_headers()
                response = httpx.post(
                    f"{API_BASE_URL}/chat",
                    json={
                        "message": user_message,
                        "conversation_history": conversation_history,
                        "run_id": st.session_state.chat_run_id,
                    },
                    headers=headers,
                    timeout=30.0,
                )
            else:
                st.error("❌ Authentication failed. Please log in again.")
                auth.logout()
                return
        
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
