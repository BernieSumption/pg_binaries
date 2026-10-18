# PostGIS and TIGER selected Linux verifier attempt

[Run 39162664578](https://github.com/BernieSumption/pg_binaries/actions/runs/39162664578) on 2026-10-18 checked the four exact same-run archive inputs from run 39075939610 and ran the combined Alpine verifier on a fresh Ubuntu runner. Its core, PostGIS and TIGER phases passed: the core and pgvector tests relocated, PostGIS created and tested all four selected SQL extensions, and TIGER tested its PostGIS prerequisite and SQL probe. The diagnostics phase failed because the trial had not copied `debug-symbols/index.json` and its symbol files from the core artifact into the verifier input directory.

The job failed after 55 seconds. It retained phase logs and static-analysis reports as a temporary Actions artifact; no passing combined verification or publication record follows. The retry copies the retained debug-symbols tree, which the diagnostics phase checks against the exact archive hashes.
