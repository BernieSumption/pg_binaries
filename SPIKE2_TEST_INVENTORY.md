# Previous test kinds and their migration

The `spike` branch has 119 Python test modules under `tests/`, plus SQL
probes, verification scripts and 229 verification profiles. They are sources
for new checks, not a suite to
copy wholesale. This inventory groups their distinct purposes. Each group
remains a candidate until the milestone named here implements, changes or
retires its behaviour. Before a milestone is complete, inspect the old files
in its groups and record the new test entry point and evidence in the
milestone result.

## Mac ARM64 installation slice

- **Source and target identity:** pinned upstream versions and checksums,
  selected PostgreSQL and extension compatibility, target architecture.
  Sources include `tools/source_archive.py`, `tests/test_source_archive.py`
  and `tests/test_check_source_identity.py`. Select and verify exact inputs
  before compiling.
- **Archive structure and metadata:** core manifest, extension payload,
  prerequisites, archive names, permissions and file-collision handling.
  Sources include `policies/install-process.md`, `tests/test_pgvector_archive_input.py`
  and archive layout tests. Check final archive bytes.
- **PostgreSQL tools and schema:** `initdb`, `pg_ctl`, `psql`, UTF-8, DDL,
  catalogue inspection, `pg_dump` and `pg_restore`. Sources include
  `tests/builtins/` and `scripts/macos/verify.sh`. Execute as an ordinary
  user and assert representative results.
- **Built-in SQL extensions and build capabilities:** discover installed
  controls, exercise advertised built-ins and requested options. Sources
  include `tools/discover_builtins.py`, `tests/test_discover_builtins.py`
  and `tests/builtins/`. Compare claims with the archive itself.
- **External extension behaviour:** create every advertised SQL extension,
  use its objects in schema DDL and assert an operation's result. Sources
  include project `probe.sql` files and `tests/extensions/`. Add each probe
  with its extension.
- **Installation and relocation:** copy the extension payload into the core,
  reject collisions, move the assembled prefix, remove access to the old
  path and repeat operations. Sources include `policies/testing.md`,
  `scripts/macos/verify.sh` and macOS relocation tests.
- **Native dependency closure:** inspect every executable and library for
  architecture, imports, loader paths and forbidden build paths. Mac sources
  include `scripts/macos/static_analysis.py` and the macOS static-analysis
  tests. Add ELF and PE inspection with those platforms.
- **Coherent installation:** install the complete selected set into one
  prefix and exercise it against one server, including one backend session
  where possible. The previous review queue proposes this; implementation
  begins with the first extension and grows with each addition.
- **Archive-bound results:** record input archive checksums, verifier
  revision, environment and pass/fail/skip outcomes. Sources include the
  old publication receipt and evidence tests. Keep a small record of the
  new slice; do not port cross-run profile invalidation.

## Mac hardening and release candidate

- **Diagnostics and symbols:** check that server logs and native failure
  evidence identify an archive and can be investigated. Sources include
  `policies/debugging.md`, macOS diagnostic scripts and symbol tests. Review
  while hardening the Mac slice and before publication.
- **Minimum OS claim:** select and inspect the deployment target and runtime
  imports; distinguish the supported minimum from the actual verifier OS.
  Sources include `policies/os-support.md` and macOS static-analysis tests.
- **Licence and redistribution evidence:** inspect included licences and
  bundled dependency records. Sources include `LICENSES.md`,
  `tools/license_pointer.py` and its tests. Complete before publication.
- **Inventory and publication:** derive only verified download claims,
  preflight names and checksums, then anonymously fetch public URLs after
  publication. Sources include `tools/candidate_inventory.py`,
  `tools/publication_preflight.py` and related tests. Implement a simpler
  fresh-run path for the first release candidate.
- **Manual bug hunting:** exercise the installed binaries beyond routine
  probes, record the environment and findings, and turn useful failures into
  focused regression checks. This recurs after material changes.

## Later platform slices

- **Linux isolation and ELF:** use a verifier environment separate from
  the builder, inspect ELF dependency closure and exercise installation in
  an Alpine-based container. Sources include `scripts/linux/verify.sh`,
  `tools/check_elf_dependencies.py` and their tests.
- **Windows packaging and PE:** inspect imported DLLs, application-local
  runtime files, path handling and native symbols on the Windows target.
  Sources include `scripts/windows/verify.ps1`,
  `tools/check_pe_dependencies.py` and their tests.
- **Older environments and kernel probes:** previous Ubuntu and QEMU
  checks are candidates for targeted manual bug hunting or a regression
  caused by a finding; they are not automatically part of each release run.

## Previous state machinery

Tests of `plan_work.py`, core artifact pins, candidate archive reuse,
historical verification profiles, changed-profile gates and retained-URL
reconciliation protect the old incremental process. Review their underlying
claims when implementing GitHub fan-out and release publication. Retire tests
that only assert the old process's internal state; retain the requirement to
verify the final bytes and to expose failed work.
