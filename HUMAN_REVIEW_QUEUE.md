# Human review queue

## PostGIS package scope for the first macOS slice

The current design selects `postgis`, `postgis_raster`, `postgis_sfcgal`, `postgis_topology` and the standalone TIGER Geocoder in one independently downloadable PostGIS package. The archive must carry its runtime libraries and data, and files shared with the PostgreSQL archive must be byte-identical.

The Spike 1 macOS recipe built GDAL and SFCGAL from source, used a Conda dependency environment for GEOS, PROJ and other libraries, and used dedicated runtime-closure and archive-assembly tools to handle libraries also present in PostgreSQL. The selected PostGIS 3.6.4 release can disable its bundled Address Standardizer and TIGER Geocoder, so those duplicate SQL files are straightforward to avoid. Its GDAL and SFCGAL dependency closure and potential native-library overlaps still appear to require substantial packaging work. No Spike 2 PostGIS build has yet been attempted, so a conflicting archive has not been demonstrated.

Should the first macOS slice retain the full selected PostGIS feature set and accept this packaging work, or should `postgis_raster` and `postgis_sfcgal` be deferred so the first package supplies base PostGIS, topology and TIGER Geocoder? Another simpler package scope or dependency approach is also possible. A changed scope requires a design update. Until then, the full selection remains in force and PostGIS implementation is paused while PostgreSQL and the other extension packages proceed.

## macOS VM manager for local builds

Milestone 2 assumes Lume for local macOS builds, subject to human approval. The Lume 0.6.1 trial created a macOS ARM64 VM from Apple's latest restore image after a roughly 20 GB download. The VM booted, but Lume reported SSH unavailable. A separate `lume setup spike2-macos-arm64 --unattended tahoe --no-display` completed its offline patch, then failed all 60 SSH health checks and stopped the VM. The VM remains available for inspection; no build ran in it. Starting the VM headlessly also required host permission beyond the normal sandbox.

The [Tart quick start](https://github.com/openai/tart/blob/main/docs/quick-start.md) documents prebuilt macOS ARM64 images with SSH credentials, CLI control and read-only directory sharing. A Tart base image would require another substantial download and a short trial, but avoids Lume's unattended setup path. Should local macOS development switch to a Tart base image, or should the build sequence use another environment? The Lume trial is paused because it does not currently provide a usable command channel.

## Linux userspace portability

The current inventory format records a minimum Linux kernel version but no minimum distribution or libc version. The distribution design requires archives to carry runtime components beyond those guaranteed by the target operating system. Spike 1 handled this by bundling glibc and a static launcher, plus relocation and empty-host tests. That is a substantial packaging system compared with the build-script scope intended for Spike 2. Docker is available locally on ARM64, but no Spike 2 Linux build has been attempted.

Should the first Linux slice support a specified userspace baseline such as Ubuntu 22.04, allowing ordinary dynamically linked binaries, or retain the kernel-only claim and its libc-bundling work? A userspace baseline would change the inventory support contract and needs a design decision. Linux archive implementation is paused while independent macOS and shared verification work continues.
