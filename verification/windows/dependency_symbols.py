"""Check competing Windows DLL identities in backend-loaded package closures."""

from collections import defaultdict
import hashlib
from pathlib import Path
import re
import subprocess

from platforms.windows.bundle import inspect as imports
from verification.windows.static import is_system_dll


def backend_module(path):
    output = subprocess.check_output(['dumpbin', '/exports', str(path)], text=True, errors='replace')
    return bool(re.search(r'^\s*\d+\s+[0-9A-F]+\s+[0-9A-F]+\s+Pg_magic_func(?:\s|$)', output, re.I | re.M))


def inspect(installation, target, owners):
    if target != 'windows-x86_64':
        raise ValueError(f'unsupported Windows target: {target}')
    root = Path(installation).resolve()
    binaries = {path: imports(path) for path in sorted(root.rglob('*'))
                if path.is_file() and path.suffix.lower() in ('.dll', '.exe')}
    server = root / 'bin/postgres.exe'
    if server not in binaries:
        raise RuntimeError('no inspected native PostgreSQL backend found')
    by_name = defaultdict(list)
    for path in binaries:
        by_name[path.name.lower()].append(path)
    roots = [server, *[path for path in binaries if path.suffix.lower() == '.dll' and backend_module(path)]]
    consumers = defaultdict(set)
    for start in roots:
        pending, seen = [start], set()
        while pending:
            path = pending.pop()
            if path in seen:
                continue
            seen.add(path)
            consumers[path].add(start.relative_to(root).as_posix())
            for name in binaries[path]:
                if is_system_dll(name):
                    continue
                candidates = by_name.get(name.lower(), [])
                if not candidates:
                    raise RuntimeError(f'{path.relative_to(root)}: unresolved dependency {name}')
                pending.extend(candidates)
    packages = {}
    for path in consumers:
        relative = path.relative_to(root).as_posix()
        if not owners.get(relative):
            raise RuntimeError(f'no archive package ownership for {relative}')
        supplied_by = set(owners[relative])
        packages[path] = set() if 'postgresql' in supplied_by else supplied_by
    conflicts = []
    for identity, candidates in sorted(by_name.items()):
        candidates = [path for path in candidates if path in consumers]
        for index, first in enumerate(candidates):
            for second in candidates[index + 1:]:
                if not any(left != right for left in packages[first] for right in packages[second]):
                    continue
                fingerprints = [hashlib.sha256(path.read_bytes()).hexdigest() for path in (first, second)]
                if fingerprints[0] == fingerprints[1]:
                    continue
                libraries = [{'path': path.relative_to(root).as_posix(),
                              'packages': owners[path.relative_to(root).as_posix()],
                              'identity': identity, 'sha256': digest,
                              'consumers': sorted(consumers[path])}
                             for path, digest in zip((first, second), fingerprints)]
                conflicts.append({'libraries': libraries, 'symbols': [],
                                  'competing_identity': identity, 'references': {}})
    return {'scope': 'between extension packages; PostgreSQL-supplied files are excluded',
            'inspected_binaries': len(consumers),
            'backend_roots': [path.relative_to(root).as_posix() for path in roots],
            'conflicts': conflicts, 'exceptions': [],
            'limitations': ['PE imports bind to named DLLs; export-name overlap between distinct DLL identities is safe.',
                            'Computed LoadLibrary names require runtime probes; the import closure includes normal and delay imports.']}
