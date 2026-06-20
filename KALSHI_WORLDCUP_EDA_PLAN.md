# Kalshi World Cup EDA Blog Post Plan

Goal: use the Kalshi World Cup orderbook and trade data we collected to search for tradable signals or useful features that predict short/medium-term in-match price changes over `1, 5, 15, 30, 60` minute horizons.

Output path:

```text
notebooks/04_kalshi_worldcup_blog_eda.ipynb
reports/kalshi_worldcup_eda_blog.md
```

## Core Question

Can orderbook structure, trade intensity, and cross-outcome pressure help predict short-horizon price changes during a match?

We are not trying to prove a production strategy yet. First pass is EDA:

- What moved prices?
- When was trading most active?
- Did the three outcome markets move together coherently?
- Did imbalance or trade pressure lead price movement?
- What outside match information would have helped explain jumps?

## Data We Have

### Orderbook snapshots

Stored under:

```text
data/raw/kalshi/orderbooks/
```

Each snapshot includes:

- timestamp
- event ticker
- submarket ticker
- YES bid/ask
- NO bid/ask
- top 10 YES bid levels
- top 10 NO bid levels
- derived YES ask levels from NO bids
- derived NO ask levels from YES bids
- raw Kalshi orderbook payload

### Trade prints

Stored under:

```text
data/raw/kalshi/trades/
```

Each trade includes:

- timestamp
- ticker
- YES price
- NO price
- trade size / `count_fp`
- taker side / aggressor side fields

## Methodology Section

### 0. Fetching and normalization

Explain the data collection process:

- orderbooks polled every ~30 seconds during active match windows
- trade prints fetched after settlement using Kalshi historical trades API
- all timestamps converted to UTC
- markets grouped by event ticker
- each match has three mutually exclusive outcomes: team A, team B, tie

Important normalization check:

```text
Buying YES at p is economically equivalent to selling NO at 1 - p.
Buying NO at q is economically equivalent to selling YES at 1 - q.
```

So for each outcome we should collapse into one YES-price view:

- YES bid = direct YES bid
- YES ask = `1 - best NO bid`
- YES mid = `(YES bid + YES ask) / 2`
- YES-side buy pressure = visible demand to buy YES
- YES-side sell pressure = visible demand to buy NO, converted into YES ask liquidity

Deliverable checks:

- [ ] Verify existing snapshots already store direct and derived YES/NO sides correctly
- [ ] Build a clean normalized table with one row per `(event, outcome, timestamp)`
- [ ] Build one normalized trades table with all trades represented as YES-price trades

### 0.5 Prediction targets

Create forward return targets for each outcome:

```text
ret_1m  = YES_mid(t + 1m)  - YES_mid(t)
ret_5m  = YES_mid(t + 5m)  - YES_mid(t)
ret_15m = YES_mid(t + 15m) - YES_mid(t)
ret_30m = YES_mid(t + 30m) - YES_mid(t)
ret_60m = YES_mid(t + 60m) - YES_mid(t)
```

Use `merge_asof` with timestamp tolerance so uneven 30-second polling does not break labels.

Also create directional targets:

```text
up_5m = ret_5m > 0
large_move_5m = abs(ret_5m) >= threshold
```

Deliverable checks:

- [ ] Drop rows too close to match end where future target is unavailable
- [ ] Avoid leakage from settlement period unless explicitly analyzing settlement
- [ ] Split results by match and outcome

## Blog / Notebook Components

### 1. Trading activity intensity through the match

Questions:

- When does volume cluster?
- Does volume spike near goals, late-game pressure, or settlement?
- Are trade counts and contract volume telling different stories?

Plots:

- contracts traded per minute by outcome
- trade count per minute by outcome
- cumulative volume by outcome
- volume share over time across the three outcomes

Features:

```text
volume_1m
volume_5m
trade_count_1m
avg_trade_size_1m
aggressive_yes_volume_1m
aggressive_no_volume_1m
```

### 2. Correlation between main market and submarkets

In this dataset, each match has three outcome submarkets rather than a separate parent/main contract.

Represent the whole match as a three-outcome simplex:

```text
P(home), P(away), P(draw)
```

Questions:

- Do the three outcomes move as a coherent probability system?
- When one outcome rallies, which outcome sells off most?
- Does total implied probability stay near 1?

Metrics:

```text
sum_bid = bid_home + bid_away + bid_draw
sum_mid = mid_home + mid_away + mid_draw
sum_ask = ask_home + ask_away + ask_draw
```

