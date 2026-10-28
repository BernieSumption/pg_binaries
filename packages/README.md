# Package layout and build contract

Each directory here represents one package named in `support.json`. An extension package may supply more than one SQL extension. Its `probes/` directory has one `<extension>.sql` probe for each SQL extension it supplies.

For every implemented target, an extension package has `<target>/build.sh`. `build.py extension-build` calls that script on the target operating system. The arguments are each selected source's URL, SHA-256 and version in `support.json` order, followed by the PostgreSQL development prefix and output directory. The script verifies its sources and writes one independently installable archive containing a top-level `postgresql/` directory and a `LICENCE` pointer. Build dependencies are supplied by the job or local environment; the script does not start Docker.

PostgreSQL is the core package. Each implemented target has `postgresql/<target>/build.sh` to compile it and `package.sh` to create its runtime and development archives. A target has `build-dependencies.sh` when it builds PostgreSQL dependencies separately. These scripts use the corresponding `build.py` commands.

Packages may add files required by their builds, such as dependency recipes or lock files. Each extension package still has one build entry point per target: `<target>/build.sh`. `build.py` passes the selected sources through the same interface for every package and has no package-specific branches. Shared tools under `platforms/linux/` manage the local Linux development environment.

Agents may edit this README when changing the contract, but must update the affected packages and `build.py` in the same change. Package-specific interfaces are not allowed unless this README explains why they are required.
