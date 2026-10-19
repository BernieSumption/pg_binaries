FROM alpine:3.22
RUN apk add --no-cache bash binutils coreutils findutils grep openssl python3 shadow util-linux
COPY scripts/linux/verify-in-container.sh /usr/local/bin/verify-core
COPY scripts/linux/diagnostics-in-container.sh /usr/local/bin/verify-diagnostics
COPY scripts/linux/combined-verify-in-container.sh /usr/local/bin/verify-combined
COPY tools/check_elf_dependencies.py /usr/local/bin/check-elf-dependencies
COPY tools/stage_extension_archive.py /usr/local/bin/stage-extension-archive
COPY tools/check_source_identity.py tools/source_archive.py /verification/tools/
COPY support.json /verification/support.json
COPY support/postgresql-releases.json /verification/support/postgresql-releases.json
COPY tests /tests
RUN chmod +x /usr/local/bin/verify-core \
    /usr/local/bin/verify-diagnostics /usr/local/bin/verify-combined
ENTRYPOINT ["/usr/local/bin/verify-combined"]
