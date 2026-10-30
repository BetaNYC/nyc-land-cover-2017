# AGENTS.md — NYC Land Cover 2017

Guidance for agents and scripts that read this catalog.

**One rule survives every edit to this file.** Every claim here is either quoted
from a source or measured from the data. If you cannot point at where a fact
came from, it does not belong in this file.

## What this catalog holds

The root is
`https://data.source.coop/betanyc/nyc-land-cover-2017/catalog.json`. It holds one
collection:

- [`land-cover-2017`](land-cover-2017/collection.json): New York City's 2017
  land cover map, 6-inch pixels, 8 classes, as one Cloud Optimized GeoTIFF in
  EPSG:2263. Read its [AGENTS.md](land-cover-2017/AGENTS.md) before you query
  it. It has the class table, recipes, and the quirks that produce wrong
  answers.

This is a mirror. The NYC Office of Technology and Innovation publishes the data
on [NYC Open Data](https://data.cityofnewyork.us/d/he6d-2qns).
[BetaNYC](https://beta.nyc) maintains this copy. Report problems in the
[issue tracker](https://github.com/BetaNYC/nyc-land-cover-2017/issues).

## How to read it

Walk the STAC links from the root. The data asset of a collection is the asset
with the `data` role. Its `bands[0]["classification:classes"]` maps each pixel
value to a class name, a colour, and an exact pixel count:

<!-- check -->
```python
import json, urllib.request

ROOT = "https://data.source.coop/betanyc/nyc-land-cover-2017/"
cat = json.load(urllib.request.urlopen(ROOT + "catalog.json"))
for link in cat["links"]:
    if link["rel"] == "child":
        col = json.load(urllib.request.urlopen(ROOT + link["href"].lstrip("./")))
        data = [a for a in col["assets"].values() if "data" in a["roles"]][0]
        print(col["id"], data["href"], data["file:size"])
```

## Join keys

None. The catalog holds a single raster.

## Quirks that produce silently wrong answers

- The raster is in US survey feet (EPSG:2263), not metres or degrees.
- Water covers the harbor out to the city boundary, and it is the largest
  class. Exclude it for land-only shares.
- The collection's [AGENTS.md](land-cover-2017/AGENTS.md) lists the rest.

## Structure

Structural links (`root`, `parent`, `child`) are relative. The root
`catalog.json` also carries an absolute `self` link. Each catalog and collection
links to the data browser (`alternate`), the repository (`vcs`), the issue
tracker (`issues`), and the Source Cooperative page (`about`).
