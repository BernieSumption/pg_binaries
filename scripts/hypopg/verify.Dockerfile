FROM alpine:3.22
RUN apk add --no-cache bash binutils coreutils grep python3 shadow util-linux
COPY scripts/hypopg/verify-in-container.sh /usr/local/bin/verify-hypopg-pilot
COPY scripts/hypopg/probe.sql /work/probe.sql
COPY tools/check_elf_dependencies.py /usr/local/bin/check-elf-dependencies
COPY tools/stage_extension_archive.py /usr/local/bin/stage-extension-archive
COPY tools/select_extension_archive.py /usr/local/bin/select_extension_archive.py
COPY tools/coverage.py /usr/local/bin/coverage.py
COPY tools/linux_project_assembly_inventory.py /usr/local/bin/linux-project-assembly-inventory
COPY support.json /work/support.json
COPY tools/license_pointer.py /usr/local/bin/license_pointer.py
RUN chmod +x /usr/local/bin/verify-hypopg-pilot
ENTRYPOINT ["/usr/local/bin/verify-hypopg-pilot"]
