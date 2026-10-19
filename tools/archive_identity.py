"""Checks shared by archive evidence importers."""

from pathlib import Path

import coverage


def verify_sidecar(path, digest):
    path = Path(path)
    sidecar = path.with_name(path.name + ".sha256")
    try:
        text = sidecar.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise coverage.CoverageError(f"missing checksum sidecar {sidecar}: {exc}") from exc
    if text != f"{digest}  {path.name}":
        raise coverage.CoverageError(f"checksum sidecar does not match {path.name}")
