#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${PLAYPAD_LAUNCH_MODE:-player}" == "development" ]]; then
  exec python3 "$project_root/server.py" "$@"
fi
exec python3 "$project_root/server.py" --open "$@"
