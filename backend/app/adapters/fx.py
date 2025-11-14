"""FX rate adapter using fixture data."""

from datetime import UTC, date, datetime

from backend.app.models.common import Provenance
from backend.app.models.tool_results import FxRate


def get_fx_rate(
    from_currency: str,
    to_currency: str = "USD",
    as_of: date | None = None,
) -> FxRate:
    """
    Get foreign exchange rate from fixture data.

    Args:
        from_currency: Source currency code
        to_currency: Target currency code (default: USD)
        as_of: Date for the rate (default: T-1, yesterday)

    Returns:
        FxRate object with provenance
    """
    if as_of is None:
        # Use T-1 (yesterday) as default
        as_of = date.today()

    # Get fixture rate
    rate = _get_fixture_fx_rate(from_currency, to_currency)

    # Create provenance
    provenance = Provenance(
        source="tool",
        ref_id=f"fixture:fx:{from_currency}-{to_currency}:{as_of.isoformat()}",
        source_url="fixture://fx",
        fetched_at=datetime.now(UTC),
        cache_hit=False,
    )

    return FxRate(
        rate=rate,
        as_of=as_of,
        provenance=provenance,
    )


def _get_fixture_fx_rate(from_currency: str, to_currency: str) -> float:
    """
    Get fixture FX rate.

    Args:
        from_currency: Source currency code
        to_currency: Target currency code

    Returns:
        Exchange rate
    """
    # Fixture rates (from_currency → USD)
    # Updated weekly in production; static for fixtures
    usd_rates = {
        "USD": 1.0,
        "EUR": 1.08,  # 1 EUR = 1.08 USD
        "GBP": 1.27,  # 1 GBP = 1.27 USD
        "JPY": 0.0067,  # 1 JPY = 0.0067 USD
        "CAD": 0.74,  # 1 CAD = 0.74 USD
        "AUD": 0.66,  # 1 AUD = 0.66 USD
    }

    # If converting to USD
    if to_currency == "USD":
        return usd_rates.get(from_currency, 1.0)

    # If converting from USD
    if from_currency == "USD":
        target_rate = usd_rates.get(to_currency, 1.0)
        return 1.0 / target_rate if target_rate != 0 else 1.0

    # Converting between two non-USD currencies
    from_to_usd = usd_rates.get(from_currency, 1.0)
    to_to_usd = usd_rates.get(to_currency, 1.0)

    # from → USD → to
    return from_to_usd / to_to_usd if to_to_usd != 0 else 1.0
