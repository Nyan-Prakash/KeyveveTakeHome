#!/usr/bin/env python3
"""Test with detailed logging to see what's happening in the background thread."""

import logging
import sys
import threading
from datetime import date
from uuid import UUID

from backend.app.db.session import get_session_factory
from backend.app.graph import start_run
from backend.app.models.intent import DateWindow, IntentV1, Preferences

# Set up detailed logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def test_with_logging():
    """Test with detailed logging enabled."""
    print("Testing with detailed logging...")
    
    # Create test intent
    intent = IntentV1(
        city="Barcelona",
        date_window=DateWindow(
            start=date(2025, 11, 1),
            end=date(2025, 11, 5),
            tz="Europe/Madrid"
        ),
        budget_usd_cents=320000,
        airports=["BCN"],
        prefs=Preferences(
            kid_friendly=True,
            themes=["architecture"],
            avoid_overnight=False,
            locked_slots=[]
        )
    )
    
    factory = get_session_factory()
    session = factory()
    
    try:
        print("Starting run...")
        run_id = start_run(
            session=session,
            org_id=UUID("00000000-0000-0000-0000-000000000001"),
            user_id=UUID("00000000-0000-0000-0000-000000000002"),
            intent=intent,
            seed=42
        )
        
        print(f"Started run: {run_id}")
        
        # Let's also check if there are any active threads
        import time
        time.sleep(1)
        
        active_threads = threading.active_count()
        print(f"Active threads: {active_threads}")
        
        for thread in threading.enumerate():
            print(f"Thread: {thread.name}, alive: {thread.is_alive()}, daemon: {thread.daemon}")
        
        # Monitor for a shorter time
        from sqlalchemy import text
        uuid_format = str(run_id).replace('-', '')
        
        for i in range(5):  # Just 5 seconds
            time.sleep(1)
            
            result = session.execute(text(
                "SELECT status FROM agent_run WHERE run_id = :run_id"
            ), {"run_id": uuid_format}).scalar()
            
            if result:
                print(f"[{i+1}s] Status: {result}")
                if result in ["completed", "error"]:
                    return True
            else:
                print(f"[{i+1}s] No status found")
        
        return False
        
    finally:
        session.close()


if __name__ == "__main__":
    if test_with_logging():
        print("✅ Success!")
    else:
        print("❌ Still hanging")
