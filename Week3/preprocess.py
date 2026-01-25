import polars as pl
import os

def preprocess_csv_to_parquet():
    input_csv = "../Week2/csv.csv"
    output_parquet = "data.parquet"

    df = pl.scan_csv(input_csv)

    # parse timestamp
    # map user_id strings to integers
    # split coords into x and y integers
    df = df.with_columns([
        pl.col("timestamp").str.replace(" UTC", "").str.to_datetime("%Y-%m-%d %H:%M:%S%.f").alias("timestamp"),
        pl.col("coordinate").str.replace_all('"', '').str.split(",").alias("coords"),
        pl.col("pixel_color").alias("color"),
    ]).with_columns([
        pl.col("coords").list.get(0).cast(pl.Int16).alias("x"),
        pl.col("coords").list.get(1).cast(pl.Int16).alias("y"),
    ]).with_columns([
        pl.col("user_id").rank("dense").cast(pl.UInt32).alias("user_id"),
    ]).select(["timestamp", "user_id", "color", "x", "y"])

    # write to parquet 
    df.collect().write_parquet(output_parquet, compression="zstd")


if __name__ == "__main__":
    preprocess_csv_to_parquet()
