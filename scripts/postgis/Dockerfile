FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential binutils curl ca-certificates pkg-config file patchelf \
    libgeos-dev libproj-dev libgdal-dev libjson-c-dev libxml2-dev \
    libsfcgal-dev libpcre2-dev libprotobuf-c-dev protobuf-c-compiler \
    libicu-dev liblz4-dev libzstd-dev libssl-dev libxslt1-dev \
    zlib1g-dev libreadline-dev libuuid1 uuid-dev \
    python3 passwd util-linux \
 && rm -rf /var/lib/apt/lists/*
COPY scripts/postgis/build-in-container.sh /usr/local/bin/build-postgis-pilot
COPY tools/create_linux_symbols.py /usr/local/bin/create-linux-symbols
COPY scripts/postgis/probe.sql /work/probe.sql
COPY support.json /work/support.json
COPY tools/license_pointer.py /usr/local/bin/license_pointer.py
RUN chmod +x /usr/local/bin/build-postgis-pilot
ENTRYPOINT ["/usr/local/bin/build-postgis-pilot"]
