"""Make a writable GNU PGXS copy without modifying cached build dependencies."""

from pathlib import Path
import shutil
import subprocess
import sys


def prepare(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    pairs = [(str(source), str(destination)), (source.as_posix(), destination.as_posix())]
    if sys.platform == 'win32':
        pairs.append(tuple(subprocess.check_output(['cygpath', '-u', str(path)], text=True).strip()
                           for path in (source, destination)))
    for path in destination.rglob('*'):
        if not path.is_file() or not (path.name.startswith('Makefile') or path.suffix in ('.mk', '.pc', '.la')):
            continue
        original = path.read_text()
        updated = original
        for before, after in pairs:
            updated = updated.replace(before, after)
        if updated != original:
            path.write_text(updated)


if __name__ == '__main__':
    prepare(*sys.argv[1:])
