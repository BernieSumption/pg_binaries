# pg_jsonschema Linux candidate publication, run 39092888140

[GitHub Actions run 39092888140](https://github.com/BernieSumption/pg_binaries/actions/runs/39092888140) passed on x86-64 and arm64. Both jobs built pg_jsonschema 0.3.4 from pinned upstream source against the exact PostgreSQL 18.6 core archive, ran schema SQL after relocating the final archives into Alpine 3.22, and passed ELF dependency inspection. The importer rechecked the downloaded archive hashes, sidecars, receipts, reports and records before retaining the evidence here.

The final extension archive SHA-256 values are `602d49362f9d59c990108fca8f30c41f2d79db604c508fc2bc7264ce52dbed49` for x86-64 and `b30c3e03aceacea1e762a7fb75062b23227b1a95c20299ca9ae7330904f112fa` for arm64. Both records identify the Linux host kernel as `6.17.0`; the planner accepts them as current-profile records. Release eligibility remains false while the seahash notice and core dependency redistribution reviews are unresolved.
