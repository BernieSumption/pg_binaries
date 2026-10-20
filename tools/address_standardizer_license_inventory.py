"""Check the reviewed licence evidence embedded in an Address Standardizer archive."""

import json
import tarfile

import coverage

INVENTORY = "address_standardizer/LICENSES/license-inventory.json"
NOTICE_FILES = {
    "Address Standardizer": ("3.7.0", "Address-Standardizer.txt", ()),
    "PCRE2": ("10.48", "PCRE2.txt", ("SLJIT.txt",)),
}
MAX_EVIDENCE_BYTES = 1024 * 1024


def validate_archive(path):
    """Require the final archive's inventory and all reviewed notices to agree."""
    try:
        with tarfile.open(path, "r:gz") as archive:
            members = {}
            for member in archive.getmembers():
                if member.name in members:
                    raise coverage.CoverageError(
                        f"duplicate Address Standardizer archive member: {member.name}")
                members[member.name] = member

            def read_file(name):
                member = members.get(name)
                if (member is None or not member.isfile() or member.size <= 0
                        or member.size > MAX_EVIDENCE_BYTES):
                    raise coverage.CoverageError(
                        f"Address Standardizer archive lacks a non-empty regular file: {name}")
                stream = archive.extractfile(member)
                if stream is None:
                    raise coverage.CoverageError(f"cannot read Address Standardizer archive member: {name}")
                data = stream.read(MAX_EVIDENCE_BYTES + 1)
                if len(data) != member.size or len(data) > MAX_EVIDENCE_BYTES:
                    raise coverage.CoverageError(f"invalid Address Standardizer archive member: {name}")
                return data

            try:
                inventory = json.loads(read_file(INVENTORY))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise coverage.CoverageError("invalid Address Standardizer licence inventory") from exc
            if (not isinstance(inventory, dict) or inventory.get("schema_version") != 1
                    or not isinstance(inventory.get("components"), list)):
                raise coverage.CoverageError("invalid Address Standardizer licence inventory")
            components = inventory["components"]
            if len(components) != len(NOTICE_FILES):
                raise coverage.CoverageError("Address Standardizer licence inventory has unexpected components")
            by_name = {item.get("component"): item for item in components if isinstance(item, dict)}
            if set(by_name) != set(NOTICE_FILES):
                raise coverage.CoverageError("Address Standardizer licence inventory has unexpected components")

            for component, (version, license_file, additional) in NOTICE_FILES.items():
                item = by_name[component]
                review = item.get("redistribution_review")
                if (item.get("version") != version or item.get("license_file") != license_file
                        or item.get("additional_license_files", []) != list(additional)
                        or not isinstance(item.get("payload_paths"), list) or not item["payload_paths"]
                        or not isinstance(review, dict) or review.get("status") != "resolved"
                        or review.get("source_obligation") != "none"
                        or not isinstance(review.get("basis"), str) or not review["basis"].strip()):
                    raise coverage.CoverageError(
                        f"Address Standardizer redistribution review is incomplete for {component}")
                for notice in (license_file, *additional):
                    read_file(f"address_standardizer/LICENSES/{notice}")
    except (OSError, tarfile.TarError) as exc:
        raise coverage.CoverageError(f"cannot inspect Address Standardizer archive licence evidence: {exc}") from exc
