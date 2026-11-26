#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
set -eu
root=$(CDPATH= cd -- "$SRCROOT/.." && pwd)
initramfs=${TOUCHARIUM_INITRAMFS_TOOL:-"$root/.build/toucharium/config-tools/bin/uml-initramfs"}
shell=${TOUCHARIUM_LOMIRI_SHELL:-"$root/.build/toucharium/lomiri-Shell.qml.original"}
oriented_shell=${TOUCHARIUM_LOMIRI_ORIENTED_SHELL:-"$root/.build/toucharium/lomiri-OrientedShell.qml.original"}
for interface in phone desktop; do
    for keyboard in ios ubuntu; do
        case "$interface:$keyboard" in
            phone:ios) name=TouchariumGuestPolicy ;;
            phone:ubuntu) name=TouchariumUbuntuKeyboardPolicy ;;
            desktop:ios) name=TouchariumDesktopGuestPolicy ;;
            desktop:ubuntu) name=TouchariumDesktopUbuntuKeyboardPolicy ;;
        esac
        python3 -B "$root/tools/rootfs/ubuntu-touch/build-policy.py" \
            --initramfs "$initramfs" --mode dynamic \
            --keyboard-source "$keyboard" --shell-mode "$interface" \
            --output "$TARGET_BUILD_DIR/$UNLOCALIZED_RESOURCES_FOLDER_PATH/$name.cpio"
    done
done

for interface in phone desktop; do
    python3 -B "$root/tools/rootfs/ubuntu-touch/build-display-policy.py" \
        --initramfs "$initramfs" --lomiri-shell "$shell" --shell-mode "$interface" \
        --lomiri-oriented-shell "$oriented_shell" \
        --output-directory "$TARGET_BUILD_DIR/$UNLOCALIZED_RESOURCES_FOLDER_PATH"
done

python3 -B "$SRCROOT/scripts/stage-system-image.py"
