FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl python3 passwd util-linux \
 && rm -rf /var/lib/apt/lists/*
COPY scripts/pg_cron/build-in-container.sh /usr/local/bin/build-pgcron-pilot
COPY tools/license_pointer.py /usr/local/bin/license_pointer.py
RUN chmod +x /usr/local/bin/build-pgcron-pilot
ENTRYPOINT ["/usr/local/bin/build-pgcron-pilot"]
