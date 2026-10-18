FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*
COPY scripts/pg_stat_monitor/linux-build-in-container.sh /usr/local/bin/build-pg-stat-monitor
RUN chmod +x /usr/local/bin/build-pg-stat-monitor
ENTRYPOINT ["/usr/local/bin/build-pg-stat-monitor"]
