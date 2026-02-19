import pandas as pd
import os
from glob import glob

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "binance")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "explore_output")

files = sorted(glob(os.path.join(DATA_DIR, "*.parquet")))
print(f"{len(files)} files")

sample_file = os.path.join(DATA_DIR, "BTC-USDT.parquet")
btc = pd.read_parquet(sample_file)
print(f"BTC-USDT.parquet")
print(f"Columns: {btc.columns.tolist()}")
print(f"Index name: {btc.index.name}")
print(f"Dtypes:{btc.dtypes}")
print(f"Date range: {btc.index.min()} to {btc.index.max()}")

# gaps in candles

def analyze_gaps(df, pair_name):
    idx = pd.DatetimeIndex(df.index).sort_values()
    diffs = pd.Series(idx).diff().dt.total_seconds().dropna()

    expected_seconds = 60
    gaps = diffs[diffs > expected_seconds]

    total_expected = int((idx.max() - idx.min()).total_seconds() / 60) + 1
    total_actual = len(idx)
    missing = total_expected - total_actual

    return {
        "pair": pair_name,
        "start": idx.min(),
        "end": idx.max(),
        "expected_candles": total_expected,
        "actual_candles": total_actual,
        "missing_candles": missing,
        "pct_missing": 100 * missing / total_expected if total_expected > 0 else 0,
        "num_gaps": len(gaps),
        "max_gap_minutes": gaps.max() / 60 if len(gaps) > 0 else 0,
        "median_gap_minutes": gaps.median() / 60 if len(gaps) > 0 else 0}

# scan across all 1000 pairs
all_gap_results = []
for f in files:
    pair = os.path.basename(f).replace(".parquet", "")
    df = pd.read_parquet(f)
    result = analyze_gaps(df, pair)
    all_gap_results.append(result)

gap_df = pd.DataFrame(all_gap_results)
print(f"mean missing candles: {gap_df['missing_candles'].mean()}")
print(f"median missing %: {gap_df['pct_missing'].median()}%")
print(f"pairs with >5% missing: {(gap_df['pct_missing'] > 5).sum()}")
print(f"pairs with >20% missing: {(gap_df['pct_missing'] > 20).sum()}")
print(f"max gap across all pairs: {gap_df['max_gap_minutes'].max()} minutes ({gap_df['max_gap_minutes'].max() / 60} hours)")

gap_df.to_csv(os.path.join(OUTPUT_DIR, "gap_analysis.csv"), index=False)


def check_candle_validity(df, pair_name):
    """Check for OHLC violations and anomalies."""
    issues = {}

    # high < low (impossible)
    bad_hl = (df["high"] < df["low"]).sum()
    issues["high_lt_low"] = bad_hl

    # open or close outside [low, high]
    open_out = ((df["open"] < df["low"]) | (df["open"] > df["high"])).sum()
    close_out = ((df["close"] < df["low"]) | (df["close"] > df["high"])).sum()
    issues["open_outside_range"] = open_out
    issues["close_outside_range"] = close_out

    # zero or negative prices
    issues["zero_price"] = (df[["open", "high", "low", "close"]] == 0).any(axis=1).sum()
    issues["negative_price"] = (df[["open", "high", "low", "close"]] < 0).any(axis=1).sum()

    # NaN values
    issues["any_nan"] = df.isna().any(axis=1).sum()

    # number_of_trades = 0 (but volume > 0, contradictory)
    if "number_of_trades" in df.columns:
        issues["trades_0_vol_pos"] = ((df["number_of_trades"] == 0) & (df["volume"] > 0)).sum()

    # number_of_trades at uint16 max (65535) — possible overflow
    if "number_of_trades" in df.columns:
        issues["trades_at_max"] = (df["number_of_trades"] == 65535).sum()

    # duplicate timestamps
    issues["duplicate_timestamps"] = df.index.duplicated().sum()

    return issues

print(" scan for critical issues across all pairs")
total_high_lt_low = 0
total_negative = 0
total_nan = 0
total_duplicates = 0
total_candles = 0
total_trades_overflow = 0

for f in files:
    try:
        df = pd.read_parquet(f)
        if "high" not in df.columns:
            continue
        total_candles += len(df)
        total_high_lt_low += (df["high"] < df["low"]).sum()
        total_negative += (df[["open", "high", "low", "close"]] < 0).any(axis=1).sum()
        total_nan += df.isna().any(axis=1).sum()
        total_duplicates += df.index.duplicated().sum()
        if "number_of_trades" in df.columns:
            total_trades_overflow += (df["number_of_trades"] == 65535).sum()
    except Exception as e:
        print(e)

print(f"all {len(files)} pairs ({total_candles} total candles):")
print(f"high < low violations: {total_high_lt_low}")
print(f"negative prices: {total_negative}")
print(f"rows with NaN: {total_nan}")
print(f"duplicate timestamps: {total_duplicates}")
print(f"number_of_trades at uint16 max (65535): {total_trades_overflow:,}")


# computed in gap_df
gap_df["start"] = pd.to_datetime(gap_df["start"])
gap_df["end"] = pd.to_datetime(gap_df["end"])
gap_df["duration_days"] = (gap_df["end"] - gap_df["start"]).dt.days

print(f"earliest data point: {gap_df['start'].min()}")
print(f"latest data point: {gap_df['end'].max()}")
print(f"shortest pair history: {gap_df['duration_days'].min()} days ({gap_df.loc[gap_df['duration_days'].idxmin(), 'pair']})")
print(f"longest pair history: {gap_df['duration_days'].max()} days ({gap_df.loc[gap_df['duration_days'].idxmax(), 'pair']})")
print(f"mean pair history: {gap_df['duration_days'].mean():.0f} days")
print(f"pairs with < 1 year of data: {(gap_df['duration_days'] < 365).sum()}")
print(f"pairs with > 3 years of data: {(gap_df['duration_days'] > 365*3).sum()}")

# moves >5% in 1 minute
btc["ret_1m"] = btc["close"].pct_change()
extreme = btc[btc["ret_1m"].abs() > 0.05].copy()
print(f"candles with >5% 1-min move: {len(extreme)}")
if len(extreme) > 0:
    print("10 most extreme 1-min moves:")
    extreme_sorted = extreme.sort_values("ret_1m", key=abs, ascending=False).head(10)
    for ts, row in extreme_sorted.iterrows():
        print(f"{ts}: {row['ret_1m']} (${row['close']})")


btc_overflow = (btc["number_of_trades"] == 65535).sum()
print(f"BTC-USDT candles at uint16 max (65535): {btc_overflow} / {len(btc)}")
if btc_overflow > 0:
    print(f"{100*btc_overflow/len(btc)}% of candles with potentially truncated trade counts.")
    # show when these overflows happen
    overflow_dates = btc[btc["number_of_trades"] == 65535].index
    print(f"  First overflow: {overflow_dates.min()}")
    print(f"  Last overflow: {overflow_dates.max()}")
    # monthly frequency
    monthly_overflow = btc[btc["number_of_trades"] == 65535].resample("M").size()
    peak_month = monthly_overflow.idxmax()
    print(f"peak overflow month: {peak_month.strftime('%Y-%m')} ({monthly_overflow.max()} candles)")

print(f"across all pairs, total candles at uint16 max: {total_trades_overflow}")





