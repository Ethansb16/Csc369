import duckdb
import polars as pl
import time
import sys
import os
import datetime as dt

# colors - english
COLOR_NAMES = {
    "#000000": "Black",
    "#00756F": "Dark Teal",
    "#009EAA": "Teal",
    "#00A368": "Green",
    "#00CC78": "Light Green",
    "#00CCC0": "Cyan",
    "#2450A4": "Dark Blue",
    "#3690EA": "Blue",
    "#493AC1": "Indigo",
    "#515252": "Dark Gray",
    "#51E9F4": "Torquise",
    "#6A5CFF": "Purple",
    "#6D001A": "Dark Red",
    "#6D482F": "Brown",
    "#7EED56": "Lime",
    "#811E9F": "Dark Purple",
    "#898D90": "Gray",
    "#94B3FF": "Light Blue",
    "#9C6926": "Dark Brown",
    "#B44AC0": "Magenta",
    "#BE0039": "Red",
    "#D4D7D9": "Light Gray",
    "#DE107F": "Pink",
    "#E4ABFF": "Light Purple",
    "#FF3881": "Hot Pink",
    "#FF4500": "Orange",
    "#FF99AA": "Light Pink",
    "#FFA800": "Gold",
    "#FFB470": "Peach",
    "#FFD635": "Yellow",
    "#FFF8B8": "Cream",
    "#FFFFFF": "White",
}

def get_color_name(hex_code):
    return COLOR_NAMES.get(hex_code.upper(), hex_code)

def run_analysis(start_time, end_time):
    start_ts = start_time + ":00:00"
    end_ts = end_time + ":00:00"
    start_dt = dt.datetime.strptime(start_ts, "%Y-%m-%d %H:%M:%S")
    end_dt = dt.datetime.strptime(end_ts, "%Y-%m-%d %H:%M:%S")

    print(f"finding results for ==> {start_time} to {end_time}")

    con = duckdb.connect()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parquet_file = os.path.join(script_dir, "data.parquet")

    results = {}
    timings = {}

    # task 1: rank colors by unique users
    t = time.perf_counter()
    color_query = """
    SELECT
        color,
        COUNT(DISTINCT user_id) as distinct_users
    FROM read_parquet(?)
    WHERE timestamp >= ?::TIMESTAMP AND timestamp < ?::TIMESTAMP
    GROUP BY color
    ORDER BY distinct_users DESC """
    color_results = con.execute(color_query, [parquet_file, start_ts, end_ts]).fetchall()
    results['colors'] = [(get_color_name(row[0]), row[1]) for row in color_results]
    timings['task1'] = (time.perf_counter() - t) * 1000

    # task 2: average session length using polars
    t = time.perf_counter()
    start_dt = pl.lit(start_ts).str.to_datetime()
    end_dt = pl.lit(end_ts).str.to_datetime()

    # filters to our time range
    df = pl.scan_parquet(parquet_file).filter(
        (pl.col("timestamp") >= start_dt) & (pl.col("timestamp") < end_dt)
    ).collect()

    sessions = (
        # sorts by user then timestamps for user, adds gap column since last placement
        df.sort(["user_id", "timestamp"])
        .with_columns(
            pl.col("timestamp").diff().over("user_id").alias("gap"))

        # adds session id column to track disjoint sessions
        .with_columns(
            (pl.col("gap").is_null() | (pl.col("gap") > pl.duration(minutes=15)))
            .cum_sum().over("user_id")
            .alias("session_id"))

        # groups by user and session adds count to filter out individual placements
        .group_by(["user_id", "session_id"])
        .agg([pl.col("timestamp").min().alias("start"),
            pl.col("timestamp").max().alias("end"),
            pl.len().alias("count")])
        
        # filters out counts less than 1, finds session length
        .filter(pl.col("count") > 1)
        .with_columns(
            (pl.col("end") - pl.col("start")).dt.total_seconds().alias("length")))

    avg_length = sessions["length"].mean()
    results['avg_session_length'] = avg_length if avg_length is not None else 0
    timings['task2'] = (time.perf_counter() - t) * 1000

    # task 3: pixel placement percentiles
    t = time.perf_counter()
    percentile_query = """
    WITH user_counts AS (
        SELECT
            user_id,
            COUNT(*) as pixel_count
        FROM read_parquet(?)
        WHERE timestamp >= ?::TIMESTAMP AND timestamp < ?::TIMESTAMP
        GROUP BY user_id)
    SELECT
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY pixel_count) as p50,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY pixel_count) as p75,
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY pixel_count) as p90,
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY pixel_count) as p99
    FROM user_counts"""
    percentile_result = con.execute(percentile_query, [parquet_file, start_ts, end_ts]).fetchone()
    results['percentiles'] = {
        'p50': percentile_result[0],
        'p75': percentile_result[1],
        'p90': percentile_result[2],
        'p99': percentile_result[3]}
    timings['task3'] = (time.perf_counter() - t) * 1000

    # task 4: first time users
    t = time.perf_counter()
    first_time_query = """
    WITH first_placements AS (
        SELECT
            user_id,
            MIN(timestamp) as first_ts
        FROM read_parquet(?)
        GROUP BY user_id
    )
    SELECT COUNT(*) as first_time_users
    FROM first_placements
    WHERE first_ts >= ?::TIMESTAMP AND first_ts < ?::TIMESTAMP"""

    first_time_result = con.execute(first_time_query, [parquet_file, start_ts, end_ts]).fetchone()
    results['first_time_users'] = first_time_result[0]
    timings['task4'] = (time.perf_counter() - t) * 1000

    con.close()

    return results, timings

def print_results(results, timings):
    print(f"task 1 ({timings['task1']} ms)")
    for i, (color, count) in enumerate(results['colors'], 1):
        print(f"{i}. {color}: {count} users")

    print(f"task 2 ({timings['task2']} ms)")
    print(f"Average session length: {results['avg_session_length']:.2f} seconds")

    print(f"task 3 ({timings['task3']} ms)")
    print(f"50th percentile: {results['percentiles']['p50']} pixels")
    print(f"75th percentile: {results['percentiles']['p75']} pixels")
    print(f"90th percentile: {results['percentiles']['p90']} pixels")
    print(f"99th percentile: {results['percentiles']['p99']} pixels")

    print(f"task 4 ({timings['task4']} ms)")
    print(f"first time users: {results['first_time_users']}")

    total = sum(timings.values())
    print(f"total: {total} ms")


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("invalid input format")

    start_time = f"{sys.argv[1]} {sys.argv[2]}"
    end_time = f"{sys.argv[3]} {sys.argv[4]}"

    if end_time <= start_time:
        print("error: end time must be after start time")

    results, timings = run_analysis(start_time, end_time)
    print_results(results, timings)
