# Selected macOS extension attempts

On 2026-10-22, local first-release staging lacked current evidence for 92 macOS SQL-extension targets. An Actions plan-log audit found exact queued or running requests for 80 of them, including the long-running PostgreSQL 18.6 Intel PostGIS build. The remaining 12 requests below were checked against `support.json` with `tools/extension_archive_plan.py` and dispatched through the selected-target workflow. A later audit of completed runs found that HypoPG 16.15 x86-64 and pgTAP 15.19 arm64 had already passed but had not been imported; their duplicate requests were cancelled and their passing archives imported. The other ten requests remain attempts, not passing evidence.

- Collection 1.1.1, PostgreSQL 16.15, x86-64: [39708188093](https://github.com/BernieSumption/pg_binaries/actions/runs/39708188093).
- Collection 2.1.3, PostgreSQL 15.19: [arm64 39708191005](https://github.com/BernieSumption/pg_binaries/actions/runs/39708191005), [x86-64 39708193735](https://github.com/BernieSumption/pg_binaries/actions/runs/39708193735).
- Collection 2.1.3, PostgreSQL 16.15: [arm64 39708196272](https://github.com/BernieSumption/pg_binaries/actions/runs/39708196272), [x86-64 39708198544](https://github.com/BernieSumption/pg_binaries/actions/runs/39708198544).
- Collection 2.1.3, PostgreSQL 17.11: [arm64 39708201215](https://github.com/BernieSumption/pg_binaries/actions/runs/39708201215), [x86-64 39708203644](https://github.com/BernieSumption/pg_binaries/actions/runs/39708203644).
- Collection 2.1.3, PostgreSQL 18.6: [arm64 39708206630](https://github.com/BernieSumption/pg_binaries/actions/runs/39708206630), [x86-64 39708209109](https://github.com/BernieSumption/pg_binaries/actions/runs/39708209109).
- HypoPG 1.4.3, PostgreSQL 16.15, x86-64: duplicate [39708211365](https://github.com/BernieSumption/pg_binaries/actions/runs/39708211365) cancelled; passing [39700464811](https://github.com/BernieSumption/pg_binaries/actions/runs/39700464811) imported.
- pg_jsonschema 0.3.4, PostgreSQL 16.15, arm64: [39708213900](https://github.com/BernieSumption/pg_binaries/actions/runs/39708213900).
- pgTAP 1.3.4, PostgreSQL 15.19, arm64: duplicate [39708216603](https://github.com/BernieSumption/pg_binaries/actions/runs/39708216603) cancelled; passing [39700707397](https://github.com/BernieSumption/pg_binaries/actions/runs/39700707397) imported.
