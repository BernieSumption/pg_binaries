# Human review queue

No pending decision blocks the current local builds.

## Linux PostGIS: CFITSIO redistribution terms

The locally built Linux ARM64 PostGIS archive bundles Ubuntu's `libcfitsio.so.9` as part of GDAL's runtime dependencies. [CFITSIO declares its own licence](https://heasarc.gsfc.nasa.gov/docs/software/fitsio/c/f_user/node9.html), which [SPDX does not mark as OSI approved](https://spdx.org/licenses/CFITSIO.html). The current licence design accepts OSI-approved terms automatically and requires a human decision for alternative terms before the affected archive is published.

Please decide whether to approve the declared CFITSIO terms for this bundled library or have the Linux PostGIS recipe rebuilt with a narrower GDAL dependency set that omits CFITSIO. The archive can continue through local milestone 4 verification, but it cannot enter a public download until this is resolved.

## Linux PostGIS: Cyrus SASL redistribution terms

The locally built Linux ARM64 PostGIS archive bundles `libsasl2.so.2` through GDAL's runtime dependencies. The Ubuntu Jammy package copyright declaration identifies BSD-4-Clause for this library, and [SPDX does not mark BSD-4-Clause as OSI approved](https://spdx.org/licenses/BSD-4-Clause.html). The current licence design requires a human decision on alternative terms before publication.

Please decide whether to approve these terms for the bundled Cyrus SASL library or have the Linux PostGIS recipe omit the dependency. This does not block local milestone 4 verification, but the affected archive cannot enter a public download until it is resolved.

## Local build environments for concurrent agents

Linux currently reuses one retained development container with a broad set of installed dependencies. This avoids repeated setup, but its build wrappers replace `/opt/postgresql` and a shared development archive path, so concurrent extension builds can interfere. macOS uses retained Lume build VMs and a separate clean verification VM. Package dependency preparation is callable per component on GitHub runners and locally.

Please choose a default local iteration model after measuring the cost of preparing a fresh environment, repeating a build with retained source and compiler caches, and running multiple environments concurrently on the available host. One candidate is a retained development VM or container per active agent, prepared for the packages that agent works on. Another is one broadly prepared environment for serial work, with extra environments only when builds overlap. The decision should set a practical concurrency limit for Lume VMs and containers. Clean verification remains separate in either model. This decision does not block the Mac and Linux script refactor.
