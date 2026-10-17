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

version=1.5.7
expected_sha256=eb33e51f49a15e023950cd7825ca74a4a2b43db8354825ac24fc1b7ee09e6fa3
archive="zstd-${version}.tar.gz"
base_url="https://github.com/facebook/zstd/releases/download/v${version}"
work_dir=$(mktemp -d "${RUNNER_TEMP:-/tmp}/zstd-floor.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT
build_log="$output_dir/build.log"
inspection="$output_dir/inspection.txt"
archive_path="$work_dir/$archive"

{
  echo "Zstandard macOS dependency-floor feasibility probe"
  echo "version=$version"
  echo "architecture=$architecture"
  echo "macosx_deployment_target=11.0"
  echo "source_url=$base_url/$archive"
  echo "expected_sha256=$expected_sha256"
} > "$inspection"

curl --fail --location --retry 3 "$base_url/$archive" --output "$archive_path"
actual_sha256=$(shasum -a 256 "$archive_path" | awk '{ print $1 }')
printf '%s  %s\n' "$actual_sha256" "$archive" > "$output_dir/source.sha256"
echo "computed_sha256=$actual_sha256" >> "$inspection"
[[ $actual_sha256 == "$expected_sha256" ]] || {
  echo "Zstandard source checksum did not match the pinned upstream digest" >&2
  exit 1
}

mkdir "$work_dir/source" "$work_dir/prefix"
tar -xzf "$archive_path" -C "$work_dir/source" --strip-components=1
export MACOSX_DEPLOYMENT_TARGET=11.0
(
  cd "$work_dir/source"
  make -j"$(sysctl -n hw.ncpu)" CC=clang
  make install PREFIX="$work_dir/prefix" CC=clang
) > "$build_log" 2>&1 || {
  tail -n 100 "$build_log" >&2
  exit 1
}

{
  echo ""
  echo "Build log summary:"
  grep -En '(^| )clang|\.dylib|install|error:|warning:' "$build_log" | tail -n 80 || true
  echo ""
  echo "Produced dylib inspection:"
} >> "$inspection"

dylibs=()
while IFS= read -r dylib; do dylibs+=("$dylib"); done < <(find "$work_dir/prefix" -type f -name '*.dylib' -print | sort)
if ((${#dylibs[@]} == 0)); then
  echo "No dylibs produced under the install prefix" | tee -a "$inspection" >&2
  exit 1
fi
inspection_failed=0
for dylib in "${dylibs[@]}"; do
  echo "--- ${dylib#"$work_dir/prefix"/} ---" >> "$inspection"
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
  if [[ -z $minos ]]; then
    inspection_failed=1
  elif ! awk -v version="$minos" 'BEGIN { split(version, parts, "."); exit !((parts[1] + 0) < 11 || ((parts[1] + 0) == 11 && (parts[2] + 0) <= 0)) }'; then
    inspection_failed=1
  fi
  linked=$(otool -L "$dylib" | tail -n +2)
  echo "$linked" | sed 's/^/linked=/' >> "$inspection"
  if host_paths=$(grep -E '(/Users/runner|/private/var/folders|/opt/homebrew|/usr/local/lib|zstd-floor\.)' <<< "$linked
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
echo "outcome=minimum-target source build passed; relocation requires final-archive verification" >> "$inspection"
