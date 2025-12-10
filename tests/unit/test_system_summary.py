#!/usr/bin/env python3
"""Comprehensive system test summary."""

import sys
import subprocess
from typing import List, Tuple


def run_test(name: str, command: List[str]) -> Tuple[str, bool]:
    """Run a test command and return results."""
    try:
        print(f"🔄 Running {name}...")
        result = subprocess.run(
            command,
            cwd="/Users/nyanprakash/Desktop/Triply/Attempt2/TriplyTakeHome",
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print(f"✅ {name} - PASSED")
            return name, True
        else:
            print(f"❌ {name} - FAILED")
            print(f"   Error: {result.stderr[:200]}")
            return name, False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {name} - TIMEOUT")
        return name, False
    except Exception as e:
        print(f"💥 {name} - ERROR: {e}")
        return name, False


def main():
    """Run comprehensive system tests."""
    print("🚀 LangGraph System Test Summary")
    print("=" * 50)
    
    # Activate virtual environment command prefix
    venv_prefix = ["bash", "-c", "source venv/bin/activate && "]
    
    tests = [
        ("Core Models & Contracts", venv_prefix + ["python -m pytest tests/unit/test_contracts_validators.py -q"]),
        ("Planner Component", venv_prefix + ["python -m pytest tests/unit/test_planner.py -q"]),
        ("Selector Component", venv_prefix + ["python -m pytest tests/unit/test_selector.py -q"]),
        ("Synthesis Component", venv_prefix + ["python -m pytest tests/unit/test_synthesizer.py -q"]),
        ("Repair Component", venv_prefix + ["python -m pytest tests/unit/test_repair_moves.py -q"]),
        ("Verification Components", venv_prefix + ["python -m pytest tests/unit/test_verify_*.py -q"]),
        ("Tool Executor", venv_prefix + ["python -m pytest tests/unit/test_executor.py -q"]),
        ("PR6 Happy Path E2E", venv_prefix + ["python -m pytest tests/eval/test_pr6_happy_path.py -q"]),
        ("LangGraph Nodes Integration", venv_prefix + ["python test_langgraph_integration.py"]),
        ("FastAPI Server", venv_prefix + ["python test_server_startup.py"]),
    ]
    
    results = []
    for name, command in tests:
        # Fix command format for bash
        if command[0] == "bash":
            command = ["bash", "-c", f"source venv/bin/activate && {' '.join(command[3:])}"]
        result = run_test(name, command)
        results.append(result)
    
    print("\n" + "=" * 50)
    print("📊 FINAL SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {name}")
    
    print(f"\n🎯 Overall Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All systems operational! LangGraph tools and system are working correctly.")
        return 0
    else:
        print("⚠️  Some components need attention.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
