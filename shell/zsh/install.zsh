#!/usr/bin/env zsh
set -euo pipefail

repo_url="${SIGIL_REPO_URL:-https://raw.githubusercontent.com/rlouf/sigil/main}"
install_dir="${SIGIL_SHELL_DIR:-$HOME/.sigil/shell/zsh}"
binding_path="$install_dir/sigil.zsh"
zshrc="${ZDOTDIR:-$HOME}/.zshrc"

mkdir -p "$install_dir"

if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$repo_url/shell/zsh/sigil.zsh" -o "$binding_path"
else
  print -u2 "sigil install: curl is required to fetch shell/zsh/sigil.zsh"
  exit 1
fi

chmod 644 "$binding_path"

snippet='
# Sigil
if [[ -r "$HOME/.sigil/shell/zsh/sigil.zsh" ]]; then
  source "$HOME/.sigil/shell/zsh/sigil.zsh"
fi
'

touch "$zshrc"
if ! grep -Fq "$HOME/.sigil/shell/zsh/sigil.zsh" "$zshrc"; then
  print -r -- "$snippet" >> "$zshrc"
fi

print "installed Sigil zsh binding at $binding_path"
print "restart your shell or run: source $zshrc"

for dep in sigil fzf glow pi; do
  if ! command -v "$dep" >/dev/null 2>&1; then
    print -u2 "warning: '$dep' is not on PATH"
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
    print -u2 "warning: local model endpoint is not reachable at $qwen_url"
  fi
else
  print -u2 "warning: python3 is not on PATH; skipped local model endpoint check"
fi
