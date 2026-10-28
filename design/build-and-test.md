# Building and verifying the distribution

The build produces independently downloadable PostgreSQL and extension archives that users can extract into one installation. A target is an operating system and architecture selected in `support.json`. For each target, GitHub Actions builds PostgreSQL, builds the selected extension packages against it, and tests the archives individually and together. PostgreSQL and every selected extension are built afresh for a new release. An agent investigates failures and retries the affected work to complete the build.

## Build selection

`support.json` records exact PostgreSQL and extension releases, source URLs and checksums, selected targets, package grouping, supplied SQL names, build inputs, extension prerequisites and required PostgreSQL settings.

Each target records its minimum supported OS version. Build options and allowed system dependencies are chosen to support that version. On macOS, the deployment target is set at or below it. Required libraries and support data are packaged unless the selected OS version guarantees them. A capability that cannot meet these requirements is referred for human review before publication.

## Build and verification sequence on GitHub Actions

One GitHub Actions workflow defines the full build and verification sequence for a target. Its jobs run on standard GitHub-hosted runners. The sections below describe those jobs in dependency order.

Build jobs upload the PostgreSQL and extension archives as GitHub artefacts. The verification job downloads those artefacts and tests the archives. Each build job also uploads a build record containing its Git revision, selected sources and archive checksums. Extension build records identify the PostgreSQL archive used for compilation.

### PostgreSQL build job

Build scripts translate the capabilities in [postgresql-options.md](postgresql-options.md) into the options accepted by the selected PostgreSQL release. Optional capabilities are selected explicitly rather than enabled because a library happens to be installed on the runner.

The PostgreSQL job installs the required compiler and dependencies, downloads the PostgreSQL source archive recorded in `support.json`, verifies its checksum, and builds and packages PostgreSQL. It uploads the PostgreSQL archive and the development files needed to compile extensions, including headers, libraries and build tools. The development files need not be included in the PostgreSQL archive downloaded by users.

### Extension build jobs

After the PostgreSQL job uploads its artefacts, the workflow starts one build job per selected [extension package](distribution.md). These jobs run independently in parallel. Each job downloads the PostgreSQL archive and development files, installs the compiler and dependencies required by that package, and downloads its selected sources and verifies their checksums.

Each extension job builds the SQL extensions belonging to its package against the downloaded PostgreSQL build. It collects their installation files and required runtime dependencies in a staging directory, packages them into an extension archive, and uploads the archive and build record as GitHub artefacts.

Build recipes specify their dependencies, toolchain versions and enabled features. Inline checks confirm that the compiled files exist, control files name the intended SQL extensions, and staging directories contain the required runtime files. Recipes can run inexpensive smoke tests to help diagnose build failures.

### Verification job

