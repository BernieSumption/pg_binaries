"""Find competing dependency symbols in the PostgreSQL backend's loadable closure."""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import subprocess

from verification.linux.static import dynamic_entries
from verification.macos.static import is_system, load_commands

CHECK_NAME = "dependency symbol isolation"


class IsolationError(RuntimeError):
    def __init__(self, details: dict):
        self.details = details
        libraries = sorted({item["path"] for conflict in details["conflicts"] for item in conflict["libraries"]})
        super().__init__(f"competing dependency implementations in {', '.join(libraries)}; see check details for packages, consumers and symbols")


@dataclass
class Binary:
    path: Path
    exports: set[str] = field(default_factory=set)
    imports: set[str] = field(default_factory=set)
    dependencies: list[str] = field(default_factory=list)
    search: list[Path] = field(default_factory=list)
    flat_imports: set[str] = field(default_factory=set)
    flat: bool = False
    identity: str | None = None
    versions: dict[str, set[str | None]] = field(default_factory=dict)
    references: dict[str, set[str | None]] = field(default_factory=dict)
    relocations: set[str] = field(default_factory=set)
    kinds: dict[str, str] = field(default_factory=dict)
    protected: set[str] = field(default_factory=set)


def command(*args: str) -> str:
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f"cannot inspect {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


def elf(path: Path) -> Binary:
    dynamic = command("readelf", "-dW", str(path))
    symbols = command("readelf", "--dyn-syms", "-W", str(path))
    binary = Binary(path, dependencies=dynamic_entries(dynamic, "NEEDED"))
    binary.identity = next(iter(dynamic_entries(dynamic, "SONAME")), None)
    symbolic = "(SYMBOLIC)" in dynamic or bool(re.search(r"\(FLAGS\).*\bSYMBOLIC\b", dynamic))
    for value in dynamic_entries(dynamic, "RPATH|RUNPATH"):
        for directory in value.split(":"):
            binary.search.append(Path(directory.replace("${ORIGIN}", str(path.parent)).replace("$ORIGIN", str(path.parent))))
    for line in symbols.splitlines():
        match = re.match(r"\s*\d+:\s+\S+\s+\S+\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)", line)
        if not match:
            continue
        kind, binding, visibility, section, name = match.groups()
        # Weak and GNU-unique definitions have coalescing semantics, unlike strong dependency APIs.
        if binding != "GLOBAL" or kind not in ("FUNC", "OBJECT", "NOTYPE", "IFUNC"):
            continue
        if section == "ABS":
            continue
        name, separator, version = name.partition("@")
        version = version.lstrip("@") if separator else None
        if section == "UND":
            binary.imports.add(name)
            binary.references.setdefault(name, set()).add(version)
        elif visibility in ("DEFAULT", "PROTECTED"):
            binary.exports.add(name)
            binary.kinds[name] = kind
            if visibility == "PROTECTED":
                binary.protected.add(name)
            binary.versions.setdefault(name, set()).add(version)
    relocations = command("readelf", "-rW", str(path))
    for line in relocations.splitlines():
        fields = line.split()
        if len(fields) >= 5 and re.fullmatch(r"[0-9a-fA-F]+", fields[0]) and fields[2].startswith("R_"):
            name, separator, version = fields[4].partition("@")
            if fields[2].endswith("_COPY"):
                # Executable COPY relocations allocate the canonical storage for a dependency's object.
                binary.exports.discard(name)
                binary.imports.add(name)
                binary.references.setdefault(name, set()).add(version.lstrip("@") if separator else None)
            if name in binary.imports or (name in binary.exports and name not in binary.protected and not symbolic):
                binary.relocations.add(name)
    return binary


def macho(path: Path, arch: str) -> Binary:
    linked = command("otool", "-arch", arch, "-L", str(path))
    loads = command("otool", "-arch", arch, "-l", str(path))
    header = command("otool", "-arch", arch, "-hv", str(path))
    symbols = command("nm", "-arch", arch, "-m", "-g", str(path))
    commands = load_commands(loads)
    identity = next((value for kind, value in commands if kind == "LC_ID_DYLIB"), None)
    dependencies = [line.strip().split(" (compatibility version", 1)[0]
                    for line in linked.splitlines()[1:] if " (compatibility version" in line]
    binary = Binary(path, dependencies=[name for name in dependencies if name != identity],
                    identity=identity, flat="TWOLEVEL" not in header or "FORCE_FLAT" in header)
    for line in symbols.splitlines():
        if " external " not in line or "weak" in line or "private external" in line:
            continue
        match = re.search(r" external (_\S+)(?:\s|$)", line)
        if not match:
            continue
        name = match[1][1:]
        if "(undefined)" in line:
            binary.imports.add(name)
            if binary.flat or "dynamically looked up" in line or "from " not in line:
                binary.flat_imports.add(name)
        else:
            binary.exports.add(name)
    return binary


