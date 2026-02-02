I analyzed the complete r/place 2022 dataset to identify pixels not placed by regular human users. Two major categories of irregular activity were identified: (1) 2.3M throwaway accounts that each placed only a single pixel, many in coordinated clusters, and (2) ~18,000 automated bot accounts detectable through consistent timing, sequential spatial patterns, or obsessive single-pixel defense.


## Bucket 1: One-and-Done Accounts

Of the 10.4 million accounts that participated in r/place, 2,340,498 (22.5%) placed exactly one pixel. Additionally 1.9M placed only 2–3 pixels, bringing the total for the 3 or fewer bracket to **4,283,885** accounts (41.3%).

A single pixel placement is not suspicious alone, its reasonable for a user to place one and lose interest. However, the sheer scale and clustering patterns suggest a significant portion of these are not genuine one-time participants. When hundreds of single-use accounts place the same color in the same pixel region, within the same hour, that is coordinated behavior. This is likely the work of bot swarms deployed by communities to overwhelm competition. 

## Examples

The most concentrated clusters of single-pixel accounts, grouped by region, color, and hour:

| Region | Color | Hour (UTC) | Single-Pixel Accounts

| (1480, 1980) | Blue (#3690EA) | Apr 4, 20:00 | 652
| (1460, 1980) | Blue (#3690EA) | Apr 4, 20:00 | 631
| (1400, 1440) | White (#FFFFFF) | Apr 4, 22:00 | 571
| (1440, 1980) | Blue (#3690EA) | Apr 4, 21:00 | 565
| (1460, 1980) | Lt Blue (#94B3FF) | Apr 4, 20:00 | 552 
| (1440, 1980) | Blue (#3690EA) | Apr 4, 20:00 | 545
| (1480, 1980) | Lt Blue (#94B3FF) | Apr 4, 20:00 | 544
| (1440, 1980) | Black (#000000) | Apr 4, 21:00 | 525

The pattern is noticable: the bottom-right corner of the canvas x~1440–1480, y~1980 was spammed with single-use accounts placing blue and light blue pixels during the final evening. This region corresponds to a heavily contested area. This is likely a coordinated effort by a community using disposable accounts to win a territory war in the closing hours.

## Visualization

[Throwaway Histogram](output/throwaway_histogram.png)

**Script:** [`bucket1_throwaway.py`](bucket1_throwaway.py)

**Mechanism:** Groups all placements by `user_id` and counts totals. Users with exactly 1 placement are flagged as throwaways. Their placements are then analyzed spatially (50x50 grid) to reveal cluster patterns. A secondary query groups single-pixel placements by 20x20 region, color, and hour to find coordinated bursts.

## Bucket 2: Automated Placements

Approximately **17,959 accounts** displayed behavior consistent with automation, scripts, or bots placing pixels. This bucket combines three patterns that all point to the use of automation. 

## Timing Bots

**16,963 users** placed pixels at intervals so regular that normal human behavior is likely ruled out.

My choice of metric is the *coefficient of variation* (CV) of each user's placement gaps: standard_deviation / mean. A human user might place pixels every 5–10 minutes on average, but with high variance.  Humans get distracted, take a break, sleep, etc. This produces CV values typically in the 0.5–1.5 range. A bot running on a timer produces CV values near 0. 

The most extreme examples:

| User ID | Placements | Avg Gap | Std Dev | CV 

| 3753209064798274122 | 11 | 1201.7s | 0.2s | 0.0002
| 11478447767598980236 | 20 | 304.0s | 0.1s | 0.0003
| 3794149242530367336 | 11 | 301.1s | 0.1s | 0.0003
| 18257826769433940823 | 288 | 303.6s | 1.2s | 0.003
| 5617811564683695636 | 358 | 305.8s | 5.2s | 0.0171

User 18257826769433940823 placed 288 pixels with an average gap of 303.6 seconds and a standard deviation of just 1.2 seconds. That's a placement every 5 minutes and 3.6 seconds, plus or minus one second. No human does this. This user's script was likely set to `sleep(300)` with latency accounting for the small variation.  

## Template Bots

**983 users** placed 80% or more of their pixels in spatially adjacent positions (within 1 pixel in each direction of their previous placement), with at least 20 total placements.

These are likely pattern matching bots: scripts that reference a target image and fill in pixels one-by-one, walking across the canvas in a sequential pattern. A human placing 20+ pixels would naturally jump around checking different artworks, placing more sparatically. A bot works through a queue, placing each pixel next to the last.

| User ID | Placements | Adjacent | Ratio 

| 15297389269990531724 | 389 | 388 | 100%
| 1896552860169575729 | 126 | 125 | 100%
| 12434558990346812516 | 100 | 99 | 100%
| 5414382227185409061 | 96 | 95 | 100%
| 11782485895272664220 | 84 | 83 | 100%

User `15297389269990531724` placed 389 pixels, every single one adjacent to the last. That is a script systematically painting an image pixel by pixel

## Pixel Defenders

**139 unique users** placed on the same exact coordinate 100 or more times.

These are single-pixel defense bots. They are scripts that monitor one specific pixel and replace it whenever another participant overwrites it. The most extreme cases:

| User ID | Pixel | Times Defended 

| 17976084429917695543 | (45, 14) | 443
| 15297389269990531724 | (826, 826) | 389
| 1804403978205938850 | (459, 881) | 368
| 11816328284384778285 | (998, 1466) | 316
| 13735586095455919689 | (208, 523) | 275

User `17976084429917695543` placed a pixel at coordinate (45, 14) **443 times** over the course of the event. At a 5-minute cooldown, that's 2,215 minutes or ~37 hours of none stop defense on a single pixel. This is a bot, or a very robotic person. 

## Visualizations

[CV Distribution](output/automated_cv_distribution.png)
[Defender Heatmap](output/automated_defender_heatmap.png)

## Detection Script

**Script:** [`bucket2_automated.py`](bucket2_automated.py)

**Mechanism:** Three independent detectors run against the full dataset:
Clock detection: Computes the coefficient of variation (std/mean) of each user's inter-placement gaps. Users with CV < 0.1 and 10+ placements are flagged.
Template detection: For each user, computes the fraction of consecutive placements that are spatially adjacent. Users with 80%+ adjacency and 20+ placements are flagged.
Defender detection: Groups by (user_id, x, y) and flags any combination with 100+ occurrences.

