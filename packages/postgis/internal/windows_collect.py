"""Collect the selected PostGIS modules, generated SQL and runtime data."""

from pathlib import Path
import shutil
import sys


EXTENSIONS = ('postgis', 'postgis_raster', 'postgis_sfcgal', 'postgis_topology', 'postgis_tiger_geocoder')


def collect(installation, payload, data):
    installation, payload, data = map(Path, (installation, payload, data))
    libraries, extensions = payload / 'lib', payload / 'share/extension'
    libraries.mkdir(parents=True, exist_ok=True)
    extensions.mkdir(parents=True, exist_ok=True)
    for name in EXTENSIONS:
        control = installation / 'share/extension' / f'{name}.control'
        shutil.copy2(control, extensions / control.name)
        scripts = list(control.parent.glob(f'{name}--*.sql'))
        if not scripts:
            raise RuntimeError(f'no generated SQL for {name}')
        for script in scripts:
            shutil.copy2(script, extensions / script.name)
    for name in EXTENSIONS[:-1]:
        module = installation / 'lib' / f'{name}-3.dll'
        shutil.copy2(module, libraries / module.name)
    for name in ('proj', 'gdal'):
        shutil.copytree(data / name, payload / 'share' / name)


if __name__ == '__main__':
    collect(*sys.argv[1:])
