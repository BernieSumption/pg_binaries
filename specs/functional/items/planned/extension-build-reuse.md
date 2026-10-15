# D03 — Extension build reuse

**F08 — initial build strategy; runtime compatibility requires verification.** Start with separate native builds per PostgreSQL major, using the oldest eligible compatible minor to avoid dependence on later server symbols. PostgreSQL's [C-extension guidance](https://www.postgresql.org/docs/18/xfunc-c.html) informs expected ABI compatibility; our tests establish the advertised runtime range.

If a minor needs different interfaces, split the build range. SQL-only packages can also require version-specific generation or syntax, so broader reuse needs tests even without compilation.

## Completion

Demonstrate reuse of identical archive bytes across eligible minors, retaining separate build targets and runtime evidence. Split ranges when a tested minor is incompatible.
