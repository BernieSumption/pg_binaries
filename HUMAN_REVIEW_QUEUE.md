# Human review queue

## Missing upstream licence text for a declared standard licence

The selected pg_jsonschema 0.3.4 build includes seahash 4.1.0. Its [published package metadata](https://docs.rs/crate/seahash/4.1.0/source/Cargo.toml.orig) declares MIT and names its authors, and its [VCS metadata](https://docs.rs/crate/seahash/4.1.0/source/.cargo_vcs_info.json) identifies the exact upstream commit. Neither the package nor that commit contains a licence text or copyright notice, as recorded in [the exact-source review](support/evidence/pg-jsonschema-crate-licenses-2026-10-18/README.md). The release policy currently keeps this dependency unresolved and pg_jsonschema archives ineligible.

Should a package that declares a standard licence but omits its text be considered redistributable when we include the standard licence terms and the package's declared author metadata as a separately identified notice, without claiming that it is an upstream copyright notice? If so, apply that rule to seahash and similar packages, recording the exact package/source identity and the constructed notice. Otherwise keep pg_jsonschema ineligible until upstream supplies an authoritative notice. Other builds can proceed.

## Backlog ideas

From Bernie: Adding this here so that we don't forget it. Don't start work on this yet. I'd like to discuss the viability of these and specify them properly before we go ahead. If indeed we decide to go ahead at all.

1. Size review. Look for ways to reduce binary size before building out the backlog of many versions. Potential options include compiler flags like -Os, reviewing the enabled build options for any that provide does proportionately small value in return for their increase in binary size, different compression algorithms and so forth. As a first step in this, some analysis about of the built archive to get a picture of what the greatest contributors are to size might be helpful.

2. Adversarial correctness review. Have an Astra agent review the implementation and tests to identify both specific and systematic potential issues.

3. Manual post-release bug hunting. Discuss and specify an occasional, manually initiated process that downloads and exercises released assets in environments outside routine GitHub-runner coverage. Examples include different operating systems and distributions (including older Ubuntu, outside the routine Alpine verification environment), older OS versions and Linux kernels, different distros, Windows without the Visual C++ redistributable installed, and macOS without development tools. These investigations seek production bugs and inform fixes and useful regression tests; they are not an automatic CI job or a prerequisite for each release. Decide the process before implementing it.
