#!/usr/bin/env python3
"""Convert combined Alpine verifier phase status to GitHub case outcomes."""

import argparse
import json
from pathlib import Path
import re
import sys


PHASES = ("core", "diagnostics", "postgis", "tiger")
_ROW = re.compile(r"^(core|diagnostics|postgis|tiger)\t(running|passed|skipped|failed\([0-9]+\))$")


def read_outcomes(status_path, verification_skipped=False):
    """Return one GitHub Actions outcome for each registered verifier phase.

    Missing, duplicate, malformed, running, or unreadable phase evidence fails
    closed. A verifier invocation intentionally skipped because its build input
    is unavailable can be represented explicitly with verification_skipped.
    """
    if verification_skipped:
        return {phase: "skipped" for phase in PHASES}

    outcomes = {phase: "failure" for phase in PHASES}
    rows = {phase: [] for phase in PHASES}
    try:
        lines = Path(status_path).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return outcomes

    malformed = False
    for line in lines:
        match = _ROW.fullmatch(line)
        if not match:
            # Corrupt or unrecognized evidence prevents accepting any pass.
            malformed = True
            continue
        phase, result = match.groups()
        rows[phase].append(result)

    if malformed:
        return {phase: "failure" for phase in PHASES}
    for phase in PHASES:
        if rows[phase] == ["skipped"]:
            outcomes[phase] = "skipped"
        elif len(rows[phase]) == 2 and rows[phase][0] == "running":
            if rows[phase][1] == "passed":
                outcomes[phase] = "success"
    return outcomes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", type=Path, required=True,
                        help="combined verifier status/phases.tsv")
    parser.add_argument("--verification-skipped", action="store_true",
                        help="the verification step was skipped because build input was unavailable")
    args = parser.parse_args(argv)
    print(json.dumps(read_outcomes(args.status, args.verification_skipped),
                     separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
