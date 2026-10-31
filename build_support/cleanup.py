"""Remove disposable build trees, including Windows read-only source files."""

import os
from pathlib import Path
import shutil
import stat


def remove_tree(path, *, missing_ok=False):
    root = Path(path).resolve()

    def retry_readonly_file(operation, filename, exception):
        error = exception[1]
        candidate = Path(filename)
        if os.name != "nt" or not isinstance(error, PermissionError):
            raise error
        info = candidate.lstat()
        if (not candidate.resolve().is_relative_to(root) or not stat.S_ISREG(info.st_mode)
                or not info.st_file_attributes & stat.FILE_ATTRIBUTE_READONLY):
            raise error
        candidate.chmod(info.st_mode | stat.S_IWRITE)
        operation(filename)

    try:
        shutil.rmtree(path, onerror=retry_readonly_file)
    except FileNotFoundError:
        if not missing_ok or root.exists():
            raise
