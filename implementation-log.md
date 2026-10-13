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
  resolve GitHub and PostgreSQL source hosts. Escalated calls succeeded for
  some checks, but the user subsequently reported additional local permission
  prompts. `docker info` reported Docker 29.8.0 Linux;
  `gh api` returned this repository; `git ls-remote origin refs/heads/spike`
  returned a commit; an authenticated `git push --dry-run` succeeded; and an
  HTTPS HEAD request returned 200 for the PostgreSQL 18.6 source archive.
- Docker keeps compilation and compiled-artifact tests off the host, but access
  to the Docker socket is still a host permission boundary. Git staging and
  commits also write `.git`, and GitHub/source calls need network access.
  Those operations can prompt even when the build itself runs in Docker.
- The user requires an unattended run without further local permission prompts.
  The goal was paused while this access behavior was clarified, then the user
  explicitly resumed it after the local permission rules were installed.
- A machine-local, Git-ignored project rule file now exists at
  `.codex/rules/pilot.rules`. It covers Docker, the Linux Docker wrapper scripts,
  spike staging/commits/pushes, and pilot Actions inspection, artifact download,
  reruns, and workflow triggers. `codex execpolicy check` confirmed intended
  matches and that a main push and unrelated workflow trigger do not match.
  After restart, `docker info`, Docker builds, Git staging/commits/pushes, and
  GitHub Actions inspection have succeeded without further approval pauses.
  This is observed behavior for those tested operations, not a guarantee that
  every future command will be permitted.

## Operating constraints carried from the conversation

- Do not edit `docs/` or settle its unresolved product decisions. Keep new
  questions or implementation incompatibilities in this log with `REVIEW:`.
- Reuse shared version pins, archive layout, manifest fields, and
  `tests/schema.sql` across platforms. Use parallel agents only for distinct
  work, avoiding duplicate build logic where a common component is practical.
- All compilation and compiled-artifact tests on the local computer run inside
  Docker. Native macOS and Windows builds/tests run on standard GitHub-hosted
  runners. Keep workflow triggers narrow, timeouts bounded, and artifacts short
  lived. Do not publish a Release, choose a source-code license, or change main.

## Current blockers and questions

- A fresh Windows Actions runner has the Visual C++ runtime installed. A pass
  there alone will not demonstrate portability to a stock Windows host lacking
  that runtime. The archive must either carry the redistributable runtime or
  declare it as a normal OS prerequisite; record which approach actually works.

## Evidence

Pilot CI runs:

- [Intel macOS pilot run 38472480717](https://github.com/BernieSumption/pg_binaries/actions/runs/38472480717), commit `ff99636`: PostgreSQL built, but the dependency bundler mistook a static `.a` archive for a Mach-O binary. Packaging stopped; the bundler needs a stronger file-type check.
- [Intel macOS pilot run 38475001486](https://github.com/BernieSumption/pg_binaries/actions/runs/38475001486), commit `5113c0c`: PostgreSQL and bundled Mach-O dependencies built successfully; license collection failed after treating PostgreSQL's own `libecpg.6.dylib` in the temporary install tree as an external Homebrew dependency. The staged archive already contains that library. The packaging logic needs to recognize identical staged PostgreSQL libraries while preserving collision checks.
- [Windows pilot run 38472429193](https://github.com/BernieSumption/pg_binaries/actions/runs/38472429193), commit `4bb8625`: failed during Meson setup because `flex`/`win_flex` was absent from the runner PATH. This happened after dependency installation, before PostgreSQL compilation.
- [Linux pilot run 38472795566](https://github.com/BernieSumption/pg_binaries/actions/runs/38472795566), commit `35d2b02`: failed during `configure` because the build image lacked `pkg-config`, needed to detect ICU.
- [Linux pilot run 38474130386](https://github.com/BernieSumption/pg_binaries/actions/runs/38474130386), commit `05d5bb9`: built both archives, unpacked and moved PostgreSQL onto clean Ubuntu 24.04, started the server, and passed the shared schema corpus. ICU collation creation then failed because `initdb` chose a SQL_ASCII database on the minimal verifier image. The verifier needs explicit UTF-8 initialization before collation testing. The run uploaded 30.9 MB of temporary artifacts (Actions artifact ID `11853088087`); no full end-to-end pass yet.
- [Linux pilot run 38475251840](https://github.com/BernieSumption/pg_binaries/actions/runs/38475251840), commit `ca7191d`: **passed** on Ubuntu 24.04.5 LTS, x86_64. The independent verifier unpacked and moved the final PostgreSQL archive, checked both manifests and licenses, started PostgreSQL 18.6, applied the shared schema corpus, created and queried ICU and libc collations, exercised LZ4 TOAST and Zstandard WAL and dump compression, installed pgvector 0.8.7, and ran an HNSW indexed nearest-neighbor query. The short-lived downloadable artifact is [11853747706](https://github.com/BernieSumption/pg_binaries/actions/runs/38475251840/artifacts/11853747706), about 31 MB. Archive SHA-256: PostgreSQL `783f1c08c50f19c9a752d298d26522da60dc16e525f07b631b5742b41d011fe2`; pgvector `ae17373ba603240d201a50d9c2d93a238b0689b19b73dc65b1a0abd9db272224`.

macOS and Windows have not yet passed end-to-end verification. Record archive
checksums, exact operating system details, and failures as the workflows run.

The macOS workflow was not dispatchable while its file existed only on `spike`:
GitHub returned a 404 because it was absent from the default branch. A path
scoped `spike` push trigger started the pilot without changing `main`.