Once the PostgreSQL and all selected extension archives are available, one verification job downloads them onto a fresh standard GitHub-hosted runner. It installs no additional dependencies. The job tests PostgreSQL with each extension package separately, PostgreSQL alone, and PostgreSQL with all selected packages, using a fresh installation and database for each combination. [Verification job details](#verification-job-details) describes the environment, test sequence and checks.

## Failures and retries

### Continue independent work

A failed job does not cancel independent jobs or remove a component or target from `support.json`. The workflow reports which jobs passed, failed or could not run because a required archive or test result was unavailable. The agent uses the GitHub CLI or API to inspect failed jobs and retrieve their logs.

A source checksum mismatch stops the affected build. The agent investigates the source selection and download before changing a recorded checksum.

### Retry a PostgreSQL build

If PostgreSQL needs rebuilding, for example to change a build setting, the agent starts a fresh workflow run that rebuilds PostgreSQL and every selected extension. Previous runs are excluded from the new build’s archive selection.

### Retry an extension build

For a retry, the agent starts a workflow run that builds only the selected extension package, using the selected script revision and PostgreSQL artefacts from a specified previous workflow run. The agent can therefore fix a package recipe and build that package again while keeping the successful PostgreSQL and other extension archives. The new job runs on a new GitHub-hosted runner, installs its compiler and dependencies, downloads the existing PostgreSQL archive and development files, and uploads the replacement extension archive.

Verification uses the current run’s archives by default. To combine builds from several runs, the agent supplies an ordered list of workflow runs, from earliest selection to latest replacement. For each component and target, the verification command selects the successful build from the last listed run that produced one. A failed build does not replace an earlier successful build. The command examines only the supplied runs; the agent does not maintain a component-to-artefact map.

The command checks that every selected extension was built against the selected PostgreSQL archive. A missing component or PostgreSQL mismatch stops verification and reports what needs building. A successful build means that the build job produced its archive and build record; its verification checks still need to pass. The verification result records the resolved component-to-artefact map and archive checksums. GitHub artefact storage retains the archives while the agent completes the build within the artefact retention period.

After retry builds finish, the agent starts the verification job with the ordered list of runs. The job downloads the selected PostgreSQL and extension archives and repeats the installation combinations and checks below, including those that use a replacement extension as a prerequisite.

### Retry verification

When verification code needs correction, the agent runs the corrected checks against the existing archives. Each result records the build and verification revisions actually used, so a build completed through retries can include fixes from several Git revisions.

## Build commands and local iteration

### Build command interface

The Python 3 entry point [`build.py`](../build.py) provides the build commands used by agents and GitHub Actions jobs. Its argument definitions and help describe the available commands. Python handles argument parsing and shared orchestration logic; short shell scripts can implement project build recipes, and SQL files contain tests of installed extension functionality.

The agent uses this interface to start a GitHub Actions workflow run for the selected target. The workflow reads `support.json` to determine the PostgreSQL version, extension packages and source archives, then schedules the build and verification jobs as their prerequisites finish. The interface also supports starting workflow runs for selected builds or verification when completing retries.

Default selections come from `support.json`, including the extension set for the selected target. Explicit selections allow an agent to build one extension package, choose existing PostgreSQL artefacts, or verify archives selected from an ordered list of workflow runs. Preparation, PostgreSQL compilation, extension compilation, packaging, installation assembly and verification are independently callable operations, so an agent can compose a custom sequence without writing orchestration code. Commands report the files they produce and their success or failure status.

GitHub Actions workflows schedule jobs and transfer artefacts. Build commands perform the work within each job and resolve the archive selections supplied for retries. The agent diagnoses failures and chooses which commands or workflows to run again.

### Local iteration

Agents develop recipes locally before porting them to GitHub Actions. The same build and verification commands run inside disposable macOS VMs, Linux Docker containers or Linux VMs. The host computer controls the VM or container and transfers source files and build archives. Compilation, dependency installation and tests that execute compiled artefacts take place inside the VM or container. Host package managers and `sudo` are not used to work around build problems.

The local build VM or container retains installed toolchains, compiled files and packaged archives so an agent can rerun a failed command. A local source cache can retain downloads whose checksums match `support.json`. Local verification copies final archives into a separate clean test environment. Generated files stay outside Git, and unrelated local files, images, containers and VMs remain intact.

Lume supplies the macOS VM interface. Its CLI starts a headless VM, and SSH executes commands and transfers source and build archives. A stopped VM can be cloned to preserve a build state or recover from a failed iteration.

Adding or updating a project includes the dependency and licence review in [dependency-licenses.md](dependency-licenses.md#dependency-review-during-development).

GitHub Actions workflows use scoped targets and reasonable job timeouts. Agents space status checks, download build archives and test results after jobs finish, and back off on secondary rate limits while continuing independent work.

## Verification job details

Test fixtures and executable assertions define the concrete cases within the coverage below.

The verification job runs on a fresh standard GitHub-hosted runner and installs no additional dependencies. It has no access to the build environment’s installed dependencies, source trees or staging directories. Build-related environment variables provided to the build runners are not provided to the verification runner.

The job uses the repository’s test scripts with tools already available on the runner. Runtime tests consume the inventory’s `config` fields using the [client protocol](distribution.md#postgresql-startup-configuration), including package data paths, startup settings and SQL extension creation. They do not hard-code those requirements in individual probes. Tests target failures introduced by build settings, packaging and installation; their examples are small enough to isolate those failures.

Runtime tests run on the operating-system version supplied by the selected GitHub-hosted runner.

The job downloads the selected archives and build records once. It tests the following combinations in sequence:

- For each selected extension package, PostgreSQL plus that package alone. The tests create and exercise every SQL extension supplied by the package, including its prerequisites. This checks that package grouping includes all required SQL extensions beyond PostgreSQL’s built-ins.
- PostgreSQL without any separately downloaded extensions. Its built-in extensions remain part of the PostgreSQL archive.
- PostgreSQL with every selected extension, to detect file, library and runtime conflicts between extensions.

For each combination, the job checks archive contents and overlapping paths, then extracts the archives into a fresh installation directory at a path different from the build location, including spaces to catch quoting errors. It inspects native dependencies and uses the extracted PostgreSQL tools to initialize a new database cluster and run the applicable PostgreSQL and extension tests. It then checks failure diagnostics. The PostgreSQL-only combination also receives the capability and built-in extension checks. The complete combination receives the coherent extension checks described below.

After testing a combination, the job stops its PostgreSQL processes and removes its installation and database directories before testing the next combination. A failed check is recorded with its logs, and testing continues with independent checks and combinations. An unsafe archive or conflicting files block extraction of the affected combination. The job reports failure if any required check fails or cannot run.

The job uploads a verification report and test logs as GitHub artefacts. The report identifies the selected archives by their originating runs and SHA-256 checksums, links them to their build records, and records the test-code revision, target and actual operating-system version. It lists the outcome of each check for each installation combination, including the reason for any check that did not run. This lets the agent locate failures and lets publication identify the exact archives that passed.

### Inventory configuration

For each target, the verifier checks that the `config` fields of all advertised SQL extensions and their packages can be combined without conflicting values. It compares environment-variable paths by name and combines preload lists as a set. A conflict fails verification so clients can combine any advertised extension selection without resolving configuration conflicts themselves.

### Archive contents and extraction

These checks catch missing or misplaced files, unsafe extraction paths and conflicts between archives. Before extraction, the verifier confirms that it downloaded the selected archives and that their contents follow the installation layout in [distribution.md](distribution.md#archive-format-and-installation). Representative checks include archive checksums, the `postgresql/` root directory, LICENCE file linking to LICENSES.md, executable permissions and the control files that make SQL extensions discoverable. Paths and links that escape the installation directory are rejected.

The verifier also checks overlapping paths before combining archives. Shared files are allowed when they meet the distribution’s overlap rules; incompatible copies fail the check. This catches cases where installing one extension would overwrite a library needed by another.

The test installer performs only the extraction defined in [distribution.md](distribution.md#archive-format-and-installation). It executes no package code, hooks or SQL and makes no configuration changes. The runtime tests subsequently create databases, start PostgreSQL and exercise SQL extensions as described below.

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

The expected built-in extension names are determined from the selected PostgreSQL source and enabled capabilities, independently of the packaged output. The verifier compares those names with the control files found in the archive, then creates each extension and runs a small operation that loads its packaged code or data. This detects missing installation files and modules that cannot load. The names found in the archive are recorded with the build result and mapped to the PostgreSQL package in `inventory.json`.

### Extension probes

A probe is a small test that confirms an extension’s packaged code and data can be used. Every supplied SQL extension name is created through the inventory’s configuration contract. The probe then performs a representative operation and checks the result, such as calculating a vector distance.

Some libraries and data files are located only when a feature is used. Recipes identify these dependencies, and the runtime tests exercise the features that load them. For example, a spatial operation can expose a missing coordinate-system data file that library inspection would not find.

The cases target plausible packaging failures: missing libraries, omitted data files, incorrect module paths or required configuration that has not been documented. Packages with several modules need cases that load each module. Background work has a bounded wait so a worker that fails to start produces a test failure. Tests use only the external data or services included in the documented package scope.

The implementation defines the operations and expected results. The same probes run with the extension’s package installed alone alongside PostgreSQL and with the complete extension set. Changes to packaged modules or dependencies include review of whether the probes exercise them.

### Coherent extension behaviour

The complete-installation test checks that extensions which work separately can also work together. It combines the `config` fields for all available SQL extensions and their packages, starts PostgreSQL with those requirements, creates the extensions through the same client protocol and runs all extension probes against that instance. Using the same database and backend session where supported exposes library and configuration conflicts that isolated tests can miss.

The server and loaded modules remain in place between probes. If an extension requires another database or session, the test records that requirement and runs its probe there. Conflicting settings, objects or libraries fail the test.

### Failure diagnostics

These checks establish that a failed packaged operation leaves enough information to investigate it. Tests cause a PostgreSQL error and a missing-library error in a disposable installation, then check that the captured output identifies the failed operation or library and the reason for failure.

The test harness also retains server logs and failing command output from ordinary test failures. This lets an agent investigate a failed verification job using its downloaded logs.

## Publication checks

### Public downloads

Publication copies the minimum supported OS versions from the build selection into the inventory’s `os_support` field.

Automated publication checks confirm that download metadata identifies the archives that passed verification and that SQL extension names map to the packages that supplied them on each target. Publication uploads those PostgreSQL and extension archives to GitHub Releases, checks that their download URLs are anonymously accessible, and then advertises them through `inventory.json`.

A final anonymous download of the public inventory and every referenced archive checks that users can retrieve the tested files and that their checksums match. Publication requires human authorization under the repository instructions.
