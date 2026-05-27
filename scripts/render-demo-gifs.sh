#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAPE_DIR="$ROOT/docs/demos/tapes"

if [[ "${1:-}" == "--list" ]]; then
  find "$TAPE_DIR" -maxdepth 1 -type f -name '*.tape' | sort
  exit 0
fi

if [[ "$#" -gt 0 ]]; then
  tapes=("$@")
else
  tapes=()
  while IFS= read -r tape; do
    tapes+=("$tape")
  done < <(find "$TAPE_DIR" -maxdepth 1 -type f -name '*.tape' | sort)
fi

if [[ "${#tapes[@]}" -eq 0 ]]; then
  echo "no tapes found" >&2
  exit 1
fi

for tape in "${tapes[@]}"; do
  if [[ "$tape" != /* ]]; then
    tape="$ROOT/$tape"
  fi
  echo "rendering ${tape#$ROOT/}"
  vhs "$tape"
done
