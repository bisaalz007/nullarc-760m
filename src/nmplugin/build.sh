#!/bin/bash
# SPDX-License-Identifier: MIT
# Compile the fork's entire one-translation-unit Metal plugin; no system installation.
# Usage: build.sh <Vulkan-Headers checkout/include directory>
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
HDR=$(cd "${1:?provide Vulkan-Headers}" && pwd)
[ ! -d "$HDR/include/vulkan" ] || HDR="$HDR/include"
[ -f "$HDR/vulkan/vulkan_core.h" ] || { echo 'missing Vulkan headers' >&2; exit 1; }
SDK_VERSION=$(xcrun --sdk macosx --show-sdk-version)
[ "${SDK_VERSION%%.*}" -ge 26 ] || { echo 'Tahoe SDK 26 or newer required' >&2; exit 1; }
OUT="$HERE/build/NVMTLDriver.bundle"
mkdir -p "$OUT/Contents/MacOS"
xcrun clang -arch x86_64 -mmacosx-version-min=26.0 -bundle -fobjc-arc -O1 \
  -Wno-protocol -Wno-incomplete-implementation -I"$HDR" \
  "$HERE/NVMTLDevice.m" -o "$OUT/Contents/MacOS/NVMTLDriver.new" \
  -framework Foundation -framework Metal -framework IOSurface -framework MetalFX -framework IOKit
mv "$OUT/Contents/MacOS/NVMTLDriver.new" "$OUT/Contents/MacOS/NVMTLDriver"
cp "$HERE/Info.plist" "$OUT/Contents/Info.plist"
codesign --force --sign - "$OUT"
echo "Built source Metal plugin: $OUT (runtime dependencies assembled separately)"
