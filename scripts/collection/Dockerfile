FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl passwd python3 util-linux \
 && rm -rf /var/lib/apt/lists/*
COPY scripts/collection/build-in-container.sh /usr/local/bin/build-collection-pilot
RUN chmod +x /usr/local/bin/build-collection-pilot
ENTRYPOINT ["/usr/local/bin/build-collection-pilot"]
