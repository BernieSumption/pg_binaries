# Linux ARM64 local development

Run `bash platforms/linux/dev-container.sh` from the host to create or start the retained development container. It has the common system build dependencies, the repository at `/repo` and a persistent workspace at `/work`. Agents can enter it with `docker exec -it pg-binaries-linux-arm64-dev bash` and install further tools there as needed.

`build-postgresql-local.sh` and `build-extension-local.sh` call the repository's native `build.py` commands in this container and copy their archives back to the host. They share `/opt/postgresql` and `/work`, so concurrent builds need separate containers. `docker stop pg-binaries-linux-arm64-dev` retains installed tools and files; `docker rm pg-binaries-linux-arm64-dev` removes the container, while the host-mounted workspace remains.

The separate `verification/linux/run-local.sh` command checks final archives in a clean, disposable container.
