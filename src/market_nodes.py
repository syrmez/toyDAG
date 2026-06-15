from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from src.http import get_json
from src.io import write_json

MS = 1000
DAY = 24 * 60 * 60

BINANCE_SPOT = "https://api.binance.com"
BINANCE_FUTURES = "https://fapi.binance.com"
COINBASE = "https://api.exchange.coinbase.com"
KRAKEN = "https://api.kraken.com"
KRAKEN_FUTURES = "https://futures.kraken.com"

SYMBOLS = {
    "BTC": {"binance": "BTCUSDT", "coinbase": "BTC-USD", "kraken": "XBTUSD", "kraken_perp": "PF_XBTUSD"},
    "ETH": {"binance": "ETHUSDT", "coinbase": "ETH-USD", "kraken": "ETHUSD", "kraken_perp": "PF_ETHUSD"},
}


def ms(dt: datetime) -> int:
    return int(dt.timestamp() * MS)


def window(days: int) -> tuple[datetime, datetime]:
    end = datetime.now(UTC)
    return end - timedelta(days=days), end


def fetch_binance_funding(asset: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
    rows, cursor = [], ms(start)
    while cursor < ms(end):
        batch = get_json(
            f"{BINANCE_FUTURES}/fapi/v1/fundingRate",
            {"symbol": SYMBOLS[asset]["binance"], "startTime": cursor, "endTime": ms(end), "limit": 1000},
        )
        if not batch:
            break
        rows.extend(batch)
        cursor = int(batch[-1]["fundingTime"]) + 1
    return rows


def fetch_kraken_funding(asset: str) -> Any:
    # Kraken exposes recent historical perp funding by futures symbol.
    return get_json(
        f"{KRAKEN_FUTURES}/derivatives/api/v3/historical-funding-rates",
        {"symbol": SYMBOLS[asset]["kraken_perp"]},
    )


def fetch_coinbase_funding(asset: str) -> dict[str, Any]:
    # Coinbase spot has no funding. Coinbase International perps are not exposed on the public Exchange API.
    return {"asset": asset, "exchange": "coinbase", "rows": [], "note": "No public funding endpoint on Coinbase Exchange spot API."}


def fetch_binance_candles(asset: str, start: datetime, end: datetime, interval: str = "1m") -> list[list[Any]]:
    rows, cursor = [], ms(start)
    while cursor < ms(end):
        batch = get_json(
            f"{BINANCE_SPOT}/api/v3/klines",
            {"symbol": SYMBOLS[asset]["binance"], "interval": interval, "startTime": cursor, "endTime": ms(end), "limit": 1000},
        )
        if not batch:
            break
        rows.extend(batch)
        cursor = int(batch[-1][0]) + 1
    return rows


def fetch_coinbase_candles(asset: str, start: datetime, end: datetime, granularity: int = 60) -> list[list[Any]]:
    rows, cursor = [], start
    step = timedelta(seconds=granularity * 300)  # Coinbase max: 300 candles/request.
    while cursor < end:
        chunk_end = min(cursor + step, end)
        rows.extend(get_json(
            f"{COINBASE}/products/{SYMBOLS[asset]['coinbase']}/candles",
            {"start": cursor.isoformat(), "end": chunk_end.isoformat(), "granularity": granularity},
        ))
        cursor = chunk_end
    return rows


def fetch_kraken_candles(asset: str, start: datetime, interval: int = 1) -> Any:
    return get_json(
        f"{KRAKEN}/0/public/OHLC",
        {"pair": SYMBOLS[asset]["kraken"], "interval": interval, "since": int(start.timestamp())},
    )


def fetch_day1(asset: str = "BTC", funding_days: int = 365, candle_days: int = 7) -> None:
    funding_start, funding_end = window(funding_days)
    candle_start, candle_end = window(candle_days)
    write_json(f"data/raw/funding/binance_{asset}.json", fetch_binance_funding(asset, funding_start, funding_end))
    write_json(f"data/raw/funding/coinbase_{asset}.json", fetch_coinbase_funding(asset))
    write_json(f"data/raw/funding/kraken_{asset}.json", fetch_kraken_funding(asset))
    write_json(f"data/raw/candles/binance_{asset}_1m.json", fetch_binance_candles(asset, candle_start, candle_end))
    write_json(f"data/raw/candles/coinbase_{asset}_1m.json", fetch_coinbase_candles(asset, candle_start, candle_end))
    write_json(f"data/raw/candles/kraken_{asset}_1m.json", fetch_kraken_candles(asset, candle_start))


if __name__ == "__main__":
    for asset in ("BTC", "ETH"):
        fetch_day1(asset)
