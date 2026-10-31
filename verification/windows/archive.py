"""Reject archive paths whose Windows identity differs from their tar identity."""

import re

from verification.archive import ArchiveError


def validate_paths(entries):
    identities = {}
    for path, entry in entries.items():
        for component in path.split('/'):
            if (any(ord(character) < 32 or character in ':<>"|?*' for character in component)
                    or component.endswith(('.', ' '))
                    or re.fullmatch(r'(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', component, re.I)):
                raise ArchiveError(f'unsafe Windows archive path: {path!r}')
        identity = path.casefold()
        if identity in identities and identities[identity] != entry:
            raise ArchiveError(f'conflicting case-insensitive Windows archive path: {path!r}')
        identities[identity] = entry
