# Linux ARM64 local development

Run `bash platforms/linux/dev-container.sh` from the host to create or start the retained development container. It has the common system build dependencies, the repository at `/repo` and a persistent workspace at `/work`. Agents can enter it with `docker exec -it pg-binaries-linux-arm64-dev bash` and install further tools there as needed.

`build-postgresql-local.sh OUTPUT_DIR` builds PostgreSQL and copies its runtime archive, development archive, checksums and output manifest to the host. `build-extension-local.sh PACKAGE DEVELOPMENT_ARCHIVE OUTPUT_DIR` builds one extension package against a private copy of the supplied development archive and copies its archive, checksum and output manifest to the host.

Each invocation creates a separate build directory under `/work`. Installed tools, verified source downloads and Rust caches remain available between builds. The retained container shares installed system dependencies; dependency installation and changes to the environment require coordination between agents. The human review queue tracks the proposed default of one environment per active agent and practical concurrency limits.

`docker stop pg-binaries-linux-arm64-dev` retains installed tools and files; `docker rm pg-binaries-linux-arm64-dev` removes the container, while the host-mounted workspace remains.

The separate `verification/linux/run-local.sh` command checks final archives in a clean, disposable container.
