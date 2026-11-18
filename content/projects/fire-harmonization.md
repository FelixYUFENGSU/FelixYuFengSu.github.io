---
title: Fire Harmonization
summary: Making wildfire measurements from two generations of satellites comparable, so the fire record can continue after MODIS shuts down. California, 2012–2020.
---
For more than twenty years, a lot of what we know about wildfire activity has come from **MODIS**, an instrument on NASA's Aqua and Terra satellites. MODIS is being retired, and its successor, **VIIRS**, sees the ground in much finer detail: about 375 m pixels instead of about 1 km. That's better for spotting fires, but it means the two sensors don't report the same numbers for the same fire. Stitching their records together naively would create a fake jump in fire activity right at the handover.

This team project works on that problem using every satellite fire detection over California from 2012 to 2020.

## The key quantity: Fire Radiative Power

Each row in the data is one **active-fire detection**: a pixel that looked hot enough to contain fire. The main number attached to it is **FRP (Fire Radiative Power)**, in megawatts, roughly how much heat the fire was radiating at that moment.

Because a VIIRS pixel covers about 1/7 the area of a MODIS pixel, VIIRS records many more detections, each with a smaller FRP. The question is how the two add up. Harmonization means finding the correction that makes

$$\frac{\text{total FRP}_{\text{VIIRS}}}{\text{total FRP}_{\text{MODIS}}} \approx 1$$

for the same fires.

## Exploring the data

The first notebook looks at the raw data before any modeling:

- Detection counts and total FRP per year for each sensor, and the yearly VIIRS/MODIS ratio, which is the gap that has to be corrected
- How FRP is distributed (it spans orders of magnitude, so on a log scale)
- Day/night splits, since the sensors pass over at different times
- Pixel footprint: pixels get larger toward the edge of the satellite's swath (the "bow-tie" effect), which affects FRP
- Seasonality, with California's fire season peaking in late summer and fall
- **Persistent hotspots:** a 2 km grid cell that "burns" in many different months is almost certainly an oil field, flare, or industrial site, not a wildfire, so these are flagged as candidates to filter out before comparing sensors

## Which fire does each detection belong to?

To compare the sensors fairly, a MODIS detection and a VIIRS detection need to be looking at the **same real fire**. The second notebook focuses on the area northwest of Redding, CA and groups detections into fires with **DBSCAN**, a clustering method that joins points that are close together in space and time and labels isolated points as noise.

The clusters are then checked against an "answer key" of fires that actually burned there (Carr, Hirz, Delta, Zogg, Bully, and Bagley). A cluster counts as a match only if its dates overlap the real fire's dates **and** its center is near that fire's ignition point. Interactive controls let you change the year, the sensors, and the space and time scales, and watch the clusters merge or split.

## Tools

Python, pandas, NumPy, scikit-learn (DBSCAN), statsmodels, xarray, folium for interactive maps, and marimo notebooks. The data came from NASA FIRMS, exported through Google Earth Engine.
