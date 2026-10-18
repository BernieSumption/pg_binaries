# Separate Linux pgvector build trial

Created 18 October 2026 to determine whether pgvector 0.8.7 can be built for PostgreSQL 18.6 Linux x86-64 from an existing PostgreSQL archive, without recompiling PostgreSQL. Separate build code is needed to test that boundary because the active Linux recipe compiles both packages in one container. The extension build runs in Docker and leaves the core archive unchanged.

Provide the core archive, its adjacent .sha256 sidecar, the independently trusted core SHA-256, the exact pgvector v0.8.7 source tarball, and an output directory. Run:

    scripts/pgvector/linux-build.sh /path/to/postgresql-18.6-linux-x86_64.tar.gz TRUSTED_CORE_SHA256 /path/to/pgvector-v0.8.7.tar.gz /path/to/output

The source tarball must match the SHA-256 in support.json. The core bytes must match the separately supplied trusted digest and adjacent sidecar; the basename and embedded manifest must identify PostgreSQL 18.6 Linux x86-64. The output uses the existing pgvector-0.8.7-postgresql-18.6-linux-x86_64.tar.gz basename, with a checksum sidecar and pgvector/ plus metadata.json archive roots. Its metadata records the exact input core basename and SHA-256. The scoped GitHub Actions trial downloads core run 39075939610 from the `pilot/` artifact directory and retains its output artifact for seven days; the workflow records this temporary run ID and expected core digest.

Run the pure input checks with:

    python3 -m unittest discover -s tests -p 'test_pgvector_separate_linux_build.py'

The first build run checked the archive, checksum sidecar, required extension files and metadata bound to the pinned core archive. The first fresh-runner verification [stopped at an outdated core manifest](../../support/evidence/pgvector-separate-linux-39162159498.md), before static or SQL checks. The [retry](../../support/evidence/pgvector-separate-linux-39162527736.md) passed the full Alpine relocation, dependency and SQL suite against a later checked core. The [build-input trial](../../support/evidence/pgvector-build-input-39163686051.md) then embedded an identity covering the selected source pin, recipe files and Docker builder image; the build job checked that identity from the final archive before fresh-runner verification. This is trial evidence, not a publication record. Integration still requires wiring the builder into the active Linux recipe and recording separate build provenance in publication evidence. The experiment ends when the useful code moves into that recipe, or when the approach is rejected and these trial scripts are removed. Retain any result selected for permanent review under `support/evidence/`.
