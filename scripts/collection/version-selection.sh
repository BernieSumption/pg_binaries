#!/usr/bin/env bash

select_collection_versions() {
  local requested=${COLLECTION_VERSION:-}
  SELECTED_COLLECTION_VERSIONS=()
  case "$requested" in
    '') SELECTED_COLLECTION_VERSIONS=(1.1.1 2.1.3) ;;
    1.1.1|2.1.3) SELECTED_COLLECTION_VERSIONS=("$requested") ;;
    *) echo "Unsupported Collection version: $requested" >&2; return 2 ;;
  esac
}
