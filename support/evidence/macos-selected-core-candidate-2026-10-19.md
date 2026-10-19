# Selected macOS core candidate retrieval trial

On 2026-10-19, the shared candidate retriever found the PostgreSQL 18.6 macOS arm64 archive in [successful selected-core run 39264498472](https://github.com/BernieSumption/pg_binaries/actions/runs/39264498472). It checked the GitHub artifact ZIP digest `abdca7f7beec38b41de5b3143707fdac7e09f9f5d95c0760f3988e708798e464` (artifact ID `12192063860`, 54,207,253 bytes), extracted the requested archive by safe path, and checked its adjacent SHA-256 sidecar. The archive SHA-256 was `33807e7b17519acf8643ed73429ba7c983cf9572be12048bdb7b6a872f682608`.

The archive manifest identifies PostgreSQL 18.6 macOS arm64 and builder run `39260057987` attempt 1 at revision `6bf40592ad718f4bf97d653dd1c3f9c6a7df8234`. The builder run is completed successfully on `spike` under the selected PostgreSQL workflow. The current checkout has no changes to the resolver's listed core build inputs since that builder revision, and the manifest's PostgreSQL source archive identity matches the current 18.6 source pin.

This is a local, non-compiling retrieval and provenance check. A selected extension CI run still needs to prove that the resolver stages this candidate and that a fresh runner verifies the final PostgreSQL and extension archives.
