#!/usr/bin/env bash
set -euo pipefail

architecture=${1:?architecture required}
output_dir=$(mkdir -p "${2:?output directory required}" && cd "$2" && pwd)
case "$architecture" in
  arm64|x86_64) ;;
  *) echo "Unsupported macOS architecture: $architecture" >&2; exit 2 ;;
esac
if [[ $(uname -s) != Darwin || $(uname -m) != "$architecture" ]]; then
  echo "This probe requires native macOS $architecture" >&2
  exit 1
fi

version=3.15.0
expected_sha256=d5e5192a686d065eaed082de14dd26244c5c8e02bff16b2c6cce3265f648e00e
archive="geos-${version}.tar.bz2"
source_url="https://download.osgeo.org/geos/$archive"
work_dir=$(mktemp -d "${RUNNER_TEMP:-/tmp}/geos-floor.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT
archive_path="$work_dir/$archive"
source_dir="$work_dir/source"
build_dir="$work_dir/build"
prefix="$work_dir/prefix"
inspection="$output_dir/inspection.txt"

{
  echo "GEOS macOS 11 dependency-floor feasibility probe"
  echo "version=$version"
  echo "architecture=$architecture"
  echo "macosx_deployment_target=11.0"
  echo "source_url=$source_url"
  echo "expected_sha256=$expected_sha256"
  echo "checksum_reference=https://www.mail-archive.com/debian-devel-changes%40lists.debian.org/msg988455.html"
  echo "checksum_note=SHA-256 published in the signed Debian FTP Masters source-acceptance notice for the upstream orig tarball"
} > "$inspection"

curl --fail --location --retry 3 "$source_url" --output "$archive_path"
actual_sha256=$(shasum -a 256 "$archive_path" | awk '{ print $1 }')
printf '%s  %s\n' "$actual_sha256" "$archive" > "$output_dir/source.sha256"
echo "computed_sha256=$actual_sha256" >> "$inspection"
[[ $actual_sha256 == "$expected_sha256" ]] || {
  echo "GEOS source checksum did not match the pinned SHA-256" >&2
  exit 1
}

mkdir "$source_dir" "$build_dir" "$prefix"
tar -xjf "$archive_path" -C "$source_dir" --strip-components=1
export MACOSX_DEPLOYMENT_TARGET=11.0
cmake -S "$source_dir" -B "$build_dir" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$prefix" \
  -DCMAKE_OSX_DEPLOYMENT_TARGET=11.0 \
  -DBUILD_SHARED_LIBS=ON \
  -DBUILD_TESTING=OFF \
  -DBUILD_BENCHMARKS=OFF \
  -DBUILD_DOCUMENTATION=OFF > "$output_dir/configure.log" 2>&1 || {
    tail -n 100 "$output_dir/configure.log" >&2
    exit 1
  }
cmake --build "$build_dir" --parallel "$(sysctl -n hw.ncpu)" > "$output_dir/build.log" 2>&1 || {
  tail -n 100 "$output_dir/build.log" >&2
  exit 1
}
cmake --install "$build_dir" >> "$output_dir/build.log" 2>&1 || {
  tail -n 100 "$output_dir/build.log" >&2
  exit 1
}

inspection_failed=0
dylib_count=0
while IFS= read -r dylib; do
  [[ -n $dylib ]] || continue
  dylib_count=$((dylib_count + 1))
  relative=${dylib#"$prefix"/}
  echo "--- $relative ---" >> "$inspection"
  if ! archs=$(lipo -archs "$dylib" 2>&1); then
    echo "architecture_inspection_error=$archs" >> "$inspection"
    inspection_failed=1
    continue
  fi
  echo "architectures=$archs" >> "$inspection"
  if [[ " $archs " != *" $architecture "* ]]; then inspection_failed=1; fi

  load_commands=$(otool -l "$dylib")
  minos=$(awk '/cmd LC_BUILD_VERSION/ { build=1; next } build && /minos/ { print $2; exit } /cmd LC_VERSION_MIN_MACOSX/ { legacy=1; next } legacy && /version/ { print $2; exit }' <<< "$load_commands")
  echo "minimum_os=${minos:-unavailable}" >> "$inspection"
  if [[ -z $minos ]] || ! awk -v version="$minos" 'BEGIN { split(version, p, "."); exit !((p[1] + 0) < 11 || ((p[1] + 0) == 11 && (p[2] + 0) <= 0)) }'; then
    inspection_failed=1
  fi

  echo "install_id=$(otool -D "$dylib" | sed -n '2p')" >> "$inspection"
  otool -L "$dylib" | tail -n +2 | sed 's/^/linked=/' >> "$inspection"
  awk '/cmd LC_RPATH/ { rpath=1; next } rpath && /path / { print "rpath=" $2; rpath=0 }' <<< "$load_commands" >> "$inspection"
  if host_paths=$(grep -E '(/Users/runner|/private/var/folders|/opt/homebrew|/usr/local/lib|geos-floor\.)' <<< "$(otool -L "$dylib")
$load_commands"); then
    echo "temporary_or_host_path_reference=found" >> "$inspection"
    echo "$host_paths" | sed 's/^/path_reference=/' >> "$inspection"
  else
    echo "temporary_or_host_path_reference=none" >> "$inspection"
  fi
done < <(find "$prefix" -type f -name '*.dylib' -print | sort)

if ((dylib_count == 0)); then
  echo "No dylibs produced under the install prefix" | tee -a "$inspection" >&2
  exit 1
fi
if ((inspection_failed)); then
  echo "Inspection found a macOS floor or architecture issue" >&2
  exit 1
fi
echo "dylib_count=$dylib_count" >> "$inspection"
echo "outcome=minimum-target source build passed; load-path relocation and final-archive verification remain open" >> "$inspection"
