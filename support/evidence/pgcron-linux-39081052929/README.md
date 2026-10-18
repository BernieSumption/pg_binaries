# pg_cron 1.6.8 Linux x86-64 feasibility result

[Run 39081052929](https://github.com/BernieSumption/pg_binaries/actions/runs/39081052929) built unmodified pg_cron 1.6.8 against PostgreSQL 18.6 on a native x86-64 runner. Its extension archive SHA-256 is `7e4477ab62588b9e1860bc6cc6237448fafc80ad4a8ada1c89d86222173cd223`; the exact core archive SHA-256 is `eb62e7ecff782399672f7850e02e54b4428fd0af9c234e9cfef9f45b6209e053`. The downloaded extension sidecar matched the final archive.

The [raw attempt](x86_64/attempt.json) records passed source build and relocated Alpine 3.22 verification. The [static report](x86_64/static-analysis.json) binds both archive hashes and reports ELF dependency closure. The runtime probe created the extension and observed a scheduled background-worker job complete. The binary archives remain temporary CI artifacts. This is feasibility evidence for one target, not a publication-profile record or proof for other architectures and PostgreSQL versions.
