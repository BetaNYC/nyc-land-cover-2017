# NYC Land Cover 2017 — Portolan catalog

**[Open in the data browser](https://browser.portolan-sdi.org/#/external/data.source.coop/betanyc/nyc-land-cover-2017/catalog.json)** ·
[Source Cooperative](https://source.coop/betanyc/nyc-land-cover-2017) ·
[Report a problem](https://github.com/BetaNYC/nyc-land-cover-2017/issues)

The metadata for a [Portolan](https://www.portolan-sdi.org/) catalog of New
York City's 2017 high-resolution land cover map: 6-inch pixels, 8 classes (tree
canopy, grass/shrubs, bare soil, water, buildings, roads, other impervious,
railroads). The data is a mirror of the
[NYC Open Data release](https://data.cityofnewyork.us/d/he6d-2qns) from the NYC
Office of Technology and Innovation, converted from a zipped ERDAS Imagine file
to a Cloud Optimized GeoTIFF that can be read in place.

Maintained by [BetaNYC](https://beta.nyc) (lab@beta.nyc).

## How this repository works

- `metadata/` holds the hand-written, sourced metadata.
- `tools/build_catalog.py` generates the STAC JSON and READMEs under `catalog/`.
- `catalog/` is exactly what is published to
  `https://data.source.coop/betanyc/nyc-land-cover-2017/`.
- The COG itself never enters git. It is built with `tools/build_cog.sh` and
  uploaded with `tools/upload_data.py`.
- CI validates every pull request with [rashid](https://github.com/portolan-sdi/rashid),
  checks links, and checks that the generated files are current.

[AGENTS.md](AGENTS.md) has the rebuild and publish steps.

## Contributing

Found a wrong date, a broken link, or a class description that does not match
the source? Open an [issue](https://github.com/BetaNYC/nyc-land-cover-2017/issues)
or a pull request that edits `metadata/`, then run:

```bash
python3 tools/build_catalog.py
python3 tests/run_all.py
```

## License

The catalog metadata in this repository is under the terms in [LICENSE](LICENSE).
The land cover data is published by the City of New York. NYC Open Data states
no license for it. NYC Administrative Code section 23-502(d) makes public data
sets available without license requirements or restrictions on use. See the
collection README for attribution.
