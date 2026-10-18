# pgTAP Windows upstream-source generation attempt

[Run 39081721084](https://github.com/BernieSumption/pg_binaries/actions/runs/39081721084) downloaded the exact PostgreSQL 18.6 core and pinned pgTAP 1.3.4 source, installed GNU make and the SQL-generation tools on its disposable Windows runner, then stopped before running upstream `make all`. The first MSYS2 shell startup printed setup messages into the captured `cygpath` output. Its resulting `cd` argument included that text and named a nonexistent directory. The workflow produced no extension archive or verification artifact, so this attempt establishes no source-generation or runtime result.

The path conversion now calls MSYS2's `cygpath.exe` directly, and the subsequent shell invocations suppress profile startup. Rerun the workflow to test the actual upstream generation and relocated Windows behavior.
