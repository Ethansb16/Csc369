import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import duckdb

import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARQUET = os.path.join(SCRIPT_DIR, "data.parquet")
OUTPUT = os.path.join(SCRIPT_DIR, "output")

def detect_throwaways():
    con = duckdb.connect()
    results = {}

    # query 1: placement count distribution
    dist = con.execute('''
        -- count how many placements each user made
        WITH user_counts AS (
            SELECT user_id, COUNT(*) AS cnt
            FROM read_parquet(?)
            GROUP BY user_id)
        -- group users into buckets: 1, 2, ..., 21+
        SELECT
            CASE WHEN cnt <= 20 THEN cnt ELSE 21 END AS bucket,
            COUNT(*) AS num_users,
            SUM(cnt) AS total_placements
        FROM user_counts
        GROUP BY bucket
        ORDER BY bucket
    ''', [PARQUET]).fetchall()
    results['dist'] = dist

    # overall stats
    overall = con.execute('''
        -- count placements per user
        WITH user_counts AS (
            SELECT user_id, COUNT(*) AS cnt
            FROM read_parquet(?)
            GROUP BY user_id)
        -- how many users fall into categories
        SELECT
            COUNT(*) AS total_users,
            COUNT(*) FILTER (WHERE cnt = 1) AS one_placement,
            COUNT(*) FILTER (WHERE cnt <= 3) AS three_or_fewer,
            SUM(cnt) FILTER (WHERE cnt = 1) AS single_total_placements
        FROM user_counts
    ''', [PARQUET]).fetchone()
    results['overall'] = overall

    # query 2: single placement users by hour
    hourly = con.execute('''
        -- find users who only ever placed one pixel
        WITH single_users AS (
            SELECT user_id
            FROM read_parquet(?)
            GROUP BY user_id
            HAVING COUNT(*) = 1),
        -- total placements per hour (all users)
        all_hourly AS (
            SELECT
                date_trunc('hour', timestamp) AS hour,
                COUNT(*) AS total_placements
            FROM read_parquet(?)
            GROUP BY hour),
        -- placements per hour from single-pixel users only
        single_hourly AS (
            SELECT
                date_trunc('hour', p.timestamp) AS hour,
                COUNT(*) AS single_placements
            FROM read_parquet(?) p
            SEMI JOIN single_users s ON p.user_id = s.user_id
            GROUP BY hour)
        -- combine both counts side by side
        SELECT
            a.hour,
            a.total_placements,
            COALESCE(s.single_placements, 0) AS single_placements
        FROM all_hourly a
        LEFT JOIN single_hourly s ON a.hour = s.hour
        ORDER BY a.hour
    ''', [PARQUET, PARQUET, PARQUET]).fetchall()
    results['hourly'] = hourly

    # query 3: grid of single-pixel users (50x50 bins)
    spatial = con.execute('''
        -- find single-pixel users
        WITH single_users AS (
            SELECT user_id
            FROM read_parquet(?)
            GROUP BY user_id
            HAVING COUNT(*) = 1)
        -- divide the canvas into 50x50 grid cells and count placements in each
        SELECT
            FLOOR(p.x / 50)::INT AS grid_x,
            FLOOR(p.y / 50)::INT AS grid_y,
            COUNT(*) AS cnt
        FROM read_parquet(?) p
        SEMI JOIN single_users s ON p.user_id = s.user_id
        GROUP BY grid_x, grid_y
    ''', [PARQUET, PARQUET]).fetchall()
    results['spatial'] = spatial

    # query 4: single pixel users in same area/color/time
    clusters = con.execute('''
        -- find single-pixel users
        WITH single_users AS (
            SELECT user_id
            FROM read_parquet(?)
            GROUP BY user_id
            HAVING COUNT(*) = 1),
        -- get the actual placement data for those users
        single_placements AS (
            SELECT p.user_id, p.timestamp, p.x, p.y, p.color
            FROM read_parquet(?) p
            SEMI JOIN single_users s ON p.user_id = s.user_id)
        -- group by 20x20 region, color, and hour to find clusters
        SELECT
            FLOOR(x / 20)::INT * 20 AS region_x,
            FLOOR(y / 20)::INT * 20 AS region_y,
            color,
            date_trunc('hour', timestamp) AS hour,
            COUNT(*) AS cluster_size
        FROM single_placements
        GROUP BY region_x, region_y, color, hour
        HAVING COUNT(*) >= 20 -- only keep large clusters
        ORDER BY cluster_size DESC
        LIMIT 10
    ''', [PARQUET, PARQUET]).fetchall()
    results['clusters'] = clusters

    con.close()
    return results

def plot_histogram(dist, overall):
    buckets = [row[0] for row in dist]
    users = [row[1] for row in dist]
    labels = [str(b) if b <= 20 else '21+' for b in buckets]

    fig, ax = plt.subplots(figsize=(12, 5))

    ax.bar(range(len(labels)), users, color='#e67e22')
    ax.set_yscale('log')
    ax.set_ylabel('Number of Users (log scale)', fontsize=11)
    ax.set_xlabel('Pixel Placements per User', fontsize=11)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=9)

    pct_one = overall[1] / overall[0] * 100
    pct_three = overall[2] / overall[0] * 100
    ax.set_title(f'{pct_one:.1f}% of users placed exactly 1 pixel — {pct_three:.1f}% placed 3 or fewer',
                 fontsize=12, fontweight='bold')
    plt.tight_layout()
    path = os.path.join(OUTPUT, 'throwaway_histogram.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()


if __name__ == "__main__":
    results = detect_throwaways()
    plot_histogram(results['dist'], results['overall'])
    o = results['overall']

    # overall stats
    pct_one = o[1] / o[0] * 100
    pct_three = o[2] / o[0] * 100
    print(f"total users: {o[0]:,}")
    print(f"single-pixel accounts: {o[1]} ({pct_one:.1f}%)")
    print(f"3-or-fewer accounts: {o[2]} ({pct_three:.1f}%)")

    # top clusters table
    print(f"\n{'region'} {'color'} {'hour'} {'single-pixel accounts'}")
    for region_x, region_y, color, hour, size in results['clusters']:
        print(f"({region_x}, {region_y}) {color} {str(hour)} {size}")
