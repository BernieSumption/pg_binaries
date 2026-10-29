# Human review queue

No pending decision blocks the current local builds.

## Linux PostGIS: CFITSIO redistribution terms

The locally built Linux ARM64 PostGIS archive bundles Ubuntu's `libcfitsio.so.9` as part of GDAL's runtime dependencies. [CFITSIO declares its own licence](https://heasarc.gsfc.nasa.gov/docs/software/fitsio/c/f_user/node9.html). No listing of the CFITSIO licence as open source by OSI, FSF or Debian has been identified, so the dependency licence design requires a human decision before publication.

Please decide whether to approve the declared CFITSIO terms for this bundled library or have the Linux PostGIS recipe rebuilt with a narrower GDAL dependency set that omits CFITSIO. The archive can continue through local milestone 4 verification, but it cannot enter a public download until this is resolved.

## Local build environments for concurrent agents

Linux currently reuses one retained development container with a broad set of installed dependencies. This avoids repeated setup, but its build wrappers replace `/opt/postgresql` and a shared development archive path, so concurrent extension builds can interfere. macOS uses retained Lume build VMs and a separate clean verification VM. Package dependency preparation is callable per component on GitHub runners and locally.

The proposed default is one development environment per active build agent. On Linux, each agent creates a container from the prepared image with its own writable workspace and PostgreSQL installation. On macOS, each agent clones the Lume base VM, then prepares the dependencies for the packages it builds. The agent retains that environment and its source and compiler caches across iterations. A separate clean environment verifies final archive bytes. This removes interference between concurrent builds without repeating dependency installation on every attempt.

Please review this default and set a practical limit on concurrent Lume VMs and containers after measuring clone or container startup, dependency preparation, a repeated build and host memory use with two builds running. The existing shared Linux container remains useful for serial work until this decision is made. This decision does not block the Mac and Linux script refactor.
