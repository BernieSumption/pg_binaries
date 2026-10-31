#!/usr/bin/env bash
set -euo pipefail

[[ $1 == windows && $2 == x86_64 && ${MSYSTEM:-} == MINGW64 ]]
workspace=$(cygpath -u "$3")
internal=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
prefix="$workspace/build/dependencies"
shadow="$prefix/mingw-postgresql"
jobs=${PG_BUILD_JOBS:-2}
export CC=gcc CXX=g++ AR=ar RANLIB=ranlib
export PATH="/mingw64/bin:/usr/bin"
# An MSVC environment's pkg-config settings select incompatible import libraries.
unset PKG_CONFIG_PATH PKG_CONFIG_LIBDIR CMAKE_PREFIX_PATH CFLAGS CXXFLAGS CPPFLAGS LDFLAGS
while IFS= read -r package; do
  package=${package%$'\r'}
  [[ -z $package ]] || pacman -Q "$package" >/dev/null
done < "$internal/windows-packages.txt"
mkdir -p "$prefix/bin"
pacman -Q > "$prefix/msys2-packages.txt"

selected_version=$("$workspace/postgresql/bin/pg_config.exe" --version | tr -d '\r')
source_version=$(sed -n 's/^AC_INIT(\[PostgreSQL\], \[\([^]]*\)\].*/PostgreSQL \1/p' "$workspace/sources/postgresql/configure.ac")
[[ $source_version == "$selected_version" ]] || { echo "MinGW PostgreSQL source $source_version differs from selected SDK $selected_version" >&2; exit 1; }

mkdir -p "$workspace/build/mingw-postgresql-build"
cd "$workspace/build/mingw-postgresql-build"
"$workspace/sources/postgresql/configure" --host=x86_64-w64-mingw32 --prefix="$shadow" \
  --without-readline --without-zlib --without-icu --without-libxml \
  --without-lz4 --without-zstd --without-ldap --without-gssapi --without-libcurl \
  --without-perl --without-python --without-tcl --without-pam --without-bonjour \
  --without-libnuma --without-liburing --without-selinux
make -j"$jobs"
make install
[[ $("$shadow/bin/pg_config.exe" --version | tr -d '\r') == "$selected_version" ]]
# PostGIS uses GNU PGXS, but its imports must name the selected MSVC backend's exports.
test -s "$workspace/postgresql/lib/postgres.lib"
cp "$workspace/postgresql/lib/postgres.lib" "$shadow/lib/libpostgres.a"

# These are build-time providers; the harness copies only the final DLL closure.
for library in /mingw64/bin/*.dll; do
  destination="$prefix/bin/$(basename "$library")"
  cp "$library" "$destination"
done

cmake -S "$(cygpath -m "$workspace/sources/sfcgal")" -B "$(cygpath -m "$workspace/build/sfcgal-build")" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$(cygpath -m "$prefix")" \
  -DCMAKE_PREFIX_PATH="$(cygpath -m /mingw64)" -DBUILD_SHARED_LIBS=ON \
  -DSFCGAL_BUILD_TESTS=OFF -DSFCGAL_BUILD_EXAMPLES=OFF -DSFCGAL_BUILD_DOC=OFF
cmake --build "$(cygpath -m "$workspace/build/sfcgal-build")" --parallel "$jobs"
cmake --install "$(cygpath -m "$workspace/build/sfcgal-build")"
