#!/usr/bin/env python3

# Test the luxury budget selection logic directly
from backend.app.models.intent import IntentV1, DateWindow, Preferences
from backend.app.planning.selector import _calculate_cost_weight
from datetime import date

# Create high budget intent
intent = IntentV1(
    city="Rio de Janeiro",
    date_window=DateWindow(
        start=date(2024, 1, 15),
        end=date(2024, 1, 20),
        tz="America/Sao_Paulo"
    ),
    budget_usd_cents=1000000,  # $10,000
    airports=["GIG"],
    prefs=Preferences(
        kid_friendly=False,
        themes=["beach", "luxury", "nightlife"],
        avoid_overnight=False,
        locked_slots=[]
    )
)

# Test the cost weight calculation
cost_weight = _calculate_cost_weight(intent)
print(f"Budget: ${intent.budget_usd_cents/100:.0f}")
print(f"Days: {(intent.date_window.end - intent.date_window.start).days}")
print(f"Per day: ${(intent.budget_usd_cents / 5)/100:.0f}")
print(f"Cost weight: {cost_weight}")

# Expected: cost_weight should be 0.5 (positive = prefer expensive)
