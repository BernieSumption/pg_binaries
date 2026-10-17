FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl passwd util-linux python3 \
 && rm -rf /var/lib/apt/lists/*
COPY scripts/pg_ivm/build-in-container.sh /usr/local/bin/build-pgivm-pilot
COPY scripts/pg_ivm/probe.sql /work/probe.sql
RUN chmod +x /usr/local/bin/build-pgivm-pilot
ENTRYPOINT ["/usr/local/bin/build-pgivm-pilot"]
