import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


home = Path(os.environ['CODEX_HOME'])
home.mkdir(mode=0o700, parents=True, exist_ok=True)
os.chmod(home, 0o700)
raw = os.environ.pop('RUNNER_AUTH_JSON')
auth = json.loads(raw)
assert auth.get('auth_mode') == 'chatgpt' and auth.get('tokens'), 'ChatGPT login required'
assert not any(os.environ.get(k) for k in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'CODEX_ACCESS_TOKEN'))
path = home / 'auth.json'
path.write_text(raw)
os.chmod(path, 0o600)
original = hashlib.sha256(path.read_bytes()).digest()
redactions = [raw] + [v for v in auth['tokens'].values() if isinstance(v, str) and v]
result = {'job': os.environ['PROBE_JOB'], 'requests': []}
output = Path('out/runner-spike')
output.mkdir(parents=True, exist_ok=True)
try:
    for attempt in range(2):
        message = home / f'message-{attempt}.txt'
        start = time.monotonic()
        run = subprocess.run([
            'codex', 'exec', '--ignore-user-config', '--ephemeral', '--sandbox', 'read-only',
            '--model', 'gpt-6-luna', '--json', '--output-last-message', str(message),
            'Reply with exactly READY. Do not inspect files or execute any commands.'
        ], capture_output=True, text=True, timeout=120)
        entry = {'attempt': attempt + 1, 'seconds': time.monotonic() - start,
                 'exit_code': run.returncode,
                 'expected_reply': message.is_file() and message.read_text().strip() == 'READY'}
        if run.returncode:
            error = (run.stderr + run.stdout)[-2500:]
            for value in redactions:
                error = error.replace(value, '[REDACTED]')
            entry['error'] = error
        for line in run.stdout.splitlines():
            try:
                event = json.loads(line)
                if event.get('type') == 'turn.completed':
                    entry['usage'] = event.get('usage')
            except ValueError:
                pass
        result['requests'].append(entry)
        print(json.dumps(entry), flush=True)
        if run.returncode or not entry['expected_reply']:
            raise RuntimeError('Subscription inference probe failed')
    result['auth_changed'] = hashlib.sha256(path.read_bytes()).digest() != original
finally:
    path.unlink(missing_ok=True)
    result['auth_file_removed'] = not path.exists()
    (output / 'auth-result.json').write_text(json.dumps(result, indent=2) + '\n')

checkpoint = Path('spikes/runner-iteration/checkpoints') / f"{os.environ['PROBE_JOB']}.json"
checkpoint.parent.mkdir(parents=True, exist_ok=True)
checkpoint.write_text(json.dumps(result, indent=2) + '\n')
subprocess.run(['git', 'config', 'user.name', 'runner-spike'], check=True)
subprocess.run(['git', 'config', 'user.email', 'runner-spike@users.noreply.github.com'], check=True)
subprocess.run(['git', 'add', str(checkpoint)], check=True)
subprocess.run(['git', 'commit', '-m', 'Record subscription authentication probe'], check=True)
subprocess.run(['git', 'push', 'origin', f"HEAD:refs/heads/{os.environ['RESULT_BRANCH']}"], check=True)
