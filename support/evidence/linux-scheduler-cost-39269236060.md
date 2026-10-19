# Linux selected scheduler run 39269236060

GitHub Actions [run 39269236060](https://github.com/BernieSumption/pg_binaries/actions/runs/39269236060) started on 2026-10-19 at 14:28 UTC and ended cancelled at 16:30 UTC. Cancellation was requested after a broad changed-profile refresh became historical under subsequent source changes. The selector had chosen 75 extension targets.

The GitHub jobs API returned 1,748 job records: 315 succeeded, 1,426 skipped, four were cancelled and three failed. Of these, 322 have nonzero start-to-completion intervals. Summing those intervals gives about 411.7 elapsed job-minutes: 29.4 for selection, 27.6 for planning, 285.0 for builds and 69.7 for verification. This is a sum of job elapsed times, not a billing measurement. The workflow created one planner and 21 conditional route jobs for each selected extension target; 20 conditional routes skipped for a Linux target.

The three failed jobs were pgvector verifiers for PostgreSQL 16.15 on both Linux architectures and 15.19 on x86-64. Their cause remains to be investigated; this cancelled run cannot supply a passing overall publication record.

The measured work suggests that reducing skipped routing records would help queue size and workflow readability, but most timed work was in build and verification jobs. Compare a focused retry and any routing redesign against that larger cost before changing the scheduler structure.
