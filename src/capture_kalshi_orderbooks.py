from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.http import get_json

KALSHI = "https://external-api.kalshi.com/trade-api/v2"
EVENTS = {
    "iraq_norway": "KXWCGAME-26JUN16IRQNOR",
    "argentina_algeria": "KXWCGAME-26JUN16ARGDZA",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def levels(rows: list[list[str]], n: int = 10) -> list[dict[str, float]]:
    return [
        {"price": price, "quantity": quantity}
        for price, quantity in sorted(((float(p), float(q)) for p, q in rows), reverse=True)[:n]
    ]


def summarize_orderbook(orderbook: dict[str, Any], n: int = 10) -> dict[str, Any]:
    book = orderbook.get("orderbook_fp", orderbook)
    yes_bids = levels(book.get("yes_dollars", []), n)
    no_bids = levels(book.get("no_dollars", []), n)
    yes_bid = yes_bids[0]["price"] if yes_bids else None
    no_bid = no_bids[0]["price"] if no_bids else None
    yes_ask = round(1 - no_bid, 4) if no_bid is not None else None
    no_ask = round(1 - yes_bid, 4) if yes_bid is not None else None
    return {
        "yes_bid": yes_bid,
        "yes_ask": yes_ask,
        "yes_spread": round(yes_ask - yes_bid, 4) if yes_bid is not None and yes_ask is not None else None,
        "no_bid": no_bid,
        "no_ask": no_ask,
        "no_spread": round(no_ask - no_bid, 4) if no_bid is not None and no_ask is not None else None,
        "yes_bids_top10": yes_bids,
        "no_bids_top10": no_bids,
        "yes_asks_top10": [{"price": round(1 - r["price"], 4), "quantity": r["quantity"]} for r in no_bids],
        "no_asks_top10": [{"price": round(1 - r["price"], 4), "quantity": r["quantity"]} for r in yes_bids],
    }


def fetch_event_markets() -> list[dict[str, str]]:
    markets = []
    for event_name, event_ticker in EVENTS.items():
        data = get_json(f"{KALSHI}/events/{event_ticker}")
        for m in data.get("markets", []):
            markets.append({
                "event": event_name,
                "event_ticker": event_ticker,
                "ticker": m["ticker"],
                "title": m.get("title", ""),
                "subtitle": m.get("subtitle", ""),
                "status": m.get("status", ""),
                "result": m.get("result", ""),
                "expiration_value": m.get("expiration_value", ""),
            })
    return markets


def fetch_orderbook(ticker: str, depth: int) -> dict[str, Any]:
    return get_json(f"{KALSHI}/markets/{ticker}/orderbook", {"depth": depth})


def capture(hours: float, interval: float, depth: int, out: Path, once: bool = False) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    markets = fetch_event_markets()
    out.with_suffix(".markets.json").write_text(json.dumps(markets, indent=2, sort_keys=True))
    print(f"capturing {len(markets)} submarkets until all are non-active")

    end = time.monotonic() + hours * 60 * 60
    with out.open("a", buffering=1) as f:
        while once or time.monotonic() < end:
            started = time.monotonic()
            markets = fetch_event_markets()
            active = [m for m in markets if m.get("status") == "active"]
            if not active:
                print(utc_now(), "all markets non-active; stopping")
                break
            for market in active:
                ts = utc_now()
                try:
                    raw = fetch_orderbook(market["ticker"], depth)
                    summary = summarize_orderbook(raw)
                    row = {"ts": ts, **market, **summary, "raw": raw}
                    print(ts, market["ticker"], "YES", row["yes_bid"], "/", row["yes_ask"], "NO", row["no_bid"], "/", row["no_ask"])
                except Exception as e:  # ponytail: keep overnight capture alive; inspect error rows tomorrow.
                    row = {"ts": ts, **market, "error": repr(e)}
                    print(ts, market["ticker"], row["error"])
                f.write(json.dumps(row, sort_keys=True) + "\n")
            if once:
                break
            time.sleep(max(0, interval - (time.monotonic() - started)))


def main() -> None:
    p = argparse.ArgumentParser(description="Capture Kalshi orderbook snapshots for World Cup event submarkets.")
    p.add_argument("--hours", type=float, default=10)
    p.add_argument("--interval", type=float, default=30, help="Seconds between full event sweeps")
    p.add_argument("--depth", type=int, default=100, help="Raw book depth to request; summaries keep top 10 levels per side")
    p.add_argument("--once", action="store_true", help="Fetch one snapshot and exit")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or Path(f"data/raw/kalshi/orderbooks/worldcup_{stamp}.jsonl")
    capture(args.hours, args.interval, args.depth, out, args.once)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
