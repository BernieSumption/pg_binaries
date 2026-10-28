FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential binutils ca-certificates curl file patchelf pkg-config \
    libgeos-dev libproj-dev proj-data libgdal-dev gdal-data libjson-c-dev \
    libxml2-dev libsfcgal-dev libprotobuf-c-dev protobuf-c-compiler \
    libicu-dev liblz4-dev libzstd-dev libssl-dev libxslt1-dev \
    zlib1g-dev libreadline-dev uuid-dev python3 \
 && rm -rf /var/lib/apt/lists/*
COPY build-in-container.sh /usr/local/bin/build-postgis
RUN chmod +x /usr/local/bin/build-postgis
ENTRYPOINT ["/usr/local/bin/build-postgis"]
