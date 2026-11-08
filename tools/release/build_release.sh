#!/bin/sh
# Source-built release assembler; never snapshots the running system or mounts EFI.
# Usage: build_release.sh --version VERSION --stack DIR --firmware DIR --mesa DIR --output NEW_DIR
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$HERE/build_release.py" "$@"
