# AGENTS.md — nyc-land-cover-2017 repository

Instructions for people and agents who change this repository. The guides that
readers of the published catalog use are `catalog/AGENTS.md` and
`catalog/land-cover-2017/AGENTS.md`.

This repository holds the metadata of a [Portolan](https://www.portolan-sdi.org/)
catalog that mirrors NYC Land Cover 2017 from
[NYC Open Data](https://data.cityofnewyork.us/d/he6d-2qns). The catalog and the
data are served from Source Cooperative at
<https://source.coop/betanyc/nyc-land-cover-2017>. The
[portolan-spec](https://github.com/portolan-sdi/portolan-spec) is the ground
truth for what the catalog must contain. Use conventional commits.

## Where things live

| Path | What it is | Edited by |
|---|---|---|
| `metadata/catalog.yaml` | Catalog title, description, navigation targets, host | hand |
| `metadata/land-cover-2017.yaml` | Collection metadata. Every claim names its source | hand |
| `metadata/land-cover-2017.measured.json` | Facts measured from the COG | `tools/measure_cog.py` |
| `catalog/**/catalog.json`, `collection.json`, `README.md` | The published STAC and READMEs | `tools/build_catalog.py` only |
| `catalog/**/AGENTS.md` | Published agent guides | hand |
| `catalog/land-cover-2017/thumbnail.png` | Collection thumbnail | `tools/make_thumbnail.py` |
| `tools/build_cog.sh`, `tools/make_vrt.py` | Source `.img` to COG conversion | hand |
| `../staging/` (outside git) | The built COG, uploaded by `tools/upload_data.py` | build |

Never hand-edit a generated file. `tests/test_generated.py` fails when one
differs from what the generator writes.

## Rebuild from the source

```bash
# 1. Download and unzip the source (1.3 GB zip, 130 GB unzipped).
curl -L -o Land_Cover.zip https://data.cityofnewyork.us/download/he6d-2qns/application/zip
unzip Land_Cover.zip
# 2. Convert.
tools/build_cog.sh Land_Cover/NYC_2017_LiDAR_LandCover.img \
  ../staging/land-cover-2017/nyc-land-cover-2017.tif
# 3. Measure, render the thumbnail, regenerate the catalog.
.venv/bin/python tools/measure_cog.py land-cover-2017 \
  --cog ../staging/land-cover-2017/nyc-land-cover-2017.tif \
  --src Land_Cover/NYC_2017_LiDAR_LandCover.img
.venv/bin/python tools/make_thumbnail.py \
  --cog ../staging/land-cover-2017/nyc-land-cover-2017.tif \
  --bbox "$(cat metadata/land-cover-2017.thumbnail-bbox)" \
  --basemap 'https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}' \
  --out catalog/land-cover-2017/thumbnail.png
.venv/bin/python tools/build_catalog.py
python3 tests/run_all.py
```

Look at the thumbnail before you commit it. The script checks that it is not
blank. It cannot check that it is readable.

## Publish

Publishing uses the template's `tools/publish.py` (the catalog under
`catalog/`) and `tools/upload_data.py` (the COG under `../staging/`). Do not use
`portolan push` on this catalog. The two do not share state.

Both scripts use the `source-coop` AWS profile from `catalog.publish.yaml`. Add
it to `~/.aws/config` once:

```ini
[profile source-coop]
credential_process = source-coop creds
endpoint_url = https://data.source.coop
```

Then log in and run each script dry before you confirm:

```bash
source-coop login
python3 tools/upload_data.py            # dry run
python3 tools/upload_data.py --confirm
python3 tools/publish.py                # dry run
python3 tools/publish.py --confirm
```

Publishing never deletes. Remove a stale object from the bucket separately.

## Rules carried over from the template

- **The publish boundary.** `catalog/` is published and nothing outside it is.
  Do not move a file into `catalog/` to make it publish, and do not widen
  `tools/publish.py`.
- **Data never enters git.** Never commit a COG, GeoParquet, PMTiles, Zarr, or
  COPC file.
- **The conformance allow-list.** `ACCEPTED` in `tests/test_conformance.py` is
  empty. Never add an entry without a row in `docs/conformance.md` that gives
  the rule, where it fires, why it is accepted, and the tracking issue.
- **Published agent guides.** Every claim in a `catalog/**/AGENTS.md` is quoted
  from a source or measured from the data, and every recipe in one was run
  against the published file.
- **Absolute repository links.** The `vcs` and `issues` links point outside the
  published catalog, so their hrefs stay absolute.
