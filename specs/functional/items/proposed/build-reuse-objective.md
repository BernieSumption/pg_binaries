# Extension build reuse objective

**Decision:** State explicitly that we minimize distinct extension builds by reusing archives across genuinely compatible PostgreSQL minors, using upstream compatibility claims to plan verification?

The architecture already describes reuse. The proposed addition would make its objective explicit while retaining tests on every advertised minor. Context: [F08](../../functional-policy.md#f08--each-advertised-extension-combination-works), [build planning](../../functional-architecture.md#build-planning-and-reuse).

**Recommendation for review:** Add the objective to F08: minimize distinct extension builds by reusing archives across compatible PostgreSQL minors. Use upstream claims to plan verification; advertise reuse only after testing each minor. This makes the existing architecture's purpose explicit without reducing verification.

## Review context

FEEDBACK: do we need to add explicit indication that the goal is a) to minimise the number of compiled extensions by sharing ones that are genuinely compatible across minors, and b) trust-but-verify on the documented compatibility range, defer to the project on which minors a version supports, but verify with tests.
