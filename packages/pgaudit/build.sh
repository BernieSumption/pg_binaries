#!/usr/bin/env bash
set -euo pipefail

os=$1 workspace=$3
source_dir="$workspace/sources/pgaudit"
pg_prefix="$workspace/postgresql"
pg_config="$pg_prefix/bin/pg_config"
stage="$workspace/build/stage"
payload="$workspace/payload"

if [[ $os == macos ]]; then
  jobs=$(sysctl -n hw.ncpu)
else
  jobs=$(nproc)
fi

make -C "$source_dir" USE_PGXS=1 PG_CONFIG="$pg_config" -j "$jobs"
make -C "$source_dir" USE_PGXS=1 PG_CONFIG="$pg_config" DESTDIR="$stage" install

sharedir=$("$pg_config" --sharedir)
share_rel=${sharedir#"$pg_prefix"/}
mkdir -p "$payload/$share_rel/extension"
cp "$stage$sharedir"/extension/pgaudit*.control "$payload/$share_rel/extension/"
cp "$stage$sharedir"/extension/pgaudit*.sql "$payload/$share_rel/extension/"

pkglibdir=$("$pg_config" --pkglibdir)
lib_rel=${pkglibdir#"$pg_prefix"/}
mkdir -p "$payload/$lib_rel"
find "$stage$pkglibdir" -maxdepth 1 -type f \
  \( -name 'pgaudit.so' -o -name 'pgaudit.dylib' \) \
  -exec cp {} "$payload/$lib_rel/" \;
