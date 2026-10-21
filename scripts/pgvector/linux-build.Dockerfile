FROM ubuntu:22.04@sha256:0a9887931b0e38af2e3487ed39e29436b0535c4f3f52e57745baaf79d1898956
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends build-essential ca-certificates file python3 tar gzip && rm -rf /var/lib/apt/lists/*
COPY scripts/pgvector/linux-build-in-container.sh /usr/local/bin/build-pgvector
COPY scripts/pgvector/archive_input.py /usr/local/bin/archive-input
COPY tools/license_pointer.py /usr/local/bin/license_pointer.py
RUN chmod +x /usr/local/bin/build-pgvector
ENTRYPOINT ["/usr/local/bin/build-pgvector"]
