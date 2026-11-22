#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
set -eu
root=$(CDPATH= cd -- "$SRCROOT/.." && pwd)
deb=${TOUCHARIUM_QTWAYLAND_DEB:-"$root/.build/toucharium/qtwayland5_5.15.13-1_arm64.deb"}
initramfs=${TOUCHARIUM_INITRAMFS_TOOL:-"$root/.build/toucharium/config-tools/bin/uml-initramfs"}
shell=${TOUCHARIUM_LOMIRI_SHELL:-"$root/.build/toucharium/lomiri-Shell.qml.original"}
output="$TARGET_BUILD_DIR/$UNLOCALIZED_RESOURCES_FOLDER_PATH/TouchariumGuestPolicy.cpio"
python3 -B "$root/tools/rootfs/ubuntu-touch/build-policy.py" \
    --qtwayland-deb "$deb" --initramfs "$initramfs" \
    --zstd "${TOUCHARIUM_ZSTD:-zstd}" --output "$output"
python3 -B "$root/tools/rootfs/ubuntu-touch/build-policy.py" \
    --qtwayland-deb "$deb" --initramfs "$initramfs" \
    --keyboard-source ubuntu --zstd "${TOUCHARIUM_ZSTD:-zstd}" \
    --output "$TARGET_BUILD_DIR/$UNLOCALIZED_RESOURCES_FOLDER_PATH/TouchariumUbuntuKeyboardPolicy.cpio"

python3 -B "$root/tools/rootfs/ubuntu-touch/build-display-policy.py" \
    --initramfs "$initramfs" --lomiri-shell "$shell" \
    --output-directory "$TARGET_BUILD_DIR/$UNLOCALIZED_RESOURCES_FOLDER_PATH"

python3 -B "$SRCROOT/scripts/stage-system-image.py"
