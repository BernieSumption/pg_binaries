FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends build-essential ca-certificates file python3 tar gzip && rm -rf /var/lib/apt/lists/*
COPY scripts/pgvector/linux-build-in-container.sh /usr/local/bin/build-pgvector
COPY scripts/pgvector/archive_input.py /usr/local/bin/archive-input
RUN chmod +x /usr/local/bin/build-pgvector
ENTRYPOINT ["/usr/local/bin/build-pgvector"]
