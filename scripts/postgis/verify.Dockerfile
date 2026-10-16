FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends python3 passwd util-linux \
 && rm -rf /var/lib/apt/lists/*
COPY scripts/postgis/verify-in-container.sh /usr/local/bin/verify-postgis-pilot
COPY scripts/postgis/probe.sql /work/probe.sql
COPY support.json /work/support.json
RUN chmod +x /usr/local/bin/verify-postgis-pilot
ENTRYPOINT ["/usr/local/bin/verify-postgis-pilot"]
