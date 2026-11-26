# SPDX-License-Identifier: GPL-2.0-or-later
"""Install the guest keyboard implementation and its default selection."""
from pathlib import Path
from setup import write


def install(root: Path, source: str = 'ubuntu') -> None:
    if source not in ('ios', 'ubuntu'):
        raise ValueError('unsupported keyboard source')
    write(root, 'etc/toucharium/keyboard-source', source + '\n')
    write(root, 'etc/systemd/user/maliit-server.service.d/90-toucharium-keyboard.conf',
          '# SPDX-License-Identifier: GPL-2.0-or-later\n'
          '[Service]\nExecStartPre=/usr/libexec/toucharium-configure-keyboard\n')
    write(root, 'usr/libexec/toucharium-configure-keyboard',
          '#!/bin/sh\n# SPDX-License-Identifier: GPL-2.0-or-later\nset -eu\n'
          'case $(cat /etc/toucharium/keyboard-source) in\n'
          'ios) hidden=true; always=false ;;\n'
          'ubuntu) hidden=false; always=true ;;\n'
          '*) exit 1 ;;\nesac\n'
          'gsettings set com.lomiri.keyboard.maliit stay-hidden $hidden\n'
          'gsettings set com.lomiri.keyboard.maliit disable-height $hidden\n'
          'gsettings set com.lomiri.Shell always-show-osk $always\n', 0o755)
