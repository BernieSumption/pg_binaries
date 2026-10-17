# HypoPG Linux source-build pilot

[Run 39068360807](https://github.com/BernieSumption/pg_binaries/actions/runs/39068360807) at revision `3a600990f3deed8e32c57b249c31653d319b50b2` passed the PostgreSQL 18.6 and HypoPG 1.4.3 build and relocated verification steps on native x86-64 and arm64 runners. The retained [x86-64](x86_64-step-outcomes.json) and [arm64](arm64-step-outcomes.json) manifests show each step outcome. This is a feasibility pilot, not a publication verification record.

The downloaded HypoPG archives match their SHA-256 sidecars: `44544a1bdd5156a6ecaf1a6921c7a796fbda6f8e8faabbeb9001aa64e3cf22d5` on x86-64 and `a36c67d70490298c06daa64d480e13a21551cffdd8e7898bee52d2c9d88eee78` on arm64. The [x86-64](x86_64-static-analysis.json) and [arm64](arm64-static-analysis.json) reports bind those digests and their respective PostgreSQL core archive digests to passed ELF inspection. The pilot archive files are not retained in Git.
