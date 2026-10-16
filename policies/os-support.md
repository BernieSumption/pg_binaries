# Operating system support

Clients download PostgreSQL archives and run them on the host that performs schema operations. Each archive must work on every OS version and architecture that its inventory entry claims, without relying on files or development packages from the build machine. The functional requirements and test process are defined in [the functional specification](../specs/functional.md) and [the testing specification](../specs/testing.md).

## Intended minimum versions

These are intended floors for future archives. They are decisions for planning builds and tests, not claims that current archives meet them. macOS and Linux support x86-64 and arm64; Windows supports x86-64.

| Platform | Intended minimum | Basis |
| --- | --- | --- |
| macOS | 11.0 (Big Sur) | arm64 Macs first shipped with Big Sur, making this the earliest common macOS floor for both supported architectures. PostgreSQL documents macOS as a supported platform but does not specify a minimum macOS release. [Apple's macOS Big Sur announcement](https://www.apple.com/newsroom/2020/11/macos-big-sur-is-here/) describes its availability alongside the first M1 Macs; [PostgreSQL 18 platform notes](https://www.postgresql.org/docs/18/supported-platforms.html) leave the minimum release unspecified. |
| Windows | 10.0.10240.0 (Windows 10, version 1507) | PostgreSQL 18 requires Windows 10 or later for its native Windows port. Use the first Windows 10 release as the baseline because PostgreSQL does not document a later minimum; the release predates the ten-year cutoff, so older Windows releases can be excluded on age grounds. [PostgreSQL 18 platform notes](https://www.postgresql.org/docs/18/installation-platform-notes.html) state Windows 10 or later; [Microsoft's Windows 10 release information](https://learn.microsoft.com/en-us/windows/release-health/release-information) identifies build 10240 as version 1507. |
| Linux | kernel 5.15 | This is the kernel generation used by Ubuntu 22.04 LTS's original release, which is the current Linux build container base. It provides a concrete, mainstream floor within the ten-year allowance. [Ubuntu's 22.04 release notes](https://documentation.ubuntu.com/release-notes/22.04/) document the release; [Ubuntu's kernel release cycle](https://ubuntu.com/about/release-cycle#ubuntu-kernel-release-cycle) documents its kernel series. PostgreSQL describes Linux as supported without setting a kernel minimum in [its platform documentation](https://www.postgresql.org/docs/18/supported-platforms.html). |

The Linux kernel number alone does not describe the user-space ABI. Build configuration must keep the required system ABI at or below the selected floor and bundle other non-universal libraries, as required by the functional specification. Current Linux artifacts have not established a glibc or other user-space baseline. The inventory schema currently records only a Linux kernel minimum, so it cannot express or validate a separate user-space ABI floor; support claims must not imply compatibility with arbitrary Linux distributions until archive tests demonstrate it.

The Windows minimum is an OS compatibility floor, not a recommendation to run an unserviced Windows edition. Microsoft ended standard support for Windows 10 version 22H2 on 14 October 2025, while some Windows 10 Enterprise LTSC releases continue under their own lifecycle. [Microsoft's Windows lifecycle FAQ](https://learn.microsoft.com/en-us/lifecycle/faq/windows) documents those distinctions. This policy retains Windows 10 because PostgreSQL's documented native minimum is Windows 10 and the specification permits retaining older OS versions; agents should not infer support for a specific edition's servicing status from the build number.

## Build and compatibility rules

Produce one binary set per architecture and platform, with no OS-version-specific variants within a supported range. Set build targets deliberately rather than inheriting the build runner's defaults. Bundle or statically link non-universal dependencies and use only platform interfaces available at the stated floor. On macOS, use a deployment target no newer than 11.0 and inspect linked system libraries. On Linux, inspect ELF interpreter and symbol-version requirements as well as kernel requirements. On Windows, inspect imported APIs and include non-universal runtime dependencies in the archive. An unavoidable external prerequisite requires a specification decision through `HUMAN_REVIEW_QUEUE.md` before an affected download is advertised.

Test archives on clean systems at the minimum and a current supported OS release, for every architecture declared for that OS, following the testing specification. Do not infer support from a successful build, a CI runner image, or upstream support for PostgreSQL alone. Advertise a minimum in `inventory.json` only after the archive passes the required behavioral tests on that floor and all dependencies satisfy the portability requirements.

## Current implementation gaps

The repository has x86-64 pilots and a Linux arm64 pilot targeting PostgreSQL 18.6. The Linux scripts can build and verify x86-64 or arm64 archives, while the macOS build targets x86-64 and the Windows build uses the x64 vcpkg tree. The [arm64 archive pilot](https://github.com/BernieSumption/pg_binaries/actions/runs/38954674617) passed on Ubuntu 24.04 on 2026-10-16, but there is no `inventory.json` recording verified minimum OS versions. These pilots therefore do not establish the intended support above.

As of October 2026, standard GitHub-hosted runners do not provide macOS 11 or Windows 10 endpoint hosts. Ubuntu 22.04 runner images currently use a newer kernel than 5.15; a container does not replace the host kernel. The proposed minima therefore lack the required endpoint test path under the current runner constraint. Investigate clean endpoint environments before finalizing or advertising these floors; if none can satisfy the testing specification, record the required decision in `HUMAN_REVIEW_QUEUE.md`. [GitHub-hosted runner matrix](https://docs.github.com/en/actions/reference/runners/github-hosted-runners), [Ubuntu 22.04 runner image](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2204-Readme.md).

The functional specification limits Windows support to x86-64. `support.json` records architecture support per operating system, and coverage planning derives only those platform and architecture pairs.

## Sources

- [Functional specification](../specs/functional.md)
- [Testing specification](../specs/testing.md)
- [PostgreSQL 18 supported platforms](https://www.postgresql.org/docs/18/supported-platforms.html)
- [PostgreSQL 18 platform-specific installation notes](https://www.postgresql.org/docs/18/installation-platform-notes.html)
- [PostgreSQL Windows port notes](https://wiki.postgresql.org/wiki/Windows)
- [Apple: macOS Big Sur is here](https://www.apple.com/newsroom/2020/11/macos-big-sur-is-here/)
- [Microsoft: Windows release information](https://learn.microsoft.com/en-us/windows/release-health/release-information)
- [Microsoft: Windows lifecycle FAQ](https://learn.microsoft.com/en-us/lifecycle/faq/windows)
- [Ubuntu 22.04 release notes](https://documentation.ubuntu.com/release-notes/22.04/)
- [Ubuntu release and kernel cycle](https://ubuntu.com/about/release-cycle)
