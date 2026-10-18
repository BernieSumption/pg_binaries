"""Create and compare versioned identities for checked build inputs."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _validate_hashes(value: Any, path: str = "identity") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "sha256" and (not isinstance(child, str) or not _SHA256.fullmatch(child)):
                raise ValueError(f"{path}.{key} must be a lowercase SHA-256 digest")
            _validate_hashes(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_hashes(child, f"{path}[{index}]")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def create_identity(
    repo_root: str | Path,
    component: str,
    target: str | dict,
    upstream_sources: dict,
    dependencies: dict,
    build_configuration: dict,
    recipe_files: list[str | Path],
) -> dict:
    """Build a canonical identity, hashing the explicitly listed repository recipes."""
    if not isinstance(component, str) or not component:
        raise ValueError("component must be a non-empty string")
    if not ((isinstance(target, str) and target) or (isinstance(target, dict) and target)):
        raise ValueError("target must be a non-empty string or object")
    for label, value in (("upstream_sources", upstream_sources), ("dependencies", dependencies),
                         ("build_configuration", build_configuration)):
        if not isinstance(value, dict):
            raise ValueError(f"{label} must be an object")
        _validate_hashes(value, label)
    try:
        root = Path(repo_root).resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"repository root does not exist: {repo_root}") from exc
    recipes = {}
    seen = set()
    for raw_path in recipe_files:
        relative = Path(raw_path)
        if relative.is_absolute():
            raise ValueError(f"recipe path must be relative to repository root: {raw_path}")
        unresolved = (root / relative).resolve(strict=False)
        try:
            unresolved.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"recipe path escapes repository root: {raw_path}") from exc
        try:
            path = (root / relative).resolve(strict=True)
        except OSError as exc:
            raise ValueError(f"recipe file does not exist: {raw_path}") from exc
        try:
            name = path.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"recipe path escapes repository root: {raw_path}") from exc
        if name in seen:
            raise ValueError(f"duplicate recipe path: {name}")
        seen.add(name)
        if not path.is_file():
            raise ValueError(f"recipe path is not a file: {raw_path}")
        recipes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "component": component,
        "target": target,
        "upstream_sources": upstream_sources,
        "dependencies": dependencies,
        "build_configuration": build_configuration,
        "recipes": recipes,
    }
    identity = dict(payload)
    identity["sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
    return identity


def assess_reuse(expected: dict, candidate: dict | None) -> dict:
    """Return a clear reusable decision for a retained candidate identity."""
    if candidate is None:
        return {"reusable": False, "reason": "candidate identity is missing"}
    for label, identity in (("expected", expected), ("candidate", candidate)):
        if not isinstance(identity, dict):
            return {"reusable": False, "reason": f"{label} identity is invalid"}
        if identity.get("schema_version") != SCHEMA_VERSION:
            return {"reusable": False, "reason": f"{label} identity has unsupported schema version"}
        try:
            _validate_hashes(identity, label)
        except ValueError as exc:
            return {"reusable": False, "reason": str(exc)}
        recorded_digest = identity.get("sha256")
        payload = {key: value for key, value in identity.items() if key != "sha256"}
        if not isinstance(recorded_digest, str) or not _SHA256.fullmatch(recorded_digest):
            return {"reusable": False, "reason": f"{label} identity has no valid SHA-256 digest"}
        if hashlib.sha256(_canonical(payload)).hexdigest() != recorded_digest:
            return {"reusable": False, "reason": f"{label} identity digest does not match its contents"}
    if expected != candidate:
        return {"reusable": False, "reason": "build input identity mismatch"}
    return {"reusable": True, "reason": "build input identity matches"}
