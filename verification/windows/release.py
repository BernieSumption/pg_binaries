"""Verify Windows archive combinations with the shared release checks."""

import platform

from verification.linux.release import main as release_main


def main(argv=None):
    return release_main(argv, platform_configuration={
        'description': 'Verify PostgreSQL and selected Windows extension archives in combinations.',
        'targets': ('windows-x86_64',), 'default': 'windows-x86_64',
        'system': 'Windows',
        # Windows on ARM can execute the x64 distribution through translation.
        'machines': {'windows-x86_64': ('amd64', 'x86_64', 'arm64')},
        'version_key': 'windows_version', 'version': platform.version,
    })


if __name__ == '__main__':
    raise SystemExit(main())
