# Kalshi World Cup orderbook/trade EDA

This is a first-pass EDA, not a proven strategy. It uses local orderbook snapshots and historical trade prints only.

## Data

- Orderbook rows: 5,520
- Window-filtered trade rows: 769,440
- Events: 8 orderbook events, 7 trade events, 24 outcome tickers
- Missing trade files after windowing: KXWCGAME-26JUN17PORCOD
- Normalized outputs:
  - `data/processed/kalshi_worldcup_orderbooks_normalized.parquet`
  - `data/processed/kalshi_worldcup_trades_yes_view.parquet`
  - `data/processed/kalshi_worldcup_features.parquet`

`KXWCGAME-26JUN18SUIBIH` had old pre-match prints in the trade file, so trade features use only the orderbook capture window plus two minutes. Cross-outcome sums use 30-second timestamp buckets because the three outcome books are captured sequentially, not at identical microsecond timestamps.

## Normalization checks

Direct YES asks matched `1 - NO bid`, and direct NO asks matched `1 - YES bid`; the notebook asserts this before analysis.

## Trading intensity

| event                  |   total_volume |   total_trades |   peak_1m_volume |
|:-----------------------|---------------:|---------------:|-----------------:|
| KXWCGAME-26JUN16ARGDZA |    3.31895e+07 |         207279 | 837425           |
| KXWCGAME-26JUN16IRQNOR |    2.95116e+07 |         129793 |      1.06386e+06 |
| KXWCGAME-26JUN17UZBCOL |    2.52026e+07 |         100409 |      1.40051e+06 |
| KXWCGAME-26JUN17GHAPAN |    2.32091e+07 |         121530 |      1.06021e+06 |
| KXWCGAME-26JUN18CZERSA |    1.35067e+07 |          93001 | 410325           |
| KXWCGAME-26JUN18SUIBIH |    1.27597e+07 |          76989 | 620269           |
| KXWCGAME-26JUN17ENGCRO |    8.89631e+06 |          40439 |      1.0709e+06  |

Volume was very uneven by match. That matters: any global signal can mostly be a high-volume-match artifact, so the notebook also reports by-event correlations. `KXWCGAME-26JUN17PORCOD` has orderbooks but no matching trade file in the raw folder.

## Three-outcome market behavior

Average odds sums by event:

| event                  |   sum_bid |   sum_mid |   sum_ask |   buy_all_edge |   sell_all_edge |
|:-----------------------|----------:|----------:|----------:|---------------:|----------------:|
| KXWCGAME-26JUN16ARGDZA |    0.9617 |    0.9089 |    0.9241 |         0.0759 |         -0.0383 |
| KXWCGAME-26JUN16IRQNOR |    0.9907 |    0.8618 |    0.8779 |         0.1221 |         -0.0093 |
| KXWCGAME-26JUN17ENGCRO |    0.9496 |    0.5314 |    0.5482 |         0.4518 |         -0.0504 |
| KXWCGAME-26JUN17GHAPAN |    0.9469 |    0.905  |    0.9202 |         0.0798 |         -0.0531 |
| KXWCGAME-26JUN17PORCOD |    0.9815 |    0.9773 |    0.9925 |         0.0075 |         -0.0185 |
| KXWCGAME-26JUN17UZBCOL |    0.9405 |    0.8588 |    0.8752 |         0.1248 |         -0.0595 |
| KXWCGAME-26JUN18CZERSA |    0.9504 |    0.9    |    0.9152 |         0.0848 |         -0.0496 |
| KXWCGAME-26JUN18SUIBIH |    0.9516 |    0.745  |    0.7609 |         0.2391 |         -0.0484 |

The three-outcome view treats each match as a probability simplex: one contract for each mutually exclusive outcome. For each 30-second bucket I take the latest quote for each outcome and sum across the three outcomes:

- `sum_bid = bid_home + bid_away + bid_draw`: what the market is visibly willing to pay if you sell each outcome at the best YES bid.
- `sum_mid = mid_home + mid_away + mid_draw`: rough implied probability mass before fees/slippage.
- `sum_ask = ask_home + ask_away + ask_draw`: what it costs to buy all three outcomes at the best YES ask.
- `buy_all_edge = 1 - sum_ask`: if positive, buying all outcomes appears to cost less than the $1 guaranteed payout before fees, slippage, fill risk, and stale quote risk.
- `sell_all_edge = sum_bid - 1`: if positive, selling all outcomes appears to collect more than the $1 maximum payout before fees, margin/short constraints, and fill risk.

So `buy_all_edge` and `sell_all_edge` are not strategy PnL. They are sanity checks for crossed/stale/fragmented quotes. In this sample, positive `buy_all_edge` often appears when one or more asks are stale or the market is moving quickly; it is a lead for execution analysis, not a free-arb claim.

## Feature construction

