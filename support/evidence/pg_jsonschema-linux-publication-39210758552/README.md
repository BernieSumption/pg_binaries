# pg_jsonschema Linux selected publication, 19 October 2026

[Run 39210758552](https://github.com/BernieSumption/pg_binaries/actions/runs/39210758552) ran the Linux changed-profile scheduler at revision `80c23e1`. All eight selected pg_jsonschema 0.3.4 targets passed: PostgreSQL 15.19, 16.15, 17.11 and 18.6 on Linux x86-64 and arm64. Each target passed the relocated Alpine 3.22 archive suite and ELF closure checks. Their exact archive identities, reports, receipts and records were imported with `tools/import_pg_jsonschema_linux_publication.py`.

The extension archive SHA-256 values are:

- PostgreSQL 15.19 x86_64: `d156008823c9a487a596e55ea81867e0972fe17f93207489f2ca4d9127a4c9d6`
- PostgreSQL 15.19 arm64: `b041db77cbc73690068cbf6aa4cb01c8845271793d71ad969942dc75ef2fcb6d`
- PostgreSQL 16.15 x86_64: `96f3697069f2d4ee0329c29627a2a427a26e8af32a3a116eb79f37ab25a3fd7a`
- PostgreSQL 16.15 arm64: `93f06a9b95e90392a84a8a842abaa411176e69034e54739c36915c0e1cc8657b`
- PostgreSQL 17.11 x86_64: `9225508cf0741b66e81015d922f7577f0f3304f2f6f0a7214e9e875cff9fd02a`
- PostgreSQL 17.11 arm64: `56b51143cd779e87bba67c930ce00a0e13a12041c915f335d2087b9fea07ecad`
- PostgreSQL 18.6 x86_64: `b8ae3410ac80d90ba65f144a68619c61ee97c2d518ca73897c580fd7df5cb8fb`
- PostgreSQL 18.6 arm64: `e0f1e46987ac6525097c5c0114e896513ba5d8d375cc143384bdfef5917c8062`

Each PostgreSQL core archive was built in run 39210758552; none was reused from another run. The target-specific `core-resolution.json` and receipts retain the exact core archive hash and provenance. These pg_jsonschema candidates remain release-ineligible while the Seahash notice is unresolved.
