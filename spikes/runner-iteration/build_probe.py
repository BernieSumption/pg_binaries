import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


ROOT = Path.cwd()
OUT = ROOT / 'out/runner-spike'
WORK = Path('/tmp/pg-runner-spike/address_standardizer')
HOME = Path(os.environ.get('CODEX_HOME', '/tmp/unused-codex-home'))
PACKAGE = ROOT / 'packages/address_standardizer/build.sh'
PHASE = sys.argv[1]
OUT.mkdir(parents=True, exist_ok=True)


def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def selection():
    return json.loads((OUT / 'selection/selection.json').read_text())['components']['postgresql']


def build_command(output):
    return ['python3', 'build.py', '--target', 'linux-x86_64', 'extension-build', 'address_standardizer',
            selection()['development_archive'], str(output), '--workspace', str(WORK),
            '--source-cache', '/tmp/pg-runner-spike/sources', '--reuse-workspace']


def commit(message):
    run(['git', 'add', 'packages/address_standardizer/build.sh'])
    run(['git', 'commit', '-m', message])


def invoke(prompt, label):
    secrets = json.loads((HOME / 'auth.json').read_text()).get('tokens', {})
    redactions = [value for value in secrets.values() if isinstance(value, str) and value]
    start = time.monotonic()
    process = subprocess.run(['codex', 'exec', '--ignore-user-config', '--model', 'gpt-6-luna',
                              '--dangerously-bypass-approvals-and-sandbox', '--json', prompt],
                             capture_output=True, text=True, timeout=900)
    transcript = process.stdout + '\n' + process.stderr
    for value in redactions:
        transcript = transcript.replace(value, '[REDACTED]')
    (OUT / f'{label}-agent.jsonl').write_text(transcript)
    print(f'{label}: agent exit={process.returncode}, seconds={time.monotonic() - start:.2f}', flush=True)
    if process.returncode:
        print(transcript[-6000:])
        raise RuntimeError('Agent failed')


def candidate(number):
    dest = OUT / f'candidate-{number}'
    start = time.monotonic()
    with (OUT / f'candidate-{number}-build.log').open('w') as log:
        run(build_command(dest), stdout=log, stderr=subprocess.STDOUT)
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert not subprocess.check_output(['git', 'diff', 'HEAD', '--', 'packages/address_standardizer/build.sh'], text=True)
    manifest = json.loads((dest / 'extension-build.json').read_text())
    runtime = Path(selection()['archive'])
    shutil.copyfile(runtime, dest / runtime.name)
    run(['python3', 'build.py', '--target', 'linux-x86_64', 'build-record', 'address_standardizer',
         str(dest / manifest['archive']['filename']), str(dest / 'record.json'), '--revision', revision,
         '--postgresql-archive', str(runtime)])
    dependency = WORK / 'build/dependencies/lib/libpcre2-8.a'
    report = {'commit': revision, 'round': number, 'postgresql': runtime.name,
              'extension': manifest['archive']['filename'], 'build_seconds': time.monotonic()-start,
              'dependency_sha256': hashlib.sha256(dependency.read_bytes()).hexdigest(),
              'dependency_mtime_ns': dependency.stat().st_mtime_ns,
              'workspace_marker': json.loads((WORK / '.pg-binaries-extension-workspace.json').read_text())}
    (dest / 'candidate.json').write_text(json.dumps(report, indent=2)+'\n')
    run(['git', 'push', 'origin', 'HEAD:refs/heads/runner-spike-results-20261101-build'])
    print(json.dumps(report), flush=True)


COMMON = '''The human explicitly authorises this GitHub-hosted development experiment as an exception to local-first instructions.
Use gpt-6-luna for this bounded task; do not spawn agents. Only edit packages/address_standardizer/build.sh.
Do not read authentication files or environment credentials. Do not change tests, harness, metadata or workflows.
No runtime tests run on this development runner: a separate clean runner performs them.
Keep experimental dependencies and work at the existing paths. Commit the package fix, but do not merge or force-push.
'''

