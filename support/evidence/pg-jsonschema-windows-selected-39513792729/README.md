# Windows pg_jsonschema packaging failure

[Run 39513792729](https://github.com/BernieSumption/pg_binaries/actions/runs/39513792729) at revision `3570b6f765e9e8855c4cab049662cec154f00281` built PostgreSQL 18.6 and compiled unmodified pg_jsonschema 0.3.4 on Windows. Archive packaging then stopped in `inventory_cargo_licenses.py` with `seahash declaration evidence changed`. The extension archive was not produced, and fresh-runner verification consequently failed.

The repository's global Git text conversion changed the declaration-evidence file's line endings on Windows checkout. The collector correctly rejected the changed bytes. The evidence file now has a `-text` attribute so later Windows checkouts preserve the reviewed bytes; the focused Cargo inventory test checks that attribute and exact file content. A fresh selected run is needed to verify the correction.
