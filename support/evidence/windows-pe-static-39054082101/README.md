# Windows PE import-check failure on an ICU data DLL

[Run 39054082101](https://github.com/BernieSumption/pg_binaries/actions/runs/39054082101) built PostgreSQL 18.6 and pgvector 0.8.7 and passed their initial relocated SQL probe. The retained failed verification records and `static-analysis.json` bind the final archive checksums. The checker parsed eight packaged PE files before it rejected `bin/icudt78.dll` because `dumpbin /imports` showed no recognized import section.

The exact core archive downloaded from the run matches the report's SHA-256, `07eabbc40490d3381b885115fd72ee6a42b480299bb4d7d23fcc6317afbcefb5`. Non-executing inspection of its `icudt78.dll` PE32+ optional header found both the normal import and delay-import directory RVA/size pairs equal to zero. This data-only DLL needs a verified empty-import case; other unrecognized `dumpbin` output must still fail closed. The current archive has no passing PE static-analysis record.
