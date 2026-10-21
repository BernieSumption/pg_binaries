FROM alpine:3.22
RUN apk add --no-cache bash binutils coreutils grep python3 shadow util-linux
COPY scripts/pg_cron/verify-in-container.sh /usr/local/bin/verify-pgcron-pilot
COPY tools/check_elf_dependencies.py /usr/local/bin/check-elf-dependencies
COPY tools/license_pointer.py /usr/local/bin/license_pointer.py
RUN chmod +x /usr/local/bin/verify-pgcron-pilot
ENTRYPOINT ["/usr/local/bin/verify-pgcron-pilot"]
