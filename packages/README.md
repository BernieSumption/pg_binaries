# Package layout and build contract

Each directory named in `support.json` represents one package. The `shared/` directory contains build helpers. An extension package may supply more than one SQL extension. Its `probes/` directory has one `<extension>.sql` probe for each SQL extension it supplies.

Each extension package has one `build.sh` entry point. `build.py extension-build` passes the operating system, architecture, each selected source's URL, SHA-256 and version in `support.json` order, then the PostgreSQL development prefix and output directory. Packages with the same recipe on both architectures keep one script per operating system; packages with material architecture differences can delegate to target-specific scripts. The recipe verifies its sources and writes one independently installable archive containing a top-level `postgresql/` directory and a `LICENCE` pointer. The build entry point does not create a VM or container.

`build.py prepare-dependencies` prepares system build tools for one component before compilation on a GitHub runner. Linux package requirements live in each package's `linux-build-requirements.txt`; common Linux tools live in `platforms/linux/base-build-requirements.txt`. macOS checks for basic compiler and archive tools. Selected source dependencies and versions remain in `support.json` and package-local lock files or dependency recipes. The preparation command is also available locally, but a retained development environment may contain tools for many packages.

PostgreSQL is the core package. Its `build.sh` entry point takes the operating system, architecture and operation, then delegates to target recipes for compilation, packaging and pinned dependency builds. `build.py` supplies the same target to this entry point for all three operations.

Packages may add files required by their builds, such as dependency recipes or lock files. `build.py` passes selected sources through the same interface for every package and has no package-specific branches. Shared tools under `platforms/linux/` manage the local Linux development environment. Package recipes own their compilation options and file selection. `packages/shared/fetch.sh` downloads and checks selected sources; `packages/shared/archive.sh` writes the common licence pointer, normalises shared directory permissions and creates an archive and checksum.

Linux PostgreSQL and PostGIS packaging use `platforms/linux/bundle-runtime.sh` to copy the runtime library closure. The helper compares any existing copy before accepting it, then scans newly copied libraries for further dependencies. `platforms/linux/relocate-runtime.sh` sets relative ELF library paths after the package has arranged its files.

Agents may edit this README when changing the contract, but must update the affected packages and `build.py` in the same change. Package-specific interfaces are not allowed unless this README explains why they are required.
