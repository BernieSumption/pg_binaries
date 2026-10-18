# Windows bundled-DLL provenance attempt

[Run 39079865085](https://github.com/BernieSumption/pg_binaries/actions/runs/39079865085) passed the mapper unit tests and installed the PostgreSQL 18.6 dependencies, then failed during archive assembly. `map_vcpkg_dlls.py` rejected the installed `vcpkg-cmake:x64-windows` status record as lacking version metadata. The workflow uploaded no archive or raw attempt artifact, and its verification job was skipped. This run therefore establishes no final-byte provenance or runtime result.

The parser had required `Version` or `Version-String` plus `Port-Version`. The revised parser accepts exactly one of vcpkg's four version fields (`Version`, `Version-String`, `Version-Date`, `Version-Semver`) and treats an omitted `Port-Version` as zero. The actual status paragraph was not retained, so the next Windows run must establish whether this fixes the runner metadata and whether the DLL map matches the assembled archive.
