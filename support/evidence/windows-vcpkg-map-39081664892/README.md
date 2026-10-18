# Windows vcpkg ownership-map attempt

[Run 39081664892](https://github.com/BernieSumption/pg_binaries/actions/runs/39081664892) installed the selected vcpkg packages and compiled PostgreSQL 18.6 on Windows 2022. Packaging stopped when `map_vcpkg_dlls.py` rejected the installed ICU status paragraph under its exactly-one-version-field assumption. The [retained failure lines](failed-log.txt) identify the rejected package and step. The runner did not upload a final archive or publication record, so this run establishes no release coverage.
