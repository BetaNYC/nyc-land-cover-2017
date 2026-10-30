#!/usr/bin/env python3
"""Generate the published catalog from metadata/.

Inputs, all committed:
  metadata/catalog.yaml               catalog title, description, navigation
  metadata/<collection>.yaml          collection metadata, every claim sourced
  metadata/<collection>.measured.json facts measured from the COG
                                      (tools/measure_cog.py writes it)

Outputs, all under catalog/ and never hand-edited:
  catalog/catalog.json, catalog/README.md
  catalog/<collection>/collection.json, catalog/<collection>/README.md

AGENTS.md files are written by hand and only read here, never written.

    python3 tools/build_catalog.py           # write
    python3 tools/build_catalog.py --check   # fail if any output is stale

Needs PyYAML. Needs no data on disk.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
META = ROOT / "metadata"
CATALOG = ROOT / "catalog"

PORTOLAN_SCHEMA = "https://schemas.portolan-sdi.org/portolan/v0.2.0/schema.json"
EXT = {
    "file": "https://stac-extensions.github.io/file/v2.1.0/schema.json",
    "proj": "https://stac-extensions.github.io/projection/v2.0.0/schema.json",
    "classification": "https://stac-extensions.github.io/classification/v2.0.0/schema.json",
}
COG_TYPE = "image/tiff; application=geotiff; profile=cloud-optimized"

# Link relations this generator owns. Any other link already in a file is kept.
OWNED_RELS = {
    "root", "parent", "self", "child", "describedby", "agents", "vcs",
    "issues", "about", "alternate", "via", "related", "license", "icon",
}


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def multihash(path: Path) -> str:
    return "1220" + hashlib.sha256(path.read_bytes()).hexdigest()


def file_fields(path: Path) -> dict:
    return {"file:size": path.stat().st_size, "file:checksum": multihash(path)}


def browser_url(template: str, json_url: str) -> str:
    return template.format(url=json_url.removeprefix("https://"))


def human_size(n: int) -> str:
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            return f"{n:,.0f} {unit}" if unit == "bytes" else f"{n:,.1f} {unit}"
        n /= 1000
    return str(n)


def nav_links(cat: dict, json_url: str) -> list[dict]:
    return [
        {"rel": "alternate", "href": browser_url(cat["browser_template"], json_url),
         "type": "text/html", "title": "Open in the Portolan data browser"},
        {"rel": "vcs", "href": cat["repository"], "type": "text/html",
         "title": "Source repository"},
        {"rel": "issues", "href": cat["issues"], "type": "text/html",
         "title": "Report a problem"},
        {"rel": "about", "href": cat["hosting_page"], "type": "text/html",
         "title": "Hosting repository on Source Cooperative"},
    ]


def nav_line(cat: dict, json_url: str) -> str:
    return (
        f"[Open in data browser]({browser_url(cat['browser_template'], json_url)})"
        f" · [Source repository]({cat['repository']})"
        f" · [Report a problem]({cat['issues']})"
        f" · [Hosting repository]({cat['hosting_page']})"
    )


def merge_links(existing_path: Path, generated: list[dict]) -> list[dict]:
    kept = []
    if existing_path.exists():
        kept = [link for link in json.loads(existing_path.read_text()).get("links", [])
                if link.get("rel") not in OWNED_RELS]
    return generated + kept


# --- collection --------------------------------------------------------------

def build_collection(cat: dict, col: dict, measured: dict) -> tuple[dict, str]:
    cid = col["id"]
    cdir = CATALOG / cid
    json_url = f"{cat['public_base']}/{cid}/collection.json"
    data_href = f"{cat['public_base']}/{cid}/{measured['file']}"

    counts = {int(k): v for k, v in measured["class_counts"].items()}
    valid = sum(n for v, n in counts.items() if v != 0)
    classes = []
    for c in col["classes"]:
        entry = {"value": c["value"], "name": c["name"], "title": c["title"]}
        if c.get("description"):
            entry["description"] = " ".join(c["description"].split())
        if c.get("color_hint"):
            entry["color_hint"] = c["color_hint"]
        if c.get("nodata"):
            entry["nodata"] = True
        else:
            n = counts.get(c["value"], 0)
            entry["count"] = n
            entry["percentage"] = round(100 * n / valid, 4)
        classes.append(entry)

    band = {
        "name": col["data"]["band_name"],
        "description": " ".join(col["data"]["band_description"].split()),
        "data_type": measured["data_type"],
        "nodata": int(measured["nodata"]),
        "statistics": measured["statistics"],
        "classification:classes": classes,
    }

    assets = {
        "data": {
            "href": data_href,
            "type": COG_TYPE,
            "title": col["data"]["title"],
            "roles": ["data"],
            "file:size": measured["file_size"],
            "file:checksum": measured["file_checksum"],
            "proj:code": measured["proj_code"],
            "proj:shape": measured["proj_shape"],
            "proj:transform": measured["proj_transform"],
            "proj:bbox": measured["proj_bbox"],
            "bands": [band],
        },
        "thumbnail": {
            "href": "./thumbnail.png",
            "type": "image/png",
            "title": "Preview of the default rendering over a light basemap. "
                     "Basemap: Esri World Light Gray Base. Esri, HERE, Garmin, "
                     "(c) OpenStreetMap contributors, and the GIS user community.",
            "roles": ["thumbnail"],
            **file_fields(cdir / "thumbnail.png"),
        },
        "source": {
            "href": col["source_asset"]["href"],
            "type": col["source_asset"]["type"],
            "title": col["source_asset"]["title"],
            "roles": ["source"],
            "file:size": col["source_asset"]["file_size"],
            "file:checksum": col["source_asset"]["file_checksum"],
        },
    }
    for m in col["metadata_assets"]:
        asset = {"href": m["href"], "type": m["type"], "title": m["title"],
                 "roles": ["metadata"]}
        if not m["href"].startswith("http"):
            asset.update(file_fields(cdir / m["href"]))
        elif "file_size" in m:
            asset.update({"file:size": m["file_size"],
                          "file:checksum": m["file_checksum"]})
        assets[m["key"]] = asset

    links = [
        {"rel": "root", "href": "../catalog.json", "type": "application/json",
         "title": cat["title"]},
        {"rel": "parent", "href": "../catalog.json", "type": "application/json",
         "title": cat["title"]},
        {"rel": "agents", "href": "./AGENTS.md", "type": "text/markdown",
         "title": "Guidance for AI agents"},
        {"rel": "describedby", "href": "./README.md", "type": "text/markdown",
         "title": "Human-readable documentation"},
    ]
    for s in col["sources"]:
        links.append({"rel": s["rel"], "href": s["href"], "type": "text/html",
                      "title": s["title"]})
    for lic in col["license_links"]:
        links.append({"rel": "license", "href": lic["href"], "type": "text/html",
                      "title": lic["title"]})
    links += nav_links(cat, json_url)

    collection = {
        "type": "Collection",
        "stac_version": "1.1.0",
        "stac_extensions": [PORTOLAN_SCHEMA, EXT["file"], EXT["proj"],
                            EXT["classification"]],
        "id": cid,
        "title": col["title"],
        "description": " ".join(col["description"].split()),
        "license": col["license"],
        "keywords": col["keywords"],
        "providers": col["providers"] + [cat["host"]],
        "extent": {
            "spatial": {"bbox": [measured["bbox_wgs84"]]},
            "temporal": {"interval": [col["temporal"]]},
        },
        "assets": assets,
        "links": merge_links(cdir / "collection.json", links),
        "updated": col["updated"],
    }
    return collection, collection_readme(cat, col, measured, classes, json_url,
                                         data_href)


def para(text: str) -> str:
    return " ".join(text.split())


def collection_readme(cat, col, measured, classes, json_url, data_href) -> str:
    out = [
        "<!-- Generated by tools/build_catalog.py from metadata/. Do not edit. -->",
        f"# {col['title']}", "", nav_line(cat, json_url), "",
        para(col["description"]), "",
        "## Classes", "",
        "Pixel counts and shares are measured from the published file. Each "
        "pixel is 0.5 ft x 0.5 ft (0.25 sq ft). Shares are of pixels inside the "
        "city boundary, which includes water.", "",
        "| Value | Class | Colour | Pixels | Share | Notes |",
        "|---:|---|---|---:|---:|---|",
    ]
    for c in classes:
        if c.get("nodata"):
            out.append(f"| {c['value']} | {c['title']} | transparent | | | "
                       f"{c.get('description', '')} |")
            continue
        out.append(
            f"| {c['value']} | {c['title']} | `#{c['color_hint']}` | "
            f"{c['count']:,} | {c['percentage']:.2f}% | {c.get('description', '')} |")
    m = measured
    rows, cols = m["proj_shape"]
    out += [
        "", "## Files", "",
        "| File | Format | Size |", "|---|---|---|",
        f"| [{m['file']}]({data_href}) | Cloud Optimized GeoTIFF, "
        f"{m['compression']}, {m['block_shape'][0]} x {m['block_shape'][1]} tiles | "
        f"{human_size(m['file_size'])} |",
        f"| [Land_Cover.zip]({col['source_asset']['href']}) | Original download, "
        f"ERDAS Imagine in a zip | {human_size(col['source_asset']['file_size'])} |",
        "",
        "## Grid and coordinate reference system", "",
        f"- {cols:,} columns x {rows:,} rows, 0.5 ft pixels, one band "
        f"(`{m['data_type']}`), NoData = {int(m['nodata'])}.",
        f"- {m['proj_code']}, NAD83 / New York Long Island (ftUS). Coordinates "
        "and pixel sizes are in US survey feet, not metres.",
        f"- Overview factors: {', '.join(str(f) for f in m['overview_factors'])} "
        "(nearest neighbour, so overview pixels are real class values).",
        f"- Extent in WGS84: {', '.join(str(v) for v in m['bbox_wgs84'])}.",
        "",
        "## Method and accuracy", "",
        para(col["method"]), "",
        para(col["accuracy"]) + " (Source: the ArcGIS metadata in the original zip.)",
        "",
        "## Uses", "",
    ]
    out += [f"- {para(u)}" for u in col["uses"]]
    out += ["", "## Not suited for", ""]
    out += [f"- {para(u)}" for u in col["not_suited_for"]]
    out += ["", "## Known biases and uncertainty", ""]
    out += [f"- {para(u)}" for u in col["biases"]]
    out += [
        "", "## Known issues", "",
    ]
    out += [f"- {para(k)}" for k in col["known_issues"]]
    out += [
        "", "## License", "",
        f"`{col['license']}`. {para(col['license_summary'])}", "",
    ]
    out += [f"- [{lic['title']}]({lic['href']})" for lic in col["license_links"]]
    out += [
        "", "## Attribution", "", para(col["attribution"]), "",
        "## Provenance", "",
        f"Mirror of [NYC Open Data he6d-2qns]({col['source_url']}), file version "
        f"{col['source_version']}. Last synced {col['updated'][:10]}.", "",
        para(col["processing_notes"]), "",
        "Producers:", "",
    ]
    out += [f"- [{p['name']}]({p['url']}) ({', '.join(p['roles'])})"
            for p in col["providers"]]
    out += ["", "Related documentation:", ""]
    out += [f"- [{s['title']}]({s['href']})" for s in col["sources"]
            if s["rel"] == "related"]
    out += [f"- [{a['title']}]({a['href']})" for a in col["metadata_assets"]]
    out += ["", "For queries and recipes, read the [AGENTS.md](AGENTS.md).", ""]
    return "\n".join(out)


# --- catalog -----------------------------------------------------------------

def build_catalog(cat: dict, cols: list[dict]) -> tuple[dict, str]:
    json_url = f"{cat['public_base']}/catalog.json"
    links = [
        {"rel": "root", "href": "./catalog.json", "type": "application/json",
         "title": cat["title"]},
        {"rel": "self", "href": json_url, "type": "application/json"},
        {"rel": "describedby", "href": "./README.md", "type": "text/markdown",
         "title": "Catalog README"},
        {"rel": "agents", "href": "./AGENTS.md", "type": "text/markdown",
         "title": "Catalog agent guide"},
    ]
    for col in cols:
        links.append({"rel": "child", "href": f"./{col['id']}/collection.json",
                      "type": "application/json", "title": col["title"]})
    links += nav_links(cat, json_url)
    if cat.get("logo"):
        links.append({"rel": "icon", **cat["logo"]})
    catalog = {
        "type": "Catalog",
        "stac_version": "1.1.0",
        "stac_extensions": [PORTOLAN_SCHEMA],
        "id": cat["id"],
        "title": cat["title"],
        "description": para(cat["description"]),
        "links": merge_links(CATALOG / "catalog.json", links),
        # A mirror catalog records its last sync, the latest collection sync.
        "updated": max(col["updated"] for col in cols),
    }
    out = [
        "<!-- Generated by tools/build_catalog.py from metadata/. Do not edit. -->",
        f"# {cat['title']}", "", nav_line(cat, json_url), "",
        para(cat["description"]), "",
        "## Collections", "",
        "| Collection | Coverage | Documentation |", "|---|---|---|",
    ]
    for col in cols:
        cj = f"{cat['public_base']}/{col['id']}/collection.json"
        out.append(
            f"| [{col['title']}]({browser_url(cat['browser_template'], cj)}) | "
            f"New York City, {col['temporal'][0][:4]}–{col['temporal'][1][:4]} | "
            f"[README]({col['id']}/README.md) · [AGENTS.md]({col['id']}/AGENTS.md) |")
    first = cols[0]
    out += [
        "", "## License", "",
        f"`{first['license']}`. {para(first['license_summary'])}", "",
        "## Provenance", "",
        f"A mirror, not the official publication. The data comes from "
        f"[NYC Open Data]({first['source_url']}) and is maintained here by "
        f"[{cat['host']['name']}]({cat['host']['url']}) "
        f"({cat['host']['email']}). Metadata changes go through "
        f"[the repository]({cat['repository']}).", "",
        "## Access", "",
        "Read the class at a point without downloading the file "
        "(GDAL 3.x, longitude then latitude):", "",
        "<!-- check -->",
        "```bash",
        "gdallocationinfo -valonly -wgs84 \\",
        f"  /vsicurl/{cat['public_base']}/{first['id']}/"
        f"{first['data']['file']} \\",
        "  -73.9654 40.7829",
        "```", "",
        "The [AGENTS.md](AGENTS.md) has more recipes.", "",
    ]
    return catalog, "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="fail if any generated file differs from its output")
    args = ap.parse_args()

    cat = load_yaml(META / "catalog.yaml")
    cols = [load_yaml(META / f"{cid}.yaml") for cid in cat["collections"]]

    outputs: dict[Path, str] = {}
    for col in cols:
        measured = json.loads((META / f"{col['id']}.measured.json").read_text())
        collection, readme = build_collection(cat, col, measured)
        outputs[CATALOG / col["id"] / "collection.json"] = (
            json.dumps(collection, indent=2, ensure_ascii=False) + "\n")
        outputs[CATALOG / col["id"] / "README.md"] = readme
    catalog, readme = build_catalog(cat, cols)
    outputs[CATALOG / "catalog.json"] = json.dumps(catalog, indent=2, ensure_ascii=False) + "\n"
    outputs[CATALOG / "README.md"] = readme

    stale = []
    for path, text in outputs.items():
        current = path.read_text() if path.exists() else None
        if current == text:
            continue
        if args.check:
            stale.append(path.relative_to(ROOT))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            print(f"wrote {path.relative_to(ROOT)}")
    if stale:
        print("stale generated files (run python3 tools/build_catalog.py):")
        for p in stale:
            print(f"  {p}")
        return 1
    if args.check:
        print("generated files are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
