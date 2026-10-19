FROM alpine:3.22
RUN apk add --no-cache bash binutils coreutils grep python3 shadow util-linux
COPY scripts/collection/verify-in-container.sh /usr/local/bin/verify-collection-pilot
COPY scripts/collection/version-selection.sh /usr/local/bin/collection-version-selection.sh
COPY scripts/collection/probe.sql /usr/local/share/collection-probe.sql
COPY tools/check_elf_dependencies.py /usr/local/bin/check-elf-dependencies
RUN chmod +x /usr/local/bin/verify-collection-pilot
ENTRYPOINT ["/usr/local/bin/verify-collection-pilot"]
