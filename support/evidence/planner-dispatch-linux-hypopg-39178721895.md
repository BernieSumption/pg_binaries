# Planner retry with coordinator artifact reuse

[Run 39178721895](https://github.com/BernieSumption/pg_binaries/actions/runs/39178721895) planned one HypoPG 1.4.3, PostgreSQL 17.11, Linux x86-64 target and called the selected publication workflow from commit `04cda9dcc0ef7a59bf75a24cbeacd982832cb42a`. All jobs passed in 98 seconds. The core resolver selected the checksum-verified artifact uploaded by the preceding coordinator [run 39178528526](https://github.com/BernieSumption/pg_binaries/actions/runs/39178528526), rather than the older standalone candidate. It checked the source/run identity and builder inputs before reuse. The retained core SHA-256 is `dcda10d41f048d3c638dbd71f23645d9815f889c323cae9020d8c2c9de120ecd`.

The selected workflow built HypoPG and passed the final-archive checks and relocated Alpine 3.22 suite. Its HypoPG archive SHA-256 is `dbce1d98805372fbbe7c283c91918a4817f6a9ab6503c7e773c5c9c21bb0987a`. The downloaded artifact was independently imported; the retained [verification record](../verification/hypopg-1.4.3-postgresql-17.11-linux-x86_64-current-39178721895.json) matches the artifact record byte for byte.

This proves checked retrieval from a coordinator-produced temporary artifact on this target. The planner still needs general target routing and applicable-archive discovery beyond the called workflow's core resolver.
