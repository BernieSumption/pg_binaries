FROM alpine:3.22
RUN apk add --no-cache bash binutils coreutils python3 shadow util-linux
COPY scripts/pg_stat_monitor/linux-verify-in-container.sh /usr/local/bin/verify-pg-stat-monitor
COPY scripts/pg_stat_monitor/linux-probe.sql /work/probe.sql
COPY tools/check_elf_dependencies.py /usr/local/bin/check-elf-dependencies
RUN chmod +x /usr/local/bin/verify-pg-stat-monitor
ENTRYPOINT ["/usr/local/bin/verify-pg-stat-monitor"]
