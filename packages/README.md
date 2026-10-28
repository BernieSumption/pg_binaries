# Package layout and build contract

Each directory here represents one package named in `support.json`. An extension package may supply more than one SQL extension. Its `probes/` directory has one `<extension>.sql` probe for each SQL extension it supplies.

For every implemented target, an extension package has `<target>/build.sh`. `build.py extension-build` calls that script on the target operating system. The arguments are each selected source's URL, SHA-256 and version in `support.json` order, followed by the PostgreSQL development prefix and output directory. The script verifies its sources and writes one independently installable archive containing a top-level `postgresql/` directory and a `LICENCE` pointer. Build dependencies are supplied by the job or local environment; the script does not start Docker.

PostgreSQL is the core package. Each implemented target has `postgresql/<target>/build.sh` to compile it and `package.sh` to create its runtime and development archives. A target has `build-dependencies.sh` when it builds PostgreSQL dependencies separately. These scripts use the corresponding `build.py` commands.

PostGIS has `macos-arm64/build-dependencies.sh` and `conda-lock.txt` for its geospatial build inputs. Linux PostgreSQL, PostGIS and pg_jsonschema have Dockerfiles to supply dependencies during local iteration. Docker orchestration belongs in shared `platforms/linux/` tools, which call the same `build.py` commands used by runner jobs. Package directories do not contain separate local build scripts.

Agents may edit this README when changing the contract. Keep it in sync with the package directories and `build.py` in the same change. New file roles or differences between packages must be described here; otherwise packages follow the layout and interfaces above.
