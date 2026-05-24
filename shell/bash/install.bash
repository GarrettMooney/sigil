#!/usr/bin/env bash
set -euo pipefail

repo_url="${SIGIL_REPO_URL:-https://raw.githubusercontent.com/rlouf/sigil/main}"
install_dir="${SIGIL_SHELL_DIR:-$HOME/.sigil/shell/bash}"
binding_path="$install_dir/sigil.bash"
bashrc="${SIGIL_BASH_RC:-$HOME/.bashrc}"

mkdir -p "$install_dir"

if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$repo_url/shell/bash/sigil.bash" -o "$binding_path"
else
  printf '%s\n' "sigil install: curl is required to fetch shell/bash/sigil.bash" >&2
  exit 1
fi

chmod 644 "$binding_path"

snippet='
# Sigil
if [[ -r "$HOME/.sigil/shell/bash/sigil.bash" ]]; then
  source "$HOME/.sigil/shell/bash/sigil.bash"
fi
'

touch "$bashrc"
if ! grep -Fq "$HOME/.sigil/shell/bash/sigil.bash" "$bashrc"; then
  printf '%s\n' "$snippet" >> "$bashrc"
fi

printf '%s\n' "installed Sigil bash binding at $binding_path"
printf '%s\n' "restart your shell or run: source $bashrc"

for dep in sigil fzf glow pi; do
  if ! command -v "$dep" >/dev/null 2>&1; then
    printf '%s\n' "warning: '$dep' is not on PATH" >&2
  fi
done

qwen_url="${QWEN_URL:-http://127.0.0.1:8080/v1/chat/completions}"
if command -v python3 >/dev/null 2>&1; then
  if ! python3 - "$qwen_url" <<'PY'
import socket
import sys
from urllib.parse import urlparse

url = urlparse(sys.argv[1])
host = url.hostname or "127.0.0.1"
port = url.port or (443 if url.scheme == "https" else 80)
try:
    with socket.create_connection((host, port), timeout=0.5):
        pass
except OSError:
    raise SystemExit(1)
PY
  then
    printf '%s\n' "warning: local model endpoint is not reachable at $qwen_url" >&2
  fi
else
  printf '%s\n' "warning: python3 is not on PATH; skipped local model endpoint check" >&2
fi
