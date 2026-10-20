#!/usr/bin/env python3
"""Emit compact archive-bound Address Standardizer macOS publication evidence."""
import argparse, hashlib, json, os, re, sys
from pathlib import Path
import coverage, extension_archive_plan, address_standardizer_license_inventory
VERSION='3.7.0'; BLOCK='pending-dependency-provenance-and-redistribution-review'; ATTEMPT_STATUS='not-assessed-final-archive-unavailable'; REDISTRIBUTION_RESOLVED='resolved'
CASES={'archive-suite','macho-closure'}
def digest(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''): h.update(b)
 return h.hexdigest()
def emit(root,core_dir,archives,out,target,steps,os_version,image_id):
 root,core_dir,archives,out=map(Path,(root,core_dir,archives,out)); t=json.loads(Path(target).read_text()); pg=t['postgresql_version']; arch=t['architecture']; platform=t['platform']; profile_id=t['profile_id']
 support=coverage.load_json(root/'support.json'); releases=coverage.load_json(root/'support/postgresql-releases.json'); extension_archive_plan.select_target(extension_archive_plan.plan(support,releases),'Address Standardizer',platform,pg,VERSION)
 profile=coverage.verification_profile(root,profile_id)
 if profile['scope']!='publication' or profile['platforms']!=[platform] or set(profile['case_ids'])!=CASES: raise coverage.CoverageError('profile mismatch')
 if set(steps)!=CASES: raise coverage.CoverageError('case outcomes incomplete')
 mapping={'success':'passed','failure':'failed','skipped':'skipped','cancelled':'skipped','timed_out':'failed'}
 if any(x not in mapping for x in steps.values()): raise coverage.CoverageError('invalid step outcome')
 results={k:mapping[v] for k,v in steps.items()}; outcome='failed' if 'failed' in results.values() else 'skipped' if 'skipped' in results.values() else 'passed'
 core_name=f'postgresql-{pg}-{platform}.tar.gz'; ext_name=f'address-standardizer-{VERSION}-postgresql-{pg}-{platform}.tar.gz'; core=core_dir/core_name; ext=archives/ext_name
 out.mkdir(parents=True,exist_ok=True); pub=out/'publication'; pub.mkdir(exist_ok=True)
 revision=os.environ.get('GITHUB_SHA',''); run=os.environ.get('GITHUB_RUN_ID',''); repo=os.environ.get('GITHUB_REPOSITORY',''); server=os.environ.get('GITHUB_SERVER_URL','')
 if not coverage.REVISION.fullmatch(revision) or not run.isdigit() or not repo or not server: raise coverage.CoverageError('GitHub provenance missing')
 attempt={'schema_version':1,'run_id':run,'source_revision':revision,'profile_id':profile_id,'postgresql_version':pg,'version':VERSION,'architecture':arch,'steps':steps,'release_eligible':False,'redistribution_status':ATTEMPT_STATUS,'archives_present':{core_name:core.is_file(),ext_name:ext.is_file()}}
 (pub/'attempt.json').write_text(json.dumps(attempt,indent=2,sort_keys=True)+'\n')
 if not core.is_file() or not ext.is_file(): return
 hashes={core_name:digest(core),ext_name:digest(ext)}
 for p in (core,ext):
  side=Path(str(p)+'.sha256').read_text().split()
  if len(side)<2 or side[0]!=hashes[p.name]: raise coverage.CoverageError(f'bad checksum sidecar for {p.name}')
 address_standardizer_license_inventory.validate_archive(ext)
 if not re.fullmatch(r'\d+(?:\.\d+)*',os_version) or not image_id: raise coverage.CoverageError('runner identity missing')
 attempt['archives']=hashes; (pub/'attempt.json').write_text(json.dumps(attempt,indent=2,sort_keys=True)+'\n')
 report=archives/'static-analysis.json'; probe=archives/'probe-output.txt'; reports={}
 if report.is_file(): reports['static_analysis']=digest(report)
 if probe.is_file(): reports['probe_output']=digest(probe)
 ci={'provider':'github-actions','run_id':run,'run_url':f'{server.rstrip("/")}/{repo}/actions/runs/{run}','source_revision':revision,'build_revision':revision,'test_revision':revision}
 env={'os':'macos','os_version':os_version,'architecture':arch,'clean_system':True,'endpoint':'current','image_id':image_id,'dependency_check_profile':'macho-system-dependencies-v1','dependency_checks_passed':results['macho-closure']=='passed'}
 receipt={'schema_version':1,'profile_id':profile_id,'profile_revision':profile['profile_revision'],'test_revision':revision,'project':'Address Standardizer','version':VERSION,'postgresql_version':pg,'architecture':arch,'platform':platform,'endpoint':'current','case_results':results,'archives':hashes,'extension_archive':ext_name,'reports':reports,'clean_system':True,'dependency_check_profile':'macho-system-dependencies-v1','dependency_checks_passed':env['dependency_checks_passed'],'release_eligible':False,'redistribution_status':REDISTRIBUTION_RESOLVED,'environment':env,'ci':ci}
 (pub/'current-receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
 record={'schema_version':2,'scope':'publication','profile_id':profile_id,'profile_revision':profile['profile_revision'],'test_cases':profile['case_ids'],'case_results':results,'test_revision':revision,'ci':ci,'outcome':outcome,'sha256':hashes[ext_name],'component':'address_standardizer','project':'Address Standardizer','version':VERSION,'platform':platform,'postgresql_version':pg,'assembled_core':{'archive':core_name,'sha256':hashes[core_name],'version':pg},'prerequisite_archives':[],'release_eligible':False,'redistribution_status':REDISTRIBUTION_RESOLVED,'environment':env}
 sql_names=support['extensions']['Address Standardizer']['sql_names']
 if sql_names != ['address_standardizer','address_standardizer_data_us']: raise coverage.CoverageError('Address Standardizer SQL names differ from the tested probe')
 for component in sql_names:
  component_record={**record,'component':component}; coverage.validate_verification_record(component_record,support,root)
  filename='verification-record.json' if component==sql_names[0] else f'verification-record-{component}.json'
  (pub/filename).write_text(json.dumps(component_record,indent=2,sort_keys=True)+'\n')
def main():
 p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]); p.add_argument('--target',required=True); p.add_argument('--core-archives',required=True); p.add_argument('--archives',required=True); p.add_argument('--output',required=True); p.add_argument('--archive-suite-result',required=True); p.add_argument('--macho-closure-result',required=True); p.add_argument('--os-version',required=True); p.add_argument('--image-id',required=True); a=p.parse_args()
 try: emit(a.root,a.core_archives,a.archives,a.output,a.target,{'archive-suite':a.archive_suite_result,'macho-closure':a.macho_closure_result},a.os_version,a.image_id); return 0
 except (coverage.CoverageError,OSError,ValueError,KeyError,TypeError) as e: print(f'Address Standardizer macOS evidence: {e}',file=sys.stderr); return 2
if __name__=='__main__': raise SystemExit(main())
