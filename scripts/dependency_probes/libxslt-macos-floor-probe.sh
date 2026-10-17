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

version=1.1.45
expected_sha256=9acfe68419c4d06a45c550321b3212762d92f41465062ca4ea19e632ee5d216e
archive="libxslt-${version}.tar.xz"
base_url=https://download.gnome.org/sources/libxslt/1.1
work_dir=$(mktemp -d "${RUNNER_TEMP:-/tmp}/libxslt-floor.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT
build_log="$output_dir/build.log"
inspection="$output_dir/inspection.txt"
archive_path="$work_dir/$archive"
sidecar_path="$work_dir/${archive%.tar.xz}.sha256sum"

{
  echo "libxslt macOS 11 dependency-floor feasibility probe"
  echo "version=$version"
  echo "architecture=$architecture"
  echo "macosx_deployment_target=11.0"
  echo "source_url=$base_url/$archive"
  echo "official_checksum_url=$base_url/${archive%.tar.xz}.sha256sum"
  echo "expected_sha256=$expected_sha256"
  echo "libxml2_version=2.15.4"
  echo "libxml2_source_url=https://download.gnome.org/sources/libxml2/2.15/libxml2-2.15.4.tar.xz"
} > "$inspection"

curl --fail --location --retry 3 "$base_url/$archive" --output "$archive_path"
curl --fail --location --retry 3 "$base_url/${archive%.tar.xz}.sha256sum" --output "$sidecar_path"
sidecar_sha256=$(awk -v archive="$archive" '$2 == archive { print $1; exit }' "$sidecar_path")
actual_sha256=$(shasum -a 256 "$archive_path" | awk '{ print $1 }')
printf '%s  %s\n' "$actual_sha256" "$archive" > "$output_dir/source.sha256"
{
  echo "official_sidecar=$(cat "$sidecar_path")"
  echo "sidecar_sha256=${sidecar_sha256:-missing}"
  echo "computed_sha256=$actual_sha256"
} >> "$inspection"
[[ $sidecar_sha256 == "$expected_sha256" && $actual_sha256 == "$expected_sha256" ]] || {
  echo "libxslt source checksum did not match the pinned official digest" >&2
  exit 1
}

mkdir "$work_dir/xml-source" "$work_dir/xslt-source" "$work_dir/xml-prefix" "$work_dir/prefix"
curl --fail --location --retry 3 https://download.gnome.org/sources/libxml2/2.15/libxml2-2.15.4.tar.xz --output "$work_dir/libxml2.tar.xz"
actual_xml_sha256=$(shasum -a 256 "$work_dir/libxml2.tar.xz" | awk '{ print $1 }')
[[ $actual_xml_sha256 == 98087fd181d9070724f3fbc65c7377db03038eb92bd882374daff44940138821 ]] || {
  echo "libxml2 source checksum did not match the pinned digest" >&2
  exit 1
}
echo "libxml2_computed_sha256=$actual_xml_sha256" >> "$inspection"
tar -xJf "$work_dir/libxml2.tar.xz" -C "$work_dir/xml-source" --strip-components=1
tar -xJf "$archive_path" -C "$work_dir/xslt-source" --strip-components=1
export MACOSX_DEPLOYMENT_TARGET=11.0
(
  cd "$work_dir/xml-source"
  ./configure --prefix="$work_dir/xml-prefix" --with-iconv \
    --without-zlib --without-lzma --without-icu --without-python \
    --without-readline --without-history --without-docs
  make -j"$(sysctl -n hw.ncpu)"
  make install
  cd "$work_dir/xslt-source"
  export PKG_CONFIG_PATH="$work_dir/xml-prefix/lib/pkgconfig"
  export CPPFLAGS="-I$work_dir/xml-prefix/include"
  export LDFLAGS="-L$work_dir/xml-prefix/lib"
  ./configure --prefix="$work_dir/prefix" --without-python --without-crypto --without-plugins
  make -j"$(sysctl -n hw.ncpu)"
  make install
) > "$build_log" 2>&1 || {
  tail -n 100 "$build_log" >&2
  exit 1
}

{
  echo ""
  echo "Build log summary:"
  grep -En '(^| )clang|\.dylib|install|error:|warning:' "$build_log" | tail -n 100 || true
  echo ""
  echo "Produced dylib inspection:"
} >> "$inspection"

dylibs=()
while IFS= read -r dylib; do dylibs+=("$dylib"); done < <(find "$work_dir/xml-prefix" "$work_dir/prefix" -type f -name '*.dylib' -print | sort)
if ((${#dylibs[@]} == 0)); then
  echo "No dylibs produced under the install prefixes" | tee -a "$inspection" >&2
  exit 1
fi
inspection_failed=0
for dylib in "${dylibs[@]}"; do
  echo "--- $dylib ---" >> "$inspection"
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
  if [[ -z $minos ]] || ! awk -v version="$minos" 'BEGIN { split(version, p, "."); exit !((p[1] + 0) < 11 || ((p[1] + 0) == 11 && (p[2] + 0) <= 0)) }'; then inspection_failed=1; fi
  linked=$(otool -L "$dylib" | tail -n +2)
  echo "$linked" | sed 's/^/linked=/' >> "$inspection"
  if host_paths=$(grep -E '(/Users/runner|/private/var/folders|/opt/homebrew|/usr/local/lib|libxslt-floor\.)' <<< "$linked
$load_commands"); then
    echo "host_path_reference=found" >> "$inspection"
    echo "$host_paths" | sed 's/^/host_path=/' >> "$inspection"
  else
    echo "host_path_reference=none" >> "$inspection"
  fi
done
if ((inspection_failed)); then
  echo "Inspection found a floor or architecture issue" >&2
  exit 1
fi
echo "outcome=unmodified source builds of libxml2 and libxslt passed; relocation requires final-archive verification" >> "$inspection"
