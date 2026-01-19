import pandas as pd
import time
import sys


def find_most_common(start_time, end_time):
    print(f"finding results for ==> {start_time} to {end_time}")

    color_counts = pd.Series(dtype='int64')
    pixel_counts = pd.Series(dtype='int64')

    # read in chunk instead of all at once
    for chunk in pd.read_csv('csv.csv', chunksize=1_000_000, dtype={'pixel_color': 'category', 'coordinate': 'category'}):
        filtered = chunk[(chunk['timestamp'] >= start_time) & (chunk['timestamp'] < end_time)]
        color_counts = color_counts.add(filtered['pixel_color'].value_counts(), fill_value=0)
        pixel_counts = pixel_counts.add(filtered['coordinate'].value_counts(), fill_value=0)

    most_common_color = (color_counts.idxmax(), int(color_counts.max()))
    most_common_pixel = (pixel_counts.idxmax(), int(pixel_counts.max()))

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
