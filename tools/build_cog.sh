#!/usr/bin/env bash
# Convert the NYC 2017 land cover .img to a COG with an embedded palette and
# exact embedded statistics. Usage: build_cog.sh SRC.img OUT.tif
set -euo pipefail
SRC=$1; OUT=$2
HERE=$(cd "$(dirname "$0")" && pwd)
VRT="${OUT%.tif}.vrt"
python3 -I "$HERE/make_vrt.py" "$SRC" "$VRT"
GDAL_CACHEMAX=8192 gdal_translate -of COG -a_srs EPSG:2263 \
  -co COMPRESS=DEFLATE -co LEVEL=9 -co PREDICTOR=NO \
  -co BLOCKSIZE=512 -co OVERVIEW_RESAMPLING=NEAREST \
  -co STATISTICS=YES -co BIGTIFF=YES -co NUM_THREADS=ALL_CPUS \
  "$VRT" "$OUT"
rm -f "$VRT"
