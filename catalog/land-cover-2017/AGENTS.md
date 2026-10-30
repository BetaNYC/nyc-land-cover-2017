# AGENTS.md — NYC Land Cover 2017 (6-inch, 8 classes)

Guidance for agents and scripts that read this collection. Every fact here is
quoted from a source named in [README.md](README.md) or measured from the
published file with the code shown. Every code block marked for checking runs
weekly against the published data (`tests/check_published.py` in the
[repository](https://github.com/BetaNYC/nyc-land-cover-2017)).

## What it is

One Cloud Optimized GeoTIFF covering New York City:

```
https://data.source.coop/betanyc/nyc-land-cover-2017/land-cover-2017/nyc-land-cover-2017.tif
```

The grid, CRS, and file facts are in `collection.json` (`proj:*`, `bands`) and
the [README](README.md). What matters for code: one `uint8` band of 0.5 ft
pixels in EPSG:2263 (US survey feet), 0 is NoData outside the city boundary,
and the internal overviews use nearest-neighbour sampling, so every overview
pixel is a real class value.

| Value | Class | Source definition |
|---:|---|---|
| 1 | Tree Canopy | Vegetation over 8 ft, including canopy over other features |
| 2 | Grass/Shrubs | Vegetation 8 ft or lower |
| 3 | Bare Soil | Not defined beyond the name |
| 4 | Water | Not defined beyond the name |
| 5 | Buildings | Not defined beyond the name |
| 6 | Roads | Not defined beyond the name |
| 7 | Other Impervious | Not defined beyond the name |
| 8 | Railroads | Not defined beyond the name. Part of Roads in the 2010 map |

Exact pixel counts and shares for every class are in `collection.json`, under
`assets.data.bands[0]["classification:classes"]`. Do not recompute them from the
full-resolution file. They came from a full pass over every pixel and match
the source attribute table exactly.

## Recipes

These need GDAL 3.x, or Python with `rasterio`, `pyproj`, and `numpy`. None of
them downloads the whole file. A COG reader fetches only the tiles it needs.

### The class at a point

`gdallocationinfo` takes longitude then latitude with `-wgs84`. This point is
in Central Park:

<!-- check -->
```bash
gdallocationinfo -valonly -wgs84 \
  /vsicurl/https://data.source.coop/betanyc/nyc-land-cover-2017/land-cover-2017/nyc-land-cover-2017.tif \
  -73.9654 40.7829
```

It prints `2`, Grass/Shrubs.

### Class areas inside a bounding box, at full resolution

Transform the box to EPSG:2263 first. Each pixel is 0.25 sq ft, and an acre is
43,560 sq ft. The box below is in Lower Manhattan:

<!-- check -->
```python
import numpy as np, rasterio
from rasterio.windows import from_bounds
from pyproj import Transformer

URL = ("https://data.source.coop/betanyc/nyc-land-cover-2017/"
       "land-cover-2017/nyc-land-cover-2017.tif")
NAMES = {1: "Tree Canopy", 2: "Grass/Shrubs", 3: "Bare Soil", 4: "Water",
         5: "Buildings", 6: "Roads", 7: "Other Impervious", 8: "Railroads"}

to_2263 = Transformer.from_crs("EPSG:4326", "EPSG:2263", always_xy=True)
xmin, ymin = to_2263.transform(-74.0170, 40.7000)
xmax, ymax = to_2263.transform(-74.0000, 40.7130)
with rasterio.open(URL) as ds:
    a = ds.read(1, window=from_bounds(xmin, ymin, xmax, ymax, ds.transform))

values, counts = np.unique(a[a != 0], return_counts=True)
total = counts.sum()
for v, n in zip(values, counts):
    print(f"{NAMES[v]:<17} {n * 0.25 / 43560:8.1f} acres {100 * n / total:5.1f}%")
```

Output:

```
Tree Canopy           45.8 acres   8.9%
Grass/Shrubs           9.3 acres   1.8%
Bare Soil              0.5 acres   0.1%
Water                113.2 acres  22.1%
Buildings            149.3 acres  29.1%
Roads                 87.0 acres  17.0%
Other Impervious     107.3 acres  20.9%
```

For a polygon (a borough, a park, a census tract), reproject the polygon to
EPSG:2263 and read it with `rasterio.mask.mask(ds, [geometry], crop=True)`.

### Fast estimates for the whole city from an overview

Overview level 4 has 16 ft pixels (9,714 x 9,826), about 95 million pixels
instead of 97.7 billion:

<!-- check -->
```python
import numpy as np, rasterio

URL = ("https://data.source.coop/betanyc/nyc-land-cover-2017/"
       "land-cover-2017/nyc-land-cover-2017.tif")
with rasterio.open(URL, overview_level=4) as ds:
    a = ds.read(1)
values, counts = np.unique(a[a != 0], return_counts=True)
for v, n in zip(values, counts):
    print(v, f"{100 * n / counts.sum():.2f}%")
```

Because overviews sample the nearest pixel, the result is an estimate. At this
level every class share is within 0.1 percentage points of the exact share in
`collection.json`. This check prints any class that is not:

<!-- claim -->
```python
import json, urllib.request
import numpy as np, rasterio

BASE = "https://data.source.coop/betanyc/nyc-land-cover-2017/land-cover-2017/"
col = json.load(urllib.request.urlopen(BASE + "collection.json"))
exact = {c["value"]: c["percentage"]
         for c in col["assets"]["data"]["bands"][0]["classification:classes"]
         if not c.get("nodata")}
with rasterio.open(BASE + "nyc-land-cover-2017.tif", overview_level=4) as ds:
    a = ds.read(1)
values, counts = np.unique(a[a != 0], return_counts=True)
for v, n in zip(values, counts):
    est = 100 * n / counts.sum()
    if abs(est - exact[int(v)]) >= 0.1:
        print(v, round(est, 3), exact[int(v)])
```

### Labels and colours from the metadata

<!-- check -->
```python
import json, urllib.request

BASE = "https://data.source.coop/betanyc/nyc-land-cover-2017/land-cover-2017/"
col = json.load(urllib.request.urlopen(BASE + "collection.json"))
for c in col["assets"]["data"]["bands"][0]["classification:classes"]:
    print(c["value"], c["title"], c.get("color_hint", "transparent"),
          c.get("percentage", ""))
```

## Quirks that produce silently wrong answers

- **Feet, not metres.** Coordinates and pixel sizes are US survey feet. A pixel
  is 0.25 sq ft, about 0.0232 square metres. Divide pixel counts by 174,240 for
  acres.
- **Water includes the harbor.** The map covers everything inside the city
  boundary, including open water out to that line. Water is the largest class
  (its `percentage` is in `collection.json`). A "share of NYC" computed over all valid pixels
  counts the harbor. Exclude class 4 for land-only shares.
- **Top-down mapping.** Tree canopy that overhangs a road, building, or lawn is
  classed as Tree Canopy. Roads, Buildings, and Other Impervious therefore
  measure what is visible from above, not the full paved or built area.
- **Mixed dates.** Tree Canopy and Buildings are current as of 2017 (LiDAR,
  May 2017). The other classes are current as of 2016 (orthophotography).
- **Comparing with 2010.** The 2010 map has 7 classes, with railroads inside
  Roads (6). Reassign 8 to 6 before you compare.
- **Bare Soil is the least reliable class.** The source reports user's and
  producer's accuracies of 89% and 82% for it, against more than 94% for every
  other class.
- **Do not read the whole band into memory.** At full resolution it is 97.7 GB
  of `uint8`. Use windows, masks, or overviews.
- **Overviews are samples.** Counts from an overview are estimates (see the
  check above). Use full resolution or the counts in `collection.json` for
  exact figures.
- **The source's own histogram is scaled.** The `.aux.xml` in the original zip
  holds class counts divided by 21.64. Its proportions are right, its counts
  are not.

## Join keys

None. This is a single raster. Combine it with vector data by zonal statistics
after reprojecting the vectors to EPSG:2263.

## Related datasets

Not in this catalog. Both are on NYC Open Data:

- [Landcover Raster Data (2010) – 6in Resolution](https://data.cityofnewyork.us/d/sknu-4f6s),
  the 7-class predecessor. Merge class 8 into 6 here before comparing.
- [Tree Canopy Change (2010 - 2017)](https://data.cityofnewyork.us/d/by9k-vhck).

## Checks on the published file

These print nothing when the published file matches `collection.json`.

The file size:

<!-- claim -->
```python
import json, urllib.request

BASE = "https://data.source.coop/betanyc/nyc-land-cover-2017/land-cover-2017/"
col = json.load(urllib.request.urlopen(BASE + "collection.json"))
data = col["assets"]["data"]
req = urllib.request.Request(data["href"], method="HEAD")
size = int(urllib.request.urlopen(req).headers["Content-Length"])
if size != data["file:size"]:
    print("size", size, "!=", data["file:size"])
```

The embedded statistics:

<!-- claim -->
```python
import json, urllib.request
import rasterio

BASE = "https://data.source.coop/betanyc/nyc-land-cover-2017/land-cover-2017/"
col = json.load(urllib.request.urlopen(BASE + "collection.json"))
stats = col["assets"]["data"]["bands"][0]["statistics"]
with rasterio.open(col["assets"]["data"]["href"]) as ds:
    tags = ds.tags(1)
for key in ("minimum", "maximum", "mean", "stddev", "valid_percent"):
    if abs(float(tags["STATISTICS_" + key.upper()]) - stats[key]) > 1e-9:
        print(key, tags["STATISTICS_" + key.upper()], stats[key])
```
