from __future__ import annotations

import argparse

from src.market_nodes import build_kalshi_btc_edge, fetch_day1, fetch_kalshi_btc, kalshi_btc_edge, normalize_funding

NODES = {
    "fetch_day1": fetch_day1,
    "normalize_funding": normalize_funding,
    "fetch_kalshi_btc": fetch_kalshi_btc,
    "build_kalshi_btc_edge": build_kalshi_btc_edge,
    "kalshi_btc_edge": kalshi_btc_edge,
}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("node", choices=NODES)
    p.add_argument("--asset", choices=["BTC", "ETH"], default="BTC")
    p.add_argument("--funding-days", type=int, default=365)
    p.add_argument("--candle-days", type=int, default=7)
    args = p.parse_args()
    NODES[args.node](args.asset, args.funding_days, args.candle_days)


if __name__ == "__main__":
    main()
