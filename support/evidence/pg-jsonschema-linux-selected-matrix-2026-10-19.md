# pg_jsonschema selected Linux matrix, 19 October 2026

At revision `614b9a5`, the shared dispatcher selected pg_jsonschema 0.3.4 for seven remaining Linux targets. Each build job produced a final extension archive and transferred it with a checked PostgreSQL core archive to a fresh runner. That runner passed the relocated Alpine archive suite and ELF closure. The artifacts were downloaded and independently imported with the exact source revision; all 11 retained files for each target matched the CI copies byte-for-byte.

- PostgreSQL 15.19 x86-64: [run 39203559616](https://github.com/BernieSumption/pg_binaries/actions/runs/39203559616), core built in the selected run, 9.3 elapsed runner-minutes.
- PostgreSQL 15.19 arm64: [run 39203562875](https://github.com/BernieSumption/pg_binaries/actions/runs/39203562875), core built in the selected run, 7.7 runner-minutes.
- PostgreSQL 16.15 x86-64: [run 39203560282](https://github.com/BernieSumption/pg_binaries/actions/runs/39203560282), core built in the selected run, 9.2 runner-minutes.
- PostgreSQL 16.15 arm64: [run 39203560326](https://github.com/BernieSumption/pg_binaries/actions/runs/39203560326), core built in the selected run, 7.6 runner-minutes.
- PostgreSQL 17.11 arm64: [run 39203560220](https://github.com/BernieSumption/pg_binaries/actions/runs/39203560220), core built in the selected run, 8.4 runner-minutes.
- PostgreSQL 18.6 x86-64: [run 39203560632](https://github.com/BernieSumption/pg_binaries/actions/runs/39203560632), core reused from run `39178721826`, 5.2 runner-minutes.
- PostgreSQL 18.6 arm64: [run 39203560784](https://github.com/BernieSumption/pg_binaries/actions/runs/39203560784), core reused from run `39178721826`, 5.3 runner-minutes.

These jobs consumed about 52.7 runner-minutes in total. Together with the [PostgreSQL 17.11 x86-64 fallback and reuse trials](pg-jsonschema-linux-dynamic-core-2026-10-19.md), they cover all eight declared pg_jsonschema Linux profiles on the selected path. The next migration step is to preserve automatic changed-profile scheduling while removing the older publication workflows and their permanent core pins. Those code changes will make these records historical under the resulting profile source sets and require a final current-profile refresh.