Arb sanity checks:

```text
sum_ask < 1  -> buying all outcomes appears underpriced before fees/slippage
sum_bid > 1  -> selling all outcomes appears overpriced, but short/margin constraints matter
```

Plots:

- three outcome mids over time
- rolling correlation matrix of outcome returns
- sum of bid/mid/ask over time
- ternary/simplex-style view if useful, otherwise skip

### 3. Orderbook imbalance vs future returns

Definitions:

For each outcome, build combined YES-view book:

```text
buy_depth_N  = sum top N YES bid quantities
sell_depth_N = sum top N YES ask quantities, derived from NO bids
imbalance_N = buy_depth_N / (buy_depth_N + sell_depth_N)
centered_imbalance_N = imbalance_N - 0.5
```

Use levels:

```text
N = 1, 5, 10
```

Also create market-normalized pressure:

```text
outcome_depth_share = buy_depth_N(outcome) / sum buy_depth_N(all outcomes)
outcome_mid_share = mid(outcome) / sum mid(all outcomes)
excess_pressure = outcome_depth_share - outcome_mid_share
```

Questions:

- Does high imbalance predict positive future returns?
- Is top-1 too noisy and top-10 more stable?
- Does imbalance work better early/mid/late match?

Tables:

- correlation of `imbalance_1/5/10` vs `ret_1m/5m/15m/30m/60m`
- bucketed forward returns by imbalance quintile
- same analysis by match and outcome

### 4. Other microstructure features vs targets

Features:

```text
lagged_mid_return_1m
lagged_mid_return_5m
spread
spread_pct
pressure_change_1m
pressure_change_5m
volume_1m
volume_5m
trade_count_1m
aggressive_yes_share_1m
time_to_close_minutes
sum_mid_deviation_from_1
```

Questions:

- Is momentum or mean reversion stronger at short horizons?
- Does wide spread reduce predictability or just increase execution cost?
- Does pressure change matter more than pressure level?
- Does predictive power increase near match end?

Tables:

- feature correlation matrix vs targets
- univariate bucket analysis
- simple baseline regression/classifier only if EDA suggests signal

No complex ML yet. If a feature does not show monotonic bucket behavior or stable cross-match behavior, do not overfit it.

### 5. Alternative data and match narration

Useful missing data: text/event narration of each match.

Goal: align market moves with match events:

- goals
- red/yellow cards
- substitutions
- penalties
- injury time
- dangerous attacks / shots on target
- halftime/fulltime

Possible sources:

- public live match commentary pages
- sports news live blogs
- ESPN / FotMob / Flashscore / BBC live text, depending availability
- official FIFA match center if available
- Kalshi event comments/channel if accessible
- manual annotation for first few matches if scraping is painful

Approach:

1. Start manual for 2–3 matches:
   - create `data/raw/sports_narration/manual_match_events.csv`
   - columns: `event_ticker, ts, minute, event_type, team, text, source`
2. Use this to annotate price/volume charts.
3. Only automate scraping after the manual version proves useful.

Desired chart:

- YES mid over time
- trade volume bars
- vertical markers for goals/cards/halftime/fulltime

This helps answer whether imbalance predicted price moves before public match events, or merely reacted after obvious news.

## Notebook Outline

```text
notebooks/04_kalshi_worldcup_blog_eda.ipynb
```

Sections:

