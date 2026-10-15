# D05 — Windows runtime packaging

**F04 — runtime required, linking choice open.** The pilot's external VC redistributable prerequisite violates F04. Microsoft's [deployment guidance](https://learn.microsoft.com/en-us/cpp/windows/choosing-a-deployment-method?view=msvc-170) describes app-local DLLs and static linking; the [UCRT guidance](https://learn.microsoft.com/en-us/cpp/windows/universal-crt-deployment?view=msvc-170) distinguishes OS-provided UCRT from other runtime files.

Try permitted app-local DLLs first. Compare static linking for size and behaviour, including allocations crossing library boundaries. Check files against the exact toolchain's [redistribution terms](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170).

Establish the dependency set, test without preinstalled non-OS CRT files, and measure compressed/extracted overhead. The pilot's combined archive sizes do not provide that measurement. Use an isolated environment without removing runtimes from a shared runner.

## Completion

Select a permitted runtime packaging method and pass final-archive tests without a preinstalled non-OS CRT. Record compressed and extracted runtime overhead.
