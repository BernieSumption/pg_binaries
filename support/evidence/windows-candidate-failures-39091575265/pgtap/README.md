# pgTAP Windows candidate run failure

[Run 39091575265](https://github.com/BernieSumption/pg_binaries/actions/runs/39091575265) used source revision `2ea355e60e1bb3cd7304b9c8ce7be3246442b320`. The candidate workflow downloaded the core archive, but `scripts/pgtap/windows-feasibility.ps1` rejected it because the script still pinned the earlier archive SHA. The retained [attempt](attempt.json) records both cases as failed and the pgTAP archive as absent; the [log excerpt](failure-log-excerpt.txt) records the checksum failure.

The workflow, checker and emitter had already moved to core run 39089826690. The feasibility script's stale run ID, checksum and source revision caused the run to stop before SQL generation or archive inspection. Those pins have since been updated, and the focused test now checks script/workflow/emitter alignment. This directory preserves failure evidence only; it is not a passing publication record.
