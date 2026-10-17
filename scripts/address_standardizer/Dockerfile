FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl git libpcre2-dev libreadline-dev \
    zlib1g-dev flex bison perl passwd util-linux \
 && rm -rf /var/lib/apt/lists/*
COPY scripts/address_standardizer/build-in-container.sh /usr/local/bin/build-address-standardizer-pilot
COPY scripts/address_standardizer/probe.sql /work/probe.sql
RUN chmod +x /usr/local/bin/build-address-standardizer-pilot
ENTRYPOINT ["/usr/local/bin/build-address-standardizer-pilot"]
