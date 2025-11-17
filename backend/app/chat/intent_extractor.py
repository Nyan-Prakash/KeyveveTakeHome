"""Extract travel intent from natural language conversations using OpenAI."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from backend.app.config import get_settings
from backend.app.models.intent import DateWindow, IntentV1, Preferences


class Message(BaseModel):
    """Chat message."""

    role: str = Field(description="Role: 'user' or 'assistant'")
    content: str = Field(description="Message content")


class IntentExtractionResult(BaseModel):
    """Result of intent extraction from conversation."""

    assistant_message: str = Field(description="Response to user")
    intent: IntentV1 | None = Field(
        default=None, description="Extracted intent (if complete)"
    )
    missing_fields: list[str] = Field(
        default=[], description="Required fields still missing"
    )
    is_complete: bool = Field(
        default=False, description="Whether intent is complete and ready to plan"
    )


# OpenAI function schema for intent extraction
EXTRACT_INTENT_FUNCTION = {
    "name": "extract_travel_intent",
    "description": "Extract travel planning details from the user's message",
    "parameters": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "Destination city (e.g., 'Madrid', 'Denver')",
            },
            "start_date": {
                "type": "string",
                "description": "Trip start date in YYYY-MM-DD format",
            },
            "end_date": {
                "type": "string",
                "description": "Trip end date in YYYY-MM-DD format",
            },
            "timezone": {
                "type": "string",
                "description": "IANA timezone for destination (e.g., 'Europe/Madrid', 'America/Denver')",
            },
            "budget_usd": {
                "type": "number",
                "description": "Total trip budget in US dollars",
            },
            "airports": {
                "type": "array",
                "items": {"type": "string"},
                "description": "IATA airport codes (e.g., ['JFK', 'LGA']). Infer from common airports near user or destination if not specified.",
            },
            "kid_friendly": {
                "type": "boolean",
                "description": "Whether trip should be kid-friendly",
            },
            "themes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Preferred activity themes (e.g., ['museum', 'art', 'food', 'outdoor', 'history'])",
            },
            "avoid_overnight_flights": {
                "type": "boolean",
                "description": "Whether to avoid overnight/red-eye flights",
            },
        },
        "required": [],  # Allow partial extraction
    },
}


SYSTEM_PROMPT = """You are a helpful travel planning assistant. Your job is to extract travel details from the user's messages to help plan their trip.

Required information:
- Destination city
- Start and end dates for the trip
- Total budget in USD
- Departure airports (if not mentioned, infer common airports)

Optional information:
- Whether the trip is kid-friendly
- Preferred themes (art, food, museums, outdoor activities, etc.)
- Whether to avoid overnight flights

When information is missing:
- Ask for the missing details in a friendly, conversational way
- Don't ask for everything at once - focus on the most important missing info first
- Be helpful and suggest reasonable defaults when appropriate

When you have all required information:
- Confirm the details with the user
- Use the extract_travel_intent function to structure the data

