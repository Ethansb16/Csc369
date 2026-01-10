from collections import Counter
from datetime import datetime
import time
import sys

def find_most_common(start_time, end_time):

    # format for faster comparison, string comparison faster than datetime
    start_str = start_time.strftime("%Y-%m-%d %H:%M")
    end_str = end_time.strftime("%Y-%m-%d %H:%M")

    color_counter = Counter()
    pixel_counter = Counter()

    print(f"finding results for ==> {start_str} to {end_str}")

    # large buffer (8mb) = faster IO 
    with open("csv.csv", 'r', encoding='utf-8', buffering=8*1024*1024) as f:
        for line in f:
            timestamp_prefix = line[:16]

            if start_str <= timestamp_prefix <= end_str:
                tokens = line.strip().split(',', maxsplit=3)

                if len(tokens) >= 4:
                    color = tokens[2]
                    pixel = tokens[3]

                    color_counter[color] += 1
                    pixel_counter[pixel] += 1

    most_common_color = color_counter.most_common(1)[0] 
    most_common_pixel = pixel_counter.most_common(1)[0]

    return most_common_color, most_common_pixel


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("incorrect input format")

    start_time = f"{sys.argv[1]} {sys.argv[2]}"
    end_time = f"{sys.argv[3]} {sys.argv[4]}"

    try:
        execution_time = time.time()

        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H")
        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H")

        if end_dt <= start_dt:
            print("end hour must be after start hour")

        color_result, pixel_result = find_most_common(start_dt, end_dt)

        print(f"time elapsed: {time.time() - execution_time}")
        print(f"most common color: {color_result[0]} (placed {color_result[1]} times)")
        print(f"most common pixel: {pixel_result[0]} (placed {pixel_result[1]} times)")
    except Exception as e:
        print(e)
