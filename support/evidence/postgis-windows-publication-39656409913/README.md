# Selected Windows PostGIS archive trial

[Run 39656409913](https://github.com/BernieSumption/pg_binaries/actions/runs/39656409913) built PostGIS 3.6.4 for the checked PostgreSQL 18.6 Windows x86-64 core. A separate fresh runner relocated the exact archives, passed SQL probes for all four PostGIS extension names, and inspected 301 PE files with no dependency findings. The retained [static report](static-analysis.json), [PE report](pe-dependency-analysis.json), and [SQL output](probe-output.txt) bind those results to the archive digests.

The job failed afterward while creating publication records because its emitter searched for root-level `metadata.json`; the archive contains `postgis/metadata.json`. The emitter now uses the archive's actual path. The old run remains historical technical evidence; rerun the selected workflow before importing current-profile records.
