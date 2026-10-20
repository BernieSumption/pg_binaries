#!/usr/bin/env python3
"""Write a validated Address Standardizer macOS target."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import coverage
import extension_archive_plan

def main():
 p=argparse.ArgumentParser(description=__doc__); p.add_argument('postgresql_version'); p.add_argument('--architecture',required=True,choices=('arm64','x86_64')); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
 try:
  support=coverage.load_json(ROOT/'support.json'); releases=coverage.load_json(ROOT/'support/postgresql-releases.json')
  extension_archive_plan.select_target(extension_archive_plan.plan(support,releases),'Address Standardizer',f'macos-{a.architecture}',a.postgresql_version,'3.7.0')
 except (coverage.CoverageError,ValueError,KeyError,TypeError) as e: print(f'unsupported target: {e}',file=sys.stderr); return 2
 t={'schema_version':1,'profile_id':f'address-standardizer-publication-macos-{a.architecture}-{a.postgresql_version}','postgresql_version':a.postgresql_version,'architecture':a.architecture,'platform':f'macos-{a.architecture}','extension_version':'3.7.0','core_archive':{'basename':f'postgresql-{a.postgresql_version}-macos-{a.architecture}.tar.gz'}}
 a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(t,indent=2)+'\n'); return 0
if __name__=='__main__': raise SystemExit(main())
