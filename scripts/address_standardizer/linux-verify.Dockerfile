FROM alpine:3.22
RUN apk add --no-cache bash binutils coreutils grep python3 shadow util-linux
COPY scripts/address_standardizer/linux-verify-in-container.sh /usr/local/bin/verify-address-standardizer
COPY scripts/address_standardizer/linux-probe.sql /work/probe.sql
COPY tools/check_elf_dependencies.py /usr/local/bin/check-elf-dependencies
COPY tools/license_pointer.py /usr/local/bin/license_pointer.py
RUN chmod +x /usr/local/bin/verify-address-standardizer
ENTRYPOINT ["/usr/local/bin/verify-address-standardizer"]
