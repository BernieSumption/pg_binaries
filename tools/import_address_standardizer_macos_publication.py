#!/usr/bin/env python3
"""Validate and retain one selected Address Standardizer macOS publication attempt."""
import argparse, json, shutil, sys
from pathlib import Path
import coverage
import emit_address_standardizer_macos_publication as publication

def main():
 p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]); p.add_argument('--core-archives',type=Path,required=True); p.add_argument('--archives',type=Path,required=True); p.add_argument('--run-id',required=True); a=p.parse_args(); root=a.root.resolve(); pub=a.archives/'publication'
 try:
  attempt=json.loads((pub/'attempt.json').read_text()); pg=attempt['postgresql_version']; arch=attempt['architecture']; pid=attempt['profile_id']; run=str(a.run_id)
  if not run.isdigit() or str(attempt['run_id'])!=run or attempt.get('release_eligible') is not False or attempt.get('redistribution_status')!=publication.BLOCK: raise coverage.CoverageError('attempt identity or redistribution status mismatch')
  core_name=f'postgresql-{pg}-macos-{arch}.tar.gz'; ext_name=f'address-standardizer-3.7.0-postgresql-{pg}-macos-{arch}.tar.gz'; core=a.core_archives/core_name; ext=a.archives/ext_name
  receipt=json.loads((pub/'current-receipt.json').read_text()); record=json.loads((pub/'verification-record.json').read_text())
  hashes={core_name:publication.digest(core),ext_name:publication.digest(ext)}
  if receipt.get('archives')!=hashes or record.get('sha256')!=hashes[ext_name] or record.get('assembled_core',{}).get('sha256')!=hashes[core_name] or receipt.get('profile_id')!=pid or record.get('profile_id')!=pid or str(receipt.get('ci',{}).get('run_id'))!=run: raise coverage.CoverageError('archive-bound evidence does not match this run')
  coverage.validate_verification_record(record,coverage.load_json(root/'support.json'),root)
  dest=root/'support/evidence'/f'address-standardizer-macos-publication-{run}'/arch; copies=[(pub/'attempt.json',dest/'attempt.json'),(pub/'current-receipt.json',dest/'current-receipt.json'),(pub/'verification-record.json',dest/'verification-record.json'),(a.archives/'static-analysis.json',dest/'static-analysis.json'),(a.archives/'probe-output.txt',dest/'probe-output.txt'),(pub/'verification-record.json',root/'support/verification'/f'address-standardizer-3.7.0-postgresql-{pg}-macos-{arch}-current-{run}.json')]
  for src,dst in copies:
   if not src.is_file():
    if src==a.archives/'static-analysis.json' or src==a.archives/'probe-output.txt': continue
    raise coverage.CoverageError(f'missing evidence: {src}')
   if dst.exists() and dst.read_bytes()!=src.read_bytes(): raise coverage.CoverageError(f'refusing to replace {dst}')
  for src,dst in copies:
   if src.is_file(): dst.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(src,dst)
  return 0
 except (coverage.CoverageError,OSError,ValueError,TypeError,KeyError) as e: print(f'Address Standardizer macOS import: {e}',file=sys.stderr); return 2
if __name__=='__main__': raise SystemExit(main())
