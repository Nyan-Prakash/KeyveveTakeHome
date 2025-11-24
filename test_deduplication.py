"""Test script to verify attraction deduplication works correctly."""

import sys
sys.path.insert(0, '/Users/nyanprakash/Desktop/Keyveve/Attempt2/KeyveveTakeHome')

import random
from datetime import date, time
from uuid import uuid4

from backend.app.models.intent import IntentV1, DateWindow, Preferences
from backend.app.planning.planner import build_candidate_plans
from backend.app.planning.budget_utils import BudgetProfile


def test_deduplication():
    """Test that attractions aren't duplicated in a plan."""
    
    # Create a simple intent
    intent = IntentV1(
        city="Munich, Germany",
        date_window=DateWindow(
            start=date(2025, 6, 1),
            end=date(2025, 6, 5),
            tz="Europe/Berlin"
        ),
        budget_usd_cents=200_000,  # $2000
        airports=["MUC"],
        prefs=Preferences(
            themes=["culture", "history"],
            locked_slots=[],
        ),
    )
    
    # Create fake RAG attractions with just 3 options
    class FakeAttraction:
        def __init__(self, id: str, name: str, price: int):
            self.id = id
            self.name = name
            self.est_price_usd_cents = price
            self.indoor = None
    
    rag_attractions = [
        FakeAttraction("attr_1", "Museum A", 3000),
        FakeAttraction("attr_2", "Museum B", 3200),
        FakeAttraction("attr_3", "Museum C", 2800),
    ]
    
    print("Testing with 3 fake attractions and 4-day trip...")
    print("Attractions available:")
    for attr in rag_attractions:
        print(f"  - {attr.name} (ID: {attr.id}, Price: ${attr.est_price_usd_cents/100:.2f})")
    print()
    
    # Build plans
    plans = build_candidate_plans(intent, rag_attractions)
    
    # Check each plan for duplicates
    for idx, plan in enumerate(plans):
        print(f"\n{'='*80}")
        print(f"Plan {idx + 1}: {len(plan.days)} days")
        print(f"{'='*80}")
        
        # Collect all attraction IDs used in this plan
        attraction_ids = []
        attraction_details = []
        
        for day_idx, day in enumerate(plan.days):
            print(f"\nDay {day_idx + 1} ({day.date}):")
            for slot in day.slots:
                for choice in slot.choices:
                    # Check if this is an attraction from RAG
                    if choice.option_ref in ["attr_1", "attr_2", "attr_3"]:
                        attraction_ids.append(choice.option_ref)
                        attr_name = next(a.name for a in rag_attractions if a.id == choice.option_ref)
                        attraction_details.append({
                            "id": choice.option_ref,
                            "name": attr_name,
                            "day": day_idx + 1,
                            "time": f"{slot.window.start} - {slot.window.end}",
                        })
                        print(f"  {slot.window.start} - {slot.window.end}: {attr_name} (ID: {choice.option_ref})")
        
        # Check for duplicates
        unique_ids = set(attraction_ids)
        if len(attraction_ids) != len(unique_ids):
            print(f"\n❌ FAILED: Found {len(attraction_ids)} attractions but only {len(unique_ids)} unique IDs")
            print("Duplicate attractions found:")
            for attr_id in unique_ids:
                count = attraction_ids.count(attr_id)
                if count > 1:
                    attr_name = next(a.name for a in rag_attractions if a.id == attr_id)
                    print(f"  - {attr_name} (ID: {attr_id}): appears {count} times")
            return False
        else:
            print(f"\n✅ PASSED: All {len(attraction_ids)} attractions are unique!")
            print(f"Used attraction IDs: {unique_ids}")
    
    print("\n" + "="*80)
    print("✅ ALL PLANS PASSED - No duplicate attractions found!")
    print("="*80)
    return True


if __name__ == "__main__":
    test_deduplication()
