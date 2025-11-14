"""Feature extraction for tool results.

The feature mapper is the ONLY place where raw tool objects become ChoiceFeatures.
All mappers must be:
- Pure functions (no side effects)
- Deterministic (same input → same output)
- Type-safe (strict mypy)
"""

from .mapper import (
    attraction_to_choice,
    flight_to_choice,
    lodging_to_choice,
    to_choice,
    transit_to_choice,
)

__all__ = [
    "flight_to_choice",
    "lodging_to_choice",
    "attraction_to_choice",
    "transit_to_choice",
    "to_choice",
]
