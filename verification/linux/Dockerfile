FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C
RUN apt-get update && apt-get install -y --no-install-recommends \
    binutils ca-certificates file git openssl python3 \
 && rm -rf /var/lib/apt/lists/*
ARG VERIFY_UID=1000
RUN useradd --create-home --uid "$VERIFY_UID" verifier
USER verifier
WORKDIR /src
ENTRYPOINT ["python3", "-m", "verification.runtime"]
