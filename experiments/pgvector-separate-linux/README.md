# Separate Linux pgvector build trial

Created 18 October 2026 to determine whether pgvector 0.8.7 can be built for PostgreSQL 18.6 Linux x86-64 from an existing PostgreSQL archive, without recompiling PostgreSQL. Separate build code is needed to test that boundary because the active Linux recipe compiles both packages in one container. The extension build runs in Docker and leaves the core archive unchanged.

Provide the core archive, its adjacent .sha256 sidecar, the independently trusted core SHA-256, the exact pgvector v0.8.7 source tarball, and an output directory. Run:

    scripts/pgvector/linux-build.sh /path/to/postgresql-18.6-linux-x86_64.tar.gz TRUSTED_CORE_SHA256 /path/to/pgvector-v0.8.7.tar.gz /path/to/output

The source tarball must match the SHA-256 in support.json. The core bytes must match the separately supplied trusted digest and adjacent sidecar; the basename and embedded manifest must identify PostgreSQL 18.6 Linux x86-64. The output uses the existing pgvector-0.8.7-postgresql-18.6-linux-x86_64.tar.gz basename, with a checksum sidecar and pgvector/ plus metadata.json archive roots. Its metadata records the exact input core basename and SHA-256. The scoped GitHub Actions trial downloads core run 39061346204 and retains its output artifact for seven days; the workflow records this temporary run ID and expected core digest.

Run the pure input checks with:

    python3 -m unittest discover -s tests -p 'test_pgvector_separate_linux_build.py'

The trial checks that the builder produces the expected archive, checksum sidecar, required extension files and metadata bound to the pinned core archive. It does not run the complete publication verification suite or establish publication evidence. Integration still requires wiring this builder into the Linux x86-64 workflow and adapting archive verification and evidence generation to accept separate core and extension build provenance. The experiment ends when a separate extension build passes final-archive verification against an exact checked core archive and its useful code moves into the active recipe, or when the approach is rejected and these trial scripts are removed. Retain any result selected for permanent review under `support/evidence/`.
