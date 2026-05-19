#!/usr/bin/env python3
"""Smoke-test script imports without running network crawls."""

from pathlib import Path
import py_compile


ROOT = Path(__file__).resolve().parents[1]
for path in sorted((ROOT / "scripts").glob("*.py")):
    if path.name.startswith("._"):
        continue
    py_compile.compile(str(path), doraise=True)
    print(f"compiled {path.relative_to(ROOT)}")
