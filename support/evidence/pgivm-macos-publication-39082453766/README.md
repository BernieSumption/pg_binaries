# pg_ivm 1.16 macOS publication attempt

[Run 39082453766](https://github.com/BernieSumption/pg_binaries/actions/runs/39082453766) built and exercised pg_ivm 1.16 against the exact PostgreSQL 18.6 Apple Silicon core, with final-archive static analysis passing. Its publication finalizer rejected the passing probe because it expected a `CREATE MATERIALIZED VIEW` command tag; the upstream test invokes `pgivm.create_immv()` and reports its function result instead. The finalizer and its fixture now use the observed probe output. No passing archive-bound publication record came from this run.
