# macOS arm64 PostGIS archive trial

On 2026-10-21, [run 39602429364](https://github.com/BernieSumption/pg_binaries/actions/runs/39602429364) built unmodified PostGIS 3.6.4 and its four SQL extensions against the selected PostgreSQL 18.6 macOS arm64 archive. It assembled a 38-library runtime closure. The [owner report](conda-package-owners.json) identifies 23 conda-forge packages contributing libraries or runtime data; the only unresolved owner is SFCGAL, which this trial built from the pinned upstream source.

Archive assembly then failed because it requested the obsolete `LICENSES/inventory.json` from the selected PostgreSQL core. The central licence-pointer migration had already removed that file. This run therefore produced no PostGIS archive or fresh-runner result. A revised assembler uses the shared `LICENSES.md` pointer and is being tested in a later run.
