"""Run a command and record elapsed time and sampled filesystem use."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


SAMPLE_INTERVAL_SECONDS = 0.1


def measure(output: Path, command: list[str], disk_path: Path) -> int:
    baseline = shutil.disk_usage(disk_path).used
    peak = baseline
    started = time.monotonic()
    process = subprocess.Popen(command)
    while process.poll() is None:
        time.sleep(SAMPLE_INTERVAL_SECONDS)
        peak = max(peak, shutil.disk_usage(disk_path).used)
    exit_code = process.returncode
    elapsed = time.monotonic() - started
    peak = max(peak, shutil.disk_usage(disk_path).used)

    result = {
        "elapsed_seconds": elapsed,
        "baseline_used_bytes": baseline,
        "peak_added_bytes": max(0, peak - baseline),
        "child_exit_code": exit_code,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return exit_code


def main(argv: Optional[list[str]] = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--" not in arguments:
        argparse.ArgumentParser().error("expected OUTPUT_JSON -- COMMAND...")
    separator_index = arguments.index("--")
    wrapper_args, command = arguments[:separator_index], arguments[separator_index + 1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disk-path", type=Path, default=Path("/private/tmp"),
                        help="path on the filesystem to measure (default: /private/tmp)")
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args(wrapper_args)
    if not command:
        parser.error("expected OUTPUT_JSON -- COMMAND...")
    try:
        return measure(args.output_json, command, args.disk_path)
    except OSError as exc:
        print(f"measurement failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
