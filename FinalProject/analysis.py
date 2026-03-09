import pandas as pd
import numpy as np
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "binance")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "analysis_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


TRAIN_END = "2020-12-31"
TEST_START = "2021-01-01"
FEE_PER_TRADE = 0.001 # binance charges 0.1% per trade
ROUND_TRIP_FEE = 2 * FEE_PER_TRADE # buy + sell = 0.2%
N_PERMUTATIONS = 1000
SLIPPAGE_FACTOR = 0.5 # assume you lose half the entry candle's range to slippage

DIP_LOOKBACK = 5 # how many minutes to measure the dip over
DIP_THRESHOLD = 0.02 # 2% drop triggers a "dip" signal
HOLD_MINUTES = 30 # how long to hold after a dip and measure recovery

PAIRS = [
    "BTC-USDT", "ETH-USDT", "BNB-USDT", "ADA-USDT", "XRP-USDT",
    "SOL-USDT", "DOT-USDT", "DOGE-USDT", "AVAX-USDT", "MATIC-USDT",
    "LINK-USDT", "UNI-USDT", "ATOM-USDT", "LTC-USDT", "FTM-USDT",
    "NEAR-USDT", "ALGO-USDT", "VET-USDT", "SAND-USDT", "MANA-USDT"]


def load_pair(pair_name):
    path = os.path.join(DATA_DIR, f"{pair_name}.parquet")
    return pd.read_parquet(path).sort_index()


def split_train_test(df):
    return df.loc[:TRAIN_END], df.loc[TEST_START:]


# randomly sample len(signal returns) 1000 times, count how many times the sample's mean is as extreme as the real one, if p < .05 -> significant
def permutation_test(signal_returns, all_returns):
    rng = np.random.default_rng()
    observed_mean = np.nanmean(signal_returns)
    n = len(signal_returns)
    count_as_extreme = 0
    for _ in range(N_PERMUTATIONS):
        random_sample = rng.choice(all_returns, size=n, replace=False)
        if abs(np.nanmean(random_sample)) >= abs(observed_mean):
            count_as_extreme += 1
    return count_as_extreme / N_PERMUTATIONS


# find every candle where price dropped >2% in last 5 minutes, then measure the next 30 mins
# computes both idealized returns (from dip candle close) and realistic returns (from next candle open)
# also estimates spread and slippage costs
def find_dips_and_measure_recovery(df):
    close = df["close"].values.astype(np.float64)
    open_ = df["open"].values.astype(np.float64)
    high = df["high"].values.astype(np.float64)
    low = df["low"].values.astype(np.float64)
    n = len(close)

    # how much did price change over the last 5 minutes
    rolling_return = np.full(n, np.nan)
    rolling_return[DIP_LOOKBACK:] = close[DIP_LOOKBACK:] / close[:-DIP_LOOKBACK] - 1

    # idealized forward return: enter at this candle's close, exit 30 min later at close
    forward_return = np.full(n, np.nan)
    forward_return[:n - HOLD_MINUTES] = close[HOLD_MINUTES:] / close[:n - HOLD_MINUTES] - 1

    # realistic forward return: enter at NEXT candle's open (T+1), exit at (T+1+HOLD) close
    # this accounts for the fact that you can't act until after the dip candle closes
    forward_return_realistic = np.full(n, np.nan)
    for i in range(n - HOLD_MINUTES - 1):
        if open_[i + 1] > 0:
            forward_return_realistic[i] = close[i + 1 + HOLD_MINUTES] / open_[i + 1] - 1

    # per-candle spread estimate: (high - low) / close as a proxy for effective spread
    candle_spread = (high - low) / np.where(close > 0, close, np.nan)

    # only look at candles where both values are available
    has_data = (~np.isnan(forward_return) & ~np.isnan(rolling_return)
                & ~np.isnan(forward_return_realistic))

    # which candles had a sharp dip
    is_dip = (rolling_return < -DIP_THRESHOLD) & has_data

    dip_indices = np.where(is_dip)[0]

    returns_after_dips = forward_return[is_dip]
    returns_realistic = forward_return_realistic[is_dip]
    baseline_returns = forward_return[has_data]

    # compute spread costs at entry (T+1 candle) and exit (T+1+HOLD candle)
    entry_spreads = np.array([candle_spread[i + 1] if i + 1 < n else np.nan for i in dip_indices])
    exit_spreads = np.array([candle_spread[i + 1 + HOLD_MINUTES] if i + 1 + HOLD_MINUTES < n else np.nan for i in dip_indices])

    # spread cost: pay half spread on entry + half spread on exit
    spread_cost = entry_spreads / 2 + exit_spreads / 2

    # slippage: during volatile entry candles, lose SLIPPAGE_FACTOR * candle range
    entry_slippage = entry_spreads * SLIPPAGE_FACTOR

    # returns at each cost level
    returns_after_fees = returns_realistic - ROUND_TRIP_FEE
    returns_after_spread = returns_realistic - ROUND_TRIP_FEE - spread_cost
    returns_after_all = returns_realistic - ROUND_TRIP_FEE - spread_cost - entry_slippage

    # normal candle spreads for comparison
    is_normal = (np.abs(rolling_return) <= DIP_THRESHOLD) & has_data
    normal_indices = np.where(is_normal)[0]
    normal_entry_spreads = np.array([candle_spread[i + 1] if i + 1 < n else np.nan for i in normal_indices])

    mean_after_dips = float(np.nanmean(returns_after_dips)) if len(returns_after_dips) > 0 else np.nan

    return {
        "dip_count": int(is_dip.sum()),
        "dip_indices": dip_indices,
        # idealized (original analysis)
        "mean_return_after_dip": mean_after_dips,
        "mean_return_after_fees_only": mean_after_dips - ROUND_TRIP_FEE if not np.isnan(mean_after_dips) else np.nan,
        "baseline_mean_return": float(np.nanmean(baseline_returns)),
        # realistic timing
        "mean_return_realistic": float(np.nanmean(returns_realistic)) if len(returns_realistic) > 0 else np.nan,
        # after each cost layer
        "mean_return_after_fees": float(np.nanmean(returns_after_fees)) if len(returns_after_fees) > 0 else np.nan,
        "mean_return_after_spread": float(np.nanmean(returns_after_spread)) if len(returns_after_spread) > 0 else np.nan,
        "mean_return_after_all_costs": float(np.nanmean(returns_after_all)) if len(returns_after_all) > 0 else np.nan,
        # spread info
        "mean_spread_at_entry": float(np.nanmean(entry_spreads)) if len(entry_spreads) > 0 else np.nan,
        "mean_spread_at_exit": float(np.nanmean(exit_spreads)) if len(exit_spreads) > 0 else np.nan,
        "mean_spread_normal": float(np.nanmean(normal_entry_spreads)) if len(normal_entry_spreads) > 0 else np.nan,
        # raw arrays for permutation testing and plotting
        "returns_after_dips": returns_after_dips,
        "baseline_returns": baseline_returns,
        "entry_spreads": entry_spreads,
        "normal_entry_spreads": normal_entry_spreads}


