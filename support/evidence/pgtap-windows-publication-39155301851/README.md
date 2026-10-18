# pgTAP Windows fresh-runner trial, 18 October 2026

[Run 39155301851](https://github.com/BernieSumption/pg_binaries/actions/runs/39155301851) built pgTAP 1.3.4 for PostgreSQL 17.11 on one Windows 2022 runner, then transferred the final archives to a separate Windows 2022 runner. The verifier inspected the archives, installed them after relocation, ran four pgTAP SQL assertions and checked the installed extension's owned objects. Both publication-profile cases passed. The build job took 40 seconds and the verification job 28 seconds, excluding queue time.

The retained [verification record](../../verification/pgtap-1.3.4-postgresql-17.11-windows-x86_64-current-39155301851.json) binds the pgTAP archive SHA-256 `fde76e924e0773e5b2195ed938ff7b78337436613304f7042f7efbf0af88d81b` to the PostgreSQL archive SHA-256 `c94d4cef57880ec80a4177570ab7c1f2e955f1e799a2d41fb38412e07c435285`. Both hashes were independently checked against the downloaded Actions artifact before retaining this record. The attempt, receipt, SQL output and static-analysis report are in `x86_64/`.

This proves the fresh-runner separation for this target. Its workflow still selects a fixed PostgreSQL release and pinned core run; target-driven dispatch and checked candidate retrieval remain architecture migration work.
