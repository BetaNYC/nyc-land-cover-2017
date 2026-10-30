#!/usr/bin/env python3
"""Render a framed thumbnail of a palette COG over a light basemap.

The portolan-thumbnails skill renders vector PMTiles with chiitiler and has no
raster path, so this script renders the COG with GDAL instead and keeps the
skill's framing and gates:

  * the bbox comes from the skill's frame.py (3:2 in Web Mercator);
  * the basemap comes from the skill's pick_basemap.sh;
  * Gate 1 is automated here: the share of frame pixels that carry a class
    must be well above zero, and the rendered image must differ from the
    basemap alone;
  * Gate 2 (looking at the image) is still a person's or an agent's job.

    python3 tools/make_thumbnail.py --cog PATH_OR_URL \
        --bbox W,S,E,N --basemap 'https://.../tile/{z}/{y}/{x}' \
        --out catalog/land-cover-2017/thumbnail.png

The COG's own colour table is the default rendering. The browser draws the
same colours from the classification:classes colour hints.
"""
from __future__ import annotations

import argparse
import hashlib
import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

R = 6378137.0
WORLD = math.pi * R


def to_merc(lon: float, lat: float) -> tuple[float, float]:
    return (math.radians(lon) * R,
            R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


def basemap_xml(template: str, path: Path) -> None:
    url = (template.replace("{z}", "${z}").replace("{x}", "${x}")
           .replace("{y}", "${y}"))
    path.write_text(f"""<GDAL_WMS>
  <Service name="TMS"><ServerUrl>{url}</ServerUrl></Service>
  <DataWindow>
    <UpperLeftX>{-WORLD}</UpperLeftX><UpperLeftY>{WORLD}</UpperLeftY>
    <LowerRightX>{WORLD}</LowerRightX><LowerRightY>{-WORLD}</LowerRightY>
    <TileLevel>18</TileLevel><TileCountX>1</TileCountX><TileCountY>1</TileCountY>
    <YOrigin>top</YOrigin>
  </DataWindow>
  <Projection>EPSG:3857</Projection>
  <BlockSizeX>256</BlockSizeX><BlockSizeY>256</BlockSizeY>
  <BandsCount>3</BandsCount>
  <UserAgent>nyc-land-cover-2017 thumbnail (+https://github.com/BetaNYC/nyc-land-cover-2017)</UserAgent>
  <Cache/>
</GDAL_WMS>
""")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cog", required=True)
    ap.add_argument("--bbox", required=True, help="W,S,E,N in WGS84, already framed")
    ap.add_argument("--basemap", required=True)
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    w, s, e, n = (float(v) for v in args.bbox.split(","))
    x0, y0 = to_merc(w, s)
    x1, y1 = to_merc(e, n)
    width = args.width
    height = round(width * (y1 - y0) / (x1 - x0))

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        xml, base, lc = tmp / "basemap.xml", tmp / "base.tif", tmp / "lc.tif"
        basemap_xml(args.basemap, xml)
        subprocess.run(["gdalwarp", "-q", "-t_srs", "EPSG:3857",
                        "-te", str(x0), str(y0), str(x1), str(y1),
                        "-ts", str(width), str(height), "-r", "bilinear",
                        str(xml), str(base)], check=True)
        subprocess.run(["gdalwarp", "-q", "-t_srs", "EPSG:3857",
                        "-te", str(x0), str(y0), str(x1), str(y1),
                        "-ts", str(width), str(height), "-r", "near",
                        "-ovr", "AUTO", str(args.cog), str(lc)], check=True)
        with rasterio.open(base) as ds:
            rgb = np.moveaxis(ds.read([1, 2, 3]), 0, -1).astype(np.uint8)
        with rasterio.open(lc) as ds:
            cls = ds.read(1)
            cmap = ds.colormap(1)

    lut = np.zeros((256, 4), dtype=np.uint8)
    for value, color in cmap.items():
        lut[value] = color
    lc_rgba = lut[cls]
    alpha = lc_rgba[..., 3:4].astype(np.float32) / 255
    out = (lc_rgba[..., :3] * alpha + rgb * (1 - alpha)).astype(np.uint8)

    # Gate 1.
    data_share = float(np.count_nonzero(cls)) / cls.size
    differs = (hashlib.sha256(out.tobytes()).hexdigest()
               != hashlib.sha256(rgb.tobytes()).hexdigest())
    present = sorted(int(v) for v in np.unique(cls) if v != 0)
    gate1 = data_share >= 0.1 and differs
    print(f"size={width}x{height} data_share={data_share:.3f} "
          f"classes_present={present} differs_from_basemap={differs} "
          f"gate1={'PASS' if gate1 else 'FAIL'}")
    if not gate1:
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out).save(args.out, optimize=True)
    print(f"wrote {args.out} ({args.out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
