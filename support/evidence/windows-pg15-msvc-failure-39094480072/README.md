# Windows PostgreSQL 15.19 MSVC build failure 39094480072

GitHub Actions run [39094480072](https://github.com/BernieSumption/pg_binaries/actions/runs/39094480072) failed on source revision `73badaf98b5dbf6fbea88d760c1fc9367d190f43` after the pinned vcpkg install succeeded. No PostgreSQL build started.

The failure was dependency staging: `prepare_postgresql_15_msvc.py` could not find either `zdll.lib` or `zlib.lib` under `installed/x64-windows/lib`. The run log identifies the installed vcpkg port as zlib `1.3.2#1`. The retained `failure.txt` records the exact terminal error; the focused fix stages its CMake import library under PostgreSQL 15's expected `zdll.lib` name and accepts the corresponding `z.dll` runtime.