Guidelines:
- Be conversational and natural
- Parse dates flexibly (handle formats like "next March", "March 15-20", "5 days starting March 15")
- Parse budgets flexibly (handle "$3000", "3k", "three thousand dollars")
- Infer timezone from destination city
- If airports aren't mentioned, suggest common ones based on context
"""


def _create_client() -> AsyncOpenAI:
    """Create async OpenAI client."""
    settings = get_settings()
    return AsyncOpenAI(api_key=settings.openai_api_key)


def _validate_and_build_intent(data: dict[str, Any]) -> tuple[IntentV1 | None, list[str]]:
    """Validate extracted data and build IntentV1 if complete.

    Returns:
        Tuple of (intent if complete, list of missing required fields)
    """
    missing = []

    # Check required fields
    if "city" not in data or not data["city"]:
        missing.append("destination city")
    if "start_date" not in data or not data["start_date"]:
        missing.append("start date")
    if "end_date" not in data or not data["end_date"]:
        missing.append("end date")
    if "budget_usd" not in data or not data["budget_usd"]:
        missing.append("budget")
    if "airports" not in data or not data["airports"]:
        missing.append("airports")

    if missing:
        return None, missing

    # Build IntentV1
    try:
        # Convert dates
        start_date = date.fromisoformat(data["start_date"])
        end_date = date.fromisoformat(data["end_date"])

        # Infer timezone if not provided
        timezone = data.get("timezone")
        if not timezone:
            # Simple timezone inference based on common cities
            timezone_map = {
                "madrid": "Europe/Madrid",
                "denver": "America/Denver",
                "new york": "America/New_York",
                "los angeles": "America/Los_Angeles",
                "london": "Europe/London",
                "paris": "Europe/Paris",
                "tokyo": "Asia/Tokyo",
                "barcelona": "Europe/Madrid",
            }
            city_lower = data["city"].lower()
            timezone = timezone_map.get(city_lower, "UTC")

        date_window = DateWindow(start=start_date, end=end_date, tz=timezone)

        # Convert budget to cents
        budget_usd_cents = int(data["budget_usd"] * 100)

        # Build preferences
        prefs = Preferences(
            kid_friendly=data.get("kid_friendly", False),
            themes=data.get("themes", []),
            avoid_overnight=data.get("avoid_overnight_flights", False),
        )

        intent = IntentV1(
            city=data["city"],
            date_window=date_window,
            budget_usd_cents=budget_usd_cents,
            airports=data["airports"],
            prefs=prefs,
        )

        return intent, []
    except Exception as e:
        # If validation fails, treat as incomplete
        return None, [f"validation error: {str(e)}"]


async def extract_intent_from_conversation(
    user_message: str, conversation_history: list[Message]
) -> IntentExtractionResult:
    """Extract travel intent from user message and conversation history.

    Args:
        user_message: Latest message from user
        conversation_history: Previous messages in conversation (user and assistant)

    Returns:
        IntentExtractionResult with assistant response and extracted intent
    """
    settings = get_settings()
    client = _create_client()

    # Build messages for OpenAI
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Add conversation history
    for msg in conversation_history:
        messages.append({"role": msg.role, "content": msg.content})

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    # Call OpenAI with function calling
    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        functions=[EXTRACT_INTENT_FUNCTION],
        function_call="auto",
        temperature=0.7,
    )

    choice = response.choices[0]
    message = choice.message

    # Check if function was called
    if message.function_call:
        # Extract function arguments
        try:
            extracted_data = json.loads(message.function_call.arguments)
        except json.JSONDecodeError:
            extracted_data = {}

        # Validate and build intent
        intent, missing = _validate_and_build_intent(extracted_data)

        if intent:
            # Intent is complete
            confirmation = (
                f"Great! Let me confirm your trip details:\n\n"
                f"📍 Destination: {intent.city}\n"
                f"📅 Dates: {intent.date_window.start} to {intent.date_window.end}\n"
                f"💰 Budget: ${intent.budget_usd_cents / 100:,.2f}\n"
                f"✈️ Airports: {', '.join(intent.airports)}\n"
            )

            if intent.prefs.kid_friendly:
                confirmation += "👨‍👩‍👧‍👦 Kid-friendly: Yes\n"
            if intent.prefs.themes:
                confirmation += f"🎨 Themes: {', '.join(intent.prefs.themes)}\n"
            if intent.prefs.avoid_overnight:
                confirmation += "🌙 Avoid overnight flights: Yes\n"

            confirmation += "\n✨ Generating your personalized itinerary..."

            return IntentExtractionResult(
                assistant_message=confirmation,
                intent=intent,
                missing_fields=[],
                is_complete=True,
            )
        else:
            # Still missing required fields - ask for them
            if "destination city" in missing:
                ask_message = "I'd love to help plan your trip! Where would you like to go?"
            elif "start date" in missing or "end date" in missing:
                ask_message = f"Great choice! When would you like to visit {extracted_data.get('city', 'there')}? What are your travel dates?"
            elif "budget" in missing:
                ask_message = "What's your total budget for this trip?"
            elif "airports" in missing:
                city = extracted_data.get('city', '')
                ask_message = f"Which airport would you like to depart from? (I can suggest options near {city} if helpful)"
            else:
                ask_message = "I need a bit more information. Could you provide your " + ", ".join(missing) + "?"

            return IntentExtractionResult(
                assistant_message=ask_message,
                intent=None,
                missing_fields=missing,
                is_complete=False,
            )
    else:
        # No function call - just respond conversationally
        assistant_message = message.content or "I'd be happy to help plan your trip! Could you tell me where you'd like to go and when?"

        return IntentExtractionResult(
            assistant_message=assistant_message,
            intent=None,
            missing_fields=["all required fields"],
            is_complete=False,
        )
