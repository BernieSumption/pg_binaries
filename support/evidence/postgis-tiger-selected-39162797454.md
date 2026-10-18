# PostGIS and TIGER selected Linux trial

Run [39162797454](https://github.com/BernieSumption/pg_binaries/actions/runs/39162797454) completed successfully on `spike` at revision `a1e450d1912274d74da1c62304ebd1d6f7091da3` on 2026-10-18. Its single `verify` job ran from 20:19:46 to 20:20:47 UTC (61 seconds). The Ubuntu 24.04 hosted runner used Docker to run the Alpine Linux 3.22.6 verifier on x86_64, sharing kernel `6.17.0-1022-azure`.

## Archive identity and phases

The job downloaded the selected PostgreSQL, PostGIS and TIGER evidence artifacts from run `39075939610`, selected exactly one copy of each pinned archive, compared each archive SHA-256 with its pin, required sidecars, and ran `sha256sum --check`. The four identities matched retained x86_64 receipts:

- PostgreSQL 18.6: `e532b07c29904db82d1681f1a4ab815364b769a4e1f277c9de9bcd45d0cdc7c6`
- pgvector 0.8.7: `c94c26bb5eb07fe479d182e2b02c823bd8674698c8a3629d7fcc15b9fba67ccb`
- PostGIS 3.6.4: `8afe3bb3e27e483e8b54943eec89c65737b32a57b58f4fdf14abfa7ee67f6465`
- TIGER Geocoder 2025.2: `208c0e68f10d44d4b5e764627be488464329573907efcd346f167e2c7f9ef149`

The corresponding receipts are under `support/evidence/linux-publication-39075939610/x86_64/`, `support/evidence/postgis-publication-39075939610/x86_64/` and `support/evidence/tiger-publication-39075939610/x86_64/`. The TIGER receipt also binds PostGIS 3.6.4 as its prerequisite using the matching SHA above.

The run log shows the archive-suite, relocation, and combined Alpine phases completing, followed by `PASS: requested Alpine verification phases completed for PostgreSQL 18.6 (x86_64)`. The PostGIS output lists all four advertised SQL extensions—`postgis`, `postgis_raster`, `postgis_sfcgal` and `postgis_topology`—and shows their creation plus representative spatial, raster and topology results. For TIGER, the log shows successful checksum checks for core, PostGIS and TIGER, initialization after copying the required `scripts/tiger/probe.sql`, three extension creations, a completed `DO` probe block, and the relocated PostGIS/TIGER pass. This confirms the selected smoke probe ran; it does not establish populated Census geocoding support.

The log also reports checking architecture and dependencies for 290 ELF files and checking source/licence mapping for 96 PostGIS components. The static-analysis report files were included in the retained run artifact but could not be inspected locally: the 131,502,884-byte (about 125.4 MiB) artifact download stalled at zero bytes despite an approved network retry. The artifact upload log reports 25 files and a seven-day retention period. The combined-phase log summary is available from the run URL above; this report does not claim independent inspection of the uploaded static reports.

This is selected Linux trial evidence for PostgreSQL 18.6 on x86_64. It does not establish coverage for other architectures, PostgreSQL releases, or every case required by publication profiles, and is not a publication record.
