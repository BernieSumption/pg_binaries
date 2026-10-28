# Human review queue

## PostGIS scope may require disproportionate packaging work

The current design requires one independently downloadable PostGIS archive containing `postgis`, `postgis_raster`, `postgis_sfcgal`, `postgis_topology` and the standalone TIGER Geocoder. That archive must carry the runtime libraries and data needed by all five SQL extensions. Raster support requires GDAL; SFCGAL support adds a substantial C++ dependency tree. The PostGIS archive must also install alongside PostgreSQL without conflicting files.

Spike 1 built GDAL and SFCGAL from source, used Conda for GEOS, PROJ and other dependencies, and needed separate tools to collect runtime libraries and assemble the archive. Recreating that machinery for Spike 2 appears to be substantially more work than the intended collection of build scripts. This is a concern about likely implementation cost, not a demonstrated failure: no Spike 2 PostGIS build or archive-overlap check has been attempted. The known duplicate Address Standardizer and TIGER Geocoder SQL files can be excluded from the PostGIS source build.

Is raster and SFCGAL support essential in the first slice? If so, keep the current design and attempt the full build, reviewing any concrete packaging difficulty that arises. If not, defer `postgis_raster` and `postgis_sfcgal` so the first package contains base PostGIS, topology and TIGER Geocoder. A smaller scope requires a design change. PostGIS implementation is paused for this decision because importing Spike 1's packaging machinery without review could defeat Spike 2's simpler design.

## Tart guest command channel during local builds

Tart 2.41.1 booted the macOS 26.6.2 build VM and completed the local PostgreSQL dependency, PostgreSQL and six extension-package builds. After those builds, an Address Standardizer build command and a harmless `/usr/bin/true` command both failed before execution with `GRPC.GRPCConnectionPoolError`, reporting that the Tart Guest Agent could not be reached. The VM remained running, SSH worked, and the guest-agent processes were present. One normal VM stop and restart restored `tart exec`; the six completed archives survived. The cause of the connection failure is unknown.

The current design uses Tart's guest agent for build commands. Should a restart be accepted as routine recovery for this failure, should command execution change to SSH, or should the VM route be reconsidered? Until that decision, Address Standardizer, pg_jsonschema and other work requiring the Tart command channel are blocked. The agent will not substitute SSH for builds or repeatedly restart the VM to hide the failure.

## Linux userspace portability

The current inventory format records a minimum Linux kernel version but no minimum distribution or libc version. The distribution design requires archives to carry runtime components beyond those guaranteed by the target operating system. Spike 1 handled this by bundling glibc and a static launcher, plus relocation and empty-host tests. That is a substantial packaging system compared with the build-script scope intended for Spike 2. Docker is available locally on ARM64, but no Spike 2 Linux build has been attempted.

Should the first Linux slice support a specified userspace baseline such as Ubuntu 22.04, allowing ordinary dynamically linked binaries, or retain the kernel-only claim and its libc-bundling work? A userspace baseline would change the inventory support contract and needs a design decision. Linux archive implementation remains paused pending that decision.

## Windows timing for the first public release

Milestone 7 prepares a candidate from the verified Mac and Linux targets, while milestone 9 schedules Windows x86_64. The milestones leave open whether Windows must be available before the first public release. Should the first release proceed with the verified Mac and Linux targets if Windows is not ready, or wait for Windows x86_64? This decision is needed before publication, not for the current Mac and Linux implementation work.

## Deferred Spike 1 review ideas

The Spike 1 queue recorded these ideas from Bernie with an explicit instruction to discuss and specify them before starting work. The size and correctness reviews remain deferred for the release-candidate review; bug hunting belongs to the later human-driven milestone 7.5:

- Review archive size and its main contributors before expanding the extension catalogue. Possible changes to compiler options, enabled features or compression need a separate decision.
- Ask an Astra agent for an adversarial review of the implementation and tests to find specific and systematic correctness issues.
- Discuss occasional manual checks of published downloads on operating systems and environments outside routine runner coverage. Define the scope before implementing a post-release process.

Spike 1 also queued per-platform built-in extension inventory and a coherent installation test. The Spike 2 distribution design gives a built-in SQL extension a `targets` list when availability differs by target, and its build design specifies individual and coherent installation checks. The current design covers both questions, so they do not need separate decisions in this queue.
