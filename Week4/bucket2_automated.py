import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import duckdb
import numpy as np
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARQUET = os.path.join(SCRIPT_DIR, "data.parquet")
OUTPUT = os.path.join(SCRIPT_DIR, "output")

def detect_clock_bots(con):
    # users with extremely regular placement intervals (CV < 0.1)
    # get CV distribution for visualization
    cv_dist = con.execute('''
        -- get the time between each consecutive placement per user
        WITH user_gaps AS (
            SELECT
                user_id,
                EXTRACT(EPOCH FROM timestamp - LAG(timestamp) OVER (
                    PARTITION BY user_id ORDER BY timestamp)) AS gap_seconds
            FROM read_parquet(?)),
        -- per-user stats, average gap and how much it varies
        user_stats AS (
            SELECT
                user_id,
                COUNT(*) AS num_gaps,
                AVG(gap_seconds) AS avg_gap,
                STDDEV(gap_seconds) AS std_gap
            FROM user_gaps
            WHERE gap_seconds IS NOT NULL
                AND gap_seconds > 0
                AND gap_seconds < 86400   -- gaps over 1 day
            GROUP BY user_id
            HAVING COUNT(*) >= 10)
        -- bucket users by CV (std / mean) in increments of 0.05
        SELECT
            FLOOR((std_gap / avg_gap) * 20) / 20.0 AS cv_bucket,
            COUNT(*) AS num_users
        FROM user_stats
        WHERE std_gap / avg_gap <= 3.0
        GROUP BY cv_bucket
        ORDER BY cv_bucket
    ''', [PARQUET]).fetchall()

    # get the bot users (CV < 0.1)
    clock_bots = con.execute('''
        -- same gap calculation as above
        WITH user_gaps AS (
            SELECT
                user_id,
                EXTRACT(EPOCH FROM timestamp - LAG(timestamp) OVER (
                        PARTITION BY user_id ORDER BY timestamp)) AS gap_seconds
            FROM read_parquet(?)),
        -- per user average and std dev of gaps
        user_stats AS (
            SELECT
                user_id,
                COUNT(*) AS num_gaps,
                AVG(gap_seconds) AS avg_gap,
                STDDEV(gap_seconds) AS std_gap
            FROM user_gaps
            WHERE gap_seconds IS NOT NULL
              AND gap_seconds > 0
              AND gap_seconds < 86400
            GROUP BY user_id
            HAVING COUNT(*) >= 10)
        -- keep only users whose CV is under 0.1 (unrealistically regular timing)
        SELECT
            user_id,
            num_gaps + 1 AS total_placements,
            ROUND(avg_gap, 1) AS avg_gap,
            ROUND(std_gap, 1) AS std_gap,
            ROUND(std_gap / avg_gap, 4) AS cv
        FROM user_stats
        WHERE std_gap / avg_gap < 0.1
        ORDER BY cv
    ''', [PARQUET]).fetchall()

    return clock_bots, cv_dist

def detect_template_bots(con):
    # users with 80%+ adjacent sequential placements
    template_bots = con.execute('''
        -- for each placement get the previous placement's coordinates
        WITH ordered AS (
            SELECT
                user_id, x, y,
                LAG(x) OVER (PARTITION BY user_id ORDER BY timestamp) AS prev_x,
                LAG(y) OVER (PARTITION BY user_id ORDER BY timestamp) AS prev_y
            FROM read_parquet(?)),
        -- count how many moves were to a adjacent pixel
        adjacency AS (
            SELECT
                user_id,
                COUNT(*) AS total_moves,
                SUM(CASE
                    WHEN ABS(x - prev_x) <= 1 AND ABS(y - prev_y) <= 1
                    THEN 1 ELSE 0
                END) AS adjacent_moves
            FROM ordered
            WHERE prev_x IS NOT NULL -- skip each user's first row
            GROUP BY user_id
            HAVING COUNT(*) >= 20)
        -- keep users where 80 percent + of moves were adjacent
        SELECT
            user_id,
            total_moves + 1 AS total_placements,
            adjacent_moves,
            ROUND(adjacent_moves * 1.0 / total_moves, 3) AS adj_ratio
        FROM adjacency
        WHERE adjacent_moves * 1.0 / total_moves >= 0.8
        ORDER BY adj_ratio DESC, total_placements DESC
    ''', [PARQUET]).fetchall()
    return template_bots

def detect_pixel_defenders(con):
    # users who place on the same coordinate 100+ times
    defenders = con.execute('''
        SELECT user_id, x, y, COUNT(*) AS times_hit
        FROM read_parquet(?)
        GROUP BY user_id, x, y
        HAVING COUNT(*) >= 100
        ORDER BY times_hit DESC
    ''', [PARQUET]).fetchall()
    return defenders

