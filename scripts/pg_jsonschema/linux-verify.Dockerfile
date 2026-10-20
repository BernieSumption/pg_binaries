FROM alpine:3.22
RUN apk add --no-cache bash binutils coreutils grep python3 shadow util-linux
COPY scripts/pg_jsonschema/linux-verify-in-container.sh /usr/local/bin/verify-pg-jsonschema
COPY scripts/pg_jsonschema/probe.sql /work/probe.sql
COPY tools/check_elf_dependencies.py /usr/local/bin/check-elf-dependencies
COPY tools/check_pg_jsonschema_component_inventory.py /usr/local/bin/check-pg-jsonschema-component-inventory
COPY tools/create_pg_jsonschema_component_inventory.py /usr/local/bin/create_pg_jsonschema_component_inventory.py
RUN chmod +x /usr/local/bin/verify-pg-jsonschema
ENTRYPOINT ["/usr/local/bin/verify-pg-jsonschema"]
