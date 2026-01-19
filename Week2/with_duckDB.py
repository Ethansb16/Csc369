import duckdb
import time
import sys


def find_most_common(start_time, end_time):
    print(f"finding results for ==> {start_time} to {end_time}")
    start_time_str = start_time + ":00:00"
    end_time_str = end_time + ":00:00"

    # connect to db
    con = duckdb.connect()

    # query to filter to table with pixel and color sorted
    query = """
    SELECT
        pixel_color,
        coordinate,
        COUNT(*) as count
    FROM read_csv_auto('csv.csv', header=true)
    WHERE timestamp >= ? AND timestamp < ?
    GROUP BY pixel_color, coordinate
    ORDER BY count DESC
    """

    # pull color from table above
    color_query = """
    SELECT
        pixel_color,
        COUNT(*) as count
    FROM read_csv_auto('csv.csv', header=true)
    WHERE timestamp >= ? AND timestamp < ?
    GROUP BY pixel_color
    ORDER BY count DESC
    LIMIT 1
    """

    # pull pixel from table 
    pixel_query = """
    SELECT
        coordinate,
        COUNT(*) as count
    FROM read_csv_auto('csv.csv', header=true)
    WHERE timestamp >= ? AND timestamp < ?
    GROUP BY coordinate
    ORDER BY count DESC
    LIMIT 1
    """

    color_result = con.execute(color_query, [start_time_str, end_time_str]).fetchone()
    pixel_result = con.execute(pixel_query, [start_time_str, end_time_str]).fetchone()

    con.close()

    if color_result and pixel_result:
        most_common_color = (color_result[0], color_result[1])
        most_common_pixel = (pixel_result[0], pixel_result[1])
        return most_common_color, most_common_pixel
    else:
        return None, None


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
