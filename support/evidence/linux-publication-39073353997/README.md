# Linux publication attempt 39073353997

[Run 39073353997](https://github.com/BernieSumption/pg_binaries/actions/runs/39073353997) used revision `fbc5ec1c17282c7a2dbf1e5ddbd000fee6597321`. The PostgreSQL and pgvector build failed on x86-64 and arm64 before either archive was emitted. The shared Linux build stopped when the ICU identity shell check received EOF from `dpkg-query`; [revision `d088739`](https://github.com/BernieSumption/pg_binaries/commit/d088739) fixes that check.

Both architectures retained `current-steps.json` for core, PostGIS, pgTAP, HypoPG and TIGER. The core archive suite, diagnostics and no-host-userspace checks were skipped; each extension archive suite was skipped because the core archive was unavailable. The pgTAP artifact also recorded `core_build: failure` and skipped pgTAP build and verification in `attempt.json`. Those files are retained with its evidence. No archive-bound verification records or success claims were produced.

The per-project outcome files were imported with the existing Linux core, pgTAP, HypoPG and TIGER importers. They record attempt outcomes only; they do not establish archive checksums or verification eligibility.
