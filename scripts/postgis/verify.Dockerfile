FROM alpine:3.22
RUN apk add --no-cache bash coreutils findutils grep python3 shadow util-linux
COPY scripts/postgis/verify-in-container.sh /usr/local/bin/verify-postgis-pilot
COPY tools/check_elf_dependencies.py /usr/local/bin/check-elf-dependencies
COPY tools/check_postgis_license_inventory.py /usr/local/bin/check-postgis-license-inventory
COPY scripts/postgis/probe.sql /work/probe.sql
COPY support.json /work/support.json
RUN chmod +x /usr/local/bin/verify-postgis-pilot
ENTRYPOINT ["/usr/local/bin/verify-postgis-pilot"]
