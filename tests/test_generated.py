#!/usr/bin/env python3
"""The generated catalog files match what tools/build_catalog.py produces.

catalog.json, every collection.json, and every README.md under catalog/ are
generated from metadata/. A hand edit to one of them, or a metadata change
without a regeneration, fails here.

Run: python3 tests/test_generated.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
raise SystemExit(subprocess.run(
    [sys.executable, str(ROOT / "tools" / "build_catalog.py"), "--check"]
).returncode)
