FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl git libtool pkg-config python3 \
 && rm -rf /var/lib/apt/lists/*
COPY scripts/address_standardizer/linux-build-in-container.sh /usr/local/bin/build-address-standardizer
COPY tools/license_pointer.py /usr/local/bin/license-pointer
RUN chmod +x /usr/local/bin/build-address-standardizer
ENTRYPOINT ["/usr/local/bin/build-address-standardizer"]
