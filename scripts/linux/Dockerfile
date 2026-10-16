FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential bison flex curl ca-certificates file patchelf pkg-config \
    libicu-dev liblz4-dev libzstd-dev libssl-dev libxml2-dev libxslt1-dev \
    zlib1g-dev libuuid1 uuid-dev python3 musl-tools \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /work
COPY scripts/linux/build-in-container.sh /usr/local/bin/build-pilot
COPY scripts/linux/bundle-glibc-in-container.sh /usr/local/bin/bundle-glibc
COPY scripts/linux/launcher.c /usr/local/src/pg-launcher.c
COPY tools/discover_builtins.py /usr/local/bin/discover-builtins
COPY tools/write_linux_license_inventory.py /usr/local/bin/write-linux-license-inventory
COPY tools/create_linux_symbols.py /usr/local/bin/create-linux-symbols
RUN chmod +x /usr/local/bin/build-pilot
ENTRYPOINT ["/usr/local/bin/build-pilot"]