def native(path: Path, linux: bool) -> bool:
    with path.open("rb") as source:
        magic = source.read(4)
    return magic == b"\x7fELF" if linux else magic in (b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca", b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca")


def entrypoints(binary: Binary) -> set[str]:
    if "Pg_magic_func" not in binary.exports:
        return set()
    result = {"Pg_magic_func", "_PG_init", "_PG_fini", "_PG_output_plugin_init"}
    for symbol in binary.exports:
        if symbol.startswith("pg_finfo_"):
            result.update((symbol, symbol[len("pg_finfo_"):]))
    return result


def resolve(binary: Binary, name: str, root: Path, linux: bool) -> Path | None:
    if not linux and is_system(name):
        return None
    if linux:
        candidates = ([Path(name)] if "/" in name else
                      [directory / name for directory in binary.search] +
                      [root / "lib" / name, root / "lib/runtime" / name, root / "lib/glibc" / name])
    elif name.startswith("@loader_path/"):
        candidates = [binary.path.parent / name[len("@loader_path/"):]]
    else:
        raise RuntimeError(f"{binary.path.relative_to(root)}: unresolved dependency {name}")
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file() and resolved.is_relative_to(root):
            return resolved
    raise RuntimeError(f"{binary.path.relative_to(root)}: unresolved dependency {name}")


def conflicts(binaries: dict[Path, Binary], roots: list[Path], root: Path,
              linux: bool, owners: dict[str, list[str]]) -> dict:
    loaded: set[Path] = set()
    consumers: dict[Path, set[str]] = defaultdict(set)
    for start in roots:
        pending, seen = [start], set()
        while pending:
            path = pending.pop()
            if path in seen:
                continue
            seen.add(path)
            if path not in binaries:
                raise RuntimeError(f"dependency is not an inspected native binary: {path.relative_to(root)}")
            loaded.add(path)
            consumers[path].add(str(start.relative_to(root)))
            for name in binaries[path].dependencies:
                dependency = resolve(binaries[path], name, root, linux)
                if dependency is not None:
                    pending.append(dependency)
    providers: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(loaded):
        binary = binaries[path]
        pg_entrypoints = entrypoints(binary)
        for symbol in binary.exports:
            if symbol in pg_entrypoints and not any(
                    symbol in binaries[other].imports or symbol in binaries[other].relocations
                    for other in loaded):
                continue
            # ELF linker-generated boundaries are per-object bookkeeping, not dependency APIs.
            if linux and symbol in {"_init", "_fini", "__bss_start", "__bss_start__", "__bss_end__", "_bss_end__", "_edata", "_end", "__end__"}:
                continue
            # The Itanium C++ ABI deliberately coalesces type metadata and guards across shared objects.
            # https://itanium-cxx-abi.github.io/cxx-abi/abi.html#vague
            if symbol.startswith(("_ZTI", "_ZTS", "_ZTV", "_ZTT", "_ZTC", "_ZGV")):
                continue
            # Function-local static objects share the vague linkage of their inline/template function.
            if symbol.startswith("_ZZ") and binary.kinds.get(symbol) == "OBJECT":
                continue
            providers[symbol].append(path)
    pairs: dict[tuple[Path, Path], list[str]] = defaultdict(list)
    exceptions = []
    fingerprints: dict[Path, str] = {}
    def fingerprint(path: Path) -> str:
        if path not in fingerprints:
            fingerprints[path] = hashlib.sha256(path.read_bytes()).hexdigest()
        return fingerprints[path]
    # These final-archive libraries came from Ubuntu lapack 3.10.0-2ubuntu1 on both Linux targets.
    # LSAME is the shared case predicate; XERBLA is the shared, intentionally replaceable error handler.
    # https://www.netlib.org/lapack/explore-html/d9/d64/_s_r_c_2xerbla_8f_source.html
    lapack_pairs = {
        frozenset(("5595f2a1fe7de99f5961271fbdefb335ed82c7ead64c0cdd3990730ab5c411fa",
                   "4c66375ac8f1f01c8a179cba8e7a605eecc57b93691e7300ff20212e1f05d911")),
        frozenset(("4ab47496354d13fd6079e5601f5b3de17cc8e0b967debe51027d3d80f44eb7c7",
                   "fd679be2eb9f58e3ebd59f3c7a431a157e1728845b1ba838263194181621750b")),
    }
    for symbol, paths in providers.items():
        for index, first in enumerate(paths):
            for second in paths[index + 1:]:
                if linux:
                    if not any(symbol in binaries[path].imports or symbol in binaries[path].relocations for path in loaded):
                        continue
                    if (symbol in {"lsame_", "xerbla_"}
                            and frozenset((fingerprint(first), fingerprint(second))) in lapack_pairs):
                        exceptions.append({"symbol": symbol,
                                           "libraries": {str(path.relative_to(root)): fingerprint(path) for path in (first, second)},
                                           "reason": "Shared LSAME predicate or replaceable XERBLA error-handler ABI from Ubuntu lapack 3.10.0-2ubuntu1; exact audited archive bytes.",
                                           "source": "https://www.netlib.org/lapack/explore-html/d9/d64/_s_r_c_2xerbla_8f_source.html"})
                        continue
                    first_versions = binaries[first].versions.get(symbol, {None})
                    second_versions = binaries[second].versions.get(symbol, {None})
                    # Versioned references name a particular ABI; two disjoint named ABIs cannot satisfy each other's references.
                    if None not in first_versions | second_versions and not first_versions & second_versions:
                        if not any(None in binaries[path].references.get(symbol, set()) for path in loaded):
                            continue
                    # libc and libm supply the same glibc predicates, including legacy ABI aliases.
                    if (symbol in {"__finite", "__finitef", "__finitel", "__signbit", "__signbitf", "__signbitl"}
                            and {first.name, second.name} == {"libc.so.6", "libm.so.6"}
                            and all(path.parent == root / "lib/glibc" for path in (first, second))):
                        continue
                    # libc and its paired loader exchange these GLIBC_PRIVATE exception-handling hooks.
                    if (symbol in {"_dl_catch_error", "_dl_catch_exception", "_dl_signal_error", "_dl_signal_exception"}
                            and all(path.parent == root / "lib/glibc" for path in (first, second))
                            and first_versions == second_versions == {"GLIBC_PRIVATE"}):
                        continue
                elif not (binaries[first].flat or binaries[second].flat or any(
                        symbol in binaries[path].flat_imports for path in loaded)):
                    continue
                pairs[first, second].append(symbol)
    identities: dict[tuple[Path, Path], str] = {}
    if linux:
        named: dict[str, list[Path]] = defaultdict(list)
        for path in sorted(loaded):
            if binaries[path].identity:
                named[binaries[path].identity].append(path)
        for identity, paths in named.items():
            for index, first in enumerate(paths):
                for second in paths[index + 1:]:
                    if fingerprint(first) != fingerprint(second):
                        identities[first, second] = identity
                        pairs.setdefault((first, second), [])
    findings = []
    for (first, second), symbols in sorted(pairs.items()):
        libraries = []
        for path in (first, second):
            relative = str(path.relative_to(root))
            libraries.append({"path": relative, "packages": owners.get(relative, []),
                              "identity": binaries[path].identity,
                              "consumers": sorted(consumers[path])})
        findings.append({"libraries": libraries, "symbols": sorted(symbols), "competing_identity": identities.get((first, second)),
                         "references": {symbol: [str(path.relative_to(root)) for path in sorted(loaded)
                                              if symbol in binaries[path].imports or symbol in binaries[path].relocations] for symbol in sorted(symbols)}})
    return {"inspected_binaries": len(loaded), "backend_roots": [str(path.relative_to(root)) for path in roots],
            "conflicts": findings, "exceptions": exceptions,
            "limitations": ["ELF symbol discovery covers dynamic imports and relocations; computed dlsym names and libraries loaded by application code require runtime probes."] if linux else
                           ["Mach-O system-library implementations are supplied by macOS; flat and dynamic-lookup references are checked against bundled providers."]}


