# pg_ivm Linux feasibility pilot

[Run 39073599882](https://github.com/BernieSumption/pg_binaries/actions/runs/39073599882) at revision `d088739f808018f914b1ff9f9de3cd4aa2449e0d` passed the pg_ivm 1.16 build and relocated archive verification with PostgreSQL 18.6 on native x86-64 and arm64 GitHub-hosted Ubuntu 24.04 runners. Verification ran in Alpine 3.22. The checked-in probe at that revision creates an incrementally maintained view, checks its initial contents, then checks maintenance after an insert and an update.

The [x86-64](x86_64-step-outcomes.json) and [arm64](arm64-step-outcomes.json) attempt records show successful core build, extension build, verification and archive identity steps. Their paired [x86-64](x86_64-static-analysis.json) and [arm64](arm64-static-analysis.json) reports passed ELF inspection and record the two archive SHA-256 digests for each architecture. The downloaded pg_ivm archive bytes matched their checksum sidecars and these reports. The workflow artifact includes the PostgreSQL core checksum sidecars, not the core archive bytes; their digests agree with the static reports:

- x86-64 core: `41d9e5fce6e5ae6634ba1b7fcffbee932dccbefd25b34081616eb09cdbddf06c`
- x86-64 pg_ivm: `fa86d00655fe7d3c6964cecee91551b7930fb4c47b6f0492ce334a64e3a78986`
- arm64 core: `35ae9543d344f67440061e4b86b246b45edae8a283f42bc678d833f597b81995`
- arm64 pg_ivm: `efa1e74cc25b5e309aca6b5ef5d335a8297a3f7975240ec4f2a4c0e689444246`

The extension build pins the unmodified upstream v1.16 source archive SHA-256 to `87807d6af1974fce591715d55f75d939dffea33ea6908b413e62d3dd79b9c583`. Archive bytes are not retained here, so this is feasibility evidence rather than independently rechecked publication evidence. Static ELF inspection also does not cover libraries loaded dynamically by application code.
