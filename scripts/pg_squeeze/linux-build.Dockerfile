FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends build-essential ca-certificates git python3 tar gzip \
 && rm -rf /var/lib/apt/lists/*
COPY scripts/pg_squeeze/linux-build-in-container.sh /usr/local/bin/build-pg-squeeze
RUN chmod +x /usr/local/bin/build-pg-squeeze
ENTRYPOINT ["/usr/local/bin/build-pg-squeeze"]
