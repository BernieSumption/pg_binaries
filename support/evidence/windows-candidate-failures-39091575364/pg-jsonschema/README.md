# pg_jsonschema Windows candidate run failure

[Run 39091575364](https://github.com/BernieSumption/pg_binaries/actions/runs/39091575364) used source revision `2ea355e60e1bb3cd7304b9c8ce7be3246442b320`. The core archive downloaded successfully, but `scripts/pg_jsonschema/windows-feasibility.ps1` rejected it because the script still pinned the earlier archive SHA. The retained [attempt](attempt.json) records both cases as failed and the extension archive as absent; the runner's [failure output](failure.txt) gives the expected failure and actual core SHA.

The candidate workflow and emitter already referenced core run 39089826690. The feasibility script's stale checksum and build ID caused the run to stop before source build or archive inspection. Those script pins have since been updated, and the focused test now checks script/workflow/emitter alignment. This directory preserves failure evidence only; it is not a passing publication record.
