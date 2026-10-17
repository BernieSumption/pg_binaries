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

version=1.47.3
expected_sha256=2f5164e64dd7d91eadd1e0e8a77d92c06dd7837bb19f1d9189ce1939b363d2b4
archive="e2fsprogs-${version}.tar.gz"
base_url="https://downloads.sourceforge.net/project/e2fsprogs/e2fsprogs/v${version}"
work_dir=$(mktemp -d "${RUNNER_TEMP:-/tmp}/libuuid-floor.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT
build_log="$output_dir/build.log"
inspection="$output_dir/inspection.txt"
archive_path="$work_dir/$archive"

{
  echo "e2fsprogs libuuid macOS 11 dependency-floor feasibility probe"
  echo "version=$version"
  echo "architecture=$architecture"
  echo "macosx_deployment_target=11.0"
  echo "source_url=$base_url/$archive"
  echo "source_sha256=$expected_sha256"
  echo "source_digest_authority=SourceForge project download page"
  echo "configure_scope=upstream libuuid, libblkid and filesystem utilities disabled"
} > "$inspection"

curl --fail --location --retry 3 "$base_url/$archive" --output "$archive_path"
actual_sha256=$(shasum -a 256 "$archive_path" | awk '{ print $1 }')
printf '%s  %s\n' "$actual_sha256" "$archive" > "$output_dir/source.sha256"
echo "computed_sha256=$actual_sha256" >> "$inspection"
[[ $actual_sha256 == "$expected_sha256" ]] || {
  echo "e2fsprogs source checksum did not match the pinned upstream digest" >&2
  exit 1
}

mkdir "$work_dir/source" "$work_dir/prefix"
tar -xzf "$archive_path" -C "$work_dir/source" --strip-components=1
export MACOSX_DEPLOYMENT_TARGET=11.0
(
  cd "$work_dir/source"
  ./configure --prefix="$work_dir/prefix" --enable-elf-shlibs \
    --disable-libblkid --disable-fsck --disable-uuidd --disable-e2initrd-helper
  make -C lib/uuid -j"$(sysctl -n hw.ncpu)"
  make -C lib/uuid install
) > "$build_log" 2>&1 || {
  tail -n 100 "$build_log" >&2
  echo "outcome=unmodified upstream libuuid build failed on Darwin" >> "$inspection"
  exit 1
}

{
  echo ""
  echo "Build log summary:"
  grep -En '(^| )clang|\.dylib|\.so|install|error:|warning:' "$build_log" | tail -n 80 || true
  echo ""
  echo "Produced library inspection:"
} >> "$inspection"

libraries=()
while IFS= read -r library; do libraries+=("$library"); done < <(find "$work_dir/prefix" -type f \( -name '*.dylib' -o -name '*.so' \) -print | sort)
if ((${#libraries[@]} == 0)); then
  echo "No shared library produced under the install prefix" | tee -a "$inspection" >&2
  echo "outcome=upstream build did not produce a macOS shared library" >> "$inspection"
  exit 1
fi

inspection_failed=0
for library in "${libraries[@]}"; do
  echo "--- ${library#"$work_dir/prefix"/} ---" >> "$inspection"
  if ! archs=$(lipo -archs "$library" 2>&1); then
    echo "architecture_inspection_error=$archs" >> "$inspection"
    inspection_failed=1
    continue
  fi
  echo "architectures=$archs" >> "$inspection"
  if [[ " $archs " != *" $architecture "* ]]; then inspection_failed=1; fi
  load_commands=$(otool -l "$library")
  minos=$(awk '/cmd LC_BUILD_VERSION/ { build=1; next } build && /minos/ { print $2; exit } /cmd LC_VERSION_MIN_MACOSX/ { legacy=1; next } legacy && /version/ { print $2; exit }' <<< "$load_commands")
  echo "minimum_os=${minos:-unavailable}" >> "$inspection"
  if [[ -z $minos ]] || ! awk -v version="$minos" 'BEGIN { split(version, parts, "."); exit !((parts[1] + 0) < 11 || ((parts[1] + 0) == 11 && (parts[2] + 0) <= 0)) }'; then
    inspection_failed=1
  fi
  echo "linked_libraries=$(otool -L "$library" | tail -n +2 | tr '\n' ';')" >> "$inspection"
  echo "install_name=$(otool -D "$library" | tail -n +2 | tr '\n' ';')" >> "$inspection"
  load_paths=$(otool -l "$library" | awk '/LC_RPATH/ { found=1; next } found && /path / { print $2; found=0 }')
  echo "rpaths=$(tr '\n' ';' <<< "$load_paths")" >> "$inspection"
  if grep -Eq '(/Users/runner|/private/var/folders|/opt/homebrew|/usr/local/lib|libuuid-floor\.)' <<< "$(otool -L "$library")$load_commands"; then
    echo "host_path_reference=found" >> "$inspection"
  else
    echo "host_path_reference=none" >> "$inspection"
  fi
done
if ((inspection_failed)); then
  echo "Inspection found a floor or architecture issue" >&2
  echo "outcome=build completed but architecture or minimum OS inspection failed" >> "$inspection"
  exit 1
fi
echo "outcome=unmodified upstream shared library build passed; inspect load-path evidence before packaging" >> "$inspection"
