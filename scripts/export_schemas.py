#!/usr/bin/env python3
"""Export JSON schemas for key models."""

import json
from pathlib import Path

from backend.app.models import ItineraryV1, PlanV1


def export_schemas() -> None:
    """Export JSON schemas for PlanV1 and ItineraryV1."""
    # Create schemas directory
    schemas_dir = Path("docs/schemas")
    schemas_dir.mkdir(parents=True, exist_ok=True)

    # Export PlanV1 schema
    plan_schema = PlanV1.model_json_schema()
    plan_schema_path = schemas_dir / "PlanV1.schema.json"
    with open(plan_schema_path, "w") as f:
        json.dump(plan_schema, f, indent=2)

    # Export ItineraryV1 schema
    itinerary_schema = ItineraryV1.model_json_schema()
    itinerary_schema_path = schemas_dir / "ItineraryV1.schema.json"
    with open(itinerary_schema_path, "w") as f:
        json.dump(itinerary_schema, f, indent=2)

    print(f"Exported schemas to {schemas_dir}")
    print(f"- {plan_schema_path}")
    print(f"- {itinerary_schema_path}")


if __name__ == "__main__":
    export_schemas()
