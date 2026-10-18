# Intel HypoPG target without a permanent core run ID

The [selected Intel HypoPG run 39177688539](https://github.com/BernieSumption/pg_binaries/actions/runs/39177688539) passed its build and fresh-runner archive-suite and static-analysis checks at revision `23692db7242d9488afccfe259e00c0163a6f8105`. Its static target file no longer contains a PostgreSQL Actions run ID. The checked core resolver reused the PostgreSQL 18.6 archive whose SHA-256 is `4eb0125ce114880d2d923a3873d2de148b05a895852aea40aed60c664eafea28`, and the generated runtime target recorded its builder provenance. The final HypoPG archive SHA-256 is `1bad6409dc86a2e40388e9df3d5a96fb2f693bcb4ecb678d8e416dacea926c2d`.

The candidate and publication artifacts were downloaded and imported with the exact-source importer from revision `23692db`. The imported verification record matches the CI artifact byte for byte. It records both cases as passed on macOS 15.7.9 x86-64 under profile revision `413a9563aafa8b64d0f3f6cdc13c4405c56fa98cfdd3762173c4900d29ce5912`.

The later change adding the shared macOS evidence helper to the HypoPG profile source list makes this record historical for the updated profile. Reverify that profile after the helper migration is committed.
