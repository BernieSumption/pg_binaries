FROM alpine:3.22
RUN apk add --no-cache bash binutils coreutils grep python3 shadow util-linux
COPY scripts/hypopg/verify-in-container.sh /usr/local/bin/verify-hypopg-pilot
COPY scripts/hypopg/probe.sql /work/probe.sql
COPY tools/check_elf_dependencies.py /usr/local/bin/check-elf-dependencies
RUN chmod +x /usr/local/bin/verify-hypopg-pilot
ENTRYPOINT ["/usr/local/bin/verify-hypopg-pilot"]
