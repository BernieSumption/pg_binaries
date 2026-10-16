FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends python3 passwd util-linux \
 && rm -rf /var/lib/apt/lists/*
COPY scripts/linux/verify-in-container.sh /usr/local/bin/verify-pilot
COPY tools/check_elf_dependencies.py /usr/local/bin/check-elf-dependencies
RUN chmod +x /usr/local/bin/verify-pilot
ENTRYPOINT ["/usr/local/bin/verify-pilot"]
