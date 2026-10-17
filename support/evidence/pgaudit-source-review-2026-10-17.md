# pgAudit source identities for selected PostgreSQL majors

The [pgAudit releases](https://github.com/pgaudit/pgaudit/releases) select 1.7.1 for PostgreSQL 15, 16.1 for PostgreSQL 16 and 17.1 for PostgreSQL 17. On 2026-10-17, the GitHub tag API resolved these tags to the commits below. I downloaded each commit-pinned GitHub source archive, computed SHA-256 over the received bytes and checked that its `pgaudit.control` declares the expected `default_version`.

- pgAudit 1.7.1: commit [`72da89c3fa02f3f2b9f3933214d91ad9c3428467`](https://github.com/pgaudit/pgaudit/commit/72da89c3fa02f3f2b9f3933214d91ad9c3428467), [archive](https://api.github.com/repos/pgaudit/pgaudit/tarball/72da89c3fa02f3f2b9f3933214d91ad9c3428467), SHA-256 `1e52448238908a09e0e78b3375dcefbfca51509fdbb3a4d92eb710e380ed3567`.
- pgAudit 16.1: commit [`a81792e8a4ea8f7aaf75bd610fcc4c2f96650bdc`](https://github.com/pgaudit/pgaudit/commit/a81792e8a4ea8f7aaf75bd610fcc4c2f96650bdc), [archive](https://api.github.com/repos/pgaudit/pgaudit/tarball/a81792e8a4ea8f7aaf75bd610fcc4c2f96650bdc), SHA-256 `b0648fcebe5a67340c406126e6dddc703fd03821a9ace80390e128a0d1c91c73`.
- pgAudit 17.1: commit [`538f89a93d8fd0d8913f3d740cacaea7b7eb66d9`](https://github.com/pgaudit/pgaudit/commit/538f89a93d8fd0d8913f3d740cacaea7b7eb66d9), [archive](https://api.github.com/repos/pgaudit/pgaudit/tarball/538f89a93d8fd0d8913f3d740cacaea7b7eb66d9), SHA-256 `20e980bd0c22b4ae33305ec2b774bd846bf343642adad108b6c28b422a648312`.

The 1.7.1 archive was downloaded twice and produced the same digest. These are source identities for candidate builds, not evidence that the releases compile or run against the selected PostgreSQL minors on any target platform.
