"""Wrap the source .img in a VRT that carries the land cover color table.

Usage: python3 make_vrt.py SRC.img OUT.vrt [srcwin xoff yoff xsize ysize]
"""
import re
import subprocess
import sys

PALETTE = {  # value: (r, g, b)
    1: (0x2E, 0x7D, 0x32),  # Tree Canopy
    2: (0xA6, 0xD9, 0x6A),  # Grass/Shrubs
    3: (0xC8, 0xA1, 0x65),  # Bare Soil
    4: (0x4A, 0x90, 0xC8),  # Water
    5: (0xB5, 0x47, 0x3A),  # Buildings
    6: (0x3F, 0x3F, 0x3F),  # Roads
    7: (0xA9, 0xA9, 0xA9),  # Other Impervious
    8: (0x7E, 0x4F, 0xA0),  # Railroads
}

src, out, *win = sys.argv[1:]
cmd = ["gdal_translate", "-q", "-of", "VRT"]
if win:
    cmd += ["-srcwin", *win]
subprocess.run(cmd + [src, out], check=True)

entries = []
for v in range(256):
    if v in PALETTE:
        r, g, b = PALETTE[v]
        entries.append(f'<Entry c1="{r}" c2="{g}" c3="{b}" c4="255"/>')
    else:
        entries.append('<Entry c1="0" c2="0" c3="0" c4="0"/>')
table = "<ColorInterp>Palette</ColorInterp><ColorTable>" + "".join(entries) + "</ColorTable>"

xml = open(out).read()
xml = re.sub(r"<ColorInterp>[^<]*</ColorInterp>", "", xml)
# Drop the source's PAM statistics so the COG computes its own, exactly.
xml = re.sub(r"<Metadata>.*?</Metadata>", "", xml, flags=re.S)
xml = xml.replace("<NoDataValue>0</NoDataValue>", "<NoDataValue>0</NoDataValue>" + table, 1)
xml = xml.replace("<Description>Layer_1</Description>", "<Description>land_cover_class</Description>")
open(out, "w").write(xml)
