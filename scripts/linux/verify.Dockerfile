FROM alpine:3.22
RUN apk add --no-cache bash binutils coreutils findutils grep openssl python3 shadow util-linux
COPY scripts/linux/verify-in-container.sh /usr/local/bin/verify-pilot
COPY tools/check_elf_dependencies.py /usr/local/bin/check-elf-dependencies
COPY tools/stage_extension_archive.py /usr/local/bin/stage-extension-archive
COPY tools/select_extension_archive.py /usr/local/bin/select_extension_archive.py
COPY tools/coverage.py /usr/local/bin/coverage.py
COPY tools/linux_assembly_inventory.py /usr/local/bin/linux-assembly-inventory
COPY tools/check_source_identity.py tools/source_archive.py /verification/tools/
COPY support.json /verification/support.json
COPY support/postgresql-releases.json /verification/support/postgresql-releases.json
RUN chmod +x /usr/local/bin/verify-pilot
ENTRYPOINT ["/usr/local/bin/verify-pilot"]
