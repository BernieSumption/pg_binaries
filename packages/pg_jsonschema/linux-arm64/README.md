# pg_jsonschema Linux ARM64 local build

The package image adds `libclang-dev` to `pg-binaries-postgresql-linux-arm64`, which pgrx uses to generate PostgreSQL bindings. Build the base PostgreSQL image first, then run this wrapper from the repository root:

```sh
bash packages/pg_jsonschema/linux-arm64/build-local.sh \
  SOURCE_URL SOURCE_SHA256 VERSION \
  /path/to/postgresql /path/to/output
```

`/path/to/postgresql` is the extracted PostgreSQL installation and development archive, with `bin/pg_config` at its root. The wrapper builds a package-specific image, mounts PostgreSQL at `/opt/postgresql`, and writes the package archive to the output directory.
