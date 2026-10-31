"""Copy only the transitive PE DLL closure from declared providers."""

from pathlib import Path
import shutil
import subprocess

from verification.windows.static import is_system_dll, parse_headers, parse_imports, pe_import_directories, ImportSectionsMissing


def inspect(path, dumpbin="dumpbin"):
    def run(option):
        return subprocess.check_output([str(dumpbin), option, str(path)], text=True, errors="replace")
    parse_headers(run("/headers"))
    try:
        imports = parse_imports(run("/imports"))
        if not imports and pe_import_directories(path) != ((0, 0), (0, 0)):
            raise ValueError(f"no parsed imports for PE file with import directories: {path}")
        return imports
    except ImportSectionsMissing:
        if pe_import_directories(path) == ((0, 0), (0, 0)):
            return []
        raise


def bundle(prefix, providers, *, postgres=None, dumpbin="dumpbin"):
    prefix = Path(prefix)
    bin_dir = prefix / "bin"
    bin_dir.mkdir(exist_ok=True)
    providers = [Path(path) for path in providers]
    available = {}
    for provider in providers:
        for path in provider.rglob("*"):
            if path.is_file() and path.suffix.lower() == ".dll":
                available.setdefault(path.name.lower(), []).append(path)
    supplied = {}
    for root in (prefix, Path(postgres) if postgres else prefix):
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in (".exe", ".dll"):
                key = path.name.lower()
                if key in supplied and supplied[key].read_bytes() != path.read_bytes():
                    raise ValueError(f"conflicting PE basename: {path.name}")
                supplied[key] = path
    pending = [path for path in prefix.rglob("*") if path.suffix.lower() in (".exe", ".dll")]
    copied = []
    while pending:
        path = pending.pop()
        for name in inspect(path, dumpbin):
            key = name.lower()
            if key in supplied or is_system_dll(name):
                continue
            candidates = available.get(key, [])
            if not candidates:
                raise ValueError(f"unresolved non-system import {name} in {path}")
            if any(candidate.read_bytes() != candidates[0].read_bytes() for candidate in candidates[1:]):
                raise ValueError(f"conflicting providers for {name}")
            destination = bin_dir / candidates[0].name
            shutil.copy2(candidates[0], destination)
            supplied[key] = destination
            pending.append(destination)
            copied.append(destination.name)
    return sorted(copied)
