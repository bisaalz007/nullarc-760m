#!/bin/bash
# SPDX-License-Identifier: MIT
# Build NullMoth v2.4.1's LGPL translator from a clean pinned checkout.
# Usage: tools/build_translator.sh <NullMoth-checkout> [output-directory]
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
SRC=$(cd "${1:?provide the NullMoth v2.4.1 source checkout}" && pwd)
OUT=${2:-"$REPO/build/translator"}
REV=76df0f6af5c64c2af9a22090da8b3fe14616023e
[ "$(git -C "$SRC" rev-parse HEAD)" = "$REV" ] || { echo "translator requires commit $REV" >&2; exit 1; }
[ -z "$(git -C "$SRC" status --porcelain --untracked-files=all -- translator)" ] || { echo "translator source must be clean" >&2; exit 1; }
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)
MIN_MACOS=${NULLARC_MIN_MACOS:-26.0}
case "$MIN_MACOS" in 15.0|26.0) ;; *) echo 'Supported deployment targets: 15.0 or 26.0' >&2; exit 1;; esac
MACOSX_DEPLOYMENT_TARGET="$MIN_MACOS" cargo build --locked --release --target x86_64-apple-darwin \
  --manifest-path "$SRC/translator/wrapper/Cargo.toml" --target-dir "$OUT/target-macos-$MIN_MACOS"
cp "$OUT/target-macos-$MIN_MACOS/x86_64-apple-darwin/release/libnvmtl_translate.dylib" "$OUT/"
codesign --force --sign - "$OUT/libnvmtl_translate.dylib"
git -C "$SRC" archive --format=tar.gz --output="$OUT/nvmtl-translator-source.tar.gz" "$REV" translator
printf '%s\n' "$REV" > "$OUT/SOURCE_COMMIT"
echo "Built translator with corresponding LGPL source; GPU execution untested"
