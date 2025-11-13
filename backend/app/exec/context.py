"""Run context for executor cancellation support."""

import threading
from datetime import UTC, datetime


class RunContext:
    """Context for a single executor run, supporting cancellation."""

    def __init__(self, run_id: str) -> None:
        """Initialize run context.

        Args:
            run_id: Unique identifier for this run.
        """
        self.run_id = run_id
        self.cancelled = threading.Event()
        self.started_at = datetime.now(UTC)
