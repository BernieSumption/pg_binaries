# D09 — OS and ABI baselines

**F04 — exact ranges unresolved.** Assess named OS releases under the four-year policy. An older compiler SDK or build container can remain useful even when that OS is outside the supported runtime window.

Identify Linux libc/CPU requirements and distributions, Intel macOS releases, Windows desktop editions/feature releases, and available verification environments. Record any evidence gaps or narrowing needed to preserve current OS support. The glibc scope option is a [product decision](../proposed/linux-abi-scope.md).

## Completion

Record exact assessed OS, ABI and CPU ranges with reasons and verification environments. Resolve Linux ABI scope and retain evidence gaps until tested.
