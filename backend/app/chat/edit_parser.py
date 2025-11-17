"""Parse natural language edit requests into structured edit operations."""

from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from backend.app.config import get_settings, get_openai_api_key
from backend.app.models.intent import IntentV1


class ParsedEdit(BaseModel):
    """Parsed edit request from natural language."""

    delta_budget_usd_cents: int | None = Field(
        default=None, description="Budget change in cents"
    )
    shift_dates_days: int | None = Field(
        default=None, description="Number of days to shift dates (positive = later)"
    )
    new_prefs: dict[str, Any] | None = Field(
        default=None, description="Updated preferences"
    )
    description: str = Field(description="Human-readable description of the change")
    assistant_message: str = Field(
        description="Confirmation message to send to user"
    )


# OpenAI function schema for edit parsing
PARSE_EDIT_FUNCTION = {
    "name": "parse_edit_request",
    "description": "Parse a user's request to modify their travel itinerary",
    "parameters": {
        "type": "object",
        "properties": {
            "delta_budget_usd": {
                "type": "number",
                "description": "Change in budget in USD (negative to reduce, positive to increase). E.g., -300 for '$300 cheaper'",
            },
            "shift_dates_days": {
                "type": "integer",
                "description": "Number of days to shift dates. Positive = move dates later, negative = move earlier. E.g., 2 for 'shift forward 2 days'",
            },
            "kid_friendly": {
                "type": "boolean",
                "description": "Set to true if user wants kid-friendly activities, false if not",
            },
            "themes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Updated list of preferred themes (e.g., ['museum', 'art', 'food']). Only include if user wants to change themes.",
            },
            "avoid_overnight_flights": {
                "type": "boolean",
                "description": "Set to true to avoid overnight flights, false otherwise",
            },
            "description": {
                "type": "string",
                "description": "Brief human-readable description of what was changed (e.g., 'Reduced budget by $300')",
            },
        },
        "required": ["description"],
    },
}


EDIT_SYSTEM_PROMPT = """You are a helpful travel planning assistant. The user already has a generated itinerary and wants to make changes to it.

Your job is to parse their edit request and extract the changes they want to make:

Budget changes:
- "Make it $300 cheaper" → delta_budget_usd: -300
- "Increase budget by $500" → delta_budget_usd: 500
- "I have $1000 more to spend" → delta_budget_usd: 1000

Date shifts:
- "Shift everything forward 2 days" → shift_dates_days: 2
- "Move dates back 3 days" → shift_dates_days: -3
- "Can we leave a day later?" → shift_dates_days: 1

Preference changes:
- "Make it more kid-friendly" → kid_friendly: true
- "Add more museums" → themes: add 'museum' to themes
- "I want more cultural activities" → themes: ['museum', 'art', 'history']
- "Avoid red-eye flights" → avoid_overnight_flights: true

Multiple changes:
- "Make it $500 cheaper and more kid-friendly" → both budget and preferences

Important:
- Always provide a clear description of what will change
- Be helpful and confirm what changes will be applied
- If the request is unclear, ask for clarification
- Use the parse_edit_request function to structure the edits
"""


def _create_client() -> AsyncOpenAI:
    """Create async OpenAI client."""
    return AsyncOpenAI(api_key=get_openai_api_key())


