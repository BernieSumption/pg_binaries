# Linux pg_jsonschema 0.3.4 candidate publication evidence

[Run 39091662464](https://github.com/BernieSumption/pg_binaries/actions/runs/39091662464) passed the final-archive build, relocated Alpine SQL probe and ELF closure check for PostgreSQL 18.6 on native x86-64 and arm64 runners. The importer checked the downloaded extension archives, pinned core archives, sidecars, reports, receipts and records against their exact hashes. The extension archive SHA-256 values are `fa656f90cded75bf0cbc52fc0b8cf813c03b3d1087fe4028d913b1e96d1b2ff0` for x86-64 and `21c35d0fbf8bfbe3cafc0db3e87c345e67631356fe4ecf5ed7e505c5500d4f96` for arm64.

The run predates a correction that copies validated records into `support/verification`, so these retained records are historical under the current profile. A new run is required for current-profile evidence. Release eligibility also remains blocked by the seahash notice and core dependency reviews.
