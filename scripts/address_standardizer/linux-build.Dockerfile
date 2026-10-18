FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl git libtool pkg-config \
 && rm -rf /var/lib/apt/lists/*
COPY scripts/address_standardizer/linux-build-in-container.sh /usr/local/bin/build-address-standardizer
RUN chmod +x /usr/local/bin/build-address-standardizer
ENTRYPOINT ["/usr/local/bin/build-address-standardizer"]
