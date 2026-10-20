FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates clang curl git libclang-dev libssl-dev pkg-config python3 \
 && rm -rf /var/lib/apt/lists/*
COPY scripts/pg_jsonschema/linux-build-in-container.sh /usr/local/bin/build-pg-jsonschema
COPY tools/inventory_cargo_licenses.py /usr/local/bin/inventory-cargo-licenses
COPY tools/check_pg_jsonschema_component_inventory.py /usr/local/bin/check-pg-jsonschema-component-inventory
COPY tools/create_pg_jsonschema_component_inventory.py /usr/local/bin/create_pg_jsonschema_component_inventory.py
COPY support/evidence/pg-jsonschema-crate-licenses-2026-10-18 /opt/cargo-license-supplements
RUN chmod +x /usr/local/bin/build-pg-jsonschema
ENTRYPOINT ["/usr/local/bin/build-pg-jsonschema"]
