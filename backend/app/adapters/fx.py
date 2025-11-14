"""FX (Foreign Exchange) adapter using fixture data."""

from datetime import UTC, date, datetime
from typing import Any

from backend.app.config import Settings, get_settings
from backend.app.exec.executor import ToolExecutor
from backend.app.exec.types import BreakerPolicy, CachePolicy
from backend.app.models.common import Provenance


class FxRate:
    """FX rate model (simple version for PR5)."""

    def __init__(
        self,
        from_currency: str,
        to_currency: str,
        rate: float,
        effective_date: date,
        provenance: Provenance
    ):
        self.from_currency = from_currency
        self.to_currency = to_currency
        self.rate = rate
        self.effective_date = effective_date
        self.provenance = provenance


class FxTool:
    """Tool for fetching FX rates from fixtures."""

    def __call__(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Get fixture FX rate.
        
        Args:
            args: Dict with keys from_currency, to_currency, date_str
            
        Returns:
            FX rate data
        """
        from_currency = args["from_currency"]
        to_currency = args["to_currency"]
        date_str = args["date_str"]

        # Fixture FX rates (simplified)
        fixture_rates = {
            ("USD", "EUR"): 0.85,
            ("EUR", "USD"): 1.18,
            ("USD", "GBP"): 0.73,
            ("GBP", "USD"): 1.37,
            ("EUR", "GBP"): 0.86,
            ("GBP", "EUR"): 1.16,
        }

        rate_key = (from_currency, to_currency)
        if rate_key in fixture_rates:
            return {
                "from_currency": from_currency,
                "to_currency": to_currency,
                "rate": fixture_rates[rate_key],
                "effective_date": date_str
            }
        else:
            # Default to 1.0 for same currency or unsupported pairs
            return {
                "from_currency": from_currency,
                "to_currency": to_currency,
                "rate": 1.0,
                "effective_date": date_str
            }


class FxAdapter:
    """
    FX adapter using fixture data with 24h caching.
    
    Even though it's fixture data, we still route through ToolExecutor
    to exercise the resilience patterns.
    """

    def __init__(
        self,
        executor: ToolExecutor,
        settings: Settings | None = None
    ) -> None:
        self._executor = executor
        self._settings = settings or get_settings()
        self._tool = FxTool()

    def get_rate(
        self,
        from_currency: str,
        to_currency: str,
        effective_date: date | None = None
    ) -> FxRate | None:
        """
        Get FX rate between currencies.
        
        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            effective_date: Date for rate (defaults to today)
            
        Returns:
            FX rate or None if not available
        """
        if effective_date is None:
            effective_date = datetime.now(UTC).date()

        # Cache policy: 24h TTL like weather
        cache_policy = CachePolicy(
            enabled=True,
            ttl_seconds=self._settings.fx_ttl_hours * 3600
        )

        breaker_policy = BreakerPolicy(
            failure_threshold=self._settings.breaker_failure_threshold,
            cooldown_seconds=self._settings.breaker_timeout_s
        )

        # Execute the tool call
        result = self._executor.execute(
            tool=self._tool,
            name="fx",
            args={
                "from_currency": from_currency,
                "to_currency": to_currency,
                "date_str": effective_date.isoformat()
            },
            cache_policy=cache_policy,
            breaker_policy=breaker_policy
        )

        if result.status != "success" or result.data is None:
            return None

        return self._parse_fx_rate(
            result.data,
            effective_date,
            result.from_cache
        )

    def _parse_fx_rate(
        self,
        fx_data: dict[str, Any],
        effective_date: date,
        from_cache: bool
    ) -> FxRate:
        """
        Parse fixture data into FxRate model.
        """
        # Create provenance
        provenance = Provenance(
            source="fixture",
            ref_id=f"fixture:fx:{fx_data['from_currency']}-{fx_data['to_currency']}-{effective_date.isoformat()}",
            source_url="fixture://fx",
            fetched_at=datetime.now(UTC),
            cache_hit=from_cache
        )

        return FxRate(
            from_currency=fx_data["from_currency"],
            to_currency=fx_data["to_currency"],
            rate=fx_data["rate"],
            effective_date=effective_date,
            provenance=provenance
        )
