# Human review queue

## PostgreSQL 18.6 build options and bundled extensions

The first macOS ARM64 and Intel archives were built with a minimum macOS version of 11.0 and PostgreSQL 18.6. Their configure commands enable ICU, LZ4, Zstandard, zlib, OpenSSL, libxml2, libxslt and e2fs UUID support. They explicitly disable Readline, libcurl OAuth, GSSAPI, LDAP, PAM, Bonjour, libnuma, liburing, SELinux, PL/Perl, PL/Python and PL/Tcl. PL/pgSQL is supplied by the standard build. These choices match the enabled and disabled options in `design/postgresql-options.md`; the three additional procedural languages remain draft exclusions pending review. Linux and Windows have no Spike 2 recipes yet, so their actual options cannot be reported.

Building all of PostgreSQL's `contrib` directory placed these 46 SQL extension controls in both Mac archives: amcheck, autoinc, bloom, btree_gin, btree_gist, citext, cube, dblink, dict_int, dict_xsyn, earthdistance, file_fdw, fuzzystrmatch, hstore, insert_username, intagg, intarray, isn, lo, ltree, moddatetime, pageinspect, pg_buffercache, pg_freespacemap, pg_logicalinspect, pg_prewarm, pg_stat_statements, pg_surgery, pg_trgm, pg_visibility, pg_walinspect, pgcrypto, pgrowlocks, pgstattuple, plpgsql, postgres_fdw, refint, seg, sslinfo, tablefunc, tcn, tsm_system_rows, tsm_system_time, unaccent, uuid-ossp and xml2. Fresh-runner PostgreSQL-only checks created and probed all 46 on both targets.

Should the three additional procedural languages remain excluded, and should all 46 bundled SQL extensions remain included? The design calls for this implementation review before replacing its draft decisions. Until then, the current design and macOS archive selections remain in force.

## PostGIS package scope for the first macOS slice

The current design selects `postgis`, `postgis_raster`, `postgis_sfcgal`, `postgis_topology` and the standalone TIGER Geocoder in one independently downloadable PostGIS package. The archive must carry its runtime libraries and data, and files shared with the PostgreSQL archive must be byte-identical.

The Spike 1 macOS recipe built GDAL and SFCGAL from source, used a Conda dependency environment for GEOS, PROJ and other libraries, and used dedicated runtime-closure and archive-assembly tools to handle libraries also present in PostgreSQL. The selected PostGIS 3.6.4 release can disable its bundled Address Standardizer and TIGER Geocoder, so those duplicate SQL files are straightforward to avoid. Its GDAL and SFCGAL dependency closure and potential native-library overlaps still appear to require substantial packaging work. No Spike 2 PostGIS build has yet been attempted, so a conflicting archive has not been demonstrated.

Should the first macOS slice retain the full selected PostGIS feature set and accept this packaging work, or should `postgis_raster` and `postgis_sfcgal` be deferred so the first package supplies base PostGIS, topology and TIGER Geocoder? Another simpler package scope or dependency approach is also possible. A changed scope requires a design update. Until then, the full selection remains in force and PostGIS implementation is paused while PostgreSQL and the other extension packages proceed.

## macOS VM manager for local builds

Milestone 2 assumes Lume for local macOS builds, subject to human approval. The Lume 0.6.1 trial created a macOS ARM64 VM from Apple's latest restore image after a roughly 20 GB download. The VM booted, but Lume reported SSH unavailable. A separate `lume setup spike2-macos-arm64 --unattended tahoe --no-display` completed its offline patch, then failed all 60 SSH health checks and stopped the VM. The VM remains available for inspection; no build ran in it. Starting the VM headlessly also required host permission beyond the normal sandbox.

The [Tart quick start](https://github.com/openai/tart/blob/main/docs/quick-start.md) documents prebuilt macOS ARM64 images with SSH credentials, CLI control and read-only directory sharing. A Tart base image would require another substantial download and a short trial, but avoids Lume's unattended setup path. Should local macOS development switch to a Tart base image, or should the build sequence use another environment? Local VM iteration is a required part of milestone 2, so Spike 2 implementation is paused until a usable local VM route is agreed and tested. Successful GitHub builds do not complete that local milestone.

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