All features are computed on a single YES-price view of each outcome. Kalshi has YES and NO books, but a NO bid at `q` is economically a YES ask at `1 - q`, so the normalized quote is:

```text
yes_bid = direct YES bid
yes_ask = 1 - best NO bid
yes_mid = (yes_bid + yes_ask) / 2
spread = yes_ask - yes_bid
spread_pct = spread / yes_mid
```

Forward targets are future changes in `yes_mid`, built with `merge_asof` because snapshots are unevenly spaced:

```text
ret_1m  = yes_mid(t + 1m)  - yes_mid(t)
ret_5m  = yes_mid(t + 5m)  - yes_mid(t)
ret_15m = yes_mid(t + 15m) - yes_mid(t)
ret_30m = yes_mid(t + 30m) - yes_mid(t)
ret_60m = yes_mid(t + 60m) - yes_mid(t)
```

Rows without a future snapshot inside tolerance are left unlabeled and excluded from that horizon's correlation.

Orderbook depth features use the visible top-of-book levels in YES terms:

```text
buy_depth_N  = sum quantity in top N YES bid levels
sell_depth_N = sum quantity in top N NO bid levels, converted to YES ask-side liquidity
imbalance_N  = buy_depth_N / (buy_depth_N + sell_depth_N)
```

`imbalance_N > 0.5` means more visible depth wants to buy YES than sell YES at the sampled levels. I compute this for `N = 1, 5, 10` because top-of-book can be noisy while deeper levels may be stale.

Cross-outcome pressure compares one outcome's share of visible buy depth to its share of the match's implied probability mass:

```text
outcome_mid_share     = yes_mid(outcome) / sum_mid(all outcomes)
outcome_depth_share_N = buy_depth_N(outcome) / sum buy_depth_N(all outcomes)
excess_pressure_N     = outcome_depth_share_N - outcome_mid_share
```

A positive `excess_pressure_10` means an outcome has more visible buy-side depth than its current probability share would suggest.

Trade features are rolling windows over historical prints, aligned backward to the latest snapshot:

- `volume_1m`, `volume_5m`: contracts traded in the trailing 1/5 minutes.
- `trade_count_1m`: number of prints in the trailing minute.
- `avg_trade_size_1m`: `volume_1m / trade_count_1m`.
- `aggressive_yes_volume_1m`, `aggressive_no_volume_1m`: trailing volume where the taker side was reported as YES or NO.
- `aggressive_yes_share_1m`: aggressive YES volume divided by aggressive YES + aggressive NO volume.

Lagged market-state features are also as-of aligned:

- `lagged_mid_return_1m`, `lagged_mid_return_5m`: recent momentum/reversion in `yes_mid`.
- `pressure_change_1m`, `pressure_change_5m`: recent change in `excess_pressure_10`.
- `time_to_close_minutes`: minutes until the last snapshot for that event.
- `sum_mid_deviation_from_1`: `sum_mid - 1`, a market-wide consistency/staleness feature.

The table below is simple Pearson correlation against forward midpoint changes. It is intentionally not a model; weak or unstable correlations should be treated as leads for better data collection, not tradable signals.

## Feature evidence

Feature correlations against forward YES-mid changes:

|                          |   ret_1m |   ret_5m |   ret_15m |   ret_30m |   ret_60m |
|:-------------------------|---------:|---------:|----------:|----------:|----------:|
| imbalance_1              |    0.031 |    0.014 |     0.012 |    -0.001 |     0.051 |
| imbalance_5              |   -0.011 |    0.024 |     0.002 |    -0.017 |     0.003 |
| imbalance_10             |   -0.014 |    0.028 |     0.002 |    -0.011 |     0.045 |
| excess_pressure_10       |    0.007 |    0.039 |     0.041 |     0.059 |     0.138 |
| lagged_mid_return_1m     |    0.008 |    0.016 |    -0.02  |    -0.042 |     0.017 |
| lagged_mid_return_5m     |    0.008 |   -0.02  |    -0.088 |    -0.083 |     0.079 |
| spread                   |   -0.012 |    0.003 |     0     |    -0.017 |    -0.037 |
| spread_pct               |    0.021 |    0.037 |     0.033 |     0.056 |     0.114 |
| pressure_change_1m       |   -0.034 |   -0.009 |     0.007 |    -0.004 |     0.02  |
| pressure_change_5m       |   -0.021 |    0.044 |     0.039 |     0.041 |     0.029 |
| volume_1m                |    0.007 |   -0.004 |     0.014 |     0.045 |     0.091 |
| volume_5m                |   -0.002 |   -0     |     0.021 |     0.05  |     0.117 |
| trade_count_1m           |   -0.002 |   -0.019 |     0.017 |     0.07  |     0.136 |
| aggressive_yes_share_1m  |   -0.004 |    0.023 |    -0.009 |     0.033 |     0.066 |
| time_to_close_minutes    |   -0.002 |   -0.003 |    -0.008 |    -0.011 |    -0.017 |
| sum_mid_deviation_from_1 |   -0.001 |   -0.001 |     0.001 |    -0.022 |    -0.015 |

