# Selected-target pgTAP Windows trial, 18 October 2026

[Run 39155927758](https://github.com/BernieSumption/pg_binaries/actions/runs/39155927758) selected the declared pgTAP 1.3.4, PostgreSQL 17.11, Windows x86-64 target through `tools/extension_archive_plan.py`. Separate Windows 2022 runners built and verified the final archives. Both current-profile cases passed, including static inspection, relocation and four SQL assertions.

The retained [verification record](../../verification/pgtap-1.3.4-postgresql-17.11-windows-x86_64-current-39155927758.json) binds pgTAP archive SHA-256 `b9b96a62ca180e2cd18ef86f41c05a6f54e80a2c4cc759bded7e1b3f3d145295` to PostgreSQL archive SHA-256 `c94d4cef57880ec80a4177570ab7c1f2e955f1e799a2d41fb38412e07c435285`. Both hashes were checked against the downloaded Actions artifact, and the importer accepted its attempt, receipt, reports and record under the current profile revision.

The select, profile-scope, build and verify jobs took 7, 7, 40 and 28 seconds respectively, excluding queue time. The earlier fixed-target trial used 40 and 28 seconds for build and verification. This measures roughly 14 seconds of extra runner time for the current planning and scope jobs; it does not measure broader fan-out or reuse costs.

The same workflow validates any currently selected PostgreSQL target, but only PostgreSQL 17.11 has passed this new path so far. Its core retrieval still uses a fixed run ID from `support/windows-core-pins/`, and the recipe and evidence tools are fixed to pgTAP 1.3.4.
