# Extension dependency conflicts

**Decision:** Does observed dependency usage or version conflict frequency justify special handling beyond recording upstream dependency names?

The current policy assumes extension-to-extension dependencies are rare in practice. We therefore chose not to track required dependency versions, which would be difficult to ascertain reliably. That assumption has not yet been established by a survey. Clients handle dependency selection; verification records exact tested combinations without promising compatibility with other dependency versions.

**Evidence needed:** Inspect a named sample of intended and likely extensions. Report how many declare SQL-extension dependencies, how many share prerequisites, and how many have documented or reproduced version conflicts. Identify the releases and sources behind each conflict; distinguish missing information from evidence that a combination works. Shared prerequisites alone do not establish a conflict. Keep native-library collisions separate from SQL-extension version requirements.

Use those findings to decide whether the current policy is sufficient or a specific exception is warranted. This investigation does not itself authorize a general version resolver or exhaustive compatibility matrix. The agreed names-only policy remains in force: [F03](../../../functional/functional-policy.md#f03--sql-extensions-can-be-obtained-separately), [dependency scope](../../extensions-notes.md#agreed-dependency-scope).

**Recommendation for review:** Keep the names-only policy while completing the bounded survey above. Propose specific handling only for evidenced conflicts that make the policy inadequate.