async def parse_edit_request(
    user_message: str, current_intent: IntentV1
) -> ParsedEdit:
    """Parse natural language edit request into structured edit operation.

    Args:
        user_message: User's edit request in natural language
        current_intent: Current IntentV1 to provide context

    Returns:
        ParsedEdit with structured edit operations and confirmation message
    """
    settings = get_settings()
    client = _create_client()

    # Build context about current intent
    current_budget = current_intent.budget_usd_cents / 100
    current_dates = f"{current_intent.date_window.start} to {current_intent.date_window.end}"
    current_themes = ", ".join(current_intent.prefs.themes) if current_intent.prefs.themes else "none specified"

    context = f"""Current trip details:
- Destination: {current_intent.city}
- Dates: {current_dates}
- Budget: ${current_budget:,.2f}
- Kid-friendly: {current_intent.prefs.kid_friendly}
- Themes: {current_themes}
- Avoid overnight flights: {current_intent.prefs.avoid_overnight}
"""

    # Build messages for OpenAI
    messages = [
        {"role": "system", "content": EDIT_SYSTEM_PROMPT},
        {"role": "user", "content": f"{context}\n\nUser's edit request: {user_message}"},
    ]

    # Call OpenAI with function calling
    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        functions=[PARSE_EDIT_FUNCTION],
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
            extracted_data = {"description": "Parse error"}

        # Build ParsedEdit
        delta_budget_usd_cents = None
        if "delta_budget_usd" in extracted_data:
            delta_budget_usd_cents = int(extracted_data["delta_budget_usd"] * 100)

        shift_dates_days = extracted_data.get("shift_dates_days")

        # Build new_prefs if any preference changes
        new_prefs: dict[str, Any] = {}
        if "kid_friendly" in extracted_data:
            new_prefs["kid_friendly"] = extracted_data["kid_friendly"]
        if "themes" in extracted_data:
            new_prefs["themes"] = extracted_data["themes"]
        if "avoid_overnight_flights" in extracted_data:
            new_prefs["avoid_overnight"] = extracted_data["avoid_overnight_flights"]

        # Build confirmation message
        changes = []
        if delta_budget_usd_cents is not None:
            if delta_budget_usd_cents < 0:
                changes.append(f"reduce budget by ${abs(delta_budget_usd_cents) / 100:,.2f}")
            else:
                changes.append(f"increase budget by ${delta_budget_usd_cents / 100:,.2f}")

        if shift_dates_days is not None:
            if shift_dates_days > 0:
                changes.append(f"shift dates forward by {shift_dates_days} day(s)")
            else:
                changes.append(f"shift dates back by {abs(shift_dates_days)} day(s)")

        if new_prefs.get("kid_friendly"):
            changes.append("make it more kid-friendly")
        if "themes" in new_prefs:
            changes.append(f"update themes to: {', '.join(new_prefs['themes'])}")
        if new_prefs.get("avoid_overnight"):
            changes.append("avoid overnight flights")

        if changes:
            confirmation = (
                f"Got it! I'll {' and '.join(changes)}. "
                f"Generating your updated itinerary..."
            )
        else:
            confirmation = "I'll regenerate your itinerary. One moment..."

        return ParsedEdit(
            delta_budget_usd_cents=delta_budget_usd_cents,
            shift_dates_days=shift_dates_days,
            new_prefs=new_prefs if new_prefs else None,
            description=extracted_data.get("description", "Edit request"),
            assistant_message=confirmation,
        )
    else:
        # No function call - check for vague budget requests
        user_message_lower = user_message.lower()

        # Handle vague "cheaper" requests
        if any(word in user_message_lower for word in ["cheaper", "reduce budget", "less expensive", "save money", "lower cost"]):
            # Suggest 10% reduction as default
            suggested_reduction = int(current_intent.budget_usd_cents * 0.10)

            return ParsedEdit(
                delta_budget_usd_cents=-suggested_reduction,
                shift_dates_days=None,
                new_prefs=None,
                description="Budget reduction (vague request)",
                assistant_message=(
                    f"I understand you'd like a cheaper trip. I'll reduce the budget by "
                    f"${suggested_reduction / 100:,.2f} (10% reduction). "
                    f"Regenerating your itinerary with this new budget..."
                ),
            )

        # Handle vague "more expensive" requests
        elif any(word in user_message_lower for word in ["more expensive", "increase budget", "splurge", "upgrade", "premium"]):
            suggested_increase = int(current_intent.budget_usd_cents * 0.10)

            return ParsedEdit(
                delta_budget_usd_cents=suggested_increase,
                shift_dates_days=None,
                new_prefs=None,
                description="Budget increase (vague request)",
                assistant_message=(
                    f"I'll increase your budget by ${suggested_increase / 100:,.2f} (10% increase) "
                    f"to give you more premium options. Regenerating your itinerary..."
                ),
            )

        # Original fallback for other unclear requests
        else:
            assistant_message = (
                message.content
                or "I'm not sure what changes you'd like to make. You can say things like:\n"
                "- 'Make it $300 cheaper' (specific amount)\n"
                "- 'Make it cheaper' (I'll suggest a 10% reduction)\n"
                "- 'Shift dates forward 2 days'\n"
                "- 'Make it more kid-friendly'"
            )

            return ParsedEdit(
                delta_budget_usd_cents=None,
                shift_dates_days=None,
                new_prefs=None,
                description="Clarification needed",
                assistant_message=assistant_message,
            )
