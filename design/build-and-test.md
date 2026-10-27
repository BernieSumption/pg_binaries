# Building and verifying the distribution

The build produces independently downloadable PostgreSQL and extension archives that users can extract into one installation. A target is an operating system and architecture selected in `support.json`. For each target, GitHub Actions builds PostgreSQL, builds the selected extensions against it, and tests the archives individually and together. PostgreSQL and every selected extension are built afresh for a new release. An agent investigates failures and retries the affected work to complete the build.

## Build and verification sequence on GitHub Actions

One GitHub Actions workflow defines the full build and verification sequence for a target. Its jobs run on standard GitHub-hosted runners. The sections below describe those jobs in dependency order.

Build jobs upload the PostgreSQL and extension archives as GitHub artefacts. The verification job downloads those artefacts and tests the archives. Each build job also uploads a build record containing its Git revision, selected upstream sources and archive checksums. Extension build records identify the PostgreSQL archive used for compilation.

### PostgreSQL build job

The PostgreSQL job installs the required compiler and dependencies, downloads the PostgreSQL source archive recorded in `support.json`, verifies its checksum, and builds and packages PostgreSQL. It uploads the PostgreSQL archive and the development files needed to compile extensions, including headers, libraries and build tools. The development files need not be included in the PostgreSQL archive downloaded by users.

### Extension build jobs

After the PostgreSQL job uploads its artefacts, the workflow starts one build job per selected extension project. These jobs run independently in parallel. Each job downloads the PostgreSQL archive and development files, installs its extension’s compiler and dependencies, and downloads the selected extension source and verifies its checksum.

Each extension job builds against the downloaded PostgreSQL build. It collects the extension’s installation files and required runtime dependencies in a staging directory, packages them into an extension archive, and uploads the archive and build record as GitHub artefacts.

Build recipes specify their dependencies, toolchain versions and enabled features. Inline checks confirm that the compiled files exist, control files name the intended SQL extensions, and staging directories contain the required runtime files. Recipes can run inexpensive smoke tests to help diagnose build failures.

### Verification job

