FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl python3 perl passwd util-linux \
 && rm -rf /var/lib/apt/lists/*
COPY scripts/pgtap/build-in-container.sh /usr/local/bin/build-pgtap-pilot
COPY scripts/pgtap/probe.sql /work/probe.sql
COPY tools/license_pointer.py /usr/local/bin/license_pointer.py
RUN chmod +x /usr/local/bin/build-pgtap-pilot
ENTRYPOINT ["/usr/local/bin/build-pgtap-pilot"]
