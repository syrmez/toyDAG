from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
import csv
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from src.http import get_json
from src.io import read_json, write_json

MS = 1000
DAY = 24 * 60 * 60

BINANCE_SPOT = "https://api.binance.com"
BINANCE_FUTURES = "https://fapi.binance.com"
COINBASE = "https://api.exchange.coinbase.com"
COINBASE_DERIVATIVES = "https://api.exchange.fairx.net"
KRAKEN = "https://api.kraken.com"
KRAKEN_FUTURES = "https://futures.kraken.com"
KALSHI = "https://external-api.kalshi.com/trade-api/v2"

SYMBOLS = {
    "BTC": {"binance": "BTCUSDT", "coinbase": "BTC-USD", "kraken": "XBTUSD", "kraken_perp": "PF_XBTUSD"},
    "ETH": {"binance": "ETHUSDT", "coinbase": "ETH-USD", "kraken": "ETHUSD", "kraken_perp": "PF_ETHUSD"},
}

COINBASE_FUNDING_SYMBOLS = {
    "BTC": os.getenv("COINBASE_BTC_FUNDING_SYMBOL"),
    "ETH": os.getenv("COINBASE_ETH_FUNDING_SYMBOL"),
}


def ms(dt: datetime) -> int:
    return int(dt.timestamp() * MS)


def window(days: int) -> tuple[datetime, datetime]:
    end = datetime.now(UTC)
    return end - timedelta(days=days), end


def iso_utc(value: str | int | float, unit: str = "s") -> str:
    if isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        scale = MS if unit == "ms" else 1
        dt = datetime.fromtimestamp(value / scale, UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


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


def coinbase_derivatives_headers(path: str, params: dict[str, Any]) -> dict[str, str] | None:
    key, secret, passphrase = (os.getenv(k) for k in ("CB_ACCESS_KEY", "CB_ACCESS_SECRET", "CB_ACCESS_PASSPHRASE"))
    if not all((key, secret, passphrase)):
        return None
    query = urlencode(params)
    request_path = f"{path}?{query}" if query else path
    timestamp = str(int(time.time()))
    message = f"{timestamp}GET{request_path}".encode()
    try:
        secret_bytes = base64.b64decode(secret)
    except Exception:
        secret_bytes = secret.encode()
    signature = base64.b64encode(hmac.new(secret_bytes, message, hashlib.sha256).digest()).decode()
    return {"CB-ACCESS-KEY": key, "CB-ACCESS-SIGN": signature, "CB-ACCESS-TIMESTAMP": timestamp, "CB-ACCESS-PASSPHRASE": passphrase}


def coinbase_derivatives_get(path: str, params: dict[str, Any]) -> Any:
    headers = coinbase_derivatives_headers(path, params)
    if headers is None:
        return {"rows": [], "note": "Set CB_ACCESS_KEY/SECRET/PASSPHRASE for Coinbase Derivatives API."}
    return get_json(f"{COINBASE_DERIVATIVES}{path}", params, headers)


def fetch_coinbase_funding(asset: str, start: datetime, end: datetime) -> dict[str, Any]:
    symbol = COINBASE_FUNDING_SYMBOLS[asset]
    if not symbol:
        return {"asset": asset, "exchange": "coinbase", "rows": [], "note": f"Set COINBASE_{asset}_FUNDING_SYMBOL; Coinbase endpoint needs a derivatives symbol."}

    rows, notes, day = [], [], start.date()
    while day <= end.date():
        data = coinbase_derivatives_get("/rest/funding-rate", {"symbol": symbol, "trading_session_date": day.isoformat()})
        rows.extend(data if isinstance(data, list) else data.get("rows", []))
        if isinstance(data, dict) and data.get("note"):
            notes.append(data["note"])
            break
        day += timedelta(days=1)
    return {"asset": asset, "exchange": "coinbase", "symbol": symbol, "rows": rows, "notes": notes}


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


def dollars(x: Any) -> float | None:
    if x in (None, ""):
        return None
    return float(x)


def dt_utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)


