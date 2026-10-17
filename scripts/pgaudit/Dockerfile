FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl libssl-dev passwd util-linux \
 && rm -rf /var/lib/apt/lists/*
COPY scripts/pgaudit/build-in-container.sh /usr/local/bin/build-pgaudit-pilot
COPY scripts/pgaudit/probe.sql /work/probe.sql
RUN chmod +x /usr/local/bin/build-pgaudit-pilot
ENTRYPOINT ["/usr/local/bin/build-pgaudit-pilot"]
