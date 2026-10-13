# Proposed project plan

Status: provisional, 2026-10-13. This is a suggested sequence for Goal mode, **not a specification of how to build the project**. Agents may change tools, repository layout, and order when evidence suggests a better route. A milestone is complete when it has the user-visible result and [verification evidence](verification.md), rather than when a particular script exists.

## Milestones

- [ ] **1. Make the contract executable.** Turn the [specification](specification.md) into an inventory of versions, platforms, capability checks, and a starter schema corpus. Decide how test results and supported OS ranges will be reported. Resolve only the human decisions needed for the first public release.
- [ ] **2. Prove one portable PostgreSQL download.** Produce one exact minor for one platform. Download the packaged artifact onto a clean host; initialize it, run realistic schema SQL, test collations, move it, and run it again. Investigate dependency surprises such as Homebrew LZ4 until the artifact satisfies the portability invariant.
- [ ] **3. Prove the three-platform contract.** Deliver that same minor on x86-64 Linux, Intel macOS, and x86-64 Windows. Test on current OS versions and probe backward compatibility of each single-platform artifact. Publish the measured support range, without guessing it from the build host.
- [ ] **4. Establish the extension catalogue.** Add pgvector and PostGIS for the pilot minor. Check real SQL behavior and supporting files, establish the practical PostGIS component set, and flag any proposed exclusions for review.
- [ ] **5. Prove public distribution.** Publish a pilot through the selected free distribution service. A fresh consumer downloads the right minor and platform, verifies it, obtains licenses, adds an extension, and runs the schema corpus. Check that a later rebuild can coexist with the earlier artifact.
- [ ] **6. Fill the version matrix.** Work through every released minor of 15–18. For each, deliver the three platforms and the advertised extension versions, and collect the same verification evidence. Keep failures and unavailable extension combinations explicit.
- [ ] **7. Make maintenance routine.** Add a repeatable path for new PostgreSQL minors, new extension versions, catalogue additions, dependency updates, and revalidation of historical downloads. Expand the schema corpus using failures from real consumers.

## Repository layout, when implementation begins

Keep the human contract easy to find at the root (`README.md` and `docs/`). The implementation will likely need separate areas for version/extension inventory, build logic, tests, and release automation. Their exact directories, data formats, and workflow steps should emerge from the pilot. Generated binaries do not belong in Git history.

## Evidence to bring back to the director

Before changing a requirement, report the observed limitation, the affected users or combinations, alternatives tried, and a recommendation. The [review list](decisions.md) records the decisions that are already visible; implementation may reveal others.
