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

- The upstream [pgvector 0.8.7 Makefile](https://github.com/pgvector/pgvector/blob/v0.8.7/Makefile) defaults to `-march=native` on Unix and explicitly recommends `make OPTFLAGS=""` for portability. Earlier Linux and Intel macOS pgvector builds inherited that runner-specific setting, so their passing functionality alone cannot establish portability across x86-64 CPUs. The pilot scripts now override `OPTFLAGS` to empty on both platforms; those archive bytes must be rebuilt and verified. The Windows Makefile has no `/arch` flag by default.
- The CPU-portable Linux scripts produced new archives entirely in Docker, with no `-march=native` invocation in the build log; the same archives passed the two-location clean Ubuntu 24.04 Docker verifier locally.
- [CPU-portable Linux run 38480393168](https://github.com/BernieSumption/pg_binaries/actions/runs/38480393168), commit `be9aea2`: **passed** on Ubuntu 24.04.5 LTS x86_64 with the empty pgvector `OPTFLAGS` override, two-location startup, relocated full SQL tests, and dependency license assertions. The CI compile log has no `-march=native`. [Temporary artifact 11856124035](https://github.com/BernieSumption/pg_binaries/actions/runs/38480393168/artifacts/11856124035), 30.7 MB. Archive SHA-256: PostgreSQL `767618fcbf1f5ccbb4a3b54a1cc163a36efc96bc89fb3089398c76e76e2553e9`; pgvector `39071e565cb997ba2482437d80a94489da0a3cd5d9767a9ec5a7a16536c89ab2`.
- REVIEW: A fresh Windows Actions runner has the Visual C++ runtime installed.
  A pass there alone does not demonstrate portability to a stock Windows host
  lacking that runtime. The pilot manifest declares the Microsoft Visual C++
  2015-2022 Redistributable (x64) as an OS prerequisite. The product decision
  to retain that prerequisite or bundle the permitted redistributable remains
  open; a stock host without it has not been tested.

## Evidence

Pilot CI runs:

- [Intel macOS pilot run 38472480717](https://github.com/BernieSumption/pg_binaries/actions/runs/38472480717), commit `ff99636`: PostgreSQL built, but the dependency bundler mistook a static `.a` archive for a Mach-O binary. Packaging stopped; the bundler needs a stronger file-type check.
- [Intel macOS pilot run 38475001486](https://github.com/BernieSumption/pg_binaries/actions/runs/38475001486), commit `5113c0c`: PostgreSQL and bundled Mach-O dependencies built successfully; license collection failed after treating PostgreSQL's own `libecpg.6.dylib` in the temporary install tree as an external Homebrew dependency. The staged archive already contains that library. The packaging logic needs to recognize identical staged PostgreSQL libraries while preserving collision checks.
- [Intel macOS pilot run 38477792325](https://github.com/BernieSumption/pg_binaries/actions/runs/38477792325), commit `8745830`: PostgreSQL dependency bundling and license collection passed (eight external libraries and six dependency license texts), and pgvector compiled. Packaging failed because the script expected Linux's `lib/postgresql/vector.so`; PGXS on this macOS build installed `lib/vector.dylib`. The archive path is corrected in the next iteration.
- [Intel macOS pilot run 38479157970](https://github.com/BernieSumption/pg_binaries/actions/runs/38479157970), commit `bcf36dd`: both archives built and transferred to a fresh Intel macOS verifier. `initdb` could not load bundled ICU because `libicuuc.78.dylib` referred to `@loader_path/libicudata.78.dylib`, and that data library was absent from the archive. The bundler now copies and validates missing `@loader_path` siblings from a library's original package, with collision checks and license inventory.
- [Intel macOS pilot run 38480393348](https://github.com/BernieSumption/pg_binaries/actions/runs/38480393348), commit `be9aea2`: both CPU-portable archives built and transferred. The fresh verifier started PostgreSQL 18.6 before and after relocation, demonstrating the bundled ICU runtime dependency fix. It then failed to find `tests/schema.sql` because the verification script resolved its relative script path after changing to the artifact directory. The path is now resolved before that directory change.
- [Intel macOS pilot run 38482040119](https://github.com/BernieSumption/pg_binaries/actions/runs/38482040119), commit `4890cfa`: both archives built and transferred. The fresh verifier started PostgreSQL 18.6 before and after relocation, passed the shared schema corpus, and created and queried an ICU collation. The verifier then stopped in locale discovery: `awk` exited early under Bash `pipefail`, making `locale -a` fail to flush stdout. The locale selector now consumes its entire input. This was a verifier error, not an observed failure of libc collation capability.
- [Intel macOS pilot run 38484019714](https://github.com/BernieSumption/pg_binaries/actions/runs/38484019714), commit `19b7466`: **passed** on macOS 15.7.9 x86_64. A fresh runner checked both archive hashes and manifests, started PostgreSQL 18.6 before and after moving the unpacked archive, applied the schema corpus, created and queried ICU and available libc (`ca_AD.UTF-8`) collations, exercised LZ4 TOAST and Zstandard WAL compression, installed pgvector 0.8.7 and queried an HNSW index, then scanned for non-system absolute Mach-O dependencies. The build log confirms pgvector compiled without `-march=native`. Dependency license inventory includes versioned ICU, OpenSSL, LZ4, Zstandard, libxml2, and libxslt texts. [Temporary artifact 11859033081](https://github.com/BernieSumption/pg_binaries/actions/runs/38484019714/artifacts/11859033081), 30.1 MB. Archive SHA-256: PostgreSQL `cef86c9843efcabc575ff3530e2263bb0e109e2967dd8d3bb28fdea395252b2b`; pgvector `9e1936b0108815cc8e22621f273f32df2eff0d93eb9995349f22cc01cfb37e5f`.
- [Windows pilot run 38472429193](https://github.com/BernieSumption/pg_binaries/actions/runs/38472429193), commit `4bb8625`: failed during Meson setup because `flex`/`win_flex` was absent from the runner PATH. This happened after dependency installation, before PostgreSQL compilation.
- [Windows pilot run 38475032700](https://github.com/BernieSumption/pg_binaries/actions/runs/38475032700), commit `4bd43ba`: **passed** on the Windows 2022 runner (reported OS version `10.0.20348.0`). A fresh verification job downloaded both archives, checked their SHA-256 companions, unpacked and relocated PostgreSQL into a path containing spaces, checked manifests and licenses, started PostgreSQL 18.6, applied the schema corpus, exercised ICU and libc collations, LZ4 TOAST, Zstandard WAL, gzip/LZ4/Zstandard dump compression, installed pgvector 0.8.7, and ran an HNSW indexed vector query. The temporary downloadable artifact is [11855395121](https://github.com/BernieSumption/pg_binaries/actions/runs/38475032700/artifacts/11855395121), about 32 MB. Archive SHA-256: PostgreSQL `21650125ac770d05892f3223eaeb839875ca90c1276bf593ee286eeb7f7f4554`; pgvector `b5cb3bab14dbfebf1eb13b284abd544b6ea18b962264460b8e889c2dc35ca25f`.
- [Windows two-location run 38479521174](https://github.com/BernieSumption/pg_binaries/actions/runs/38479521174), commit `119af5b`: **passed** on a fresh Windows 2022 verifier. It started and queried the unpacked PostgreSQL 18.6 archive, stopped it, moved the installation to a path containing spaces, and passed the full schema, collation, compression, and pgvector tests there. [Temporary artifact 11858335143](https://github.com/BernieSumption/pg_binaries/actions/runs/38479521174/artifacts/11858335143), 32.3 MB. Archive SHA-256: PostgreSQL `17d1c35c6eebfc9f28717444a52c241b0cafb1a40eb3d39871d82d01e6294d1e`; pgvector `42caa5ea0ea61f72433f67ac8ff4b005d024c120c1b4689cc71f6c5a11202ec8`.
- [Linux pilot run 38472795566](https://github.com/BernieSumption/pg_binaries/actions/runs/38472795566), commit `35d2b02`: failed during `configure` because the build image lacked `pkg-config`, needed to detect ICU.
- [Linux pilot run 38474130386](https://github.com/BernieSumption/pg_binaries/actions/runs/38474130386), commit `05d5bb9`: built both archives, unpacked and moved PostgreSQL onto clean Ubuntu 24.04, started the server, and passed the shared schema corpus. ICU collation creation then failed because `initdb` chose a SQL_ASCII database on the minimal verifier image. The verifier needs explicit UTF-8 initialization before collation testing. The run uploaded 30.9 MB of temporary artifacts (Actions artifact ID `11853088087`); no full end-to-end pass yet.
- [Linux pilot run 38475251840](https://github.com/BernieSumption/pg_binaries/actions/runs/38475251840), commit `ca7191d`: **passed** on Ubuntu 24.04.5 LTS, x86_64. The independent verifier unpacked and moved the final PostgreSQL archive, checked both manifests and licenses, started PostgreSQL 18.6, applied the shared schema corpus, created and queried ICU and libc collations, exercised LZ4 TOAST and Zstandard WAL and dump compression, installed pgvector 0.8.7, and ran an HNSW indexed nearest-neighbor query. The short-lived downloadable artifact is [11853747706](https://github.com/BernieSumption/pg_binaries/actions/runs/38475251840/artifacts/11853747706), about 31 MB. Archive SHA-256: PostgreSQL `783f1c08c50f19c9a752d298d26522da60dc16e525f07b631b5742b41d011fe2`; pgvector `ae17373ba603240d201a50d9c2d93a238b0689b19b73dc65b1a0abd9db272224`.
- A subsequent audit of that downloadable Linux archive found that its runtime directory held ICU, OpenSSL, LZ4, Zstandard, and other libraries without all corresponding dependency copyright texts. The first license collector looked up the `ldd` symlink path; Debian package ownership is often recorded against the resolved real file. Commit `b65faba` resolves the path, requires a copyright file for every copied non-system library, and avoids duplicating PostgreSQL's own libraries. This changes the archive bytes, so the earlier passing checksums are historical evidence only; a new build and verification are required.
- The repaired Linux archives were built locally entirely inside an x86-64 Docker container. Their license directory now includes ICU, OpenSSL, LZ4, Zstandard, libxml2, libxslt, and other copied library copyright files. The moved archives passed the clean Ubuntu 24.04 Docker verifier. The verifier now checks representative dependency license files explicitly. The local macOS Docker wrapper also now builds the verifier image for `linux/amd64`, matching the container it runs.
- [Final Linux license-checked run 38478489346](https://github.com/BernieSumption/pg_binaries/actions/runs/38478489346), commit `08f0d5a`: **passed** the same archive relocation and runtime test on Ubuntu 24.04.5 LTS x86_64, including assertions for representative bundled library copyright texts. [Temporary archive artifact 11857041455](https://github.com/BernieSumption/pg_binaries/actions/runs/38478489346/artifacts/11857041455), 30.7 MB. Archive SHA-256: PostgreSQL `39e53d611b5f4d6c84f7c1e987a0759b1b668480dd3446de7cea9ff0a34d33de`; pgvector `d4dc1c94eafab7a0f9a7c02d3955082788def6994e98dbb8b428aea2f3e139aa`.
- A verification-strategy audit found that Linux and Windows were checking startup only after relocation. The draft strategy asks for startup both before and after moving the extracted installation. Linux now starts and queries the original unpacked archive, stops it, then moves and exercises it fully; this passed locally inside Docker. Windows verification is being updated for the same two-location check. These extra tests do not change archive bytes, but the new CI runs remain the current verification evidence.
- [Linux two-location run 38479249676](https://github.com/BernieSumption/pg_binaries/actions/runs/38479249676), commit `c764cb2`: **passed** on Ubuntu 24.04.5 LTS x86_64 with startup and query before relocation, and full tests after relocation. [Temporary artifact 11857142511](https://github.com/BernieSumption/pg_binaries/actions/runs/38479249676/artifacts/11857142511), 30.7 MB. Archive SHA-256: PostgreSQL `0edc9b979802a45a2e1379d84fd1e4fa5256f53e61004e0308a02db88010ce16`; pgvector `25753c94bbc2c52d4f6470c203abc3514cbc1ea42c821e17b47fe2e70e31df4b`.
- The same locally built archive and current two-location verifier also passed inside a disposable Ubuntu 22.04 x86-64 Docker container, giving direct evidence for the Linux build's stated glibc 2.35 baseline. This is local Docker evidence, not a GitHub-hosted Ubuntu 22.04 runner result. The verifier's old success message had a hardcoded Ubuntu 24.04 label; it now reads the actual container OS release.

The core PostgreSQL 18.6 plus pgvector 0.8.7 slice now passes on all three
platforms. A Windows 2022 runner already has the Microsoft Visual C++ runtime;
stock-host behavior without it remains unverified. The listed downloadable
artifacts are short-lived Actions artifacts, not a permanent GitHub Release.

The macOS workflow was not dispatchable while its file existed only on `spike`:
GitHub returned a 404 because it was absent from the default branch. A path
scoped `spike` push trigger started the pilot without changing `main`.
