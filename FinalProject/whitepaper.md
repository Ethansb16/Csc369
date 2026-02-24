# Exploitable Patterns in Cryptocurrency Price Data

# Hypothesis

There are exploitable patterns in cryptocurrency price movements that, after accounting for transaction costs, produce returns statistically different from random chance. This hypothesis was drawn from observation of recurring patterns while watching crypto markets. To test it, I defined a pattern as "exploitable" only if it passes three filters: (1) statistically significant at p < 0.05 via permutation testing, (2) net-positive after Binance's 0.1% per-trade fee (0.2% round-trip), and (3) persists out-of-sample in an seperate test period.

# Data

The dataset consists of 1-minute OHLCV (Open, High, Low, Close, Volume) candlestick data for 1,000 cryptocurrency trading pairs from Binance, spanning August 2017 to November 2022 (~1.5 billion candles, ~33 GB of Parquet files). Data quality analysis (see `data_quality.md`) confirmed no pairs exceed 5% missing candles, no OHLC violations, no NaN rows, and no negative prices. This analysis focuses on the 20 most liquid USDT pairs (BTC, ETH, BNB, ADA, XRP, SOL, DOT, DOGE, AVAX, MATIC, LINK, UNI, ATOM, LTC, FTM, NEAR, ALGO, VET, SAND, MANA). Data was split into a training period (2017-2020) and an out-of-sample test period (2021-2022) to guard against overfitting and check validity of the strategy.

# Method

The pattern tested was mean reversion after extreme moves. A 1,000-iteration permutation test assessed statistical significance by comparing the pattern's mean forward return against randomly sampled subsets of the same size from the unconditional return distribution.

Mean Reversion After Extreme Moves: When a coin's price drops more than 2% over a 5-minute rolling window, I measured the 30-minute forward return. The hypothesis is that sharp dips partially revert as liquidity returns and panic selling subsides.

# Results

# Mean Reversion Is Supported

Mean reversion after extreme dips was a strong finding. In the training period, 17 of 20 pairs showed statistically significant (p < 0.05) positive forward returns after dips exceeding 2% in 5 minutes. All 17 remained net-positive after the 0.2% round-trip fee. In the out-of-sample test period, all 17 of those pairs continued to show profitable reversion, with mean after-fee returns actually increasing from 0.43% to 0.75% per trade. This is consistent with the idea that crypto markets became more volatile in 2021-2022 during the bull run and increased popularity, providing more extreme reversion opportunities.

[Mean Reversion Results](analysis_output/mean_reversion.png)

The left panel shows BTC-USDT's forward return distribution after dips (orange) versus normal candles (blue), with a clear rightward shift. The right panel shows every pair's mean reversion return clears the fee threshold (red dashed line) in both periods.

## Conclusion

The hypothesis that exploitable patterns exist in cryptocurrency price data is intially supported. Mean reversion after extreme dips passed all three filters: statistical significance, fee survival, and out-of-sample persistence across 17 of 20 pairs. The results suggest that crypto markets still contain short-term mean-reversion inefficiencies, likely driven by the mechanics of liquidation cascades and panic selling that temporarily push prices away from equilibrium before reverting back.
