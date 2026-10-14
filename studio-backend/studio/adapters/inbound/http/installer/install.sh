#!/bin/sh
# Install or refresh the playbook's skills and agents on this machine, served by
# playbook-studio. Downloads the bundle once and runs the playbook's own installer
# inside it (scripts/install_playbook.py), which writes what differs and prints one
# summary table. Flags pass through to it: --prune, --runtime-dir <dir>, and the
# agents-directory option of each harness (--agents-dir, --opencode-agents-dir).
# The bundle URL carries a short-lived, download-only token.
set -eu

bundle_url='__BUNDLE_URL__'

python=''
for candidate in python3 python py; do
  if command -v "$candidate" >/dev/null 2>&1 \
    && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then
    python=$candidate
    break
  fi
done
if [ -z "$python" ]; then
  echo "playbook install: needs Python 3.8 or newer on PATH (python3, python, or py)" >&2
  exit 1
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
curl -fsSL "$bundle_url" -o "$work/bundle.tar.gz"
mkdir "$work/bundle"
tar -xzf "$work/bundle.tar.gz" -C "$work/bundle"
"$python" "$work/bundle/scripts/install_playbook.py" "$@"
