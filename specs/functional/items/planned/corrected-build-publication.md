# D08 — Corrected-build publication

**F10, F11 — publication protocol.** Stage archives named with their full SHA-256 and matching metadata, verify them, then activate the catalogue revision. Changed bytes require a new filename and URL. Clients can identify stale cached builds while continuing to request the same upstream version.

Keep provenance after removing superseded binaries. Pinned sources alone do not establish reproducible archive bytes: local and CI pilot builds produced different hashes. The current contract requires integrity and traceability.

## Completion

Implement staged publication and atomic catalogue activation; pass corrected-build and cache checks. Obtain hosting authorization before publishing permanent releases.
