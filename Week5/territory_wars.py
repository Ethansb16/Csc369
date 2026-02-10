import duckdb
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np


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
            GROUP BY FLOOR(c.x / 20)::INT * 20, FLOOR(c.y / 20)::INT * 20, c.prev_color, c.color)
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



def plot_conflict_heatmap(grid):
   canvas = np.zeros((200, 200), dtype=np.float32)
   for gx, gy, cnt in grid:
       if 0 <= gx < 200 and 0 <= gy < 200:
           canvas[gy, gx] = cnt


   fig, ax = plt.subplots(figsize=(12, 12))
   im = ax.imshow(canvas, cmap='inferno', norm=mcolors.LogNorm(vmin=max(1, canvas[canvas > 0].min()), vmax=canvas.max()),
                  interpolation='nearest', aspect='equal')
   plt.colorbar(im, ax=ax, label='Color changes per 10x10 region', shrink=0.8)
   ax.set_title('Territory War Intensity\nColor changes per region across the full timeframe', fontsize=14, fontweight='bold')
   ax.set_xlabel('X')
   ax.set_ylabel('Y')
   plt.tight_layout()
   plt.savefig(os.path.join(OUTPUT, 'conflict_heatmap.png'), dpi=150, bbox_inches='tight')
   plt.close()




def plot_time_conflict(hourly):
   hours = [row[0] for row in hourly]
   changes = [row[1] for row in hourly]


   fig, ax = plt.subplots(figsize=(14, 5))
   ax.fill_between(range(len(hours)), changes, alpha=0.4, color='#c0392b')
   ax.plot(range(len(hours)), changes, color='#c0392b', linewidth=1.5)
   ax.set_ylabel('Color Changes (millions)', fontsize=12)
   ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x/1e6:.1f}'))
   ax.set_xlabel('Hour', fontsize=12)
   ax.set_title('Conflict Intensity Over Time\nHourly color changes across the entire canvas', fontsize=13)


   # label every 6th tick
   tick_positions = list(range(0, len(hours), 6))
   tick_labels = [str(hours[i])[5:16] for i in tick_positions]
   ax.set_xticks(tick_positions)
   ax.set_xticklabels(tick_labels, rotation=45, ha='right', fontsize=8)


   plt.tight_layout()
   plt.savefig(os.path.join(OUTPUT, 'conflict_timeline.png'), dpi=150, bbox_inches='tight')
   plt.close()




def plot_faction_battles(factions):
  # top color battles
   # across all regions: (overwritten_color -> placed_color) -> count
   battles = {}
   for rx, ry, lost, won, times in factions:
       key = (lost, won)
       battles[key] = battles.get(key, 0) + times


   # top 15 battles
   top = sorted(battles.items(), key=lambda x: -x[1])[:15]
   labels = []
   counts = []
   bar_colors = []
   for (lost, won), cnt in top:
       lost_name = COLOR_NAMES.get(lost, lost)
       won_name = COLOR_NAMES.get(won, won)
       labels.append(f'{won_name} over {lost_name}')
       counts.append(cnt)
       bar_colors.append(won)


   fig, ax = plt.subplots(figsize=(14, 6))
   bars = ax.bar(range(len(labels)), counts, color=bar_colors, edgecolor='#333', linewidth=0.5)


   # make light colors visible with dark edge
   for bar, color in zip(bars, bar_colors):
       r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
       if r + g + b > 600:
           bar.set_edgecolor('#999')
           bar.set_linewidth(1.5)


   ax.set_xticks(range(len(labels)))
   ax.set_xticklabels(labels, fontsize=8, rotation=45, ha='right')
   ax.set_ylabel('Times This Overwrite Occurred (in top contested regions)', fontsize=11)
   ax.set_title('Biggest Color Battles in the Most Contested Regions', fontsize=13, fontweight='bold')
   plt.tight_layout()
   plt.savefig(os.path.join(OUTPUT, 'faction_battles.png'), dpi=150, bbox_inches='tight')
   plt.close()





if __name__ == "__main__":
   con = duckdb.connect()


   grid = compute_conflict_grid(con)
   plot_conflict_heatmap(grid)
   total_changes = sum(row[2] for row in grid)
   print(f"color changes across canvas: {total_changes}")


   print("top 20 most contested pixels:")
   pixels = top_contested_pixels(con)
   print(f"{'Pixel'} {'Color Changes'}")
   for x, y, changes in pixels:
       print(f"({x}, {y}){changes}")


   print("faction analysis for top contested regions")
   factions = group_analysis_top_regions(con)
   plot_faction_battles(factions)


   # print per region summary
   current_region = None
   for rx, ry, lost, won, times in factions:
       region = (rx, ry)
       if region != current_region:
           current_region = region
           print(f"Region ({rx}, {ry}):")
       won_name = COLOR_NAMES.get(won, won)
       lost_name = COLOR_NAMES.get(lost, lost)
       if times >= 50:
           print(f"{won_name} overwrote {lost_name}: {times} times")


   hourly = time_conflict(con)
   plot_time_conflict(hourly)
   peak = max(hourly, key=lambda r: r[1])
   print(f"peak conflict hour: {peak[0]} with {peak[1]} color changes")

   con.close()

