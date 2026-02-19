# Data Quality Report

# Dataset Overview

The dataset consists of 1-minute OHLCV (Open, High, Low, Close, Volume) candlestick data for 1,000 cryptocurrency trading pairs from Binance. Data spans from July 2017 to November 2022, stored as Parquet files totaling ~33 GB. Each file contains columns: `open`, `high`, `low`, `close`, `volume`, `number_of_trades`, with a datetime index.

This dataset replaces the original QQQ/WRDS dataset referenced in `proposal.md`. The WRDS account did not have access to the data I was intersted in, so I pivoted to freely available Binance historical data, which still allows testing a similiar core hypothesis (exploitable patterns in price movements).

Overall, this data is very clean. There are no pairs missing more than 5% of their candles, no detected malformed data, no NaN rows, no negative prices, and no data lost from uint16 overflow. 


# 1 Datetime Index
The parquet files store the index as a datetime column. Pandas reads this correctly, but the index is not guaranteed to be sorted. All analysis begins by sorting the index with `sort_values()` to ensure chronological ordering before computing gaps or returns.

# 2 `number_of_trades` Stored as uint16
The `number_of_trades` column is stored as a 16-bit unsigned integer, which caps at 65,535. For high-volume pairs like BTC-USDT, candles may hit this ceiling, meaning the true trade count is truncated. This makes `number_of_trades` unreliable for any analysis that depends on accurate trade counts during high-activity periods.

# 3 Missing Data / Gaps

Across all 1,000 pairs and ~1.5 billion total candles, approximately 3.55 million candles are missing (0.24% overall). Key findings:

- Worst case: YOYO-BTC at 3.75% missing. No pair exceeds 5%.
- Only 6 out of 1,000 pairs have more than 1% missing data.
- The largest single gap observed is ~56 days (80,982 minutes) for YOYO-BTC, likely corresponding to a trading halt or delisting period.
- For most pairs, the maximum gap is under 5 hours (~286 minutes), consistent with Binance's scheduled maintenance windows.

Gaps are identified and logged in `explore_output/gap_analysis.csv`. For  analysis, gaps are handled by computing differences only between consecutive present candles. Pairs with many gaps can be filtered out using the CSV.

# 4 OHLC Validity Issues

The script checks every candle across all 1,000 pairs for:

- High < Low violations: Candles where the high price is below the low price (logically impossible).
- Open/Close outside [Low, High] range: Candles where the open or close falls outside the reported low-high range.
- Zero or negative prices: Candles with non-positive price values.

Resolution: These checks are run in `explore.py` and the counts are printed. Any rows with OHLC violations would be flagged for exclusion from analysis since they represent corrupt data.

# 5 Duplicate Timestamps

The script checks for duplicate index entries (multiple candles with the same timestamp). Duplicates would indicate data corruption or overlapping data pulls.

Duplicates are counted per pair. If found, only the first occurrence would be kept.

# 6 Pair History Length Variability

Not all pairs have the same amount of history:

- Earliest data: July 14, 2017 (BNB-BTC and other early Binance listings).
- Latest data: November 17, 2022.
- Shortest history: 368 days (SUSHIDOWN-USDT).
- Longest history: 1,951 days / ~5.3 years (BNB-BTC).
- 369 pairs have more than 3 years of data; all pairs have at least 1 year.

Any cross-pair comparison must account for differing time ranges. For the hypothesis testing, analysis focuses on pairs with sufficient history and consistent data availability.
