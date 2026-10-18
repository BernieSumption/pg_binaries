#!/usr/bin/env bash

macos_compiled_prefix_hidden=false
macos_compiled_prefix_path=
macos_compiled_prefix_target=
macos_compiled_prefix_hidden_target=

macos_hide_compiled_prefix() {
  local prefix=$1 target=$2 actual
  if [[ $macos_compiled_prefix_hidden == true ]]; then
    echo "compiled prefix is already hidden" >&2
    return 1
  fi
  if [[ ! -L $prefix ]]; then
    echo "compiled prefix must be a symlink before relocation testing: $prefix" >&2
    return 1
  fi
  actual=$(readlink "$prefix")
  if [[ $actual != "$target" ]]; then
    echo "compiled prefix symlink target does not match the build install" >&2
    return 1
  fi
  if [[ ! -d $target ]]; then
    echo "compiled prefix target is not an installation directory: $target" >&2
    return 1
  fi
  local hidden_target="${target}.relocation-hidden.$$"
  if [[ -e $hidden_target || -L $hidden_target ]]; then
    echo "refusing to replace compiled-prefix staging path: $hidden_target" >&2
    return 1
  fi
  macos_compiled_prefix_path=$prefix
  macos_compiled_prefix_target=$target
  macos_compiled_prefix_hidden_target=$hidden_target
  macos_compiled_prefix_hidden=true
  rm "$prefix"
  mv "$target" "$hidden_target"
  if [[ -e $prefix || -L $prefix || -e $target || -L $target ]]; then
    echo "original compiled-prefix location remains available during relocation testing" >&2
    return 1
  fi
}

macos_restore_compiled_prefix() {
  if [[ $macos_compiled_prefix_hidden != true ]]; then
    return 0
  fi
  if [[ -e $macos_compiled_prefix_target || -L $macos_compiled_prefix_target ]]; then
    echo "refusing to replace the original compiled-prefix target: $macos_compiled_prefix_target" >&2
    return 1
  fi
  if [[ ! -d $macos_compiled_prefix_hidden_target ]]; then
    echo "hidden compiled-prefix target is missing: $macos_compiled_prefix_hidden_target" >&2
    return 1
  fi
  mv "$macos_compiled_prefix_hidden_target" "$macos_compiled_prefix_target"
  if [[ -e $macos_compiled_prefix_path || -L $macos_compiled_prefix_path ]]; then
    echo "refusing to replace a path at the compiled prefix: $macos_compiled_prefix_path" >&2
    return 1
  fi
  ln -s "$macos_compiled_prefix_target" "$macos_compiled_prefix_path"
  macos_compiled_prefix_hidden=false
}
