FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential bison flex curl ca-certificates file patchelf pkg-config \
    libicu-dev liblz4-dev libzstd-dev libssl-dev libxml2-dev libxslt1-dev \
    zlib1g-dev uuid-dev python3 musl-tools \
 && rm -rf /var/lib/apt/lists/*
