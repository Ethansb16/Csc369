import pandas as pd
import time
import sys


def find_most_common(start_time, end_time):
    print(f"finding results for ==> {start_time} to {end_time}")

    df = pd.read_csv('csv.csv')

    # filter time
    filtered_df = df[(df['timestamp'] >= start_time) & (df['timestamp'] < end_time)]

    # find color
    color_counts = filtered_df['pixel_color'].value_counts()
    most_common_color = (color_counts.index[0], color_counts.iloc[0])

    # find coordinate
    pixel_counts = filtered_df['coordinate'].value_counts()
    most_common_pixel = (pixel_counts.index[0], pixel_counts.iloc[0])

    return most_common_color, most_common_pixel


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("incorrect input format")

    start_time = f"{sys.argv[1]} {sys.argv[2]}"
    end_time = f"{sys.argv[3]} {sys.argv[4]}"

    try:
        execution_time = time.time()

        if end_time <= start_time:
            print("end hour must be after start hour")

        color_result, pixel_result = find_most_common(start_time, end_time)

        print(f"time elapsed: {time.time() - execution_time}")
        print(f"most common color: {color_result[0]} (placed {color_result[1]} times)")
        print(f"most common pixel: {pixel_result[0]} (placed {pixel_result[1]} times)")

    except Exception as e:
        print(e)
