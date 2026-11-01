import json
import os
from pathlib import Path
import subprocess
import sys
import time


name, destination = sys.argv[1:]
deadline = time.monotonic() + 1200
while time.monotonic() < deadline:
    request = subprocess.run(['gh', 'api', f"repos/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}/artifacts?per_page=100"],
                             capture_output=True, text=True, check=True)
    if any(a['name'] == name and not a['expired'] for a in json.loads(request.stdout)['artifacts']):
        Path(destination).mkdir(parents=True, exist_ok=True)
        subprocess.run(['gh', 'run', 'download', os.environ['GITHUB_RUN_ID'], '--repo', os.environ['GITHUB_REPOSITORY'],
                        '--name', name, '--dir', destination], check=True)
        print(f'Received {name}', flush=True)
        break
    jobs = subprocess.run(['gh', 'api', f"repos/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}/jobs"],
                          capture_output=True, text=True, check=True)
    failures = [job['name'] for job in json.loads(jobs.stdout)['jobs'] if job.get('conclusion') in ('failure', 'cancelled', 'timed_out')]
    if failures:
        raise SystemExit(f'No {name}; another job stopped: {failures}')
    time.sleep(5)
else:
    raise SystemExit(f'Timed out waiting for {name}')
