# toyDAG Plan

Goal: build a 5-day crypto market microstructure mini-project that demonstrates trading curiosity, clean research workflow, and practical data engineering.

## Interview Story

> A small DAG-based research system that ingests crypto market data, runs reusable analyses, and produces concise trading research artifacts across carry, price discovery, liquidity, and options volatility.

Target audience: algorithmic trading / quant research interviews.

## Project Shape

Keep it simple:

```text
data/raw/          # API responses, partitioned by source/date
 data/processed/   # normalized tables
 notebooks/        # exploration only
 src/              # reusable DAG tasks + analysis code
 reports/          # final charts/tables/writeups
```

DAG idea: each node is a small script/function with explicit inputs and outputs.

```text
fetch_* -> normalize_* -> analysis_* -> report_*
```

Use boring tools first: Python, pandas/polars, requests/httpx, duckdb/parquet, matplotlib/plotly.

## Data Sources

- Binance: spot/perps, funding rates, order book snapshots, klines
- Coinbase: spot prices/order books/trades
- Kraken: spot prices/order books/trades
- Options: Deribit is probably the practical source for crypto options vol surface

## 5-Day Build Plan

### Day 1 — Market Data DAG

- [ ] Create minimal project structure
- [ ] Implement exchange clients for Binance, Coinbase, Kraken
- [ ] Fetch spot/perp candles for BTC, ETH, SOL if available
- [ ] Store raw API responses
- [ ] Normalize to common schema:
  - `exchange`
  - `symbol`
  - `timestamp`
  - `bid`
  - `ask`
  - `mid`
  - `last`
  - `volume`
- [ ] Write one sanity-check report: price series and missing-data summary

Deliverable: `reports/day1_market_data.md`

### Day 2 — Perp-Spot Basis and Funding Carry

Question: is funding compensation for crowded directional demand, and would a delta-neutral spot/perp carry trade have earned enough to justify the risks?

Key distinction:

```text
perp/spot price movement = market return
funding rate = periodic payment between long and short perp holders
basis = perp price - spot price
long spot + short perp ≈ cancels price exposure, leaving funding - costs - basis risk
```

- [ ] Pull Binance funding rates, and Coinbase/Kraken equivalents if available
- [ ] Pull matching spot and perp price history for BTC/ETH
- [ ] Build funding-rate and perp-spot basis history
- [ ] Check whether positive funding is persistent or mean-reverting
- [ ] Estimate delta-neutral carry return from long spot / short perp, ignoring execution first
- [ ] Add simple costs: taker/maker fee + borrow/slippage/capital assumption
- [ ] Plot cumulative funding PnL, basis, drawdown, annualized return, Sharpe-ish metric
- [ ] Compare BTC vs ETH and regime changes
- [ ] Highlight risks: basis widening, funding flips, liquidation/margin, exchange risk, stablecoin risk

Deliverable: `reports/day2_basis_funding_carry.md`

### Day 3 — Cross-Exchange Price Discovery

Question: which venue moves first during short-horizon price changes?

Better underlying choice: use BTC/USD or ETH/USD spot/perp, not USDC/USDT pairs. Stablecoins are useful for peg/liquidity analysis, but BTC/ETH have richer price movement and lead-lag signal.

- [ ] Normalize high-frequency trades or 1s/1m mid prices across exchanges
- [ ] Align timestamps
- [ ] Compute returns at multiple horizons: 1s, 5s, 10s, 1m
- [ ] Run cross-correlation lead/lag checks
- [ ] Optional: simple Granger causality if data quality supports it
- [ ] Identify whether Binance/Coinbase/Kraken tends to lead during volatile periods

Deliverable: `reports/day3_price_discovery.md`

### Day 4 — Order Book / Liquidity Analysis

Question: where is liquidity deepest, cheapest, and most fragile?

- [ ] Fetch top-of-book and depth snapshots
- [ ] Compute spread, depth within bps bands, imbalance, slippage for notional sizes
- [ ] Compare exchanges for BTC/ETH
- [ ] Plot liquidity over time and around volatility spikes
- [ ] Link order book metrics to price moves where possible

