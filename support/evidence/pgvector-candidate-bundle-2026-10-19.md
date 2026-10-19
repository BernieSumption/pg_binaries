# pgvector candidate bundle extraction

On 2026-10-19, the Actions artifact from [selected pgvector Linux run 39171748020](https://github.com/BernieSumption/pg_binaries/actions/runs/39171748020) was downloaded to temporary storage. Its 180,724,455-byte ZIP matched GitHub's reported SHA-256 `531bed96fa770e56077637ba9e5eb38e553fd5f440e8bf43bc7bc7de8aa6bd12`.

`tools/actions_candidate_bundle.py` extracted the exact PostgreSQL 17.11 and pgvector 0.8.7 Linux x86-64 archives, their adjacent checksum sidecars, and both verification records from that ZIP. It validated both sidecars and returned six files totaling 61,772,657 bytes. This proves extraction and size headroom for that artifact; it does not establish current-profile eligibility or planner no-op reuse.
