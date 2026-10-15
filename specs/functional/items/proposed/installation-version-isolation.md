# Installation version isolation

**Question:** Should the packaging model explicitly require a separate installation prefix for conflicting native releases?

**Recommendation for review:** For exact native release selection, assemble one chosen release of each extension and its dependencies into an installation. Use a separate installation prefix when another task needs a conflicting release. Preserve upstream controls and record their defaults. Supporting upstream-designed multiple SQL versions remains possible after testing their compatibility with the packaged library; do not infer it from script filenames or database version labels alone.

The [extension-file research](../../../extensions/extensions-notes.md#files-and-version-coexistence) explains why multiple SQL version labels do not imply native binary isolation. Relate the outcome to [F02–F03](../../functional-policy.md#f02--exact-choices-can-be-discovered).
