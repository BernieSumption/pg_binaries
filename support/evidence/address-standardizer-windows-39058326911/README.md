# Address Standardizer Windows probe 39058326911

[GitHub Actions run 39058326911](https://github.com/BernieSumption/pg_binaries/actions/runs/39058326911) started on 2026-10-17 from `spike` and reached the 45-minute job timeout. Its uploaded `address-standardizer-windows-x86_64-probe` artifact contained [progress.log](progress.log). No source compilation or SQL result was reached.

The log records successful download and checksum verification of the retained PostgreSQL 18.6 pilot archive, checkout of the pinned Address Standardizer 3.7.0 source commit, and download of the checksum-verified PCRE2 10.48 source. The last marker is the start of `tar.exe -xjf` for that PCRE2 archive at 18:30:08 UTC. Inference: Windows tar extraction stalled; the log does not identify its internal cause. The next probe uses Python's `tarfile` module for this extraction.
