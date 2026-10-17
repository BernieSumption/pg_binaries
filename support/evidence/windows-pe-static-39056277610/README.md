# Windows PE static check: missing system-DLL classification

[Run 39056277610](https://github.com/BernieSumption/pg_binaries/actions/runs/39056277610) built PostgreSQL 18.6 and pgvector 0.8.7, and the relocated archive passed the initial DDL test. The PE static check then failed because its system-DLL list omitted `WLDAP32.dll`, which `libpq.dll` imports. [Microsoft's WinLDAP API reference](https://learn.microsoft.com/en-us/windows/win32/api/winldap/nf-winldap-ldap_bind) identifies `Wldap32.dll` as a Windows DLL available before the Windows 10 floor. The checker now includes it and requires a new run.

The retained `static-analysis.json` and two failed pilot records came from the CI artifact. Their PostgreSQL and pgvector SHA-256 values match the separately downloaded archives and checksum sidecars from the same run. They record a failed check, not passing publication evidence.
