"""Pinned pgAudit macOS arm64 publication targets."""

import argparse
import json

TARGETS = {
    "15.19": {
        "pgaudit_version": "1.7.1",
        "core_sha256": "bd866dec8967e6320f88eb8ffe3a2f57fad36920b3d05556dae026c53226cf85",
        "core_build_id": "github-39424367764-1",
        "core_source_revision": "817362a98376ab8b0a5af6239ae5dbc92962fedf",
        "source_url": "https://api.github.com/repos/pgaudit/pgaudit/tarball/72da89c3fa02f3f2b9f3933214d91ad9c3428467",
        "source_sha256": "1e52448238908a09e0e78b3375dcefbfca51509fdbb3a4d92eb710e380ed3567",
    },
    "16.15": {
        "pgaudit_version": "16.1",
        "core_sha256": "aae8b4e67a88cb3edc074070527dda23ea5bac09b7574403fdaa18eb1e31ab8c",
        "core_build_id": "github-39424382435-1",
        "core_source_revision": "817362a98376ab8b0a5af6239ae5dbc92962fedf",
        "source_url": "https://api.github.com/repos/pgaudit/pgaudit/tarball/a81792e8a4ea8f7aaf75bd610fcc4c2f96650bdc",
        "source_sha256": "b0648fcebe5a67340c406126e6dddc703fd03821a9ace80390e128a0d1c91c73",
    },
    "17.11": {
        "pgaudit_version": "17.1",
        "core_sha256": "7c8522779eb2ab4e93c863bccc72865c59b60a21ef1cd507323e300413d5d568",
        "core_build_id": "github-39420673533-1",
        "core_source_revision": "bf0284b528dc8188c7b01bacf2f13d21fce7ee88",
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
