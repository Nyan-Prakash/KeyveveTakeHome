#!/usr/bin/env python3
"""Debug script to understand why transit isn't showing up in Rio scenario."""

import sys
from datetime import date, time, timedelta
from pathlib import Path
from uuid import uuid4

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.models.common import ChoiceKind
from backend.app.models.intent import DateWindow, IntentV1, Preferences
from backend.app.planning.planner import build_candidate_plans
from backend.app.planning.transit_injector import inject_transit_between_activities

def main():
    """Debug Rio scenario transit injection."""
    print("🔍 Debugging Rio Transit Injection")
    print("=" * 50)
    
    # Create Rio intent similar to user's scenario
    intent = IntentV1(
        city="Rio de Janeiro",
        date_window=DateWindow(
            start=date(2023, 3, 2),
            end=date(2023, 3, 6),  # 4 days
            tz="America/Sao_Paulo",
        ),
        budget_usd_cents=300000,  # $3,000 - reasonable budget
        airports=["GIG"],
        prefs=Preferences(
            kid_friendly=False,
            themes=["culture", "outdoor"],
            avoid_overnight=False,
            locked_slots=[],
        ),
    )
    
    # Generate candidate plans
    print(f"📍 Generating plans for {intent.city}")
    plans = build_candidate_plans(intent)
    
    if not plans:
        print("❌ No plans generated!")
        return 1
    
    plan = plans[0]
    print(f"✅ Generated plan with {len(plan.days)} days")
    
    # Show original plan structure
    print(f"\n📋 Original Plan Structure:")
    for day_idx, day in enumerate(plan.days):
        print(f"  Day {day_idx + 1} ({day.date}):")
        for slot_idx, slot in enumerate(day.slots):
            choice = slot.choices[0]
            print(f"    Slot {slot_idx + 1}: {choice.kind.value} ({slot.window.start}-{slot.window.end}) - {choice.option_ref}")
            print(f"      Cost: ${choice.features.cost_usd_cents / 100:.2f}")
        print(f"    Total slots: {len(day.slots)}")
    
    # Try transit injection
    org_id = uuid4()
    try:
        enhanced_plan, messages = inject_transit_between_activities(plan, intent, org_id)
        
        print(f"\n🚗 Enhanced Plan with Transit:")
        for day_idx, day in enumerate(enhanced_plan.days):
            print(f"  Day {day_idx + 1} ({day.date}):")
            total_transit_cost = 0
            for slot_idx, slot in enumerate(day.slots):
                choice = slot.choices[0]
                if choice.kind == ChoiceKind.transit:
                    print(f"    Slot {slot_idx + 1}: 🚗 {choice.kind.value} ({slot.window.start}-{slot.window.end}) - ${choice.features.cost_usd_cents / 100:.2f}")
                    total_transit_cost += choice.features.cost_usd_cents
                else:
                    print(f"    Slot {slot_idx + 1}: 📍 {choice.kind.value} ({slot.window.start}-{slot.window.end}) - {choice.option_ref}")
            print(f"    Total slots: {len(day.slots)} | Transit cost: ${total_transit_cost / 100:.2f}")
        
        print(f"\n📝 Transit Messages:")
        for msg in messages:
            print(f"  - {msg}")
            
        # Count transit events
        original_slots = sum(len(day.slots) for day in plan.days)
        enhanced_slots = sum(len(day.slots) for day in enhanced_plan.days)
        transit_slots = sum(1 for day in enhanced_plan.days for slot in day.slots 
                          if slot.choices and slot.choices[0].kind == ChoiceKind.transit)
        
        print(f"\n📊 Summary:")
        print(f"  Original slots: {original_slots}")
        print(f"  Enhanced slots: {enhanced_slots}")
        print(f"  Transit slots added: {transit_slots}")
        print(f"  Added slots: {enhanced_slots - original_slots}")
        
        if transit_slots == 0:
            print(f"❌ No transit slots created!")
            print(f"🔍 Analyzing why...")
            
            # Debug each day
            for day_idx, day in enumerate(plan.days):
                print(f"\n  Day {day_idx + 1} analysis:")
                slots = [slot for slot in day.slots if slot.choices]
                print(f"    Total slots: {len(slots)}")
                if len(slots) < 2:
                    print(f"    ⚠️  Only {len(slots)} slot(s) - need at least 2 for transit")
                else:
                    for i in range(len(slots) - 1):
                        current = slots[i]
                        next_slot = slots[i + 1]
                        time_gap = (datetime.combine(date.today(), next_slot.window.start) - 
                                  datetime.combine(date.today(), current.window.end)).total_seconds() / 60
                        print(f"      Gap {i+1}→{i+2}: {time_gap:.0f} minutes ({current.choices[0].kind.value} → {next_slot.choices[0].kind.value})")
        else:
            print(f"✅ Successfully created {transit_slots} transit slots!")
        
        return 0
        
    except Exception as e:
        print(f"❌ Transit injection failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
