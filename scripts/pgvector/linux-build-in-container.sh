#!/usr/bin/env bash
set -euo pipefail
pg_version=${PG_VERSION:?}; architecture=${PG_ARCHITECTURE:?}
vector_version=${PGVECTOR_VERSION:-0.8.7}
[[ "$pg_version" =~ ^(15|16|17|18)\.[0-9]+$ && "$architecture" =~ ^(x86_64|arm64)$ ]] || { echo "Selected path supports PostgreSQL 15 through 18 on x86_64 or arm64" >&2; exit 2; }
[[ "$vector_version" =~ ^[0-9]+(\.[0-9]+)+$ ]] || { echo "PGVECTOR_VERSION must be a dotted numeric release" >&2; exit 2; }
pg_major=${pg_version%%.*}
core_archive=${CORE_ARCHIVE:?}; source_archive=${SOURCE_ARCHIVE:?}; source_sha=${VECTOR_SOURCE_SHA256:?}
expected_core_sha=${EXPECTED_CORE_SHA256:?}
core_source_sha=${CORE_SOURCE_SHA256:?}
build_id=${BUILD_ID:?}; source_revision=${SOURCE_REVISION:?}; builder_image_id=${BUILDER_IMAGE_ID:?}
builder_packages_sha=${BUILDER_PACKAGES_SHA256:?}
source_url=${VECTOR_SOURCE_URL:?}
[[ "$source_url" == https://* ]] || { echo "VECTOR_SOURCE_URL must use HTTPS" >&2; exit 2; }
[[ "$build_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || { echo "Invalid BUILD_ID" >&2; exit 2; }
[[ "$source_revision" =~ ^([0-9a-fA-F]{40}|[0-9a-fA-F]{64})$ ]] || { echo "Invalid SOURCE_REVISION" >&2; exit 2; }
[[ "$builder_image_id" =~ ^sha256:[0-9a-f]{64}$ ]] || { echo "Invalid builder image ID" >&2; exit 2; }
[[ "$builder_packages_sha" =~ ^[0-9a-f]{64}$ ]] || { echo "Invalid builder package inventory SHA-256" >&2; exit 2; }
python3 /usr/local/bin/archive-input validate-core "/input/$core_archive" "/input/$core_archive.sha256" "$expected_core_sha" "$pg_version" "$architecture" "$core_source_sha"
python3 /usr/local/bin/archive-input validate-source "/source/$source_archive" "$source_sha" "$vector_version"
mkdir -p /work/core /work/source /work/stage/pgvector/lib /work/stage/pgvector/share/extension /out
tar -xzf "/input/$core_archive" -C /work/core
pgroot=/work/core/postgresql
test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"
# The core was configured with this prefix before it was archived.
ln -s "$pgroot" /opt/postgresql
tar -xzf "/source/$source_archive" -C /work/source
cd "/work/source/pgvector-$vector_version"
make -j "$(nproc)" PG_CONFIG="$pgroot/bin/pg_config" OPTFLAGS=
make install PG_CONFIG="$pgroot/bin/pg_config" OPTFLAGS=
stage=/work/stage/pgvector
mv "$pgroot/lib/vector.so" "$stage/lib/"
mv "$pgroot/share/extension/vector"* "$stage/share/extension/"
python3 /usr/local/bin/license_pointer.py write "$stage" pgvector
core_sha=$(sha256sum "/input/$core_archive" | awk '{print $1}')
configuration="pgvector-${vector_version};postgresql-core=${pg_version};builder=ubuntu-22.04;optflags=empty"
cat > /work/stage/metadata.json <<EOF
{"project":"pgvector","version":"${vector_version}","sql_names":["vector"],"requires":[],"configuration_prerequisites":[],"runtime_prerequisites":[],"build_id":"${build_id}","source_revision":"${source_revision}","source_archive":{"url":"${source_url}","sha256":"${source_sha}"},"core_archive":{"basename":"${core_archive}","sha256":"${core_sha}"},"build_configuration":"${configuration}","builder_image_id":"${builder_image_id}","builder_packages_sha256":"${builder_packages_sha}","platform":"linux","architecture":"${architecture}"}
EOF
PG_MAJOR="$pg_major" python3 - /work/stage/metadata.json /out/build-input-identity.json <<'PY'
import json
import os
from pathlib import Path
import sys

metadata_path, identity_path = map(Path, sys.argv[1:])
metadata = json.loads(metadata_path.read_text())
identity = json.loads(identity_path.read_text())
if (identity['upstream_sources']['pgvector']['sha256'] != metadata['source_archive']['sha256']
        or identity['dependencies']['builder_packages']['sha256'] != metadata['builder_packages_sha256']
        or identity['dependencies']['postgresql']['sha256'] != metadata['core_archive']['sha256']
        or identity['target']['platform'] != 'linux-' + metadata['architecture']
        or identity['target']['version'] != metadata['version']
        or identity['build_configuration']['architecture'] != metadata['architecture']
        or identity['target']['postgresql_major'] != int(os.environ['PG_MAJOR'])):
    raise SystemExit('build input identity disagrees with the checked build inputs')
metadata['build_inputs'] = identity
metadata_path.write_text(json.dumps(metadata, sort_keys=True) + '\n')
PY
archive="pgvector-${vector_version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
tar -C /work/stage -czf "/out/$archive" pgvector metadata.json
python3 /usr/local/bin/license_pointer.py verify "/out/$archive" pgvector
(cd /out && sha256sum "$archive" > "$archive.sha256")
