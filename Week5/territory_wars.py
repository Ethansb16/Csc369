import duckdb
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARQUET = os.path.join(SCRIPT_DIR, "data.parquet")
OUTPUT = os.path.join(SCRIPT_DIR, "output")

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


def compute_conflict_grid(con):
    # how many times the color changed into 10x10 grid for a heatmap
    grid = con.execute('''
        WITH ordered AS (
            SELECT x, y, color,
                LAG(color) OVER (PARTITION BY x, y ORDER BY timestamp) AS prev_color
            FROM read_parquet(?)),
        changes AS (
            SELECT x, y
            FROM ordered
            WHERE prev_color IS NOT NULL AND color != prev_color)
        SELECT
            FLOOR(x / 10)::INT AS gx,
            FLOOR(y / 10)::INT AS gy,
            COUNT(*) AS num_changes
        FROM changes
        GROUP BY gx, gy
    ''', [PARQUET]).fetchall()
    return grid


def top_contested_pixels(con, top_n=20):
    # find the individual pixels with the most color changes
    pixels = con.execute('''
        WITH ordered AS (
            SELECT x, y, color,
                LAG(color) OVER (PARTITION BY x, y ORDER BY timestamp) AS prev_color
            FROM read_parquet(?))
        SELECT x, y, COUNT(*) AS changes
        FROM ordered
        WHERE prev_color IS NOT NULL AND color != prev_color
        GROUP BY x, y
        ORDER BY changes DESC
        LIMIT ?
    ''', [PARQUET, top_n]).fetchall()
    return pixels


def group_analysis_top_regions(con, top_n=10):
    # find per region color details (how many times overwritten, to what color)
    factions = con.execute('''
        -- find the most contested 20x20 regions
        WITH ordered AS (
            SELECT x, y, color, timestamp,
                LAG(color) OVER (PARTITION BY x, y ORDER BY timestamp) AS prev_color
            FROM read_parquet(?)),
        changes AS (
            SELECT x, y, color, prev_color
            FROM ordered
            WHERE prev_color IS NOT NULL AND color != prev_color),
        region_conflict AS (
            SELECT
                FLOOR(x / 20)::INT * 20 AS rx,
                FLOOR(y / 20)::INT * 20 AS ry,
                COUNT(*) AS total_changes
            FROM changes
            GROUP BY rx, ry
            ORDER BY total_changes DESC
            LIMIT ?),
        -- for those top regions, get the color battles
        region_colors AS (
            SELECT
                FLOOR(c.x / 20)::INT * 20 AS rx,
                FLOOR(c.y / 20)::INT * 20 AS ry,
                c.prev_color AS attacker_lost,
                c.color AS attacker_won,
                COUNT(*) AS times
            FROM changes c
            INNER JOIN region_conflict r
                ON FLOOR(c.x / 20)::INT * 20 = r.rx
                AND FLOOR(c.y / 20)::INT * 20 = r.ry
            GROUP BY rx, ry, c.prev_color, c.color)
        SELECT rx, ry, attacker_lost, attacker_won, times
        FROM region_colors
        ORDER BY rx, ry, times DESC
    ''', [PARQUET, top_n]).fetchall()
    return factions


def time_conflict(con):
    # conflict intensity per hour across the map
    hourly = con.execute('''
        WITH ordered AS (
            SELECT x, y, color, timestamp,
                LAG(color) OVER (PARTITION BY x, y ORDER BY timestamp) AS prev_color
            FROM read_parquet(?))
        SELECT
            date_trunc('hour', timestamp) AS hour,
            COUNT(*) AS color_changes
        FROM ordered
        WHERE prev_color IS NOT NULL AND color != prev_color
        GROUP BY hour
        ORDER BY hour
    ''', [PARQUET]).fetchall()
    return hourly


def final_vs_peak_colors(con):
    # final color vs what color was placed most (who won the war)
    summary = con.execute('''
        -- final color per pixel
        WITH last_color AS (
            SELECT x, y, color AS final_color
            FROM (
                SELECT x, y, color,
                    ROW_NUMBER() OVER (PARTITION BY x, y ORDER BY timestamp DESC) AS rn
                FROM read_parquet(?))
            WHERE rn = 1),
        -- most frequently placed color per pixel
        most_freq AS (
            SELECT x, y, color AS freq_color
            FROM (
                SELECT x, y, color, COUNT(*) AS cnt,
                    ROW_NUMBER() OVER (PARTITION BY x, y ORDER BY COUNT(*) DESC) AS rn
                FROM read_parquet(?)
                GROUP BY x, y, color)
            WHERE rn = 1)
        SELECT
            l.final_color,
            m.freq_color,
            COUNT(*) AS pixels
        FROM last_color l
        JOIN most_freq m ON l.x = m.x AND l.y = m.y
        WHERE l.final_color != m.freq_color
        GROUP BY l.final_color, m.freq_color
        ORDER BY pixels DESC
        LIMIT 15
    ''', [PARQUET, PARQUET]).fetchall()
    return summary