def run_analysis():
    all_results = []

    for pair in PAIRS:
        df = load_pair(pair)
        train_df, test_df = split_train_test(df)

        for period_name, period_df in [("train", train_df), ("test", test_df)]:
            if len(period_df) < 1000:
                continue

            result = find_dips_and_measure_recovery(period_df)

            # run permutation test if we have enough dip events
            if len(result["returns_after_dips"]) >= 30:
                p_value = permutation_test(result["returns_after_dips"], result["baseline_returns"])
            else:
                p_value = np.nan

            # store summary
            all_results.append({
                "pair": pair,
                "period": period_name,
                "dip_count": result["dip_count"],
                "mean_return_after_dip": result["mean_return_after_dip"],
                "mean_return_after_fees_only": result["mean_return_after_fees_only"],
                "mean_return_realistic": result["mean_return_realistic"],
                "mean_return_after_fees": result["mean_return_after_fees"],
                "mean_return_after_spread": result["mean_return_after_spread"],
                "mean_return_after_all_costs": result["mean_return_after_all_costs"],
                "mean_spread_at_entry": result["mean_spread_at_entry"],
                "mean_spread_at_exit": result["mean_spread_at_exit"],
                "baseline_mean_return": result["baseline_mean_return"],
                "p_value": p_value})


    results_df = pd.DataFrame(all_results)
    results_df.to_csv(os.path.join(OUTPUT_DIR, "mean_reversion_results.csv"), index=False)

    train_rows = results_df[results_df["period"] == "train"]
    test_rows = results_df[results_df["period"] == "test"]

    significant_in_train = train_rows[train_rows["p_value"] < 0.05]
    profitable_in_train = significant_in_train[significant_in_train["mean_return_after_fees_only"] > 0]

    print(f"\ntrain: {len(significant_in_train)}/{len(train_rows)} pairs significant (p < 0.05)")
    print(f"train: {len(profitable_in_train)}/{len(train_rows)} pairs profitable after fees only")

    # how many survive all execution costs
    profitable_after_all = significant_in_train[significant_in_train["mean_return_after_all_costs"] > 0]
    print(f"train: {len(profitable_after_all)}/{len(train_rows)} pairs profitable after all costs")

    if len(profitable_in_train) > 0:
        profitable_pair_names = profitable_in_train["pair"].tolist()
        test_check = test_rows[test_rows["pair"].isin(profitable_pair_names)]
        still_profitable_fees = test_check[test_check["mean_return_after_fees_only"] > 0]
        still_profitable_all = test_check[test_check["mean_return_after_all_costs"] > 0]
        print(f"test: {len(still_profitable_fees)}/{len(test_check)} still profitable after fees only")
        print(f"test: {len(still_profitable_all)}/{len(test_check)} still profitable after all costs")

    return results_df


