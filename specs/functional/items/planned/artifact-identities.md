# D02 — Source, SQL and build identities

**F02, F03, F08, F11 — required distinction.** One source release can contain several SQL extensions; an extension can move source projects; a corrected build can change bytes without changing either version. Metadata retains all three identities.

PostgreSQL's [extension packaging rules](https://www.postgresql.org/docs/18/extend-extensions.html) distinguish installation scripts, update scripts and control files. SQL version strings are arbitrary. An update script's presence does not prove that its starting version can be installed with the packaged library. Test each advertised installation or update path; this creates no general production-upgrade guarantee.

**Agreed dependency scope:** Record upstream control-file dependency names. Clients choose dependency versions and handling, including any restriction on `CASCADE`. Do not recommend dependency versions, research compatibility ranges between extensions or build a general version-resolution system. Verification records the exact versions tested and establishes only that concrete combination. This leaves PostgreSQL-version compatibility and native runtime packaging requirements intact. The [dependency research](../../../extensions/extensions-notes.md) explains the upstream behaviour.

## Completion

Emit and validate the separate source, SQL and build identities, declared dependency names and exact tested combinations in manifests and catalogue records.