Deliverable: `reports/day4_liquidity.md`

### Day 5 — Options Vol Surface + Term Structure

Question: what does the options market imply about forward volatility and skew?

Use Deribit unless another exchange API is easier.

- [ ] Fetch BTC/ETH option chains
- [ ] Normalize strikes, expiries, bid/ask IV, mark IV, delta if available
- [ ] Plot volatility smile by expiry
- [ ] Plot term structure for ATM IV
- [ ] Track skew: 25-delta put IV minus call IV, or nearest-strike proxy
- [ ] Write final synthesis: carry, price discovery, liquidity, vol surface

Deliverable: `reports/day5_options_vol.md` and `reports/final_summary.md`

## Final Output

- [ ] Clean README with project motivation and screenshots
- [ ] One command to run the pipeline or selected DAG nodes
- [ ] 4–6 strong charts
- [ ] Short final writeup with findings, caveats, and next steps

## Kalshi Prediction-Market Edge Pipeline

Goal: test whether crypto prediction markets are stale or mispriced versus external BTC fair value.

Lazy first market: BTC up/down or threshold markets. Skip sports until the data pipeline works.

```text
fetch_kalshi_markets -> fetch_kalshi_prices -> fetch_btc_reference -> build_theo -> backtest_edges -> report_kalshi_btc
```

- [x] Pull Kalshi BTC-related markets and metadata
- [x] Pull historical Kalshi price candles where available
- [x] Pull BTC reference data from existing crypto sources in this repo
- [x] Build simple theo probability from spot path first; add vol/options only if needed
- [x] Compare Kalshi mid/last vs theo after spread/fee buffer
- [ ] Backtest simple rules: buy when theo - market price exceeds threshold, exit at fair/expiry
- [ ] Report hit rate, PnL, drawdown, turnover, and failure cases

Deliverable: `reports/kalshi_btc_edge.md`

## Kalshi World Cup Orderbook Overnight Capture

Goal: capture raw Kalshi order book snapshots overnight for two World Cup markets, then analyze spread/liquidity later.

Markets:
- Iraq vs Norway: `KXWCGAME-26JUN16IRQNOR-NOR`
- Argentina vs Algeria: `KXWCGAME-26JUN16ARGDZA-ARG`

Plan:
- [x] Add a tiny polling script that hits Kalshi `/markets/{ticker}/orderbook`
- [x] Store append-only JSONL under `data/raw/kalshi/orderbooks/`
- [x] Include timestamp, ticker, best YES/NO bid/ask, top 10 YES/NO depth levels, and raw orderbook payload per snapshot
- [x] Auto-discover all submarkets for both game events
- [ ] Run overnight, e.g. 30s interval for 10 hours
- [ ] Tomorrow: normalize JSONL into spread/depth time series

Run:

```bash
python -m src.capture_kalshi_orderbooks --hours 10 --interval 30
```

## Stretch Goals

Only after core deliverables work:

- [ ] Backtest funding carry with realistic execution assumptions
- [ ] Event study around large price moves
- [ ] Kalshi/Polymarket cross-market arb checks
- [ ] Historical order book depth if available from Kalshi or a third-party source
- [ ] Web dashboard
- [ ] Live data websocket ingestion
- [ ] More exchanges
- [ ] Better DAG runner

## Anti-Scope

Do not build before needed:

- custom DAG framework
- database service
- complex dashboard
- live trading
- production infra
- perfect exchange abstraction

## Progress Log

### 2026-06-15

- [x] Created initial project plan
- [x] Added first raw-data DAG node: `fetch_day1`
- [x] Added Binance funding history fetch
- [x] Added Coinbase/Kraken funding placeholders/fetchers
- [x] Added Binance/Coinbase/Kraken BTC/ETH candle fetchers for lead-lag work

### 2026-06-16

- [x] Added Kalshi BTC market/candle fetch node
- [x] Added first BTC binary theo edge snapshot using Binance spot + realized vol