def norm_cdf(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2))


def binary_theo(spot: float, strike: float, expiry: datetime, now: datetime, vol: float) -> float:
    # ponytail: Black-Scholes digital with r=0; swap in Deribit IV surface when this crude vol is the bottleneck.
    t = max((expiry - now).total_seconds(), 0) / (365 * DAY)
    if t <= 0 or vol <= 0:
        return float(spot > strike)
    d2 = (math.log(spot / strike) - 0.5 * vol * vol * t) / (vol * math.sqrt(t))
    return norm_cdf(d2)


def annualized_realized_vol(binance_klines: list[list[Any]], lookback: int = 240) -> float:
    closes = [float(r[4]) for r in binance_klines[-lookback:] if float(r[4]) > 0]
    if len(closes) < 3:
        return 0.60
    rets = [math.log(b / a) for a, b in zip(closes, closes[1:])]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / max(len(rets) - 1, 1)
    return math.sqrt(var) * math.sqrt(365 * 24 * 60)


def fetch_kalshi_markets(series: str = "KXBTCD", status: str = "open", limit: int = 1000) -> list[dict[str, Any]]:
    rows, cursor = [], ""
    while True:
        params: dict[str, Any] = {"series_ticker": series, "status": status, "limit": min(limit, 1000)}
        if cursor:
            params["cursor"] = cursor
        data = get_json(f"{KALSHI}/markets", params)
        rows.extend(data.get("markets", []))
        cursor = data.get("cursor", "")
        if not cursor or len(rows) >= limit:
            return rows[:limit]


def fetch_kalshi_candles(series: str, ticker: str, start: datetime, end: datetime, interval: int = 60) -> dict[str, Any]:
    return get_json(
        f"{KALSHI}/series/{series}/markets/{ticker}/candlesticks",
        {"start_ts": int(start.timestamp()), "end_ts": int(end.timestamp()), "period_interval": interval, "include_latest_before_start": "true"},
    )


def fetch_kalshi_btc(asset: str = "BTC", funding_days: int = 0, candle_days: int = 7) -> None:
    start, end = window(candle_days)
    open_markets = fetch_kalshi_markets("KXBTCD", "open")
    settled_markets = fetch_kalshi_markets("KXBTCD", "settled")
    write_json("data/raw/kalshi/kxbtcd_open_markets.json", open_markets)
    write_json("data/raw/kalshi/kxbtcd_settled_markets.json", settled_markets)
    write_json("data/raw/candles/binance_BTC_1m.json", fetch_binance_candles("BTC", start, end))

    candle_dir = Path("data/raw/kalshi/candles")
    candle_dir.mkdir(parents=True, exist_ok=True)
    liquid = sorted(open_markets + settled_markets, key=lambda m: float(m.get("volume_fp") or 0), reverse=True)[:30]
    for m in liquid:
        ticker = m["ticker"]
        write_json(candle_dir / f"{ticker}_60m.json", fetch_kalshi_candles("KXBTCD", ticker, start, end, 60))


