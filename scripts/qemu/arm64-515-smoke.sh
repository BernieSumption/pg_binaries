#!/usr/bin/env bash
set -euo pipefail

archives=${1:?usage: arm64-515-smoke.sh ARCHIVE_DIRECTORY PG_VERSION WORK_DIRECTORY}
pg_version=${2:?usage: arm64-515-smoke.sh ARCHIVE_DIRECTORY PG_VERSION WORK_DIRECTORY}
work=${3:?usage: arm64-515-smoke.sh ARCHIVE_DIRECTORY PG_VERSION WORK_DIRECTORY}
if [[ ! $pg_version =~ ^(15|16|17|18)\.[0-9]+$ ]]; then
  echo "Unsupported PostgreSQL pilot version: $pg_version" >&2
  exit 2
fi
test_revision=${GITHUB_SHA:-}
if [[ ! $test_revision =~ ^[[:xdigit:]]{40}$ ]]; then
  echo "GITHUB_SHA must contain a 40-character hexadecimal commit ID" >&2
  exit 2
fi

image_name=ubuntu-22.04-server-cloudimg-arm64.img
image_url="https://cloud-images.ubuntu.com/releases/jammy/release-20261004/$image_name"
image_sha256=86e13258765945ad792dac75fac7f02f4db9fa73a4a535ffa472266e7041fa19
image="$work/$image_name"
evidence="$work/evidence"
mkdir -p "$work" "$evidence"
qemu_pid=
cleanup() {
  if [[ -n ${qemu_pid:-} ]] && kill -0 "$qemu_pid" 2>/dev/null; then
    kill "$qemu_pid" 2>/dev/null || true
    wait "$qemu_pid" 2>/dev/null || true
  fi
  if [[ -f "$work/qemu.log" ]]; then
    cp "$work/qemu.log" "$evidence/qemu-serial.log"
  fi
}
trap cleanup EXIT

curl --fail --location --retry 3 "$image_url" --output "$image"
printf '%s  %s\n' "$image_sha256" "$image" | sha256sum --check
image_format=$(qemu-img info --output=json "$image" | python3 -c 'import json,sys; print(json.load(sys.stdin)["format"])')
qemu-img resize "$image" 8G
printf 'test_revision=%s\npostgresql_version=%s\nimage_url=%s\nimage_sha256=%s\nimage_manifest_url=%s\nimage_format=%s\nqemu_version=%s\nrunner_kernel=%s\n' \
  "$test_revision" "$pg_version" "$image_url" "$image_sha256" \
  "${image_url%.img}.manifest" "$image_format" "$(qemu-system-aarch64 --version | head -1)" "$(uname -r)" \
  > "$evidence/environment.txt"

key="$work/id_ed25519"
ssh-keygen -q -t ed25519 -N '' -f "$key"
cat > "$work/user-data" <<EOF
#cloud-config
users:
  - name: smoke
    groups: [adm, sudo]
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    lock_passwd: true
    ssh_authorized_keys:
      - $(cat "$key.pub")
ssh_pwauth: false
package_update: false
package_upgrade: false
EOF
printf 'instance-id: pg-binaries-linux-arm64-qemu-515\nlocal-hostname: pg-arm64-qemu-515\n' > "$work/meta-data"
cloud-localds "$work/seed.iso" "$work/user-data" "$work/meta-data"

qemu-system-aarch64 \
  -machine virt,accel=tcg \
  -cpu max \
  -smp 2 \
  -m 3072 \
  -bios /usr/share/qemu-efi-aarch64/QEMU_EFI.fd \
  -display none \
  -serial stdio \
  -no-reboot \
  -drive "file=$image,if=virtio,format=$image_format" \
  -drive "file=$work/seed.iso,media=cdrom,readonly=on" \
  -netdev user,id=net0,hostfwd=tcp::2222-:22 \
  -device virtio-net-device,netdev=net0 \
  > "$work/qemu.log" 2>&1 &
qemu_pid=$!

ssh_args=(-i "$key" -p 2222 -o BatchMode=yes -o ConnectTimeout=3 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)
scp_args=(-i "$key" -P 2222 -o BatchMode=yes -o ConnectTimeout=3 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)
ready=false
for attempt in $(seq 1 240); do
  if ssh "${ssh_args[@]}" smoke@127.0.0.1 true >/dev/null 2>&1; then
    ready=true
    break
  fi
  if ! kill -0 "$qemu_pid" 2>/dev/null; then
    echo "QEMU exited before SSH became available" >&2
    tail -n 120 "$work/qemu.log" >&2 || true
    exit 1
  fi
  sleep 2
done
if [[ $ready != true ]]; then
  echo "Guest SSH did not become available within eight minutes" >&2
  tail -n 120 "$work/qemu.log" >&2 || true
  exit 1
fi

guest_root_bytes=$(ssh "${ssh_args[@]}" smoke@127.0.0.1 'df -B1 --output=size / | tail -1 | tr -d " "')
if [[ ! $guest_root_bytes =~ ^[0-9]+$ ]] || (( guest_root_bytes < 6 * 1024 * 1024 * 1024 )); then
  echo "Guest root filesystem did not expand to at least 6 GiB: $guest_root_bytes bytes" >&2
  exit 1
fi
printf 'guest_root_filesystem_bytes=%s\n' "$guest_root_bytes" >> "$evidence/environment.txt"

pg_archive="postgresql-${pg_version}-linux-arm64.tar.gz"
vector_archive="pgvector-0.8.7-postgresql-${pg_version}-linux-arm64.tar.gz"
sha256sum "$archives/$pg_archive" "$archives/$vector_archive" > "$evidence/archive-checksums.sha256"
scp "${scp_args[@]}" "$archives/$pg_archive" "$archives/$vector_archive" smoke@127.0.0.1:/tmp/
scp "${scp_args[@]}" "$archives/$pg_archive.sha256" "$archives/$vector_archive.sha256" smoke@127.0.0.1:/tmp/
scp -r "${scp_args[@]}" /repo/tests smoke@127.0.0.1:/tmp/
scp "${scp_args[@]}" /repo/scripts/linux/verify-in-container.sh \
  /repo/scripts/linux/qemu-kernel-515-guest-full.sh \
  /repo/tools/check_elf_dependencies.py smoke@127.0.0.1:/tmp/
ssh "${ssh_args[@]}" smoke@127.0.0.1 \
  "bash /tmp/qemu-kernel-515-guest-full.sh '$pg_version' arm64" \
  | tee "$evidence/full-verifier.log"

ssh "${ssh_args[@]}" smoke@127.0.0.1 'sudo shutdown -h now' || true
for attempt in $(seq 1 5); do
  kill -0 "$qemu_pid" 2>/dev/null || break
  sleep 2
done
if kill -0 "$qemu_pid" 2>/dev/null; then
  echo "Guest test passed; stopping QEMU after shutdown request" >&2
  kill "$qemu_pid"
fi
wait "$qemu_pid" || true
qemu_pid=
