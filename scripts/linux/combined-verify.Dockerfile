FROM alpine:3.22
RUN apk add --no-cache bash binutils coreutils findutils grep openssl python3 shadow util-linux
COPY scripts/linux/verify-in-container.sh /usr/local/bin/verify-core
COPY scripts/postgis/verify-in-container.sh /usr/local/bin/verify-postgis
COPY scripts/tiger/verify-in-container.sh /usr/local/bin/verify-tiger
COPY scripts/linux/diagnostics-in-container.sh /usr/local/bin/verify-diagnostics
COPY scripts/linux/combined-verify-in-container.sh /usr/local/bin/verify-combined
COPY tools/check_elf_dependencies.py /usr/local/bin/check-elf-dependencies
COPY tools/stage_extension_archive.py /usr/local/bin/stage-extension-archive
COPY tools/check_postgis_license_inventory.py /usr/local/bin/check-postgis-license-inventory
COPY tools/check_source_identity.py tools/source_archive.py /verification/tools/
COPY support.json /verification/support.json
COPY support/postgresql-releases.json /verification/support/postgresql-releases.json
COPY support.json /work/support.json
COPY scripts/postgis/probe.sql /work/probe.sql
COPY scripts/tiger/probe.sql /repo/scripts/tiger/probe.sql
COPY tests /tests
RUN chmod +x /usr/local/bin/verify-core /usr/local/bin/verify-postgis \
    /usr/local/bin/verify-tiger /usr/local/bin/verify-diagnostics /usr/local/bin/verify-combined \
 && mkdir -p /repo/scripts/tiger
ENTRYPOINT ["/usr/local/bin/verify-combined"]
