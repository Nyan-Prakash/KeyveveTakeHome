"""Foreign exchange adapter using fixture data."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from backend.app.exec.executor import ToolExecutor
from backend.app.exec.types import BreakerPolicy, CachePolicy
from backend.app.models.common import Provenance
from backend.app.models.tool_results import FxRate

# Fixture FX rates (relative to USD)
# Rates are approximate and for testing only
_FX_RATES = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "JPY": 149.5,
    "CAD": 1.36,
    "AUD": 1.53,
}


def get_fx_rate(
    executor: ToolExecutor,
    from_currency: str,
    to_currency: str,
    as_of_date: date | None = None,
) -> FxRate:
    """
    Get foreign exchange rate from fixtures.

    Args:
        executor: ToolExecutor for consistency (exercises cache + breaker)
        from_currency: Source currency code (ISO 4217, e.g., "USD")
        to_currency: Target currency code (ISO 4217, e.g., "EUR")
        as_of_date: Date for the rate (default: today)

    Returns:
        FxRate object with provenance
    """
    if as_of_date is None:
        as_of_date = date.today()

    def _fetch_fx_rate(args: dict[str, Any]) -> dict[str, Any]:
        from_curr = args["from_currency"].upper()
        to_curr = args["to_currency"].upper()

        # Get rates relative to USD
        from_rate = _FX_RATES.get(from_curr)
        to_rate = _FX_RATES.get(to_curr)

        if from_rate is None:
            raise ValueError(f"Unsupported currency: {from_curr}")
        if to_rate is None:
            raise ValueError(f"Unsupported currency: {to_curr}")

        # Compute cross rate: (1 from_curr) * (from_rate USD/from_curr) * (to_rate to_curr/USD)
        # Actually: 1 from_curr = (1 / from_rate) USD = (1 / from_rate) * to_rate to_curr
        rate = to_rate / from_rate

        return {
            "from_currency": from_curr,
            "to_currency": to_curr,
            "rate": rate,
        }

    result = executor.execute(
        tool=_fetch_fx_rate,
        name="fx",
        args={
            "from_currency": from_currency,
            "to_currency": to_currency,
        },
        cache_policy=CachePolicy(enabled=True, ttl_seconds=24 * 3600),  # 24h cache
        breaker_policy=BreakerPolicy(
            failure_threshold=5,
            window_seconds=60,
            cooldown_seconds=30,
        ),
    )

    if result.status == "breaker_open":
        error_dict = result.error or {}
        raise RuntimeError(
            f"FX API breaker open, retry after {error_dict.get('retry_after_seconds', 30)}s"
        )
    if result.status != "success":
        raise RuntimeError(f"FX fixture failed: {result.status} - {result.error}")

    # Parse result
    if result.data is None:
        raise RuntimeError("FX fixture returned no data")

    data = result.data
    fx_rate = FxRate(
        from_currency=data["from_currency"],
        to_currency=data["to_currency"],
        rate=data["rate"],
        as_of=as_of_date,
        provenance=Provenance(
            source="tool",
            ref_id=f"fx:{data['from_currency']}-{data['to_currency']}:{as_of_date.isoformat()}",
            source_url="fixture://fx",
            fetched_at=datetime.now(UTC),
            cache_hit=result.from_cache,
            response_digest=None,
        ),
    )

    return fx_rate
