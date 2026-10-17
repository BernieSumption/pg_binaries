#!/usr/bin/env python3
"""Simulate release ordering with a filesystem-backed store; never contacts GitHub."""

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil

_PREFLIGHT_SPEC = importlib.util.spec_from_file_location(
    "local_dry_run_preflight", Path(__file__).with_name("publication_preflight.py"))
_preflight = importlib.util.module_from_spec(_PREFLIGHT_SPEC)
_PREFLIGHT_SPEC.loader.exec_module(_preflight)

_ASSET_URL = re.compile(
    r"^https://github\.com/BernieSumption/pg_binaries/releases/download/"
    r"(catalog-\d{8}-\d+)/([A-Za-z0-9._+-]+\.tar\.gz)$")


class DryRunError(ValueError):
    """A simulated publication cannot safely be promoted."""


class LocalPublicationStore:
    """Filesystem-only model of immutable release assets and current inventory."""

    def __init__(self, root):
        self.root = Path(root)
        self.releases = self.root / "releases"
        self.staging = self.root / "staging"
        self.current_path = self.root / "current" / "inventory.json"
        self.releases.mkdir(parents=True, exist_ok=True)
        self.staging.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _path_parts(url):
        match = _ASSET_URL.fullmatch(url) if isinstance(url, str) else None
        if not match:
            raise DryRunError(f"unsupported immutable release URL: {url!r}")
        return match.group(1), match.group(2)

    @staticmethod
    def _references(inventory):
        try:
            return _preflight._asset_references(inventory)
        except _preflight.PreflightError as exc:
            raise DryRunError(str(exc)) from exc

    def seed_release(self, tag, inventory, assets):
        """Install a fixture/previous release into the local store."""
        target = self.releases / tag
        if target.exists():
            raise DryRunError(f"release already exists: {tag}")
        target.mkdir(parents=True)
        for filename, content in assets.items():
            if Path(filename).name != filename or not filename.endswith(".tar.gz"):
                raise DryRunError(f"invalid archive filename: {filename!r}")
            (target / filename).write_bytes(content)
        (target / "inventory.json").write_text(
            json.dumps(inventory, sort_keys=True) + "\n", encoding="utf-8")

    def promote(self, tag, candidate, new_assets, *, preflight_context=None, fail_at=None):
        """Stage, verify, then atomically switch current inventory.

        ``new_assets`` maps immutable URLs for ``tag`` to archive bytes. ``fail_at``
        is a test hook accepting ``after_stage``, ``after_verify`` or
        ``before_current_switch``. When ``preflight_context`` is supplied, it
        contains ``support``, ``snapshot`` and optional ``root`` values for the
        publication preflight; failed candidates never become a local release.
        """
        if not re.fullmatch(r"catalog-\d{8}-\d+", tag):
            raise DryRunError(f"invalid release tag: {tag!r}")
        final_dir = self.releases / tag
        stage_dir = self.staging / tag
        if final_dir.exists() or stage_dir.exists():
            raise DryRunError(f"release tag already used: {tag}")
        if fail_at not in (None, "after_stage", "after_verify", "before_current_switch"):
            raise ValueError(f"unknown failure point: {fail_at}")
        if preflight_context is not None and (
                not isinstance(preflight_context, dict)
                or not isinstance(preflight_context.get("support"), dict)
                or not isinstance(preflight_context.get("snapshot"), dict)):
            raise DryRunError("preflight context requires support and release snapshot objects")

        refs = self._references(candidate)
        stage_dir.mkdir(parents=True)
        try:
            staged_urls = set()
            for url, content in new_assets.items():
                asset_tag, filename = self._path_parts(url)
                if asset_tag != tag:
                    raise DryRunError(f"new asset URL does not use candidate tag: {url}")
                if not isinstance(content, bytes):
                    raise DryRunError(f"archive content must be bytes: {url}")
                (stage_dir / filename).write_bytes(content)
                staged_urls.add(url)
            candidate_path = stage_dir / "inventory.json"
            candidate_path.write_text(json.dumps(candidate, sort_keys=True) + "\n", encoding="utf-8")
            if fail_at == "after_stage":
                raise DryRunError("injected failure after staging")

            if staged_urls != {url for url in refs if self._path_parts(url)[0] == tag}:
                raise DryRunError("staged archives do not exactly match candidate references for this tag")
            preflight_assets = {}
            for url, expected in refs.items():
                asset_tag, filename = self._path_parts(url)
                path = (stage_dir if asset_tag == tag else self.releases / asset_tag) / filename
                if not path.is_file():
                    raise DryRunError(f"candidate archive is unavailable in local store: {url}")
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
                if actual != expected:
                    raise DryRunError(f"checksum mismatch for {url}: expected {expected}, got {actual}")
                if asset_tag == tag:
                    preflight_assets[url] = {"path": str(path), "sha256": actual}
            if preflight_context is not None:
                try:
                    _preflight.preflight_candidate(
                        self.current_inventory(), candidate,
                        preflight_context["support"], preflight_context["snapshot"],
                        preflight_assets, root=preflight_context.get("root"))
                except _preflight.PreflightError as exc:
                    raise DryRunError(f"candidate preflight failed: {exc}") from exc
            if fail_at == "after_verify":
                raise DryRunError("injected failure after verification")

            # Archive bytes and inventory become an immutable local release before
            # current changes, matching the order being simulated.
            stage_dir.rename(final_dir)
            if fail_at == "before_current_switch":
                raise DryRunError("injected failure before current inventory switch")
            self.current_path.parent.mkdir(parents=True, exist_ok=True)
            temp_current = self.current_path.with_suffix(".json.tmp")
            shutil.copyfile(final_dir / "inventory.json", temp_current)
            temp_current.replace(self.current_path)
            return self.current_inventory()
        except Exception:
            if stage_dir.exists():
                shutil.rmtree(stage_dir)
            raise

    def current_inventory(self):
        return json.loads(self.current_path.read_text(encoding="utf-8"))

    def retrieve(self, url):
        """Retrieve one immutable archive by URL from local release directories."""
        tag, filename = self._path_parts(url)
        path = self.releases / tag / filename
        if not path.is_file():
            raise FileNotFoundError(f"URL is absent from local store: {url}")
        return path.read_bytes()

    def retrieve_current_references(self):
        """Return every archive referenced by current inventory, using local files."""
        refs = self._references(self.current_inventory())
        result = {}
        for url, checksum in refs.items():
            data = self.retrieve(url)
            if hashlib.sha256(data).hexdigest() != checksum:
                raise DryRunError(f"current inventory checksum mismatch for {url}")
            result[url] = data
        return result
