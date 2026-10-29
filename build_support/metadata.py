"""Read the package build contract."""

import json
from pathlib import Path
import re
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
NAME = re.compile(r"[a-z][a-z0-9_]*")


class MetadataError(ValueError):
    pass


def _object(value, context, required=(), optional=()):
    if not isinstance(value, dict):
        raise MetadataError(f"{context} must be an object")
    missing = set(required) - value.keys()
    unknown = value.keys() - set(required) - set(optional)
    if missing or unknown:
        raise MetadataError(f"{context}: missing={sorted(missing)}, unknown={sorted(unknown)}")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise MetadataError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def load_package(name, root=ROOT):
    if not NAME.fullmatch(name):
        raise MetadataError(f"invalid package name: {name}")
    path = root / "packages" / name / "build.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, json.JSONDecodeError) as exc:
        raise MetadataError(f"cannot read {path}: {exc}") from exc
    required = ("sources",) if name == "postgresql" else ("sources", "extensions")
    _object(data, str(path), required, ("config", "linux_apt_packages"))
    if not isinstance(data["sources"], dict) or not data["sources"]:
        raise MetadataError(f"{path}: sources must be a nonempty object")
    for source_id, source in data["sources"].items():
        if not NAME.fullmatch(source_id):
            raise MetadataError(f"{path}: invalid source id: {source_id}")
        _object(source, f"{name}.sources.{source_id}", ("project", "url", "sha256"))
        if not isinstance(source["project"], str) or not source["project"].strip():
            raise MetadataError(f"{path}: source project must be a nonempty string")
        if not isinstance(source["url"], str) or urlsplit(source["url"]).scheme != "https" or not urlsplit(source["url"]).netloc:
            raise MetadataError(f"{path}: source URL must be an HTTPS archive URL")
        if not isinstance(source["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"]):
            raise MetadataError(f"{path}: invalid source SHA-256")
    if name != "postgresql" and (not isinstance(data["extensions"], dict) or not data["extensions"]):
        raise MetadataError(f"{path}: extensions must be a nonempty object")
    for extension, details in data.get("extensions", {}).items():
        if not NAME.fullmatch(extension):
            raise MetadataError(f"{path}: invalid extension name: {extension}")
        _object(details, f"{name}.extensions.{extension}", optional=("config",))
        _config(details.get("config", {}), "extension", path)
        if not (path.parent / "probes" / f"{extension}.sql").is_file():
            raise MetadataError(f"{path}: missing probe for {extension}")
    _config(data.get("config", {}), "package", path)
    apt = data.get("linux_apt_packages", [])
    if not isinstance(apt, list) or any(not isinstance(item, str) or not re.fullmatch(r"[a-z0-9][a-z0-9+.-]*", item) for item in apt):
        raise MetadataError(f"{path}: invalid linux_apt_packages")
    return data


def _config(config, kind, path):
    allowed = ("environment_paths",) if kind == "package" else ("shared_preload_libraries",)
    _object(config, f"{path}: {kind} config", optional=allowed)
    if "environment_paths" in config:
        paths = config["environment_paths"]
        if not isinstance(paths, dict):
            raise MetadataError(f"{path}: environment_paths must be an object")
        for variable, relative in paths.items():
            if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", variable) or not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
                raise MetadataError(f"{path}: invalid environment path")
    if "shared_preload_libraries" in config:
        libraries = config["shared_preload_libraries"]
        if not isinstance(libraries, list) or any(item not in ("pgaudit", "pg_ivm") for item in libraries):
            raise MetadataError(f"{path}: invalid shared_preload_libraries")


def packages(root=ROOT):
    return {path.parent.name: load_package(path.parent.name, root)
            for path in sorted((root / "packages").glob("*/build.json"))
            if path.parent.name != "postgresql"}


def load_selection(path=ROOT / "support.json"):
    path = Path(path)
    support = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    return {"targets": support["targets"], "packages": packages(path.parent),
            "postgresql": load_package("postgresql", path.parent)}
