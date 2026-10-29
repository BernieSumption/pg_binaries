from pathlib import Path
import shutil
import subprocess
import sys


stage, postgres, payload, data = map(Path, sys.argv[1:5])
suffix = sys.argv[5]
config = postgres / "bin/pg_config"
lib = Path(subprocess.check_output([str(config), "--pkglibdir"], text=True).strip())
share = Path(subprocess.check_output([str(config), "--sharedir"], text=True).strip())
installed_lib = stage / lib.relative_to("/")
installed_share = stage / share.relative_to("/")
payload_lib = payload / lib.relative_to(postgres)
payload_share = payload / share.relative_to(postgres)
(payload_share / "extension").mkdir(parents=True)
payload_lib.mkdir(parents=True)

for name in ("postgis", "postgis_raster", "postgis_sfcgal", "postgis_topology", "postgis_tiger_geocoder"):
    control = installed_share / "extension" / f"{name}.control"
    shutil.copy2(control, payload_share / "extension" / control.name)
    for sql in (installed_share / "extension").glob(f"{name}--*.sql"):
        shutil.copy2(sql, payload_share / "extension" / sql.name)

for name in ("postgis-3", "postgis_raster-3", "postgis_sfcgal-3", "postgis_topology-3"):
    module = installed_lib / f"{name}{suffix}"
    shutil.copy2(module, payload_lib / module.name)

for directory in ("proj", "gdal"):
    shutil.copytree(data / directory, payload_share / directory, symlinks=True)
