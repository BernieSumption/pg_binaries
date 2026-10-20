# Build and verification architecture

Maintainers need to add PostgreSQL and extension releases across several platforms without copying a workflow for every combination. They also need to retry one failed build without rebuilding unrelated projects. Keep the build and test paths organized around a selected target, and use agents to coordinate work where a program would add more complexity than it saves.

## Support and available downloads

`support.json` and the retained upstream release snapshot declare the PostgreSQL releases, extension releases and platforms to support. A target identifies a PostgreSQL release, an operating system and architecture, and an extension project and release when applicable. Build scripts and workflows take a selected target as input; they do not maintain independent support lists.

`inventory.json` records published downloads. It is absent before the first release. A small manifest may locate unpublished archives and their verification records during development; it must identify their bytes and where to retrieve them, and must not appear to advertise public downloads. Build and test provenance belongs in archive metadata and retained records. Add a client-facing inventory field only when a specific client or release requirement needs it.

A deterministic coverage check compares selected targets with eligible downloads and reports missing archives, failed or missing verification, and missing public downloads separately. For the first release it may compare selected targets with staged candidate archives because no public inventory exists. It must account for prerequisites and must not turn an unbuilt selected target into an unsupported target. The same check supports later releases using `inventory.json` as the map of already published downloads.

## Build and verification paths

`scripts/<project>/` holds the upstream-specific recipe and SQL probes for PostgreSQL or an extension project. Recipes take one target, use the selected upstream source and dependencies, and produce a final archive with metadata identifying its inputs. Share common retrieval, packaging and identity checks where this removes duplication. A native extension builds against development files from the selected PostgreSQL build; its archive records the exact PostgreSQL archive used. A SQL-only package may share unchanged files where its scripts and prerequisites support the selected cores.

`scripts/<os>/` holds common operating-system setup, packaging and verification code. `.github/workflows/` provides parameterized entry points on the required standard runners. Jobs may group targets when setup savings justify the retry cost, but each target must remain independently selectable for investigation. An agent may choose job order, batching and retries from the coverage report and declared prerequisites. A general automated dispatcher is unnecessary unless measured repeated coordination work justifies one.

Verification assembles the final PostgreSQL, extension and prerequisite archives using [the installation procedure](install-process.md), outside their build environment. Shared code handles assembly, relocation, test execution and result collection; operating-system code handles runner setup and ELF, Mach-O or PE inspection. Each project supplies SQL probes that create its advertised extensions and check representative DDL and behaviour. Reuse those probes across platforms and PostgreSQL versions. Add distinct cases only when a documented upstream interface or selected build capability requires them.

For each tested combination, retain a compact result with the exact archive hashes, required case outcomes, test revision and environment. Failed and skipped cases remain visible. Reuse a result only while its archives, checks and claimed compatibility remain applicable. Test changes invalidate affected results; unrelated edits need not trigger a rebuild or repeat expensive verification. [The testing policy](testing.md) defines the required cases and environments.

## Developing a new recipe

When a PostgreSQL or native extension recipe has no checked build, normally prototype one Linux/arm64 target in local Docker before using GitHub runners. Establish the source identity, build, package and SQL probe there, then run the selected GitHub build and final-archive verification before expanding the recipe to other platforms. This catches basic recipe errors without repeated native-runner setup. Skip the prototype when an existing checked build establishes the relevant behaviour or Docker cannot exercise the question; a macOS or Windows-specific problem still needs its native runner.

When porting a component, use its checked recipe on another platform as the primary reference and a checked recipe for a comparable component on the target platform as the platform reference. Give both to a delegated agent when available. Verify the resulting archive on its own target; neither reference establishes cross-platform compatibility.

## Reusing completed work

For an unpublished archive, use its temporary manifest when its bytes and relevant build inputs still match. If its temporary artifact is unavailable, rebuild it unless the same checked bytes are readily available elsewhere. Avoid a general search through historical Actions runs solely to save a build.

After the first release, use `inventory.json` to find existing published archives. Preserve still-selected immutable URLs, check archive identity and availability when reusing them, and verify a reused extension with any newly selected PostgreSQL archive. The [delivery policy](delivery-process.md) governs support refreshes and release preparation. Implement additional automation for incremental releases when the first published inventory provides a real input and the benefit is clear.

## Code and temporary work

`tools/` holds shared coverage, archive and verification utilities; `support/evidence/` holds retained results. Generated archives and local caches stay out of source control. Keep one active implementation for each build and verification path. Remove a superseded workflow, script, adapter or test when its active callers have moved; Git history and retained evidence preserve its useful history.

Place temporary investigation scripts and workflows in `experiments/<name>/`. Record when each experiment was created, its question, required inputs and condition for finishing. Review it when its question is answered, related work ends or its target changes, and at least every three months. Move code still used by builds or tests to its owning recipe or shared tool; remove experiments with no concrete next use.

Reassess complexity during migration and extension onboarding. Prefer removing unnecessary machinery or returning a choice to agent coordination when it reduces maintenance cost without weakening a specification guarantee. Follow [the functional specification](../specs/functional.md#use-a-coherent-architecture) if a proposed architectural change itself becomes a large project.
