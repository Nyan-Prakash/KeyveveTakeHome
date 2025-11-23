"""Stress test for attraction deduplication with limited options."""

import sys
sys.path.insert(0, '/Users/nyanprakash/Desktop/Keyveve/Attempt2/KeyveveTakeHome')

from datetime import date
from uuid import uuid4

from backend.app.models.intent import IntentV1, DateWindow, Preferences
from backend.app.planning.planner import build_candidate_plans


def test_stress_deduplication():
    """Test deduplication with many days but few attractions."""
    
    # Create intent for 7-day trip
    intent = IntentV1(
        city="Munich, Germany",
        date_window=DateWindow(
            start=date(2025, 6, 1),
            end=date(2025, 6, 7),  # 7 days
            tz="Europe/Berlin"
        ),
        budget_usd_cents=500_000,  # $5000 for more activities
        airports=["MUC"],
        prefs=Preferences(
            themes=["culture", "history", "art"],
            locked_slots=[],
        ),
    )
    
    # Create only 3 attractions for a 7-day trip
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
    
    print("STRESS TEST: 7-day trip with only 3 attractions")
    print("="*80)
    print("Available attractions:")
    for attr in rag_attractions:
        print(f"  - {attr.name} (ID: {attr.id}, Price: ${attr.est_price_usd_cents/100:.2f})")
    print()
    
    # Build plans
    plans = build_candidate_plans(intent, rag_attractions)
    
    all_passed = True
    
    # Check each plan
    for idx, plan in enumerate(plans):
        print(f"\n{'='*80}")
        print(f"Plan {idx + 1}")
        print(f"{'='*80}")
        
        # Collect all attraction IDs
        attraction_ids = []
        
        for day_idx, day in enumerate(plan.days):
            day_attractions = []
            for slot in day.slots:
                for choice in slot.choices:
                    if choice.option_ref in ["attr_1", "attr_2", "attr_3"]:
                        attraction_ids.append(choice.option_ref)
                        attr_name = next(a.name for a in rag_attractions if a.id == choice.option_ref)
                        day_attractions.append(f"{attr_name} ({choice.option_ref})")
            
            if day_attractions:
                print(f"Day {day_idx + 1}: {', '.join(day_attractions)}")
        
        # Check for duplicates
        unique_ids = set(attraction_ids)
        if len(attraction_ids) != len(unique_ids):
            print(f"\n❌ FAILED: Found {len(attraction_ids)} attractions but only {len(unique_ids)} unique")
            for attr_id in unique_ids:
                count = attraction_ids.count(attr_id)
                if count > 1:
                    attr_name = next(a.name for a in rag_attractions if a.id == attr_id)
                    print(f"  DUPLICATE: {attr_name} appears {count} times")
            all_passed = False
        else:
            print(f"\n✅ PASSED: All {len(attraction_ids)} attractions unique (max 3 possible)")
            print(f"   Used: {unique_ids}")
    
    print("\n" + "="*80)
    if all_passed:
        print("✅ STRESS TEST PASSED - No duplicates even with limited options!")
    else:
        print("❌ STRESS TEST FAILED - Found duplicates")
    print("="*80)
    
    return all_passed


if __name__ == "__main__":
    success = test_stress_deduplication()
    sys.exit(0 if success else 1)
