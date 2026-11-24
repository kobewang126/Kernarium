#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
set -eu
root=$(CDPATH= cd -- "$SRCROOT/.." && pwd)
gpu_compat=${TOUCHARIUM_GPU_COMPAT_DIR:-"$root/.build/toucharium/gpu-compat"}
initramfs=${TOUCHARIUM_INITRAMFS_TOOL:-"$root/.build/toucharium/config-tools/bin/uml-initramfs"}
shell=${TOUCHARIUM_LOMIRI_SHELL:-"$root/.build/toucharium/lomiri-Shell.qml.original"}
output="$TARGET_BUILD_DIR/$UNLOCALIZED_RESOURCES_FOLDER_PATH/TouchariumGuestPolicy.cpio"
python3 -B "$root/tools/rootfs/ubuntu-touch/build-policy.py" \
    --gpu-compat "$gpu_compat" --initramfs "$initramfs" \
    --output "$output"
python3 -B "$root/tools/rootfs/ubuntu-touch/build-policy.py" \
    --gpu-compat "$gpu_compat" --initramfs "$initramfs" \
    --keyboard-source ubuntu \
    --output "$TARGET_BUILD_DIR/$UNLOCALIZED_RESOURCES_FOLDER_PATH/TouchariumUbuntuKeyboardPolicy.cpio"

python3 -B "$root/tools/rootfs/ubuntu-touch/build-display-policy.py" \
    --initramfs "$initramfs" --lomiri-shell "$shell" \
    --output-directory "$TARGET_BUILD_DIR/$UNLOCALIZED_RESOURCES_FOLDER_PATH"

python3 -B "$SRCROOT/scripts/stage-system-image.py"
