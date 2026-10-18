"""Bind HypoPG debug symbols to the DLL bytes in the final Windows archive."""

import hashlib
from pathlib import Path
import tarfile
import tempfile

from create_windows_symbols import pdb_identity, pe_codeview, sha256


def verify_symbols(extension_archive, pdb_path):
    pdb_path = Path(pdb_path)
    with tarfile.open(extension_archive, "r:gz") as archive:
        members = [member for member in archive.getmembers()
                   if member.name == "hypopg/lib/hypopg.dll"]
        if len(members) != 1 or not members[0].isfile():
            raise RuntimeError("symbol verification requires exactly one archived HypoPG DLL")
        data = archive.extractfile(members[0]).read()
    with tempfile.TemporaryDirectory() as directory:
        dll = Path(directory) / "hypopg.dll"
        dll.write_bytes(data)
        identity = pe_codeview(dll)
    if identity is None or identity != pdb_identity(pdb_path):
        raise RuntimeError("HypoPG DLL CodeView and PDB GUID/age mismatch")
    return {"module": "hypopg/lib/hypopg.dll", "module_sha256": hashlib.sha256(data).hexdigest(),
            "rsds_guid": identity[0], "rsds_age": identity[1],
            "pdb_basename": pdb_path.name, "pdb_sha256": sha256(pdb_path)}
