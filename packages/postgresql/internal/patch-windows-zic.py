"""Allow PostgreSQL 18.6 to build zic when cross-built binaries run locally."""

from pathlib import Path
import sys


path = Path(sys.argv[1]) / "src/timezone/meson.build"
source = path.read_text(encoding="utf-8")
expected = """  if meson.is_cross_build()
    zic = find_program(get_option('ZIC'), native: true, required: true)
  else
"""
if source.count(expected) != 1:
    raise SystemExit(f"PostgreSQL timezone Meson guard differs from the expected 18.6 source: {path}")
# Emulated x64 programs can run locally, including zic and its frontend libraries.
replacement = expected.replace("meson.is_cross_build()", "meson.is_cross_build() and not meson.can_run_host_binaries()")
path.write_text(source.replace(expected, replacement, 1), encoding="utf-8")