def plot_results():
    btc = load_pair("BTC-USDT")
    close = btc["close"].values.astype(np.float64)
    n = len(close)

    rolling_return = np.full(n, np.nan)
    rolling_return[DIP_LOOKBACK:] = close[DIP_LOOKBACK:] / close[:-DIP_LOOKBACK] - 1

    forward_return = np.full(n, np.nan)
    forward_return[:n - HOLD_MINUTES] = close[HOLD_MINUTES:] / close[:n - HOLD_MINUTES] - 1

    has_data = ~np.isnan(forward_return) & ~np.isnan(rolling_return)
    is_dip = (rolling_return < -DIP_THRESHOLD) & has_data
    is_normal = (np.abs(rolling_return) <= DIP_THRESHOLD) & has_data

    fig, (ax_hist, ax_bars) = plt.subplots(1, 2, figsize=(14, 5))

    ax_hist.hist(forward_return[is_normal], bins=100, alpha=0.5, label="Normal candles", density=True, range=(-0.05, 0.05))
    ax_hist.hist(forward_return[is_dip], bins=50, alpha=0.7, label="After >2% dip", density=True, range=(-0.05, 0.05))
    ax_hist.axvline(x=0, color="black", linestyle="--", alpha=0.5)

    dip_mean = np.nanmean(forward_return[is_dip])
    normal_mean = np.nanmean(forward_return[is_normal])
    ax_hist.axvline(x=dip_mean, color="red", label=f"Dip mean: {dip_mean:.4f}")
    ax_hist.axvline(x=normal_mean, color="blue", label=f"Normal mean: {normal_mean:.4f}")

    ax_hist.set_xlabel("30-min Forward Return")
    ax_hist.set_ylabel("Density")
    ax_hist.set_title("BTC-USDT: Forward Returns After Dips vs Normal")
    ax_hist.legend(fontsize=8)

    # right figure
    pair_labels = []
    train_means = []
    test_means = []

    for pair in PAIRS:
        pair_df = load_pair(pair)
        train_df, test_df = split_train_test(pair_df)

        for period_df, means_list in [(train_df, train_means), (test_df, test_means)]:
            result = find_dips_and_measure_recovery(period_df)
            recovery = result["mean_return_after_dip"]
            means_list.append(recovery if not np.isnan(recovery) else 0)

        pair_labels.append(pair.replace("-USDT", ""))

    x = np.arange(len(pair_labels))
    bar_width = 0.35
    ax_bars.bar(x - bar_width / 2, [m * 100 for m in train_means], bar_width, label="Train (2017-2020)", alpha=0.8)
    ax_bars.bar(x + bar_width / 2, [m * 100 for m in test_means], bar_width, label="Test (2021-2022)", alpha=0.8)
    ax_bars.axhline(y=0, color="black", linestyle="--", alpha=0.3)
    ax_bars.axhline(y=ROUND_TRIP_FEE * 100, color="red", linestyle="--", alpha=0.5, label=f"Fee threshold ({ROUND_TRIP_FEE * 100:.1f}%)")
    ax_bars.set_xticks(x)
    ax_bars.set_xticklabels(pair_labels, rotation=45, ha="right", fontsize=7)
    ax_bars.set_ylabel("Mean 30-min Forward Return (%)")
    ax_bars.set_title("Mean Reversion After >2% Dip: Train vs Test")
    ax_bars.legend(fontsize=8)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "mean_reversion.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_cost_degradation():
    pair_labels = []
    raw_returns = []
    after_fees = []
    after_spread = []
    after_all = []

    for pair in PAIRS:
        pair_df = load_pair(pair)
        test_df = split_train_test(pair_df)[1]
        result = find_dips_and_measure_recovery(test_df)

        pair_labels.append(pair.replace("-USDT", ""))
        raw_returns.append(result["mean_return_realistic"] if not np.isnan(result["mean_return_realistic"]) else 0)
        after_fees.append(result["mean_return_after_fees"] if not np.isnan(result["mean_return_after_fees"]) else 0)
        after_spread.append(result["mean_return_after_spread"] if not np.isnan(result["mean_return_after_spread"]) else 0)
        after_all.append(result["mean_return_after_all_costs"] if not np.isnan(result["mean_return_after_all_costs"]) else 0)

    x = np.arange(len(pair_labels))
    bar_width = 0.2

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.bar(x - 1.5 * bar_width, [r * 100 for r in raw_returns], bar_width, label="Raw return (realistic timing)", alpha=0.85, color="#2196F3")
    ax.bar(x - 0.5 * bar_width, [r * 100 for r in after_fees], bar_width, label="After fees (0.2%)", alpha=0.85, color="#4CAF50")
    ax.bar(x + 0.5 * bar_width, [r * 100 for r in after_spread], bar_width, label="After fees + spread", alpha=0.85, color="#FF9800")
    ax.bar(x + 1.5 * bar_width, [r * 100 for r in after_all], bar_width, label="After fees + spread + slippage", alpha=0.85, color="#F44336")

    ax.axhline(y=0, color="black", linestyle="-", alpha=0.3)
    ax.set_xticks(x)
    ax.set_xticklabels(pair_labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Mean 30-min Return (%)")
    ax.set_title("Mean Reversion Returns Under Increasing Execution Costs (Test Period, 2021-2022)")
    ax.legend(fontsize=8)

    plt.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "cost_degradation.png"), dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    results = run_analysis()
    plot_results()
    plot_cost_degradation()
