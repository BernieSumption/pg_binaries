# D04 — Relocation and indirect dependencies

**F04, F09 — established by pilot failures.** The pilot missed an ICU data library on macOS, required relocated PROJ/GDAL resource paths on Linux, and inherited pgvector's `-march=native` before correction. These failures justify checking transitive loading, resource lookup and effective compiler flags as well as startup. See [evidence](../../../testing/testing-evidence.md).

Platform adapters must remove builder-path dependencies and derive resource paths from the extracted prefix. Loader inspection finds known dependencies; feature execution catches runtime loading and resource access that inspection misses.

## Completion

Remove builder paths and host CPU assumptions, then pass dependency inspection and relocated feature tests on each advertised platform and OS range.