Largest absolute 5-minute correlations:

|                         |   ret_5m |
|:------------------------|---------:|
| pressure_change_5m      |    0.044 |
| excess_pressure_10      |    0.039 |
| spread_pct              |    0.037 |
| imbalance_10            |    0.028 |
| imbalance_5             |    0.024 |
| aggressive_yes_share_1m |    0.023 |

By-match stability check:

| event                  |   rows |   non_null_ret_5m |   imbalance_10_vs_ret_5m |   excess_pressure_10_vs_ret_5m |   volume_1m_vs_ret_5m |   lagged_mid_return_1m_vs_ret_5m |
|:-----------------------|-------:|------------------:|-------------------------:|-------------------------------:|----------------------:|---------------------------------:|
| KXWCGAME-26JUN16ARGDZA |   1971 |              1778 |                    0.029 |                         -0.099 |                 0.035 |                           -0.106 |
| KXWCGAME-26JUN16IRQNOR |    924 |               751 |                    0.053 |                         -0.03  |                -0.017 |                           -0.172 |
| KXWCGAME-26JUN17ENGCRO |    228 |                96 |                   -0.391 |                         -0.501 |                -0.047 |                           -0.287 |
| KXWCGAME-26JUN17GHAPAN |    414 |               354 |                    0.105 |                          0.2   |                 0.015 |                           -0.117 |
| KXWCGAME-26JUN17PORCOD |    777 |               729 |                    0.132 |                          0.064 |               nan     |                            0.127 |
| KXWCGAME-26JUN17UZBCOL |    423 |               316 |                    0.139 |                          0.138 |                -0.052 |                           -0.115 |
| KXWCGAME-26JUN18CZERSA |    402 |               347 |                    0.029 |                          0.161 |                -0.025 |                            0.223 |
| KXWCGAME-26JUN18SUIBIH |    381 |               258 |                   -0.326 |                         -0.182 |                 0.022 |                            0.045 |

## Read so far

- Orderbook imbalance is weakly positive at 5 minutes globally, but not stable enough to call a strategy.
- Excess pressure is computed across the three outcomes with 30-second buckets; it is useful as a market-state feature, not a standalone edge.
- Spread/odds-sum features look more like execution and market-quality warnings than free alpha.
- Settlement/end-of-match windows can dominate labels; the target builder drops rows without future snapshots and keeps this as EDA only.

## Match narration

Sourced narration now covers all 8 collected matches using FIFA full-time match reports, with goals/cards/subs/start/full-time markers. The overlay plots use colored vertical event lines and a legend instead of text labels, so clustered events remain readable.

The generated context plots mark sourced match start/end. The three-outcome example is clipped to the actual match window to avoid settlement-tail artifacts after full time.

For the Portugal-Congo DR example, the largest visible price steps after the two goals occur about 76-77 seconds after the minute-derived goal timestamp:

| goal | outcome | largest post-goal step | apparent delay |
|---|---:|---:|---:|
| POR 6' | POR | +0.110 | 76s |
| POR 6' | TIE | -0.090 | 77s |
| COD 45+5' | POR | -0.185 | 76s |
| COD 45+5' | TIE | +0.140 | 77s |

This does **not** verify exploitable latency. FIFA report timestamps are match-minute stamps, not exact goal timestamps, and our orderbooks are ~30-second polls. At best, this says we need exact live-event timestamps before making any latency claim.

To verify exploitable latency, we would need:

- Exact wall-clock timestamps for goals/cards/VAR decisions from a live feed, ideally with sub-second or one-second precision.
- The timestamp semantics of that feed: when the event happened on the field vs when the feed published it.
- Higher-frequency orderbook snapshots or streaming orderbook deltas around goals, not 30-second polls.
- Trade prints with exchange timestamps and aggressor side for the same windows.
- Our own collection timestamps with clock sync/NTP logs, so local machine delay is bounded.
- A clear executable benchmark: first public event timestamp, first quote move, first trade move, and whether a realistic order could be placed/filled after fees and spread.
- Multiple matches/events. One goal response is anecdote; latency needs a distribution.

`KXWCGAME-26JUN17PORCOD` still has no matching raw trade file, so that overlay is useful for orderbook-price context only. The other sourced matches have trade data and can now be used for price + volume + event comparisons.

## Figures

- `reports/figures/kalshi_worldcup/three_outcome_example.png`
- `reports/figures/kalshi_worldcup/imbalance_vs_ret5m.png`
- `reports/figures/kalshi_worldcup/narration_overlay_KXWCGAME-26JUN17PORCOD.png`
- `reports/figures/kalshi_worldcup/volume_*.png`
