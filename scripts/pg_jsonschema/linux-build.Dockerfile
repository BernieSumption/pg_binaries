FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates clang curl git libclang-dev libssl-dev pkg-config python3 \
 && rm -rf /var/lib/apt/lists/*
COPY scripts/pg_jsonschema/linux-build-in-container.sh /usr/local/bin/build-pg-jsonschema
COPY tools/license_pointer.py /usr/local/bin/license_pointer.py
RUN chmod +x /usr/local/bin/build-pg-jsonschema
ENTRYPOINT ["/usr/local/bin/build-pg-jsonschema"]
