# Evidence and remaining coverage

Snapshot: 14 October 2026. These are existing observations; the specification work ran no new binary tests.

## What the pilot passed

| Combination | Environment and evidence | Proven scope |
| --- | --- | --- |
| PostgreSQL 18.6 + vector 0.8.7, Linux x86-64 | Ubuntu 24.04.5; [run 38480393168](https://github.com/BernieSumption/pg_binaries/actions/runs/38480393168), commit `be9aea2` | Final archives, two installation locations, schema corpus, ICU/libc, selected compression operations, vector/HNSW, bundled dependency licences; native CPU tuning disabled |
| PostgreSQL 18.6 + vector 0.8.7, Intel macOS | macOS 15.7.9; [run 38484019714](https://github.com/BernieSumption/pg_binaries/actions/runs/38484019714), commit `19b7466` | Final archives moved between locations, schema/collation/compression/vector checks, Mach-O dependency scan, licence inventory; native CPU tuning disabled |
| PostgreSQL 18.6 + vector 0.8.7, Windows x86-64 | Windows Server 2022, OS `10.0.20348.0`; [run 38479521174](https://github.com/BernieSumption/pg_binaries/actions/runs/38479521174), commit `119af5b` | Final archives, startup before and after relocation into a path with spaces, schema/collation/compression/vector checks; preinstalled VC runtime was present |
| PostgreSQL 18.6 + PostGIS 3.6.4, Linux x86-64 | Clean Ubuntu 24.04 Docker on a standard runner; [run 38488516771](https://github.com/BernieSumption/pg_binaries/actions/runs/38488516771), commit `d397992` | One combined archive; all seven PostGIS SQL extensions created; representative GEOS, EPSG transform, raster, topology, SFCGAL, standardization and TIGER normalization checks after relocation |

Linux archives also passed locally in clean Ubuntu 22.04 Docker with glibc 2.35. Ubuntu 22.04 is outside the new four-year target window at this snapshot.

### Size observations

Combined PostgreSQL/vector Actions artifacts measured approximately 30.7 MB (Linux), 30.1 MB (macOS) and 32.3 MB (Windows). Individual extension and runtime contributions remain unmeasured.

The PostGIS Actions artifact was 88,157,068 bytes. The local combined package was about 85 MB compressed and 253 MB staged, with 108 licence-path entries. Separate-extension download sizes remain unmeasured.

## Remaining verification gaps

- Public distribution and generated catalogue: temporary Actions artifacts may have expired and do not count as available coverage under FUNC012.
- Windows without a preinstalled non-OS CRT is unverified. The pilot declared a VC redistributable prerequisite, which does not satisfy FUNC004.
- Exact OS ranges, desktop Windows, newer OS environments and CPU-baseline verification remain unresolved.
- Only one PostgreSQL release and one pgvector release were built. No reuse of an extension archive across PostgreSQL minors has been demonstrated.
- PostGIS was tested on Linux only, in one combined archive. Independent module packages, required-dependency-only installation and other source lines are unverified.
- PostGIS used GEOS 3.10.2 and SFCGAL 1.4.1, limiting function coverage. The [SFCGAL profile](../extensions/items/planned/postgis_sfcgal.md) records the stricter tagged requirement found during research.
- TIGER normalization passed with an empty `state` table. Real Census geocoding was untested; FUNC009 now explicitly excludes the bulk corpus.
- Compile-option, contrib, resource, licence-obligation and schema dump/restore audits remain incomplete. XML/TLS support is required by the capability policy; verification remains outstanding.

## Cutoff expansion example

This dated, hand-checked example illustrates the cutoff. Future release lists will come from generated discovery.

| Publication date | Selected releases | Source |
| --- | --- | --- |
| 2025-09-25 | 18.0 | [PostgreSQL 18 announcement](https://www.postgresql.org/about/news/postgresql-18-released-3142/) |
| 2025-11-13 | 15.15, 16.11, 17.7, 18.1 | [Release announcement](https://www.postgresql.org/about/news/postgresql-181-177-1611-1515-1420-and-1323-released-3171/) |
| 2026-02-12 | 15.16, 16.12, 17.8, 18.2 | [Release announcement](https://www.postgresql.org/about/news/postgresql-182-178-1612-1516-and-1421-released-3235/) |
| 2026-02-26 | 15.17, 16.13, 17.9, 18.3 | [Release announcement](https://www.postgresql.org/about/news/postgresql-183-179-1613-1517-and-1422-released-3246/) |
| 2026-05-14 | 15.18, 16.14, 17.10, 18.4 | [Release announcement](https://www.postgresql.org/about/news/postgresql-184-1710-1614-1518-and-1423-released-3297/) |
| 2026-08-13 | 15.19, 16.15, 17.11, 18.6 | [Release announcement](https://www.postgresql.org/about/news/postgresql-186-1711-1615-1519-1424-and-19-beta-3-released-3365/) |

That is **21 PostgreSQL releases and 63 core release/platform targets** before OS tests. PostgreSQL 18.5 was not released; do not generate it from a numeric interval. Extension targets require their own release discovery and compatibility research, so a complete percentage cannot yet be stated.


See the [next architectural experiments](../functional/items/planned/architecture-spike.md) for the work needed to expand this evidence.
