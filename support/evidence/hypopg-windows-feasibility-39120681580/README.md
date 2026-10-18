# Windows HypoPG feasibility attempt 39120681580

[The first Windows x86-64 run](https://github.com/BernieSumption/pg_binaries/actions/runs/39120681580) failed during licence-inventory path collection. The retained PowerShell transcript reports that `TrimStart` received a two-character string where it required a character. The run retained a PDB file, so it reached the link stage, but this attempt provides no relocated archive or SQL result.

The probe now supplies explicit character values to `TrimStart`. Rerun the scoped workflow and inspect its final archive, SQL and PE results before claiming Windows feasibility. `windows-build.log` and `build-identity.txt` are copied from the short-lived CI artifact; generated binaries are not retained here.
