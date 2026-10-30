#!/usr/bin/env python3
"""Measure a built COG and record the facts the catalog states about it.

Writes metadata/<collection>.measured.json. tools/build_catalog.py reads that
file, so the generator runs without the data on disk (in CI, for example).
Run this after every rebuild of the COG.

    python3 tools/measure_cog.py land-cover-2017 \
        --cog ../staging/land-cover-2017/nyc-land-cover-2017.tif \
        --src ../Land_Cover/NYC_2017_LiDAR_LandCover.img

Needs rasterio and the GDAL command line tools. --src is optional. With it,
the script checks the per-class counts against the source attribute table
(<src>.vat.dbf) and compares random windows of the source and the COG pixel
by pixel.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import random
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import Window

ROOT = Path(__file__).resolve().parent.parent


def sha256_multihash(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(16 * 1024 * 1024), b""):
            digest.update(chunk)
    return "1220" + digest.hexdigest()


def full_histogram(path: Path) -> dict[int, int]:
    """Exact per-value pixel counts over the full-resolution band."""
    env = dict(os.environ, GDAL_PAM_ENABLED="NO")
    out = subprocess.run(
        ["gdalinfo", "-json", "-hist", "-nomd", str(path)],
        check=True, capture_output=True, text=True, env=env,
    ).stdout
    hist = json.loads(out)["bands"][0]["histogram"]
    step = (hist["max"] - hist["min"]) / hist["count"]
    counts = {}
    for i, n in enumerate(hist["buckets"]):
        value = round(hist["min"] + step * (i + 0.5))
        if n:
            counts[value] = n
    return counts


def read_vat(dbf: Path) -> dict[int, int]:
    """Value -> Count from the ERDAS raster attribute table (a dBase file)."""
    data = dbf.read_bytes()
    nrec, hlen, rlen = struct.unpack("<IHH", data[4:12])
    fields, pos = [], 32
    while data[pos] != 0x0D:
        name = data[pos:pos + 11].split(b"\0")[0].decode()
        fields.append((name, data[pos + 16]))
        pos += 32
    out = {}
    for r in range(nrec):
        rec, off, row = data[hlen + r * rlen:hlen + (r + 1) * rlen], 1, {}
        for name, length in fields:
            row[name] = rec[off:off + length].decode("latin-1").strip()
            off += length
        out[int(row["Value"])] = int(float(row["Count"]))
    return out


def compare_windows(src: Path, cog: Path, n: int, size: int, seed: int) -> dict:
    rng = random.Random(seed)
    checked = differing = 0
    with rasterio.open(src) as a, rasterio.open(cog) as b:
        assert (a.width, a.height) == (b.width, b.height)
        for _ in range(n):
            x = rng.randrange(0, a.width - size)
            y = rng.randrange(0, a.height - size)
            w = Window(x, y, size, size)
            pa, pb = a.read(1, window=w), b.read(1, window=w)
            checked += pa.size
            differing += int(np.count_nonzero(pa != pb))
    return {"windows": n, "window_size": size, "seed": seed,
            "pixels_checked": checked, "pixels_differing": differing}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("collection")
    ap.add_argument("--cog", required=True, type=Path)
    ap.add_argument("--src", type=Path)
    ap.add_argument("--windows", type=int, default=200)
    args = ap.parse_args()

    cog = args.cog.resolve()
    with rasterio.open(cog) as ds:
        tags = ds.tags(1)
        epsg = ds.crs.to_epsg()
        t = ds.transform
        b = ds.bounds
        wgs84 = transform_bounds(ds.crs, "EPSG:4326", *b, densify_pts=101)
        measured = {
            "measured_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
            "gdal_version": rasterio.__gdal_version__,
            "file": cog.name,
            "file_size": cog.stat().st_size,
            "file_checksum": sha256_multihash(cog),
            "proj_code": f"EPSG:{epsg}",
            "proj_shape": [ds.height, ds.width],
            "proj_transform": [t.a, t.b, t.c, t.d, t.e, t.f],
            "proj_bbox": [b.left, b.bottom, b.right, b.top],
            "bbox_wgs84": [round(v, 6) for v in wgs84],
            "data_type": ds.dtypes[0],
            "nodata": ds.nodata,
            "block_shape": list(ds.block_shapes[0]),
            "overview_factors": ds.overviews(1),
            "compression": ds.compression.name if ds.compression else None,
            "statistics": {
                "minimum": float(tags["STATISTICS_MINIMUM"]),
                "maximum": float(tags["STATISTICS_MAXIMUM"]),
                "mean": float(tags["STATISTICS_MEAN"]),
                "stddev": float(tags["STATISTICS_STDDEV"]),
                "valid_percent": float(tags["STATISTICS_VALID_PERCENT"]),
            },
        }

    print("computing the full-resolution histogram ...", file=sys.stderr)
    counts = full_histogram(cog)
    measured["class_counts"] = {str(k): v for k, v in sorted(counts.items())}

    if args.src:
        vat = read_vat(Path(str(args.src) + ".vat.dbf"))
        measured["source_vat_counts"] = {str(k): v for k, v in sorted(vat.items())}
        measured["counts_match_source_vat"] = vat == counts
        print(f"comparing {args.windows} random windows ...", file=sys.stderr)
        measured["window_comparison"] = compare_windows(
            args.src, cog, args.windows, 2048, seed=2017)

    out = ROOT / "metadata" / f"{args.collection}.measured.json"
    out.write_text(json.dumps(measured, indent=2) + "\n")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
