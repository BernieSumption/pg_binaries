"""Pinned pgAudit macOS arm64 publication targets."""

import argparse
import json

TARGETS = {
    "17.11": {
        "pgaudit_version": "17.1",
        "core_sha256": "d9ac809946cd87bbb585135d0ff329d33d5563047b9caaa312aea9116a8d9eaa",
        "core_build_id": "github-39093804725-1",
        "core_source_revision": "42082a506adfca1628c509f2c7b17037b9a12123",
        "source_url": "https://api.github.com/repos/pgaudit/pgaudit/tarball/538f89a93d8fd0d8913f3d740cacaea7b7eb66d9",
        "source_sha256": "20e980bd0c22b4ae33305ec2b774bd846bf343642adad108b6c28b422a648312",
    },
    "18.6": {
        "pgaudit_version": "18.0",
        "core_sha256": "853e0eafb3570378225d2ea16247c9de31770f85df5230509885df2ca5e89d67",
        "core_build_id": "github-39075939632-1",
        "core_source_revision": "457919a19e43687a9615697a751454e3c055c593",
        "source_url": "https://github.com/pgaudit/pgaudit/archive/refs/tags/18.0.tar.gz",
        "source_sha256": "988e8afeda320ebe0a3e632ef6b6bce5d3a08346c2e100a173a585c9521d1fa5",
    },
}


def target(version):
    try:
        selected = dict(TARGETS[version])
    except KeyError as exc:
        raise ValueError(f"unsupported pgAudit macOS target: {version}") from exc
    selected["postgresql_version"] = version
    selected["profile_id"] = f"pgaudit-publication-macos-arm64-{version}"
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", choices=tuple(TARGETS))
    parser.add_argument("--field", choices=("pgaudit_version", "core_sha256", "core_build_id",
                                             "core_source_revision", "source_url", "source_sha256"))
    parser.add_argument("--shell", action="store_true")
    args = parser.parse_args()
    selected = target(args.version)
    if args.shell:
        fields = ("pgaudit_version", "core_sha256", "core_build_id", "core_source_revision",
                  "source_url", "source_sha256")
        print("\t".join(selected[field] for field in fields))
    elif args.field:
        print(selected[args.field])
    else:
        print(json.dumps(selected, sort_keys=True))


if __name__ == "__main__":
    main()