1. Load orderbooks/trades
2. Normalize YES-view orderbook and trades
3. Build prediction targets
4. Volume intensity charts
5. Three-outcome market consistency / odds-sum checks
6. Imbalance feature construction
7. Feature-vs-target correlation tables
8. Bucketed return analysis
9. Alternative match narration overlay plan
10. Summary: what looks promising, what failed, what data to collect next
```

## Blog Post Outline

```text
reports/kalshi_worldcup_eda_blog.md
```

Draft structure:

1. Motivation: can in-match prediction-market microstructure reveal short-horizon signal?
2. Data collection: Kalshi orderbook snapshots + historical trade prints
3. Normalization: converting YES/NO books into one YES-price view
4. Trading intensity: when volume appears during matches
5. Three-outcome market behavior: how probabilities move together
6. Orderbook imbalance: definitions and first evidence
7. Other features: volume, spread, momentum, pressure changes, time to close
8. Missing context: why match narration matters
9. Takeaways: useful signals, caveats, next steps

## Caveats

- This is EDA, not a proven strategy.
- Kalshi fees and spread crossing matter.
- Limit-order fill assumptions need trade-print validation.
- Settlement period can dominate correlations and create leakage.
- Small sample size: conclusions should be framed as hypotheses.
- Sports event information may explain more than orderbook-only features.

## Implementation Control Checklist

Capabilities needed before claiming this is done:

- [x] Load every raw orderbook/trade file under `data/raw/kalshi/orderbooks/` and `data/raw/kalshi/trades/`, not just the two-match starter file.
- [x] Verify direct/derived YES/NO orderbook fields from raw rows before using them in analysis.
- [x] Normalize all orderbooks to one YES-view table and all trades to one YES-price trade table.
- [x] Generate all requested forward targets with `merge_asof` tolerance and no settlement-period leakage.
- [x] Produce notebook outputs deterministically from repo-local data only.
- [x] Save reusable derived tables/figures or make the notebook regenerate them cheaply.
- [x] Draft the blog from observed notebook results only; mark unknowns as unknown, especially match narration.
- [x] Leave one runnable smoke check for the non-trivial normalization/target logic.

Discovered implementation todos:

- [x] Include all 8 collected World Cup events: `KXWCGAME-26JUN16IRQNOR`, `KXWCGAME-26JUN16ARGDZA`, `KXWCGAME-26JUN17PORCOD`, `KXWCGAME-26JUN17ENGCRO`, `KXWCGAME-26JUN17GHAPAN`, `KXWCGAME-26JUN17UZBCOL`, `KXWCGAME-26JUN18CZERSA`, `KXWCGAME-26JUN18SUIBIH`.
- [x] Filter `KXWCGAME-26JUN18SUIBIH` trades to the orderbook capture/match window or explicitly separate pre-match historical trades; raw trades start `2026-05-23`, while orderbooks start `2026-06-18 19:50 UTC`.
- [x] Handle mixed raw filename styles (`kxwcgame-...` and `kxwcgame_...`) by reading file contents, not filename parsing.
- [x] Add a manual narration CSV only if we can source events; otherwise include the schema/overlay code and label narration as pending.
- [x] Fetch or manually enter sourced narration for `KXWCGAME-26JUN17PORCOD` before making event-causality claims; source: FIFA full-time match report.
- [x] Add narration overlay plot to notebook/blog for `KXWCGAME-26JUN17PORCOD`.
- [x] Fix narration overlay label collisions around clustered events.
- [x] Mark sourced actual match start/end on generated match-context plots.
- [x] Fix `three_outcome_example.png` zigzag/settlement-tail artifact by sorting/deduplicating 30-second buckets and plotting only the sourced match window.
- [x] Add project skill `.pi/skills/graph-sanity` for future figure checks.
- [x] Add project skill `.pi/skills/research-plan-blog-runner` for iterative plan/notebook/blog execution.
- [x] Fetch sourced narration for all 8 collected matches from FIFA full-time match reports.
- [x] Update narration plots to use event-color legend instead of text annotations.
- [x] Check Portugal-Congo DR apparent goal-to-price-jump latency; result: visible jumps appear ~76-77s after minute-derived goal stamps, but this is not exploitable-latency evidence because goal timestamps are coarse match-minute stamps and orderbooks are ~30s polls.
- [x] Expand blog explanation of feature construction and three-outcome edge columns.
- [x] Document exact data needed before claiming exploitable latency.
- [x] Add GitHub Pages-ready docs copy of the blog post at `docs/kalshi_worldcup_eda_blog.md`.
- [x] Add GitHub Pages deploy workflow at `.github/workflows/pages.yml`.
- [ ] Compare event markers against trade volume spikes for matches with both narration and trades.
- [ ] Fetch missing trade prints for `KXWCGAME-26JUN17PORCOD` if trade-side analysis needs complete event coverage.
- [ ] Decide whether approximate minute-derived UTC timestamps are good enough, or add separate `kickoff_ts` + `minute` parsing instead of hardcoded event `ts`.

## Next Actions

- [x] Create `notebooks/04_kalshi_worldcup_blog_eda.ipynb`
- [x] Build normalized orderbook/trade tables
- [x] Add target generation for 1/5/15/30/60m
- [x] Produce volume intensity plots
- [x] Produce odds-sum and three-outcome correlation plots
- [x] Compute imbalance features at top 1/5/10 levels
- [x] Run feature-vs-target correlation and bucket analysis
- [x] Add manual narration CSV schema and first sourced match events
- [x] Draft blog post from notebook outputs