def build_kalshi_btc_edge(asset: str = "BTC", funding_days: int = 0, candle_days: int = 7) -> None:
    markets = read_json("data/raw/kalshi/kxbtcd_open_markets.json")
    btc = read_json("data/raw/candles/binance_BTC_1m.json")
    now = datetime.now(UTC)
    spot = float(btc[-1][4])
    vol = annualized_realized_vol(btc)
    rows = []
    for m in markets:
        strike = dollars(m.get("floor_strike"))
        bid, ask = dollars(m.get("yes_bid_dollars")), dollars(m.get("yes_ask_dollars"))
        if strike is None or bid is None or ask is None or ask <= 0:
            continue
        expiry = dt_utc(m["close_time"])
        theo = binary_theo(spot, strike, expiry, now, vol)
        mid = (bid + ask) / 2
        rows.append({
            "ticker": m["ticker"],
            "close_time": m["close_time"],
            "strike": strike,
            "spot": round(spot, 2),
            "realized_vol": round(vol, 4),
            "yes_bid": bid,
            "yes_ask": ask,
            "market_mid": round(mid, 4),
            "theo": round(theo, 4),
            "edge_to_buy_yes": round(theo - ask, 4),
            "edge_to_sell_yes": round(bid - theo, 4),
            "volume": m.get("volume_fp", "0.00"),
        })
    rows.sort(key=lambda r: max(r["edge_to_buy_yes"], r["edge_to_sell_yes"]), reverse=True)

    out = Path("data/processed/kalshi_btc_edge.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    top = rows[:10]
    report = ["# Kalshi BTC Edge Snapshot", "", f"Spot: `{spot:.2f}`", f"Realized vol used: `{vol:.1%}`", "", "| ticker | strike | mid | theo | buy YES edge | sell YES edge |", "|---|---:|---:|---:|---:|---:|"]
    report += [f"| {r['ticker']} | {r['strike']:.2f} | {r['market_mid']:.3f} | {r['theo']:.3f} | {r['edge_to_buy_yes']:.3f} | {r['edge_to_sell_yes']:.3f} |" for r in top]
    report += ["", "Note: this is a crude risk-neutral digital model using realized vol, not Deribit IV yet."]
    Path("reports").mkdir(exist_ok=True)
    Path("reports/kalshi_btc_edge.md").write_text("\n".join(report))

    assert 0 <= vol < 5 and spot > 0


def kalshi_btc_edge(asset: str = "BTC", funding_days: int = 0, candle_days: int = 7) -> None:
    fetch_kalshi_btc(asset, funding_days, candle_days)
    build_kalshi_btc_edge(asset, funding_days, candle_days)


def normalize_funding(asset: str = "BTC", *_: Any) -> None:
    rows = []

    binance_path = Path(f"data/raw/funding/binance_{asset}.json")
    if binance_path.exists():
        rows += [
            {
                "exchange": "binance",
                "asset": asset,
                "symbol": r["symbol"],
                "timestamp": iso_utc(r["fundingTime"], "ms"),
                "funding_rate": float(r["fundingRate"]),
                "interval_hours": 8,
                "mark_price": r.get("markPrice", ""),
            }
            for r in read_json(binance_path)
        ]

    kraken_path = Path(f"data/raw/funding/kraken_{asset}.json")
    if kraken_path.exists():
        rows += [
            {
                "exchange": "kraken",
                "asset": asset,
                "symbol": SYMBOLS[asset]["kraken_perp"],
                "timestamp": iso_utc(r["timestamp"]),
                "funding_rate": float(r["relativeFundingRate"]),
                "interval_hours": 1,
                "mark_price": "",
            }
            for r in read_json(kraken_path).get("rates", [])
        ]

    rows.sort(key=lambda r: (r["timestamp"], r["exchange"]))
    out = Path(f"data/processed/funding_{asset}.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["exchange", "asset", "symbol", "timestamp", "funding_rate", "interval_hours", "mark_price"])
        writer.writeheader()
        writer.writerows(rows)



def fetch_day1(asset: str = "BTC", funding_days: int = 365, candle_days: int = 7) -> None:
    funding_start, funding_end = window(funding_days)
    candle_start, candle_end = window(candle_days)
    write_json(f"data/raw/funding/binance_{asset}.json", fetch_binance_funding(asset, funding_start, funding_end))
    write_json(f"data/raw/funding/coinbase_{asset}.json", fetch_coinbase_funding(asset, funding_start, funding_end))
    write_json(f"data/raw/funding/kraken_{asset}.json", fetch_kraken_funding(asset))
    write_json(f"data/raw/candles/binance_{asset}_1m.json", fetch_binance_candles(asset, candle_start, candle_end))
    write_json(f"data/raw/candles/coinbase_{asset}_1m.json", fetch_coinbase_candles(asset, candle_start, candle_end))
    write_json(f"data/raw/candles/kraken_{asset}_1m.json", fetch_kraken_candles(asset, candle_start))


if __name__ == "__main__":
    for asset in ("BTC", "ETH"):
        fetch_day1(asset)
