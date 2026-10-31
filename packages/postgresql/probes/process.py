"""Capture pg_ctl output without waiting for its Windows server's inherited handles."""

import locale
import subprocess
import sys
import tempfile


def run(arguments, **options):
    tool = str(arguments[0]).replace('\\', '/').rsplit('/', 1)[-1].lower()
    if sys.platform != 'win32' or tool not in ('pg_ctl', 'pg_ctl.exe') or not options.get('capture_output'):
        return subprocess.run(arguments, **options)
    options = options.copy()
    options.pop('capture_output')
    check = options.pop('check', False)
    # Windows descendants retain these handles after pg_ctl exits. TemporaryFile
    # permits deletion to wait until the last inherited handle closes.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        result = subprocess.run(arguments, stdout=stdout, stderr=stderr, check=False, **options)
        stdout.seek(0)
        stderr.seek(0)
        result.stdout, result.stderr = stdout.read(), stderr.read()
    if options.get('text') or options.get('universal_newlines') or options.get('encoding') or options.get('errors'):
        encoding = options.get('encoding') or locale.getpreferredencoding(False)
        errors = options.get('errors') or 'strict'
        result.stdout = result.stdout.decode(encoding, errors).replace('\r\n', '\n').replace('\r', '\n')
        result.stderr = result.stderr.decode(encoding, errors).replace('\r\n', '\n').replace('\r', '\n')
    if check:
        result.check_returncode()
    return result
