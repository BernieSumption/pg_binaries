# pgTAP Windows upstream-source generation attempt

[Run 39081816082](https://github.com/BernieSumption/pg_binaries/actions/runs/39081816082) verified the pinned pgTAP 1.3.4 source and converted Windows paths directly with MSYS2 `cygpath.exe`. It then stopped before source generation because invoking Bash without its login profile omitted `/usr/bin` from `PATH`, so `pacman` could not be found. No extension archive or runtime result was produced.

The script retains direct `cygpath.exe` conversion and now starts Bash with its normal login environment for package installation and `make all`. Those steps do not capture Bash startup output as a path value. Rerun the workflow to verify upstream generation and the relocated PostgreSQL probe.