Once the PostgreSQL and all selected extension archives are available, one verification job downloads them onto a fresh standard GitHub-hosted runner. It installs no additional dependencies. The job tests PostgreSQL with each extension separately, PostgreSQL alone, and PostgreSQL with all selected extensions, using a fresh installation and database for each combination. [Verification job details](#verification-job-details) describes the environment, test sequence and checks.

## Failures and retries

### Continue independent work

A failed job does not cancel independent jobs. The workflow reports which jobs passed, failed or could not run because a required archive or test result was unavailable. The agent uses the GitHub CLI or API to inspect failed jobs and retrieve their logs.

A source checksum mismatch stops the affected build. The agent investigates the source selection and download before changing a recorded checksum.

### Retry a PostgreSQL build

If PostgreSQL needs rebuilding, for example to change a build setting, the agent starts a fresh workflow run that rebuilds PostgreSQL and every selected extension. Previous runs are excluded from the new build’s archive selection.

### Retry an extension build

For a retry, the agent starts a workflow run that builds only the selected extension, using the selected script revision and PostgreSQL artefacts from a specified previous workflow run. The agent can therefore fix an extension recipe and build that extension again while keeping the successful PostgreSQL and other extension archives. The new job runs on a new GitHub-hosted runner, installs its compiler and dependencies, downloads the existing PostgreSQL archive and development files, and uploads the replacement extension archive.

Verification uses the current run’s archives by default. To combine builds from several runs, the agent supplies an ordered list of workflow runs, from earliest selection to latest replacement. For each component and target, the verification command selects the successful build from the last listed run that produced one. A failed build does not replace an earlier successful build. The command examines only the supplied runs; the agent does not maintain a component-to-artefact map.

The command checks that every selected extension was built against the selected PostgreSQL archive. A missing component or PostgreSQL mismatch stops verification and reports what needs building. A successful build means that the build job produced its archive and build record; its verification checks still need to pass. The verification result records the resolved component-to-artefact map and archive checksums. GitHub artefact storage retains the archives while the agent completes the build within the artefact retention period.

After retry builds finish, the agent starts the verification job with the ordered list of runs. The job downloads the selected PostgreSQL and extension archives and repeats the installation combinations and checks below, including those that use a replacement extension as a prerequisite.

### Retry verification

When verification code needs correction, the agent runs the corrected checks against the existing archives. Each result records the build and verification revisions actually used, so a build completed through retries can include fixes from several Git revisions.

## Build commands and local iteration

### Build command interface

The Python 3 entry point [`build.py`](../build.py) provides the build commands used by agents and GitHub Actions jobs. Its argument definitions and help describe the available commands. Python handles argument parsing and shared orchestration logic; short shell scripts can implement project build recipes, and SQL files contain tests of installed extension functionality.

The agent uses this interface to start a GitHub Actions workflow run for the selected target. The workflow reads `support.json` to determine the PostgreSQL version, extension projects and source archives, then schedules the build and verification jobs as their prerequisites finish. The interface also supports starting workflow runs for selected builds or verification when completing retries.

Default selections come from `support.json`, including the extension set for the selected target. Explicit selections allow an agent to build one extension, choose existing PostgreSQL artefacts, or verify archives selected from an ordered list of workflow runs. Preparation, PostgreSQL compilation, extension compilation, packaging, installation assembly and verification are independently callable operations, so an agent can compose a custom sequence without writing orchestration code. Commands report the files they produce and their success or failure status.

GitHub Actions workflows schedule jobs and transfer artefacts. Build commands perform the work within each job and resolve the archive selections supplied for retries. The agent diagnoses failures and chooses which commands or workflows to run again.

### Local iteration

Agents develop recipes locally before porting them to GitHub Actions. The same build and verification commands run inside disposable macOS VMs or Linux Docker containers. The host computer controls the VM or container and transfers source files and build archives. Compilation, dependency installation and tests that execute compiled artefacts take place inside the VM or container. Host package managers and `sudo` are not used to work around build problems.

The local build VM or container retains installed toolchains, compiled files and packaged archives so an agent can rerun a failed command. A local source cache can retain downloads whose checksums match `support.json`. Local verification copies final archives into a separate clean test environment. Generated files stay outside Git, and unrelated local files, images, containers and VMs remain intact.

Lume supplies the macOS VM interface for command execution, file transfer, cloning, recovery and file retrieval through an API or CLI. Its evaluation and approval are tracked in [the milestones](../SPIKE2_MILESTONES.md).

Adding or updating a project includes the dependency and licence review in [dependency-licenses.md](dependency-licenses.md#dependency-review-during-development).

GitHub Actions workflows use scoped targets and reasonable job timeouts. Agents space status checks, download build archives and test results after jobs finish, and back off on secondary rate limits while continuing independent work.

### Source layout

`scripts/postgresql/` contains PostgreSQL build recipes, `scripts/extensions/<project>/` contains project recipes and probes, `scripts/platform/<os>/` provides environment setup and native dependency inspection, and `scripts/verify/` implements shared archive and runtime checks. Test fixtures and executable assertions define the concrete cases within the coverage below.

## Verification job details

The verification job runs on a fresh standard GitHub-hosted runner and installs no additional dependencies. It has no access to the build environment’s installed dependencies, source trees or staging directories. Build-related environment variables provided to the build runners are not provided to the verification runner.

The job uses the repository’s test scripts with tools already available on the runner. Tests target failures introduced by build settings, packaging and installation; their examples are small enough to isolate those failures.

Runtime tests run on the operating-system version supplied by the selected GitHub-hosted runner.

The job downloads the selected archives and build records once. It tests the following combinations in sequence:

- For each selected extension project, PostgreSQL plus that extension and its declared extension prerequisites. For example, TIGER Geocoder is tested with PostgreSQL and PostGIS. Unrelated extensions are absent so they cannot supply a missing dependency.
- PostgreSQL without any separately downloaded extensions. Its built-in extensions remain part of the PostgreSQL archive.
- PostgreSQL with every selected extension, to detect file, library and runtime conflicts between extensions.

For each combination, the job checks archive contents and overlapping paths, then extracts the archives into a fresh installation directory at a path different from the build location, including spaces to catch quoting errors. It inspects native dependencies and uses the extracted PostgreSQL tools to initialize a new database cluster and run the applicable PostgreSQL and extension tests. It then checks failure diagnostics. The PostgreSQL-only combination also receives the capability and built-in extension checks. The complete combination receives the coherent extension checks described below.

After testing a combination, the job stops its PostgreSQL processes and removes its installation and database directories before testing the next combination. A failed check is recorded with its logs, and testing continues with independent checks and combinations. An unsafe archive or conflicting files block extraction of the affected combination. The job reports failure if any required check fails or cannot run.

The job uploads a verification report and test logs as GitHub artefacts. The report identifies the selected archives by their originating runs and SHA-256 checksums, links them to their build records, and records the test-code revision, target and actual operating-system version. It lists the outcome of each check for each installation combination, including the reason for any check that did not run. This lets the agent locate failures and lets publication identify the exact archives that passed.

### Archive contents and extraction

These checks catch missing or misplaced files, unsafe extraction paths and conflicts between archives. Before extraction, the verifier confirms that it downloaded the selected archives and that their contents follow the installation layout in [distribution.md](distribution.md#download-units-and-installation). Representative checks include archive checksums, the `postgresql/` root directory, LICENCE file linking to LICENSES.md, executable permissions and the control files that make SQL extensions discoverable. Paths and links that escape the installation directory are rejected.

The verifier also checks overlapping paths before combining archives. Shared files are allowed when they meet the distribution’s overlap rules; incompatible copies fail the check. This catches cases where installing one extension would overwrite a library needed by another.

The test installer follows the documented extraction process without extra file copying, loader repairs or dependency installation. This checks that users can install the archives by following the same instructions.

### Static analysis of executables and libraries

Static analysis inspects every packaged executable and native library to find runtime dependencies outside the extracted installation. Only dependencies reliably supplied by the supported operating system are allowed outside it. This catches accidental use of libraries from the build machine or developer libraries preinstalled on the verification runner.

Examples of checks include:

- library references and search paths
- Target architecture
- Minimum OS version where supported
- Use only of allowed system libraries

### PostgreSQL lifecycle and schema operations

These checks establish that the packaged command-line tools work with the installed server and its bundled libraries. For each installation, the test harness uses packaged `initdb` to create a database cluster, `pg_ctl` to start and stop PostgreSQL, and `psql` to run SQL, all as an ordinary user.

In the PostgreSQL-only installation, the test creates a table containing a known row, dumps the database in custom format using packaged `pg_dump`, restores it into another database using packaged `pg_restore`, and checks the row.

### PostgreSQL capabilities and built-in extensions

These checks catch build options accidentally disabled and runtime libraries or support files omitted from the PostgreSQL archive. Each capability selected in [postgresql-options.md](postgresql-options.md) receives a small test that uses it. Examples include a TLS connection, an ICU collation, a compressed dump and restore, and an XML transformation. The cases exercise the selected dependencies with simple expected results.

The verifier compares the expected built-in extension names with those found in the archive, then creates each extension and runs a small operation that loads its packaged code or data. This detects missing installation files and modules that cannot load. The verified list supplies the built-in extension names published in `inventory.json`.

### Extension probes

A probe is a small test that confirms an extension’s packaged code and data can be used. Every supplied SQL extension name is created with its documented prerequisites and settings. The probe then performs a representative operation and checks the result, such as calculating a vector distance or running a scheduled SQL statement.

Some libraries and data files are located only when a feature is used. Recipes identify these dependencies, and the runtime tests exercise the features that load them. For example, a spatial operation can expose a missing coordinate-system data file that library inspection would not find.

The cases target plausible packaging failures: missing libraries, omitted data files, incorrect module paths or required configuration that has not been documented. Projects with several modules need cases that load each module. Background work has a bounded wait so a worker that fails to start produces a test failure. Tests use only the external data or services included in the documented package scope.

The implementation defines the operations and expected results. The same probes run with the extension installed individually and with the complete extension set. Changes to packaged modules or dependencies include review of whether the probes exercise them.

### Coherent extension behaviour

The complete-installation test checks that extensions which work separately can also work together. It starts PostgreSQL with their combined required settings, installs extensions in prerequisite order and runs all extension probes against that instance. Using the same database and backend session where supported exposes library and configuration conflicts that isolated tests can miss.

The server and loaded modules remain in place between probes. If an extension requires another database or session, the test records that requirement and runs its probe there. Conflicting settings, objects or libraries fail the test.

### Failure diagnostics

These checks establish that a failed packaged operation leaves enough information to investigate it. Tests cause a PostgreSQL error and a missing-library error in a disposable installation, then check that the captured output identifies the failed operation or library and the reason for failure.

The test harness also retains server logs and failing command output from ordinary test failures. This lets an agent investigate a failed verification job using its downloaded logs.

## Publication checks

### Public downloads

Automated publication checks confirm that download metadata identifies the archives that passed verification. Publication uploads those PostgreSQL and extension archives to GitHub Releases, checks that their download URLs are anonymously accessible, and then advertises them through `inventory.json`.

A final anonymous download of the public inventory and every referenced archive checks that users can retrieve the tested files and that their checksums match. Publication requires human authorization under the repository instructions.
