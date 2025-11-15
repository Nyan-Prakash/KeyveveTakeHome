#!/usr/bin/env python3
"""Enhanced evaluation runner for testing LangGraph scenarios."""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List
from uuid import UUID

import yaml

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.db.session import get_session_factory
from backend.app.graph import start_run
from backend.app.models.intent import DateWindow, IntentV1, Preferences
from backend.app.models.itinerary import ItineraryV1
from datetime import date


class ScenarioRunner:
    """Runner for evaluation scenarios."""
    
    def __init__(self, scenarios_path: str = None):
        """Initialize the scenario runner."""
        if scenarios_path is None:
            scenarios_path = Path(__file__).parent / "scenarios.yaml"
        self.scenarios_path = Path(scenarios_path)
        self.results = []
    
    def load_scenarios(self) -> List[Dict[str, Any]]:
        """Load evaluation scenarios from YAML file."""
        with open(self.scenarios_path) as f:
            data = yaml.safe_load(f)
            return data["scenarios"]
    
    def build_intent_from_yaml(self, intent_data: Dict[str, Any]) -> IntentV1:
        """Build IntentV1 from YAML data."""
        date_window_data = intent_data["date_window"]
        date_window = DateWindow(
            start=date.fromisoformat(date_window_data["start"]),
            end=date.fromisoformat(date_window_data["end"]),
            tz=date_window_data["tz"],
        )

        prefs_data = intent_data["prefs"]
        prefs = Preferences(
            kid_friendly=prefs_data["kid_friendly"],
            themes=prefs_data["themes"],
            avoid_overnight=prefs_data["avoid_overnight"],
            locked_slots=prefs_data.get("locked_slots", []),
        )

        return IntentV1(
            city=intent_data["city"],
            date_window=date_window,
            budget_usd_cents=intent_data["budget_usd_cents"],
            airports=intent_data["airports"],
            prefs=prefs,
        )
    
    def get_nested_field(self, obj: Any, field_path: str) -> Any:
        """Get nested field value from object using dot notation."""
        try:
            current = obj
            for part in field_path.split('.'):
                if '[' in part and ']' in part:
                    # Handle array indexing like "days[0]"
                    field_name = part.split('[')[0]
                    index = int(part.split('[')[1].split(']')[0])
                    current = getattr(current, field_name)
                    if not isinstance(current, (list, tuple)) or len(current) <= index:
                        return None
                    current = current[index]
                else:
                    current = getattr(current, part)
            return current
        except (AttributeError, IndexError, TypeError, ValueError):
            return None
    
    def check_tool_calls(self, tool_log: Dict[str, Any], required_tools: List[str]) -> Dict[str, bool]:
        """Check if required tools were called."""
        tool_call_counts = tool_log.get("tool_call_counts", {})
        results = {}
        
        for tool in required_tools:
            called = tool_call_counts.get(tool, 0) > 0
            results[tool] = called
        
        return results
    
    def evaluate_predicate(self, predicate: str, intent: IntentV1, itinerary: ItineraryV1) -> bool:
        """Evaluate a predicate string in the context of intent and itinerary."""
        try:
            # Create a safe evaluation context
            context = {
                'intent': intent,
                'itinerary': itinerary,
                'len': len,
                'any': any,
                'all': all,
                'str': str,
            }
            return eval(predicate, {}, context)
        except Exception as e:
            print(f"Error evaluating predicate '{predicate}': {e}")
            return False
    
    def check_expected_fields(self, itinerary: ItineraryV1, expected_fields: List[str]) -> Dict[str, bool]:
        """Check if expected fields are present in the itinerary."""
        results = {}
        
        for field_path in expected_fields:
            value = self.get_nested_field(itinerary, field_path)
            results[field_path] = value is not None
        
        return results
    
    def run_scenario(self, scenario: Dict[str, Any], verbose: bool = False) -> Dict[str, Any]:
        """Run a single scenario and return results."""
        scenario_id = scenario["scenario_id"]
        description = scenario["description"]
        
        if verbose:
            print(f"\n=== Running scenario: {scenario_id} ===")
            print(f"Description: {description}")
        
        # Build intent from YAML
        intent = self.build_intent_from_yaml(scenario["intent"])
        
        # Start the LangGraph run
        factory = get_session_factory()
        session = factory()
        
        start_time = time.time()
        
        try:
            # Test organization and user IDs
            test_org_id = UUID("00000000-0000-0000-0000-000000000001")
            test_user_id = UUID("00000000-0000-0000-0000-000000000002")
            
            run_id = start_run(
                session=session,
                org_id=test_org_id,
                user_id=test_user_id,
                intent=intent,
                seed=42  # Fixed seed for reproducibility
            )
            
            if verbose:
                print(f"Started run: {run_id}")
            
            # Wait for completion
            from sqlalchemy import text
            uuid_format = str(run_id).replace('-', '')
            
            for i in range(30):  # Wait up to 30 seconds
                time.sleep(1)
                
                result = session.execute(text(
                    "SELECT status, tool_log, plan_snapshot FROM agent_run WHERE run_id = :run_id"
                ), {"run_id": uuid_format}).fetchone()
                
                if result:
                    status, tool_log_json, plan_snapshot_json = result
                    
                    if status == "completed":
                        execution_time = time.time() - start_time
                        
                        # Parse tool log
                        tool_log = json.loads(tool_log_json) if tool_log_json else {}
                        node_timings = tool_log.get("node_timings", {})
                        
                        # Get itinerary
                        itinerary_result = session.execute(text(
                            "SELECT data FROM itinerary WHERE run_id = :run_id"
                        ), {"run_id": uuid_format}).fetchone()
                        
                        if itinerary_result:
                            itinerary_data = json.loads(itinerary_result[0])
                            itinerary = ItineraryV1.model_validate(itinerary_data)
                            
                            # Check tool calls
                            tool_check_results = {}
                            if "must_call_tools" in scenario:
                                tool_check_results = self.check_tool_calls(
                                    tool_log, scenario["must_call_tools"]
                                )
                            
                            # Check predicates
                            predicate_results = {}
                            if "must_satisfy" in scenario:
                                for predicate_spec in scenario["must_satisfy"]:
                                    predicate = predicate_spec["predicate"]
                                    description = predicate_spec["description"]
                                    result = self.evaluate_predicate(predicate, intent, itinerary)
                                    predicate_results[description] = result
                            
                            # Check expected fields
                            field_check_results = {}
                            if "expected_fields" in scenario:
                                field_check_results = self.check_expected_fields(
                                    itinerary, scenario["expected_fields"]
                                )
                            
                            return {
                                "scenario_id": scenario_id,
                                "description": description,
                                "status": "completed",
                                "execution_time": execution_time,
                                "node_timings": node_timings,
                                "tool_checks": tool_check_results,
                                "predicate_checks": predicate_results,
                                "field_checks": field_check_results,
                                "success": all([
                                    all(tool_check_results.values()) if tool_check_results else True,
                                    all(predicate_results.values()) if predicate_results else True,
                                    all(field_check_results.values()) if field_check_results else True
                                ])
                            }
                        else:
                            return {
                                "scenario_id": scenario_id,
                                "description": description,
                                "status": "error",
                                "error": "No itinerary generated",
                                "execution_time": execution_time,
                                "success": False
                            }
                    
                    elif status == "error":
                        execution_time = time.time() - start_time
                        return {
                            "scenario_id": scenario_id,
                            "description": description,
                            "status": "error",
                            "error": "Run failed with error status",
                            "execution_time": execution_time,
                            "success": False
                        }
            
            # Timeout
            execution_time = time.time() - start_time
            return {
                "scenario_id": scenario_id,
                "description": description,
                "status": "timeout",
                "error": "Run did not complete within 30 seconds",
                "execution_time": execution_time,
                "success": False
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "scenario_id": scenario_id,
                "description": description,
                "status": "exception",
                "error": str(e),
                "execution_time": execution_time,
                "success": False
            }
        finally:
            session.close()
    
    def run_all_scenarios(self, verbose: bool = False) -> List[Dict[str, Any]]:
        """Run all scenarios and return results."""
        scenarios = self.load_scenarios()
        results = []
        
        print(f"Running {len(scenarios)} scenarios...")
        
        for i, scenario in enumerate(scenarios, 1):
            if not verbose:
                print(f"[{i}/{len(scenarios)}] {scenario['scenario_id']}...", end=" ")
            
            result = self.run_scenario(scenario, verbose=verbose)
            results.append(result)
            
            if not verbose:
                status_icon = "✅" if result["success"] else "❌"
                print(f"{status_icon} ({result.get('execution_time', 0):.1f}s)")
        
        return results
    
    def print_summary(self, results: List[Dict[str, Any]]):
        """Print summary of results."""
        total = len(results)
        passed = sum(1 for r in results if r["success"])
        failed = total - passed
        
        print(f"\n{'='*60}")
        print(f"EVALUATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total scenarios: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success rate: {passed/total*100:.1f}%")
        
        if failed > 0:
            print(f"\nFAILED SCENARIOS:")
            for result in results:
                if not result["success"]:
                    print(f"  ❌ {result['scenario_id']}: {result.get('error', 'Unknown error')}")
        
        # Node timing summary
        print(f"\nNODE TIMING SUMMARY:")
        node_times = {}
        completed_runs = [r for r in results if r["status"] == "completed"]
        
        if completed_runs:
            for result in completed_runs:
                for node, timing in result.get("node_timings", {}).items():
                    if node not in node_times:
                        node_times[node] = []
                    node_times[node].append(timing)
            
            for node, times in sorted(node_times.items()):
                avg_time = sum(times) / len(times)
                max_time = max(times)
                print(f"  {node}: avg={avg_time:.1f}ms, max={max_time}ms ({len(times)} runs)")
        
        print(f"{'='*60}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run LangGraph evaluation scenarios")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--scenarios", "-s", type=str, help="Path to scenarios YAML file")
    parser.add_argument("--scenario-id", type=str, help="Run only specific scenario")
    
    args = parser.parse_args()
    
    runner = ScenarioRunner(args.scenarios)
    
    if args.scenario_id:
        scenarios = runner.load_scenarios()
        scenario = next((s for s in scenarios if s["scenario_id"] == args.scenario_id), None)
        if not scenario:
            print(f"Scenario '{args.scenario_id}' not found")
            sys.exit(1)
        
        result = runner.run_scenario(scenario, verbose=True)
        runner.print_summary([result])
    else:
        results = runner.run_all_scenarios(verbose=args.verbose)
        runner.print_summary(results)
    
    # Exit with error code if any scenarios failed
    failed_count = sum(1 for r in (results if not args.scenario_id else [result]) if not r["success"])
    sys.exit(0 if failed_count == 0 else 1)


if __name__ == "__main__":
    main()
