#!/usr/bin/env bash
set -euo pipefail

workspace=$3
pg_config="$workspace/postgresql/bin/pg_config"
source "$(dirname "${BASH_SOURCE[0]}")/internal/dependencies/environment.sh"
pg_jsonschema_initialize_toolchain "$workspace" "$pg_config"
