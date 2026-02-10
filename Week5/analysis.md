I analyzed the complete r/place 2022 dataset as a territory war: identifying the most contested pixels, the main color battles, and conflict intensity over time. Across the full canvas, there were **129,968,389** color changes (pixels overwritten with a different color).

## Most Contested Pixels

The top 20 individual pixels with the highest number of color changes:

| Pixel | Color Changes |
|-------|--------------|
| (0, 0) | 57,652 |
| (359, 564) | 48,668 |
| (349, 564) | 40,430 |
| (104, 768) | 26,298 |
| (859, 766) | 26,267 |
| (860, 766) | 26,138 |
| (633, 728) | 26,019 |
| (1999, 0) | 23,573 |
| (105, 768) | 23,507 |
| (1999, 999) | 21,533 |
| (1999, 1999) | 21,401 |
| (1058, 756) | 20,325 |
| (0, 999) | 19,712 |
| (999, 999) | 18,306 |
| (299, 372) | 16,611 |
| (420, 420) | 16,151 |
| (780, 888) | 15,496 |
| (300, 372) | 15,202 |
| (0, 1999) | 14,991 |
| (300, 373) | 14,849 |

The single most contested pixel was (0, 0), the top-left corner, with 57,652 color changes. Corner and edge pixels like (1999, 0), (0, 999), (1999, 1999), and (0, 1999) are all in the top 20, likely because they are easy coordinates to target and became natural battlegrounds. The cluster around (349–359, 564) saw over 89,000 combined changes, indicating a turf war between rival communities.

## Conflict Heatmap

[Conflict Heatmap](output/conflict_heatmap.png)

The heatmap aggregates color changes per 10x10 pixel region across the entire canvas. The hottest zones are concentrated in the lower-left quadrant (around x:100–140, y:1520–1600) and a band around y:500. These regions saw relentless overwriting.

**Script:** [`territory_wars.py`](territory_wars.py)

**Mechanism:** Uses a LAG window function partitioned by (x, y) ordered by timestamp to detect when a pixel's color changed. Changes are aggregated into a 10x10 grid and plotted with a logarithmic color scale.

## Color Battles in the Most Contested Regions

The top 10 most contested 20x20 regions were analyzed to determine which colors were fighting over them. Across these regions, the main conflict was White vs Dark Purple, with these two colors overwriting each other hundreds of thousands of times. For example, in Region (100, 1540) alone, White overwrote Dark Purple 65,427 times while Dark Purple overwrote White 64,879 times, a nearly even war.

The top battles across all contested regions:

| Battle | Overwrites |
| White over Dark Purple | ~408,000 |
| Dark Purple over White | ~390,000 |
| White over Black | ~62,000 |
| Orange over Torquise | ~34,000 |
| Torquise over Orange | ~34,000 |
| Lime over White | ~70,000 |
| White over Lime | ~72,000 |
| Light Gray over White | ~48,000 |
| Gold over Torquise | ~30,000 |
| Torquise over Gold | ~30,000 |

Secondary wars included Orange vs Torquise and Orange vs Black in the (200, 500) and (620, 460) regions, and Lime vs White across the lower left quadrant.

[Faction Battles](output/faction_battles.png)

## Conflict Intensity Over Time

[Conflict Timeline](output/conflict_timeline.png)

Conflict intensity was measured hourly across the entire canvas. The peak conflict hour was April 4, 2022 at 21:00 UTC, with **4,575,472** color changes in a single hour. This corresponds to the final hours of the event, when communities made their last pushes to secure territory and the canvas was expanded for the last time. It also was dominated by the "white out" event where the color palet was restricted to just white. 

**Mechanism:** Color changes are grouped by `date_trunc('hour', timestamp)` to create an hourly conflict timeline.

