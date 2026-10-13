# PostgreSQL 18.6 pilot implementation log

This log records build choices, evidence, limitations, and new questions for the
one-minor pilot. The draft documents in `docs/` remain unchanged. This log does
not settle their open product decisions.

## Scope and source selection

- PostgreSQL **18.6** is the exact minor selected for all three platforms. The
  PostgreSQL project [announced it on 2026-08-13](https://www.postgresql.org/about/news/postgresql-186-1711-1615-1519-1424-and-19-beta-3-released-3365/).
- pgvector **0.8.7** is the selected extension release for all three platforms.
  Its [upstream changelog](https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md)
  dates it 2026-10-01.
- The pilot produces separate PostgreSQL and pgvector archives per platform.
  Each archive has a single top-level component directory, a machine-readable
  manifest, license texts, and a SHA-256 companion checksum. The extension
  manifest names the exact PostgreSQL minor it is built against.

## Verification plan

- Run the shared schema corpus in `tests/schema.sql` against the final moved
  PostgreSQL archive on every platform.
- Verify each final archive on the appropriate GitHub-hosted runner, including
  PostgreSQL startup, collations, compression, pgvector installation, and vector
  queries. Keep successful and failed workflow runs visible as evidence.
- Probe PostGIS feasibility on one platform only after the core slice passes.

## Access preflight

- On 2026-10-13, ordinary sandbox calls could not reach the Docker socket or
  resolve GitHub and PostgreSQL source hosts. Auto-reviewed sandbox escalation
  succeeded without a user prompt: `docker info` reported Docker 29.8.0 Linux;
  `gh api` returned this repository; `git ls-remote origin refs/heads/spike`
  returned a commit; an authenticated `git push --dry-run` succeeded; and an
  HTTPS HEAD request returned 200 for the PostgreSQL 18.6 source archive.
  Builds, source downloads, Git pushes, and CI operations should use that
  access path where the sandbox denies them.

## Current blockers and questions

- A fresh Windows Actions runner has the Visual C++ runtime installed. A pass
  there alone will not demonstrate portability to a stock Windows host lacking
  that runtime. The archive must either carry the redistributable runtime or
  declare it as a normal OS prerequisite; record which approach actually works.

## Evidence

No platform combination has passed end-to-end verification yet. Record run
links, archive checksums, exact operating system details, and any failures here
as the workflows run.
