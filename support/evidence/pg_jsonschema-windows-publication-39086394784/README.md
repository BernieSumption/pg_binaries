# pg_jsonschema 0.3.4 Windows candidate attempt

[Run 39086394784](https://github.com/BernieSumption/pg_binaries/actions/runs/39086394784) built the pinned upstream source, assembled extension archive SHA-256 `9a82d0e47519793f1e3acb11b87f69f4b2380213c8cf43a029405ef3b5e30a26`, and passed [relocated schema SQL](x86_64/probe-output.txt) on 2026-10-18. It failed afterward because the restricted runtime `PATH` hid Python from the PE dependency checker. The archive suite and static-analysis cases are both [recorded as failed](x86_64/verification-record.json); no passing publication record was imported. The candidate remains release-ineligible because its core input is a temporary artifact and the Rust crate redistribution review is unresolved.

The CI importer validated the [attempt](x86_64/attempt.json), [receipt](x86_64/current-receipt.json) and failed record at the run revision. The script now saves Python's absolute path before restricting `PATH` for the relocated runtime probe.
