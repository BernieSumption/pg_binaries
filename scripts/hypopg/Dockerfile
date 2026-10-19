FROM ubuntu:22.04@sha256:0a9887931b0e38af2e3487ed39e29436b0535c4f3f52e57745baaf79d1898956
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl passwd util-linux python3 \
 && rm -rf /var/lib/apt/lists/*
COPY scripts/hypopg/build-in-container.sh /usr/local/bin/build-hypopg-pilot
COPY scripts/hypopg/probe.sql /work/probe.sql
RUN chmod +x /usr/local/bin/build-hypopg-pilot
ENTRYPOINT ["/usr/local/bin/build-hypopg-pilot"]