def inspect(installation: Path, target: str, owners: dict[str, list[str]] | None = None) -> dict:
    root = installation.resolve()
    linux = target.startswith("linux-")
    binaries = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file() or not native(path, linux):
            continue
        binaries[path] = elf(path) if linux else macho(path, target.removeprefix("macos-"))
    server = root / ("libexec/postgres" if linux and (root / "libexec/postgres").is_file() else "bin/postgres")
    if server not in binaries:
        raise RuntimeError("no inspected native PostgreSQL backend found")
    modules = [path for path, binary in binaries.items() if "Pg_magic_func" in binary.exports]
    # Every native object in lib/postgresql is a possible backend LOAD target, including helpers without magic.
    modules.extend(path for path in binaries if path.is_relative_to(root / "lib/postgresql"))
    roots = [server, *sorted(set(modules) - {server})]
    return conflicts(binaries, roots, root, linux, owners or {})


def require_isolation(installation: Path, target: str, owners: dict[str, list[str]] | None = None) -> dict:
    result = inspect(installation, target, owners)
    if result["conflicts"]:
        raise IsolationError(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("installation", type=Path)
    parser.add_argument("target")
    args = parser.parse_args()
    try:
        result = inspect(args.installation, args.target)
        print(json.dumps(result, indent=2))
        return bool(result["conflicts"])
    except (OSError, RuntimeError) as error:
        print(f"FAIL: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
