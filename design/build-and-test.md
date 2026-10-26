# Building and verifying the Mac ARM64 slice

The first build produces separately installable PostgreSQL and pgvector archives from one selected set of source inputs. Agents develop inside a disposable macOS ARM64 VM managed by Lume. The VM contains the tools needed to build PostgreSQL and the selected extensions; the host only controls the VM and exchanges source and output files with it.

## Build commands

Preparation, PostgreSQL build, each extension build and archive verification are separate commands. An agent can rerun the command for one failed extension without reinstalling the toolchain or rebuilding PostgreSQL. Commands read the same selected source identities and explicit PostgreSQL archive path. They do not select an older release artifact as a build input.

PostgreSQL builds first. The pgvector command uses the development files from that exact PostgreSQL build. Each command stages only the files owned by its archive, records its target and input checksums, and writes its archive to an ignored output directory. Finished archives remain available while their tests run, including when a verifier needs a correction.

## Final-archive verification

A clean verifier VM receives the final archives, without the builder's installed dependencies. The verifier checks archive checksums and metadata, copies the extension payload into a PostgreSQL prefix using the documented installation procedure, and rejects path collisions. It checks Mach-O architectures, loader paths, linked libraries and references to build paths. Runtime libraries resolve from the assembled installation or from supported macOS system components.

As an ordinary user, the verifier initializes a UTF-8 database, starts and stops PostgreSQL, connects with packaged `psql`, exercises representative schema DDL and pgvector operations, and checks the results. It exercises `pg_dump` and `pg_restore`. It then moves the installation, makes the old location unavailable and repeats representative operations.

The same verifier assembles every selected extension archive into one installation. When the selected set grows, it checks prerequisites, file collisions, shared-library closure and representative operations for each extension against one PostgreSQL instance. It loads extensions in one backend session where their configuration permits, exposing conflicts hidden by separate sessions.

Verification records identify final archive SHA-256 values, PostgreSQL and extension versions, verifier revision, VM operating-system version, checks run and outcomes. A failed or skipped check remains visible. Static checks and executed operations support the stated compatibility claim; a successful build alone does not.

## Local iteration and GitHub builds

Lume exposes VM creation, cloning, command execution and file transfer to the agent. The builder and verifier are separate VM instances or clones of different prepared bases. Build scripts accept explicit paths and selected targets so the same commands can later run on GitHub's native Mac ARM64 runner. The GitHub process builds a fresh PostgreSQL archive, passes that run's archive to independent extension jobs and verifies their final archives in a fresh environment. GitHub workflow details are defined when that milestone begins.