def plot_cv_distribution(cv_dist, num_clock_bots):
    buckets = [row[0] for row in cv_dist if row[0] is not None]
    counts = [row[1] for row in cv_dist if row[0] is not None]

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_facecolor('#fafafa')

    colors = ['#c0392b' if b < 0.1 else '#95a5a6' for b in buckets]
    ax.bar(buckets, counts, width=0.045, color=colors, edgecolor='none', alpha=0.8)
    ax.set_yscale('log')
    ax.set_xlabel('Coefficient of Variation (std / mean of placement gaps)', fontsize=12)
    ax.set_ylabel('Number of Users (log scale)', fontsize=12)
    ax.set_xlim(-0.05, 2.5)

    # bot zone annotation
    ax.axvline(x=0.1, color='#c0392b', linestyle='--', linewidth=2, alpha=0.8)
    ax.annotate(f'Bot zone: CV < 0.1\n({num_clock_bots:,} users)',
                xy=(0.1, ax.get_ylim()[1] * 0.3), xytext=(0.4, ax.get_ylim()[1] * 0.3),
                fontsize=11, fontweight='bold', color='#c0392b',
                arrowprops=dict(arrowstyle='->', color='#c0392b', lw=2))

    # human zone annotation
    ax.annotate('Human-typical range',
                xy=(0.7, ax.get_ylim()[1] * 0.05), fontsize=10, color='#2c3e50',
                ha='center')

    plt.title('Placement Timing Regularity Across All Users\nBots cluster near zero variance',
              fontsize=13, fontweight='bold', pad=15)
    plt.tight_layout()
    path = os.path.join(OUTPUT, 'automated_cv_distribution.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()

def plot_defender_heatmap(defenders):
    canvas = np.zeros((2000, 2000), dtype=np.float32)
    for _, x, y, hits in defenders:
        if 0 <= x < 2000 and 0 <= y < 2000:
            canvas[y, x] = hits

    fig, ax = plt.subplots(figsize=(10, 10))
    # show defended pixels on a dark canvas
    mask = canvas > 0
    ax.imshow(np.ones((2000, 2000, 3)) * 0.15, aspect='equal')

    if mask.any():
        ys, xs = np.where(mask)
        hits = canvas[mask]
        sc = ax.scatter(xs, ys, c=hits, cmap='YlOrRd', s=2, alpha=0.9,
                        norm=matplotlib.colors.LogNorm(vmin=100, vmax=max(hits)))
        plt.colorbar(sc, ax=ax, label='Times defended (same user, same pixel)', shrink=0.8)

    ax.set_xlim(0, 2000)
    ax.set_ylim(2000, 0)
    ax.set_title('Pixel Defender Bot Locations\nEach dot = one user defending a single pixel 100+ times',
                 fontsize=13, fontweight='bold')
    ax.set_xlabel('X coordinate')
    ax.set_ylabel('Y coordinate')

    plt.tight_layout()
    path = os.path.join(OUTPUT, 'automated_defender_heatmap.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()

if __name__ == "__main__":
    con = duckdb.connect()

    clock_bots, cv_dist = detect_clock_bots(con)
    template_bots = detect_template_bots(con)
    defenders = detect_pixel_defenders(con)

    con.close()

    plot_cv_distribution(cv_dist, len(clock_bots))
    plot_defender_heatmap(defenders)

    # timing bots
    print(f"Timing bots: {len(clock_bots):,}")
    print(f"\n{'User ID'} {'Placements'} {'Avg Gap'} {'Std Dev'} {'CV'}")
    for user_id, placements, avg_gap, std_gap, cv in clock_bots[:5]:
        print(f"{user_id} {placements} {avg_gap}s {std_gap}s {cv}")

    # template bots
    print(f"\nTemplate bots: {len(template_bots):,}")
    print(f"\n{'User ID'} {'Placements'} {'Adjacent'} {'Ratio'}")
    for user_id, placements, adjacent, ratio in template_bots[:5]:
        print(f"{user_id} {placements} {adjacent} {ratio:.0%}")

    # pixel defenders
    unique_defenders = len(set(row[0] for row in defenders))
    print(f"\nPixel defenders: {unique_defenders} unique users")
    print(f"\n{'User ID'} {'Pixel'} {'Times Defended'}")
    for user_id, x, y, times in defenders[:5]:
        print(f"{user_id} ({x}, {y}) {times}")

    # total unique bots
    all_bot_ids = set(row[0] for row in clock_bots) | set(row[0] for row in template_bots) | set(row[0] for row in defenders)
    print(f"\nTotal unique bot accounts: {len(all_bot_ids)}")
