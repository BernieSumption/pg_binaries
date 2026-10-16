FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates cloud-image-utils curl git openssh-client python3 \
    qemu-system-arm qemu-efi-aarch64 qemu-utils \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /repo
