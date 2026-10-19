# HypoPG macOS arm64 PG17.11 publication evidence

GitHub Actions run [39289944915](https://github.com/BernieSumption/pg_binaries/actions/runs/39289944915) succeeded at producer revision `4d5481a8d141b97e545ad8ade119542fc4acd09c`. Its fresh macOS 15.7.9 runner passed both `static-analysis` and `archive-suite`; the receipt and verification record bind those results to the final archive hashes below.

The selected-core resolver reused the checked core archive in this run's candidate artifact. Its target metadata identifies selected-core artifact run `39168273004`, and the embedded PostgreSQL manifest identifies the same run as the original core builder. The consumer run therefore skipped core compilation. The core archive SHA-256 is `e2fe14b3967cd06f4e9695dac2d8649bc46a3e211a9fa63b0a686d3a53018d4b`; the HypoPG archive SHA-256 is `4d77adb072570e44d755807d58974b5cedc63369fbee8466e37ab4a835167533`.

Artifacts: candidate ID `12203844270` (GitHub-reported ZIP SHA-256 `61a5fcd583be31a4402588d2c9a06900296782485a2f258d7f08940d68b35c56`) and publication ID `12203823784` (ZIP SHA-256 `afe7706a6d360904c7b4240e664f9fa5c4120da5315ed5136d2f2e3953360146`). The downloaded publication ZIP independently matched GitHub's digest.

The producer-snapshot importer at revision `4d5481a8d141b97e545ad8ade119542fc4acd09c` accepted the publication evidence. All five retained files match the publication artifact copies byte-for-byte, and all three tar archives inspected (core plus both HypoPG copies) had no absolute or parent-traversal paths. The verification record validates against both the producer and current support profiles.
