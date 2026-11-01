"""Local control for this bounded experiment; never prints authentication contents."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REPO = 'BernieSumption/pg_binaries'
SECRET = 'RUNNER_SPIKE_AUTH_20261101'
AUTH = Path('/private/tmp/pg-binaries-codex-auth/auth.json')


def run(arguments, **kwargs):
    return subprocess.run(arguments, cwd=ROOT, check=True, **kwargs)


parser = argparse.ArgumentParser()
parser.add_argument('operation', choices=['supply', 'revoke', 'push', 'fetch'])
args = parser.parse_args()
if args.operation == 'supply':
    raw = AUTH.read_bytes()
    auth = json.loads(raw)
    assert auth.get('auth_mode') == 'chatgpt' and auth.get('tokens')
    run(['gh', 'secret', 'set', SECRET, '--repo', REPO], input=raw)
    print('Supplied task authentication.')
elif args.operation == 'revoke':
    run(['gh', 'secret', 'delete', SECRET, '--repo', REPO])
    print('Removed temporary GitHub secret; local login is unchanged.')
elif args.operation == 'push':
    run(['git', 'push', 'origin', 'HEAD:refs/heads/runner-spike-20261101'])
elif args.operation == 'fetch':
    run(['git', 'fetch', 'origin', 'runner-spike-results-20261101-auth'])
    run(['git', 'show', 'FETCH_HEAD:spikes/runner-iteration/checkpoints/auth-sequential.json'])
