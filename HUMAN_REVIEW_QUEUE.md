# Human review queue

No pending decision blocks the current local builds.

## Linux PostGIS: CFITSIO redistribution terms

The locally built Linux ARM64 PostGIS archive bundles Ubuntu's `libcfitsio.so.9` as part of GDAL's runtime dependencies. [CFITSIO declares its own licence](https://heasarc.gsfc.nasa.gov/docs/software/fitsio/c/f_user/node9.html), which [SPDX does not mark as OSI approved](https://spdx.org/licenses/CFITSIO.html). The current licence design accepts OSI-approved terms automatically and requires a human decision for alternative terms before the affected archive is published.

Please decide whether to approve the declared CFITSIO terms for this bundled library or have the Linux PostGIS recipe rebuilt with a narrower GDAL dependency set that omits CFITSIO. The archive can continue through local milestone 4 verification, but it cannot enter a public download until this is resolved.

## Linux PostGIS: Cyrus SASL redistribution terms

The locally built Linux ARM64 PostGIS archive bundles `libsasl2.so.2` through GDAL's runtime dependencies. The Ubuntu Jammy package copyright declaration identifies BSD-4-Clause for this library, and [SPDX does not mark BSD-4-Clause as OSI approved](https://spdx.org/licenses/BSD-4-Clause.html). The current licence design requires a human decision on alternative terms before publication.

Please decide whether to approve these terms for the bundled Cyrus SASL library or have the Linux PostGIS recipe omit the dependency. This does not block local milestone 4 verification, but the affected archive cannot enter a public download until it is resolved.

## Proposed local Lume iteration overview

Proposed design text: A retained, stopped Lume base VM contains macOS, Xcode Command Line Tools and `pkg-config`. It contains no PostgreSQL or extension build outputs. Local macOS iteration uses a build clone for compilation and a separate clean clone to verify the final archive bytes. The clones start without a viewer; SSH runs build and verification commands, and `scp` transfers source and archives. Build files live under the guest user's home directory so they survive a graceful shutdown. Project clones can be stopped or deleted after use. Linux uses local Docker containers or Lume VMs with separate build and clean verification environments. GitHub builds begin after both ARM64 targets pass locally.

This sequence has been checked on Lume 0.6.1 with a macOS 26.6.2 ARM64 guest: C compilation, detached boot and log path, SSH, key-based `scp`, cloning, clean-VM isolation, home-directory persistence after shutdown, and deletion of a throwaway VM. This Lume version has no `lume cp` command.

This is a documentation proposal for human review and does not block local builds.
