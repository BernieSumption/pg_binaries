FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl python3 tar gzip unzip patchelf \
 && rm -rf /var/lib/apt/lists/*
COPY scripts/pg_repack/linux-build-in-container.sh /usr/local/bin/build-pg-repack
RUN chmod +x /usr/local/bin/build-pg-repack
ENTRYPOINT ["/usr/local/bin/build-pg-repack"]
