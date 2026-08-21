"""Canonical market configuration — single source of truth for supported instruments."""

from dataclasses import dataclass, field

from app.opportunity_intelligence.domain.primitives import MarketScope


@dataclass(frozen=True, slots=True)
class MarketConfig:
    """Market-specific configuration."""

    instrument: str
    asset_identifier: str
    quote_currency: str
    exchange: str
    timeframes: tuple[str, ...]


BTCUSDT = MarketConfig(
    instrument="BTCUSDT",
    asset_identifier="BTC",
    quote_currency="USDT",
    exchange="binance",
    timeframes=("5m", "10m", "15m"),
)

ETHUSDT = MarketConfig(
    instrument="ETHUSDT",
    asset_identifier="ETH",
    quote_currency="USDT",
    exchange="binance",
    timeframes=("5m", "10m", "15m"),
)

SUPPORTED_MARKETS: dict[str, MarketConfig] = {
    "BTCUSDT": BTCUSDT,
    "ETHUSDT": ETHUSDT,
}

DEFAULT_INSTRUMENT = "BTCUSDT"
DEFAULT_TIMEFRAME = "5m"


def get_default_scope() -> MarketScope:
    """Return the default pipeline scope (BTCUSDT/5m)."""
    return MarketScope(instrument=DEFAULT_INSTRUMENT, timeframe=DEFAULT_TIMEFRAME)


def get_market_config(instrument: str) -> MarketConfig:
    """Return the configuration for a supported instrument."""
    config = SUPPORTED_MARKETS.get(instrument)
    if config is None:
        raise ValueError(f"Unsupported instrument: {instrument}")
    return config


def get_supported_instruments() -> frozenset[str]:
    """Return the set of all supported instrument identifiers."""
    return frozenset(SUPPORTED_MARKETS.keys())
