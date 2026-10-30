#!/usr/bin/env python3
"""Run the documented recipes and claim checks against the published data.

Reads fenced code blocks from every Markdown file under catalog/. A block runs
when the line just before its opening fence is one of these markers:

    <!-- check -->   the block must exit 0 and print something
    <!-- claim -->   the block must exit 0 and print nothing; it prints the
                     rows that would contradict a claim made in the prose

Only ```bash and ```python blocks are supported. Blocks without a marker are
not run (a fragment, or an example that needs inputs the reader supplies).

It also checks that the upstream NYC Open Data file is the one this catalog
mirrors, so a refresh by the city shows up as a failure here.

Needs network access, GDAL command line tools, rasterio, and pyproj.
Run: python3 tests/check_published.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog"
BLOCK = re.compile(
    r"^<!-- (check|claim) -->\n```(bash|python)\n(.*?)^```", re.M | re.S)

failures: list[str] = []
ran = 0

for md in sorted(CATALOG.rglob("*.md")):
    for kind, lang, code in BLOCK.findall(md.read_text()):
        ran += 1
        cmd = ["bash", "-euo", "pipefail", "-c", code] if lang == "bash" \
            else [sys.executable, "-c", code]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        where = f"{md.relative_to(ROOT)}: {code.strip().splitlines()[0][:70]}"
        out = proc.stdout.strip()
        if proc.returncode != 0:
            failures.append(f"{where}\n  exit {proc.returncode}: {proc.stderr.strip()[-400:]}")
        elif kind == "check" and not out:
            failures.append(f"{where}\n  printed nothing")
        elif kind == "claim" and out:
            failures.append(f"{where}\n  contradicting output:\n  {out[:400]}")
        else:
            print(f"ok     {kind:5}  {where}")

# Upstream: the mirrored file is still the one NYC Open Data serves.
meta = yaml.safe_load((ROOT / "metadata" / "land-cover-2017.yaml").read_text())
with urllib.request.urlopen(
        "https://data.cityofnewyork.us/api/views/he6d-2qns.json", timeout=60) as r:
    view = json.load(r)
expected_size = meta["source_asset"]["file_size"]
if view.get("blobFileSize") != expected_size:
    failures.append(
        f"upstream: NYC Open Data now serves {view.get('blobFileSize')} bytes, "
        f"this catalog mirrors {expected_size}. The city may have replaced the file.")
else:
    print("ok     upstream file size unchanged")

print(f"\n{ran} documented block(s) run")
if failures:
    print("\nFAILED:")
    for f in failures:
        print(f"- {f}")
    raise SystemExit(1)
print("all published checks passed")
