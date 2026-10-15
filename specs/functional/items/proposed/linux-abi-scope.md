# Linux ABI scope

**Decision:** Use glibc as the first Linux ABI target, and whether to include musl systems such as Alpine.

Exact distribution and OS ranges still need research under the four-year support policy. Context: [F04](../../functional-policy.md#f04--relocation-requires-no-system-provisioning), [OS baseline reasoning](../planned/os-baseline-assessment.md).

**Recommendation for review:** Start with a documented glibc target and exclude musl from that artifact's compatibility claim. Research distribution baselines before approving the exact OS range; a musl offering would need its own build and verification.