if PHASE == 'prepare':
    run(['git', 'config', 'user.name', 'runner-spike'])
    run(['git', 'config', 'user.email', 'runner-spike@users.noreply.github.com'])
    text = PACKAGE.read_text()
    text = text.replace('os=$1 workspace=$3', 'os=$1 workspace=$3\nmake --runner-spike-invalid-option')
    text += '\nfind "$payload/$share_rel/extension" -name "address_standardizer--*.sql" -delete\n'
    PACKAGE.write_text(text)
    commit('Introduce controlled build and packaging faults for runner experiment')
    start = time.monotonic()
    with (OUT / 'initial-failure.log').open('w') as log:
        failed = subprocess.run(build_command(OUT / 'initial-output'), stdout=log, stderr=subprocess.STDOUT)
    (OUT / 'initial-failure.json').write_text(json.dumps({'exit_code': failed.returncode, 'seconds': time.monotonic()-start})+'\n')
    assert failed.returncode != 0, 'Expected controlled build failure'
elif PHASE == 'develop':
    HOME.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(HOME, 0o700)
    raw = os.environ.pop('RUNNER_AUTH_JSON')
    auth = HOME / 'auth.json'
    auth.write_text(raw)
    os.chmod(auth, 0o600)
    invoke(COMMON + '\nThe initial build failed; inspect out/runner-spike/initial-failure.log, fix only the invalid make invocation and rerun this harness command until it succeeds:\n' +
           ' '.join(build_command(OUT / 'agent-output')) +
           '\nLeave the deliberate final SQL-file removal in place for the next clean-verification experiment. Commit the build fix.', 'develop')
    candidate(1)
elif PHASE == 'repair':
    report = json.loads((OUT / 'clean-1/check-result.json').read_text())
    assert report['runtime_exit_code'] != 0, 'Expected broken packaging candidate to fail on clean runner'
    invoke(COMMON + '\nThe package compiled, but clean-machine verification failed. Read out/runner-spike/clean-1/check-result.json and its runtime.log and checks files. Fix the package recipe to address the reported failure. Rebuild with:\n' +
           ' '.join(build_command(OUT / 'agent-output')) + '\nCommit the packaging fix.', 'repair')
    candidate(2)
    first = json.loads((OUT / 'candidate-1/candidate.json').read_text())
    second = json.loads((OUT / 'candidate-2/candidate.json').read_text())
    assert first['dependency_sha256'] == second['dependency_sha256']
    assert first['dependency_mtime_ns'] == second['dependency_mtime_ns']
elif PHASE == 'verify':
    number = sys.argv[2]
    src = OUT / f'download-{number}'
    details = json.loads((src / 'candidate.json').read_text())
    dest = OUT / f'verification-{number}'
    dest.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    with (dest / 'runtime.log').open('w') as log:
        checked = subprocess.run(['python3', 'build.py', '--target', 'linux-x86_64', 'runtime-check',
                                  str(src / details['postgresql']), str(dest), '--package-archive',
                                  f"address_standardizer={src / details['extension']}"], stdout=log, stderr=subprocess.STDOUT)
    (dest / 'check-result.json').write_text(json.dumps({'runtime_exit_code': checked.returncode,
        'candidate': details, 'verification_seconds': time.monotonic()-start}, indent=2)+'\n')
    print(f'Round {number}: runtime verification exit={checked.returncode}', flush=True)
    if number == '2' and checked.returncode:
        raise RuntimeError('Final candidate did not pass clean verification')
elif PHASE == 'finish':
    final = json.loads((OUT / 'clean-2/check-result.json').read_text())
    assert final['runtime_exit_code'] == 0
    (OUT / 'result.json').write_text(json.dumps({'outcome': 'passed', 'model': 'gpt-6-luna',
        'final_commit': final['candidate']['commit'], 'clean_verification': final}, indent=2)+'\n')
else:
    raise SystemExit(f'Unknown phase: {PHASE}')
