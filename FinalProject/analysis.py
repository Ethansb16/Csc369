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


# randomly sample len(signal returns) 1000 times, count how many times the sample's mean id as extreme as the real one, if p < .05 -> significant
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
def find_dips_and_measure_recovery(df):
    close = df["close"].values.astype(np.float64)
    n = len(close)

    # how much did price change over the last 5 minutes
    rolling_return = np.full(n, np.nan)
    rolling_return[DIP_LOOKBACK:] = close[DIP_LOOKBACK:] / close[:-DIP_LOOKBACK] - 1

    # what happens over the 30 mins
    forward_return = np.full(n, np.nan)
    forward_return[:n - HOLD_MINUTES] = close[HOLD_MINUTES:] / close[:n - HOLD_MINUTES] - 1

    # only look at candles where both values are available
    has_data = ~np.isnan(forward_return) & ~np.isnan(rolling_return)

    # which candles had a sharp dip
    is_dip = (rolling_return < -DIP_THRESHOLD) & has_data

    returns_after_dips = forward_return[is_dip]

    # baseline forward returns for all candles 
    baseline_returns = forward_return[has_data]

    mean_after_dips = float(np.nanmean(returns_after_dips)) if len(returns_after_dips) > 0 else np.nan

    return {
        "dip_count": int(is_dip.sum()),
        "mean_return_after_dip": mean_after_dips,
        "mean_return_after_fees": mean_after_dips - ROUND_TRIP_FEE if not np.isnan(mean_after_dips) else np.nan,
        "baseline_mean_return": float(np.nanmean(baseline_returns)),
        # raw arrays for permutation testing
        "returns_after_dips": returns_after_dips,
        "baseline_returns": baseline_returns}


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
                "mean_return_after_fees": result["mean_return_after_fees"],
                "baseline_mean_return": result["baseline_mean_return"],
                "p_value": p_value})


    results_df = pd.DataFrame(all_results)
    results_df.to_csv(os.path.join(OUTPUT_DIR, "mean_reversion_results.csv"), index=False)

    train_rows = results_df[results_df["period"] == "train"]
    test_rows = results_df[results_df["period"] == "test"]

    significant_in_train = train_rows[train_rows["p_value"] < 0.05]
    profitable_in_train = significant_in_train[significant_in_train["mean_return_after_fees"] > 0]

    print(f"train:{len(significant_in_train)}/{len(train_rows)} pairs significant (p < 0.05)")
    print(f"train:{len(profitable_in_train)}/{len(train_rows)} pairs profitable after fees")

    if len(profitable_in_train) > 0:
        # check if those same pairs hold up out of sample
        profitable_pair_names = profitable_in_train["pair"].tolist()
        test_check = test_rows[test_rows["pair"].isin(profitable_pair_names)]
        still_profitable = test_check[test_check["mean_return_after_fees"] > 0]
        print(f"test:{len(still_profitable)}/{len(test_check)} of those pairs still profitable out of sample")

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


if __name__ == "__main__":
    results = run_analysis()
    plot_results()
