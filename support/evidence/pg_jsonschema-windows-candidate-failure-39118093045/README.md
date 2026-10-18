# pg_jsonschema Windows candidate failure

[Run 39118093045](https://github.com/BernieSumption/pg_binaries/actions/runs/39118093045) built `pg_jsonschema` 0.3.4 for PostgreSQL 18.6 on Windows x86-64, then stopped while creating its Cargo licence inventory. `inventory_cargo_licenses.py` rejected the pinned `pgrx-v0.16.1-LICENSE` because its checked bytes differed from the Windows checkout, where Git converted line endings to CRLF. The final extension archive was not created; the retained attempt record marks both archive-suite and static-analysis steps failed.

The failure log excerpt and workflow failure report preserve the error. `build-identity.txt` records source commit `cbe74b570d38aa0c4d42914e7a118bcb3adaee7a`, Cargo lock hash, core archive hash, and runner versions. The two attempt records came from the workflow's temporary publication directory and uploaded evidence directory.

The line-ending handling was fixed in commits `3bbee07` and `c8575bf`. Run [39118906656](https://github.com/BernieSumption/pg_binaries/actions/runs/39118906656) reruns the candidate with those fixes; this record documents only the earlier failed attempt.
