# Local build iteration

This document records the working development process, commands and measurements for package builds. Agents maintain it as the tooling changes. Product requirements and release verification remain in [build-and-test.md](../design/build-and-test.md).

Compilation, dependency installation and execution of built software happen inside a development VM or container. The Mac host manages environments and transfers source files and archives. Final archive verification uses a separate clean environment.

## Target environments

The environment comparison is in progress. The established routes are:

- Linux ARM64: the retained Docker development container runs ARM binaries directly.
- Linux x86_64: an amd64 Docker container runs through Rosetta inside Docker Desktop's ARM Linux VM. Both builds and final-archive verification have passed through this route.
- macOS ARM64: Lume development and clean verification VMs have passed the complete package set.
- macOS x86_64: native GitHub Intel runners have passed the complete package set. The local Rosetta trial awaits permission for Lume CLI/SSH access and acceptance of Apple's Rosetta licence.
- Windows x86_64: VMware Fusion runs a Windows 11 ARM guest headlessly. PostgreSQL and all nine extension packages have built locally and passed runtime checks. Dependency caching is proved for Address Standardizer, pg_jsonschema and PostGIS; preparing the final reusable agent template remains in progress.

The current work uses Docker for Linux, Lume for Mac and Fusion for Windows. The comparison includes startup, source transfer, dependency preparation, compilation, packaging and verification, rather than compiler speed alone. Parallels trials were blocked before guest startup; their results do not establish its build performance.

## Comparing the routes

Each plausible route receives an actual setup and build attempt. The comparison covers Parallels Linux and macOS guests as well as Windows, the existing Docker and Lume environments, local x86 translation or emulation, and hosted GitHub iteration. A documented limitation guides the experiment; it is not a substitute for trying a route when the required tools are available. A route that cannot be tried has its concrete blocker recorded.

For each route, the experiment record includes host and guest versions, CPU/RAM allocation, setup time, manual steps, failures and recovery work. Comparable workloads record cold and repeat build time, verification and transfer time, and which caches were warm. Representative workloads include a small native extension and a dependency-heavy package. Repeated timings are reported individually or with their range; parallel activity and network downloads are identified so they are not mistaken for compiler performance.

The recommendation distinguishes routes that were tested successfully, tested with poor results, blocked before a useful trial, and not yet attempted. Qualitative evidence about reliability and agent effort accompanies timings. Retaining Docker or Lume alongside Parallels requires evidence of a useful advantage, rather than familiarity alone.

A headless Ubuntu ARM64 cloud-image trial under Lume passed native and Rosetta-translated extension builds, clean SQL verification and cache reuse after restart. Its measured x86 build times were close to Docker Desktop's. Docker Desktop remains the Linux route: Lume offers a viable way to consolidate VM management, but its setup required more troubleshooting and demonstrated no clear build-speed advantage.

UTM 4.7.5 is also installed, with metadata for an ARM64 Windows guest allocated 8 GiB RAM. Its CLI help worked, but version and inventory queries returned `OSStatus error -1712`; both exited with status zero despite the errors. Guest control and build performance could not be tested. No UTM desktop control or VM changes were attempted. Standalone QEMU system executables were absent from `PATH`.

## Development loop

Agents develop and debug build scripts locally before running GitHub builds for that target. If the local environment is unavailable or blocked, dependent work stops and the blocker is reported. Using GitHub as a substitute development environment requires explicit human approval.

A local iteration produces an archive and resolves build failures quickly; inexpensive smoke checks can help diagnose a failure. GitHub jobs validate builds already demonstrated locally, using the same package build commands after preparing their runner environments.

A development environment retains its installed tools and files across stops and starts. Agents may install tools and libraries as needed. Separate workspaces isolate build files; changes to system dependencies in a shared VM or container still require coordination. Another environment is appropriate when concurrent work needs incompatible system changes. The measured environment comparison will determine the default allocation and concurrency limits.

Adding or updating a package includes the [dependency and licence review](../design/dependency-licenses.md#dependency-review-during-development).

### Docker commands

From the host repository, a Linux package build uses the development archive for its target:

```sh
bash platforms/linux/build-extension-local.sh \
  address_standardizer /path/to/postgresql-development.tar.gz \
  out/local-iteration/build-output linux-x86_64 agent-1-linux-x86
```

The helper creates or starts the named retained container, caches the supplied development archive by checksum and builds in `/work/local-iteration/<target>/<package>/workspace`. Different container names give agents separate writable environments. The repository is mounted read-only, so host edits become visible without a source-transfer step. `linux-arm64` selects the native ARM route.

Clean verification runs separately:

```sh
bash verification/linux/run-local.sh --target linux-x86_64 \
  /path/to/postgresql.tar.gz out/local-iteration/verification \
  address_standardizer=/path/to/address_standardizer.tar.gz
```

The verifier creates and removes a disposable container; the development container and its workspace remain available. Named development containers retain their installed tools across `docker stop` and `docker start`. New containers keep `/work` in the ignored repository directory `out/local-environments/<container-name>/`; `PG_BINARIES_LINUX_WORK` can select another host location at creation. Existing containers retain their original mounts, reported by `docker inspect`. Older development containers use host temporary directories; deleting those directories loses their build caches.

### Lume commands

The measured Mac setup uses `spike2-macos-arm64-build` for compilation and `spike2-macos-arm64-clean` for verification. Both guests have four vCPUs and 8 GiB RAM. Lume 0.6.1 provides headless lifecycle and address discovery:

```sh
lume run --no-display --detach spike2-macos-arm64-build
lume get spike2-macos-arm64-build --format json
```

Guest access uses SSH as user `lume`, with the project key `~/.ssh/pg_binaries_lume_id_ed25519` and host fingerprints in `~/.ssh/pg_binaries_lume_known_hosts`. Both files have owner-only permissions and are stored outside temporary directories. Authentication with these files has been checked against the retained build VM. Guest IP addresses can change and come from `lume get`.

Source transfers go into a guest-local checkout; compilation runs against the guest filesystem. The measurements used `~/local-iteration-src`, with workspaces kept separately for each package. Editing a host build script therefore requires transferring that file before invoking the shared `build.py` command over SSH. The clean VM receives the verifier source and final archives, without the development toolchain or dependency prefixes.

The clean guest can be shut down through its enabled SSH service with `sudo shutdown -h now`; `lume get` confirms that it has stopped. During this trial, Lume's own shutdown helper could not use guest SSH even though direct SSH worked. Preserve a working access key and address-discovery command rather than relying on an untested guest-control helper.

Two measured starts reached SSH readiness in 9.74 and 10.39 seconds. A 54,071,920-byte PostgreSQL development archive transferred from host to guest in 0.264 seconds with matching SHA-256; the host file was already warm in the filesystem cache. Graceful shutdown took 11.23 seconds from supplying the sudo credential to confirmed stopped state. These are retained-VM timings, excluding initial macOS installation and guest setup.

Lume and Parallels both document a limit of two concurrent macOS guests on Apple Silicon. Budget two across both products: a separate allowance for each has not been demonstrated. Two Lume guests have run together; a mixed-product trial has not run. This makes a shared development VM with separate workspaces more practical than one Mac VM per agent while retaining a clean verification VM. The limit does not apply to Linux or Windows guests. [Lume](https://cua.ai/docs/lume), [Parallels](https://kb.parallels.com/en/128867).

### Lume Linux alternative

The trial guest `pg-binaries-lume-linux-arm64-trial` uses four vCPUs, 8 GiB RAM and a 32 GiB sparse disk. Ubuntu's cloud image and a NoCloud seed provided unattended SSH setup. Installing Docker took about 72 seconds. Building the ARM development image took 329 seconds; the successful x86 image build took 148 seconds after installing Buildx and enabling `DOCKER_BUILDKIT=1`. These are preparation costs, separate from extension timings.

Address Standardizer took 7.39 seconds initially and 2.18 on repeat for ARM, and 53.09 and 7.23 seconds through x86 Rosetta. An x86 repeat after a guest restart took 7.13 seconds with the same PCRE2 checksum. PostGIS took 182.33 seconds initially and 72.57 on repeat, with its source downloads measured separately at 15.65 seconds and system geospatial libraries already installed. All three target/package combinations passed clean runtime and SQL verification. These are individual trials on the same host with different guest allocations and cache conditions, rather than a controlled performance comparison.

Two setup failures required recovery. Docker's legacy builder labelled the x86 image ARM64; installing Ubuntu's Buildx package resolved this. A Lume restart left two processes using the same VM identity and network address, making SSH reach the wrong disk. Recovery identified the processes by their actual backing disks, stopped the original-disk process and confirmed its exit. A later stop/restart verified process exit, the intended disk, SSH access and retained caches. During the duplicate-process failure, `lume get` incorrectly reported the running guest as stopped.

The trial guest is now stopped with its disk and caches retained. Guest shutdown through `sudo -n /sbin/shutdown -h now` took 4.31 seconds to confirmed exit of both VM processes. SSH returned 255 as the connection closed; checking the processes established that shutdown succeeded.

The retained trial starts from the host repository with:

```sh
lume run pg-binaries-lume-linux-arm64-trial \
  --storage "$PWD/out/local-environments/pg-binaries-lume-linux-arm64-trial" \
  --disk-path "$PWD/out/local-iteration/lume-linux/ubuntu-arm64-32g.raw" \
  --display none --vnc disabled --detach
```

SSH uses account `ubuntu`, the existing project key and `out/local-environments/pg-binaries-lume-linux-arm64-trial/known_hosts`. The copied host fingerprint and key were checked after the trial. The observed address was `192.168.64.11`; rediscover it after restart. The guest runs the same Linux helpers with `PG_BINARIES_LINUX_WORK=/home/ubuntu/pg-work`, keeping outputs in `/home/ubuntu/pg-output`. Docker access must preserve the normal user ID when invoking the clean verifier; running that helper as root makes its container-user creation fail. Trial commands, failures and cache evidence are in `out/local-iteration/lume-linux/trial.md`.

### Windows commands

#### Fusion local setup

VMware Fusion 26.0.1 is installed. Its Windows ARM VM is at `/Users/berniesumption/Documents/local-dev/vmware-vms/Windows 11 64-bit Arm.vmwarevm/Windows 11 64-bit Arm.vmx`. The user chose `password` as this development VM's TPM/encryption password. Its local Windows account is `Bernie Sumption`, also with password `password`.

The installation ISO is `/Users/berniesumption/Virtual Machines.localized/VMWIsoImages/Windows11_26100.4349_Professional_en-gb_arm64.iso`. The human installed Windows and VMware Tools through their normal installers. The VM currently has two CPUs and 4 GiB RAM. After restart, authenticated `vmrun` commands, PowerShell execution and file transfer in both directions passed. The account belongs to the Administrators group, but commands launched through `vmrun` have a non-elevated token; administrator approval is needed for the initial Visual Studio installation.

Python 3.13.3 x64 installed per user at `C:/pg-binaries-tools/python` without elevation. Its PE machine value is `0x8664` and `sysconfig.get_platform()` returns `win-amd64`; `platform.machine()` still reports the guest's ARM64 architecture.

The Python download took 7.45 seconds, installation 17.42 seconds, and installation of the pinned Meson, Ninja, CMake and pkgconf packages 19.45 seconds. A 3,998-byte script transferred into the guest in 0.468 seconds; result and log transfers back took 0.407 and 0.457 seconds. These prove basic command access and x64 execution, not extension-build performance.

The cached x64 PostgreSQL runtime and development archives transferred through `vmrun` in 16.74 seconds for 29,494,388 bytes and 42.72 seconds for 77,227,675 bytes, with matching SHA-256 checksums. Keep those inputs at `C:/pg-inputs` rather than copying them on each edit. A local diagnostic confirmed AMD64 PE binaries, created a database, started PostgreSQL, executed SQL and shut it down. Database creation took 2.92 seconds, startup 0.61 seconds and the SQL query 0.51 seconds. This was a translation smoke check, not the complete archive verifier.

The source at `C:/pg-src` started from revision `ca032de8`; subsequent build and verifier edits were transferred individually. All 20 unique selected source archives were checksum-verified in 65.37 seconds. They are retained at the helper's default `C:/pg-binaries-tools/sources`. New host edits require transferring the changed files into the guest checkout before running the build.

Visual Studio 2022 Build Tools is the command-line toolchain, without the Visual Studio editor. Setup explicitly selects `Microsoft.VisualStudio.Component.VC.Tools.x86.x64`, `Microsoft.VisualStudio.Component.Windows11SDK.26100` and `Microsoft.VisualStudio.Component.VC.Llvm.Clang` with `Microsoft.VisualStudio.Workload.VCTools`. The first interactive installation completed with the workload and Clang but omitted the compiler and SDK headers/libraries; selecting the workload alone did not provide a usable build environment. The normal installer requires administrator approval; no UAC or security-policy changes are part of this process.

The Windows desktop shortcut **Set up C++ build tools** opens the installed Visual Studio Installer in modify mode, explicitly adding the x64 compiler and Windows 11 SDK. The component list is also retained in `C:/pg-binaries-tools/bootstrap/build-tools.vsconfig`. The human completed that installation. A standalone check found the compiler, linker, librarian, NMake, dumpbin, resource compiler and manifest tool, then compiled, linked and ran an AMD64 executable using the ARM64-hosted compiler. Interactive launches omit `--norestart`, which requires quiet or passive mode.

Git installed successfully through its normal ARM installer at `C:/Users/Public/Git-2.56.0.4-arm64.exe`; the executable is `C:/Program Files/Git/cmd/git.exe`. The earlier unattended attempts failed before installation, with the cause unconfirmed. The interactive choices were bundled OpenSSH, Windows Secure Channel for HTTPS, no automatic line-ending conversion, MinTTY, Git Credential Manager and file-system caching. The repository's `.gitattributes` controls line endings.

The shared environment selects the native compiler host from Windows's reported CPU architecture, while always targeting x64. Process environment variables and .NET's architecture property can report x64 under translation. They previously made a Python-launched build select different Visual Studio paths from a directly launched build, changing the cache key. The environment now also normalises Visual Studio's MSBuild host path; both launch routes produce identical cache inputs.

One four-CPU, 8 GiB comparison built Address Standardizer in 31.53 seconds with native ARM64-hosted MSVC and 38.50 seconds with translated x64-hosted MSVC. Repeats took 14.59 and 15.29 seconds. Each retained its own PCRE2 library and key. This single pair favours using the native compiler host but does not establish a general speed ratio. Older workspaces built with the other compiler host invalidate once when switching.

Fusion's `vmrun` and `vmcli` commands are on the Mac host's `PATH`. Computer-use permissions are recorded in [AGENTS.md](../AGENTS.md#repository-operations). After restarting Codex, computer use could read Fusion's window and capture the Windows desktop. Its first connection and screenshot calls took several minutes; later screenshots returned in about 1.5 seconds. Prefer CLI commands for repeatable builds. Administrator approval remains a human step.

Fusion commands on this host require `exec_command` with `sandbox_permissions="require_escalated"`. A restricted call can report the generic error `vmrun was unable to start`; confirm access through the normal approval mechanism before diagnosing the Fusion service or restarting it.

#### Preserve the Windows baseline

Before package builds or dependency installation, shut Windows down cleanly, copy the complete VM bundle and create a named snapshot. The established baseline is `toolchain-ready-2026-10-31`. Its separate backup is `/Users/berniesumption/Documents/local-dev/vmware-vms/Windows 11 toolchain-ready backup.vmwarevm`; keep that copy powered off.

The measured shutdown took 9.11 seconds. An APFS copy-on-write copy of the 37.47 GB logical bundle took 0.04 seconds; its file lists and sizes matched, and VM configuration and NVRAM hashes matched. Snapshot creation took 0.30 seconds and Fusion listed the new snapshot. The copy shares physical disk blocks until either copy changes, and resides on the same disk; it protects the baseline from development changes, not disk loss.

Normal iterations retain package workspaces and caches. Snapshots are checkpoints before substantial environment changes, not a reset between builds. Before reverting, copy source changes, results and logs back to the host.

#### Create another agent VM

The reusable toolchain template is `/Users/berniesumption/Documents/local-dev/vmware-vms/Windows 11 toolchain template/baseline.vmtx`. It contains the baseline tools and source downloads; it predates the later Rust and PostGIS installations. Creating it from a stopped, disposable baseline copy with `vmcli VMTemplate Create -p TEMPLATE.vmtx -n NAME SOURCE.vmx` took 22.32 seconds. The command reads the existing encryption password from standard input.

An agent gets an independent VM by copying the complete template directory to a new destination and deploying its `.vmtx` file. The destination must not already exist:

```sh
windows_template='/Users/berniesumption/Documents/local-dev/vmware-vms/Windows 11 toolchain template'
windows_agent='/Users/berniesumption/Documents/local-dev/vmware-vms/Windows 11 agent-2.vmwarevm'
cp -cRp "$windows_template" "$windows_agent"
printf '%s\n' password | vmcli VMTemplate Deploy -p "$windows_agent/baseline.vmtx"
windows_vmx="$windows_agent/baseline.vmx"
```

The measured APFS copy took 0.006 seconds and deployment 0.016 seconds. First startup generated distinct VM identifiers and a distinct MAC address. The deployed VM compiled and ran an x64 executable, accepted authenticated guest commands and fetched an HTTPS page with normal certificate checks while the development VM remained running. The older `vmrun clone ... full` failed on this encrypted VM, so the tested route uses `vmcli` templates.

Headless startup from an agent command uses a separate process session and file output. Otherwise the command runner can stop the VM engine when its process group is cleaned up. This host command starts a deployed VM without opening its console:

```sh
python3 - "$windows_vmx" <<'PY'
import subprocess, sys
with open('/private/tmp/pg-binaries-vm-start.log', 'ab') as log:
    launcher = subprocess.Popen(
        ['vmrun', '-T', 'fusion', '-vp', 'password', 'start', sys.argv[1], 'nogui'],
        start_new_session=True, stdin=subprocess.DEVNULL,
        stdout=log, stderr=subprocess.STDOUT)
    launcher.wait(timeout=30)
PY
```

The detached launch returned in 0.63–0.79 seconds; the first trial reached working VMware Tools after about 14 seconds. Confirm readiness with an authenticated guest command: `checkToolsState` sometimes returned `installed` even when commands worked. Copy current repository changes into `C:/pg-src` before building. `vmrun -T fusion -vp password stop VMX soft` shuts down through VMware Tools; measured trial shutdowns took about six seconds. The preserved baseline backup's configuration and NVRAM hashes still match.

A newly deployed agent VM received a 258 KB source archive in 0.13 seconds and built HypoPG without installing additional tools. Its first build took 27.35 seconds and its repeat 17.79 seconds; runtime verification passed. The template therefore provides a working starting point, though dependency-heavy packages still need their additional tools and caches.

A second template at `/Users/berniesumption/Documents/local-dev/vmware-vms/Windows 11 prepared template/prepared.vmtx` contains the installed Rust/MSYS2 tools and extension workspaces. Preserving it required a 6.97-second shutdown, a 0.046-second APFS copy and 35.25 seconds to create the template. Its first cache-reuse experiment exposed inconsistent MSVC host selection between direct PowerShell launches and launches through x64 Python. The shared environment now produces matching cache inputs, and an Address Standardizer build retained PCRE2 when switching launch routes. Older translated-host workspaces still need a one-time migration to the native compiler host; PostGIS is undergoing that migration before a replacement template is prepared.

Two small builds in separate workspaces within the existing two-CPU, 4 GiB VM took 29.76 seconds serially and 20.47 seconds concurrently, with unchanged cache keys. Each concurrent build took longer individually. These are one isolated pair, not a general concurrency limit; available-memory measurements were before/after samples rather than peaks. Throughput across separate VMs remains unmeasured.

#### Build and verification commands

The host checkout is the source of truth. An idle, newly deployed agent VM receives the committed source before building; its workspaces and caches stay outside `C:/pg-src`:

```sh
git archive --format=tar -o /private/tmp/pg-binaries-source.tar HEAD
vmrun -T fusion -vp password -gu 'Bernie Sumption' -gp password \
  copyFileFromHostToGuest "$windows_vmx" \
  /private/tmp/pg-binaries-source.tar 'C:\Users\Public\pg-binaries-source.tar'
vmrun -T fusion -vp password -gu 'Bernie Sumption' -gp password \
  runProgramInGuest "$windows_vmx" \
  'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' \
  -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command \
  '$ErrorActionPreference="Stop"; if(Test-Path C:/pg-src){Remove-Item -Recurse -Force C:/pg-src}; & C:/pg-binaries-tools/python/python.exe -m tarfile -e C:/Users/Public/pg-binaries-source.tar C:/pg-src; exit $LASTEXITCODE'
```

During iteration, an edited build script can be transferred before the next build without committing it:

```sh
vmrun -T fusion -vp password -gu 'Bernie Sumption' -gp password \
  copyFileFromHostToGuest "$windows_vmx" \
  "$PWD/packages/pgvector/build.ps1" 'C:\pg-src\packages\pgvector\build.ps1'
```

The committed-source refresh replaces the guest checkout, including deleted files. Guest-only edits are copied back first. The selected `windows_vmx` remains the deployed agent VM for transfers and builds:

```sh
vmrun -T fusion -vp password -gu 'Bernie Sumption' -gp password \
  runProgramInGuest "$windows_vmx" \
  'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' \
  -NoProfile -NonInteractive -ExecutionPolicy Bypass \
  -File 'C:\pg-src\platforms\windows\build-extension-local.ps1' \
  -Package pgvector \
  -DevelopmentArchive 'C:\pg-inputs\postgresql-development-18.6-windows-x86_64.tar.gz' \
  -Workspace 'C:\pg-work\pgvector' -OutputDirectory 'C:\pg-output\pgvector' \
  -LogPath 'C:\pg-work\logs\pgvector.log'
```

`copyFileFromHostToGuest VMX HOST_FILE GUEST_FILE` and `copyFileFromGuestToHost VMX GUEST_FILE HOST_FILE` use the same authentication options. VMware file-transfer commands require backslashes in guest paths. A diagnostic guest script writes logs and JSON to known files, then the host copies them back; `runProgramInGuest` returns the exit status rather than streaming program output.

Both local build helpers accept an optional `-LogPath`. It records build output, including native stderr, in a guest file that can be copied back while a build runs or after it finishes. Reusing a log path replaces the previous log. VMware's command exit status still reports failure; writing a log does not suppress it.

The prepared PostGIS workspace was built with `MAKEFLAGS=-j2`. Its short-lived guest PowerShell process uses the same setting on repeat; other packages use their own fresh process so GNU Make flags do not reach NMake:

```powershell
$env:MAKEFLAGS = '-j2'
$env:PG_BUILD_JOBS = '2'
& C:/pg-src/platforms/windows/build-extension-local.ps1 `
  -Package postgis -DevelopmentArchive C:/pg-inputs/postgresql-development-18.6-windows-x86_64.tar.gz `
  -Workspace C:/pg-work/postgis -OutputDirectory C:/pg-output/postgis `
  -LogPath C:/pg-work/logs/postgis.log
```

`PG_BUILD_JOBS` controls PostGIS parallelism. Two workers completed the original dependency build in a 4 GiB guest; four workers nearly filled an 8 GiB guest during SFCGAL compilation. Changing the parallel worker count preserves the cache, while changing recorded build flags such as `MAKEFLAGS` invalidates it.

After a build, a smoke check uses the matching PostgreSQL runtime archive. This guest command can diagnose an iteration; final archive checks run in the separate verification VM after copying the source and archives there:

```powershell
& C:/pg-binaries-tools/python/python.exe C:/pg-src/build.py --target windows-x86_64 runtime-check `
  C:/pg-inputs/postgresql-18.6-windows-x86_64.tar.gz C:/pg-work/verify-pgvector `
  --package-archive pgvector=C:/pg-output/pgvector/pgvector-postgresql-18.6-windows-x86_64.tar.gz
```

These scripts run inside Windows, from its local repository checkout. The local pgvector build passed in 17.92 seconds, then 7.78 seconds in the same workspace with unchanged source, context and main input keys. Address Standardizer took 31.28 seconds initially and 10.18 seconds on repeat; its PCRE2 library hash and modification time and dependency success key remained unchanged. No PCRE2 configuration, compilation or installation ran on repeat.

Collection, HypoPG, pg_ivm, pgAudit and pgTAP also built twice locally, with repeat calls taking 11.3–14.4 seconds including VMware command overhead. pgTAP uses Git's bundled Perl when Perl is absent from `PATH`, so this build needs no separate Perl installation. The seven-package combination passed native-library inspection, SQL probes, shutdown and cleanup in 33.12 seconds. These runs used the existing verified PostgreSQL SDK from GitHub, two guest CPUs and 4 GiB RAM; they do not measure a local PostgreSQL compilation or a clean-machine build.

Pg_jsonschema's first setup attempt took 494.56 seconds and populated the scoped Rust and cargo-pgrx caches before the PowerShell logging failure below. After fixing the wrapper and recovering its stale workspace lock, the first successful build took 389.07 seconds and the repeat took 28.47 seconds, with `CARGO_BUILD_JOBS=2`. The successful first build was therefore not cold. The repeat retained its dependency success key, toolchain, registry and compiled-library cache. Pg_jsonschema alone passed runtime verification in 24.38 seconds; all eight completed packages passed together in 25.55 seconds, inspecting 101 binaries and running probes for nine SQL extensions.

PostGIS's first attempt took about 50 minutes, including its private PostgreSQL compatibility build and SFCGAL, before failing during protobuf generation. Using `protoc` directly fixed that failure. Successful edit and repeat builds then took 553.20 and 544.07 seconds, retaining all 2,246 dependency files and the dependency success key. The repeat still configured and recompiled 82 C files. Retaining successful configuration, disabling upstream's phony revision rule and retaining the derived 100 MiB PGXS SDK reduced the unchanged repeat to 172.61 seconds, with no configuration or C compilation and unchanged sampled file timestamps. The preceding script edit took 538.10 seconds and retained the same dependencies.

The optimised archive passed in a separate VM without MSYS2 or the installed build dependencies: PostGIS alone took 92.42 seconds and all nine packages together took 62.33 seconds, including probes for 14 SQL extensions. That VM also passed PostgreSQL's 15 checks and each of the other eight package combinations. These are local runtime checks using the earlier verified PostgreSQL archive, rather than a release-candidate record audit.

A fresh PostgreSQL build through the standard local helper took 437.61 seconds, including source preparation, configuration, compilation and both archives. Its 12 vcpkg dependencies restored from the local binary cache in 2.7 seconds; Ninja reported 287.59 seconds. This is a warm dependency-cache build, not a cold installation. The earlier dependency compilation took about 37 minutes before the architecture-detection failure; completed vcpkg packages survived subsequent retries.

The locally compiled PostgreSQL passed all 15 runtime checks in 94.83 seconds. A separate VM then passed PostgreSQL alone in 83.49 seconds and with all nine locally built extension archives in 64.96 seconds. Those extensions were compiled against the earlier verified SDK; this establishes runtime compatibility, not a newly bound release candidate. The new SDK is separately retained at `C:/pg-inputs/local-core/postgresql-development-18.6-windows-x86_64.tar.gz` in the prepared agent trial. Switching an existing workspace to that SDK correctly invalidates its build state; the earlier SDK remains untouched.

To build PostgreSQL and start a fresh extension workspace against its SDK, the guest commands are:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File platforms/windows/build-postgresql-local.ps1 `
  -Workspace C:/pg-work/postgresql -OutputDirectory C:/pg-output/postgresql
powershell.exe -NoProfile -ExecutionPolicy Bypass -File platforms/windows/build-extension-local.ps1 `
  -Package pgvector `
  -DevelopmentArchive C:/pg-output/postgresql/postgresql-development-18.6-windows-x86_64.tar.gz `
  -Workspace C:/pg-work/agent-1/pgvector -OutputDirectory C:/pg-output/pgvector
```

These commands use the newly produced SDK, while the earlier host command uses the SDK retained with the prepared extension workspace. Each workspace keeps its selected SDK unchanged until that input is deliberately updated.

`bootstrap.ps1` prepares a new tool installation under `C:/pg-binaries-tools`; `PG_WINDOWS_TOOLS` selects that root for subsequent scripts. Its `-Package postgis` option also prepares MSYS2. The PostgreSQL build needs an empty workspace and produces separate runtime and development archives. Extension builds reuse their named workspace and cache sources beneath the tools root. The archive filename comes from `postgresql-build.json` in the PostgreSQL output directory; the example uses the current selected version.

Vcpkg's binary archives remain in `%LOCALAPPDATA%\vcpkg\archives`. Its downloaded and extracted tools remain beneath `%VCPKG_INSTALLATION_ROOT%\downloads`; the native Perl fallback uses `tools\perl\5.42.2.1\perl\bin\perl.exe` there. Retaining both caches lets a fresh PostgreSQL workspace restore dependencies and reuse native Perl.

A PostGIS tool-bootstrap trial on a fresh native Windows GitHub runner passed in 5 minutes 16 seconds. Installing its 196 MSYS2 packages took 3 minutes 30 seconds, downloaded 429.55 MiB and occupied about 3 GiB. A retained local environment avoids repeating that installation; this hosted measurement excludes PostGIS compilation and does not measure Fusion performance.

Local Fusion preparation first failed after 286.16 seconds when two MSYS2 mirrors reset connections. The retry requested 179.42 MiB rather than 429.73 MiB because downloads remained cached, and succeeded in 421.64 seconds. A repeat setup took 10.12 seconds without downloading or installing packages. The prepared MSYS2 tree contained 282 package entries and 3.98 GB of files. This used Git's bundled Perl in the bootstrap process; it does not establish that Perl's suitability for a native PostgreSQL compilation.

PostgreSQL requires native Windows Perl: Git's MSYS Perl rewrites MSVC options such as `/nologo` into filesystem paths and fails when generating exports. Bootstrap checks for native Perl before accepting an installed interpreter. The PostgreSQL build explicitly selects native Perl, using an installed interpreter or the pinned vcpkg portable Strawberry cache; pgTAP can still use Git's Perl for its SQL generator.

The local PostgreSQL-only verifier passed all 15 checks, including capabilities, built-in extensions and mutual TLS, in 108.35 seconds during a concurrent Rust build. This used the existing runtime archive, not a locally compiled PostgreSQL. Windows ARM's `XtaCache` translation service briefly held a DLL after PostgreSQL shutdown; two cleanup attempts failed and the third succeeded after about one second. Cleanup retries Windows permission errors for up to five seconds and still fails if the lock persists. The service is left running.

The shared CLI wrappers preserve native stderr and determine success from the exit code. This matters in Windows PowerShell 5: redirected native stderr can otherwise become a terminating `NativeCommandError`, hiding the underlying error or rejecting informational Rust output. A diagnostic confirmed that stderr with exit zero succeeds and exit seven still fails. For a stale workspace lock, confirm its recorded PID has exited in the guest, then remove only the lock file; retain the workspace and caches.

Some Windows source archives contain read-only files. Workspace invalidation removes that attribute only from regular files inside the disposable tree before retrying deletion. Other permission errors remain failures; cache invalidation must not leave a partially deleted source tree behind.

Windows verification extracts archives with Python's `data` filter so directories inherit normal Windows permissions. Python 3.13's unfiltered extraction creates protected directory permissions that prevent PostgreSQL's restricted child process from loading DLLs, producing `0xc0000135` even when all required DLLs are present. The controlled trial reproduced the failure with identical archive bytes and paths. Probe scratch folders also inherit Windows permissions; Linux and macOS retain private temporary directories. [Python directory permissions](https://docs.python.org/3.13/library/os.html#os.mkdir), [PostgreSQL restricted processes](https://github.com/postgres/postgres/blob/REL_18_6/src/common/restricted_token.c).

#### Hosted validation after local proof

The hosted trial lives in `.github/workflows/local-iteration-windows.yml`. Its phases are `core`, `small`, `postgis`, `rust`, `all`, `package` and `bootstrap-postgis`. Manual dispatch selects the phase; `small` covers PostgreSQL and seven extension packages. Completed PostgreSQL archives and their build record are retained before runtime verification, so a later checker failure does not lose the SDK. Extension builds still require the runtime checkpoint to pass.

The `all` phase sends its final archives and build records to a separate Windows runner for `release-check`. That job uses the runner's preinstalled Python and Visual Studio inspection tools and installs no dependencies. Package-level checks during iteration remain separate from this final gate.

A manual run can supply `postgresql_run` to reuse that run's recorded PostgreSQL runtime and development archives; selection checks current build inputs and archive hashes, and the checkpoint still runs runtime verification. This requires the component artefact `spike2-windows-x86_64-postgresql`.

From the Mac host, a focused hosted retry uses:

```sh
gh workflow run local-iteration-windows.yml --ref BRANCH \
  -f phase=package -f package=pgvector \
  -f postgresql_run=SUCCESSFUL_POSTGRESQL_RUN -f repeat_builds=true
```

`BRANCH` selects the build-script revision; `SUCCESSFUL_POSTGRESQL_RUN` is the numeric run ID containing a compatible SDK. For a new PostgreSQL build, select `phase=core` and omit `postgresql_run`.

The optional `repeat_builds` input runs each selected extension build twice in the same workspace. `package-summary.json` records first and repeat build times separately from the total including verification, and checks that the recorded workspace keys remain unchanged. The first build can use installed tools and download caches; its timing is not necessarily a cold-machine measurement.

The `package` phase accepts one package name through the `package` input. The separate `bootstrap-postgis` phase diagnoses tool preparation without building PostgreSQL or extensions. Bootstrap logs timestamp each external operation; downloads and MSYS2 extraction have five-minute timeouts. Ambient `tar.exe` stalled extracting MSYS2 beyond the 20-minute diagnostic limit; replacing it with the prepared Python toolchain extracted the same verified archive in 28 seconds. The earlier two-hour PostGIS failure therefore cannot establish a need for compiled-dependency caching.

Build records use forward-slash paths and checkout files use LF line endings on every host. A cross-host SDK audit found that Windows path separators and Git's CRLF conversion otherwise made identical source revisions appear different. Fresh Windows SDK run `41175933237` passed the native record tests and PostgreSQL runtime checkpoint with this correction. Earlier records remain historical evidence and are not rewritten to bypass current input checks.

A native x64 hosted success does not establish that Windows ARM can build and run the same software through x64 translation.

## Persistent build state

The source-download cache contains checksum-verified archives. It is separate from compiled dependency installations, Cargo's compiled output and installed toolchains. Keeping downloaded archives alone does not make a repeat build incremental.

Local extension iteration uses one stable workspace per agent, package and target. Dependency prefixes can contain absolute paths, so the workspace stays at the same path between runs. The harness owns reuse and invalidation; package scripts consume the prepared state without implementing a local or GitHub cache backend.

Inside the development environment, the shared command is:

```sh
python3 build.py --target linux-arm64 extension-build \
  address_standardizer /work/postgresql-development.tar.gz /work/output \
  --workspace /work/agents/agent-1/address_standardizer \
  --source-cache /work/source-cache --reuse-workspace
```

The target, package and development archive select the build. The output directory receives the finished archive. The workspace is an absolute path without whitespace, retained between runs; the source cache may be shared because archives are checksum-verified. Each simultaneous build needs its own workspace. Outputs stay outside the workspace.

Before each invocation, the harness replaces the private PostgreSQL copy and empties `payload/` and `build/stage/`. With unchanged inputs, it retains prepared sources, build intermediates and successful dependency installations. Changing the main build script refreshes sources and main intermediates while retaining `build/dependencies/`, Cargo's `build/target/` and pgrx state. Changing a source checksum, dependency-build implementation, PostgreSQL development archive, or recorded toolchain/settings refreshes source and build state. A failed dependency phase is retried.

The optional `build-dependencies.sh` or `build-dependencies.ps1` entry point prepares dependencies without implementing caching itself. Its helpers live in `internal/dependencies/`; changes there invalidate the dependency installation. Installed Debian and MSYS2 package versions also form part of the build context, so updating a system dependency invalidates retained build state. The entry-point contract is documented in [README.md](README.md).

The harness rejects simultaneous use of a workspace. A crash can leave `.pg-binaries-extension-workspace.lock`; its error names the owning PID. Remove the lock only after confirming that process has exited. Fresh-workspace builds remain available by omitting `--reuse-workspace`.

Upgrading the harness's cache-key definition can invalidate existing workspaces. During these trials, adding empty Windows environment fields changed a Mac workspace's context fingerprint and cleared its compiled dependencies. The sources, compiler, SDK and dependency script were unchanged. Recovery took 208 seconds using the retained package-download cache; the next identical run skipped dependencies and took 47 seconds. This was a one-time harness upgrade, separate from the original cold/warm results.

## Measured iteration time

These measurements used verified source-download caches. “Cold” means a new compiled dependency prefix or Cargo target directory, rather than a machine without installed tools. Times include the extension-build command through archive production; clean runtime verification is timed separately.

- Docker Linux ARM64, Address Standardizer, four allocated CPUs: 9.76 seconds cold, 3.00 seconds warm, 4.13 seconds after a main-script comment edit. Three further warm runs took 2.98–2.99 seconds.
- Docker Linux x86_64 through Rosetta, Address Standardizer, four allocated CPUs: 51.51 seconds cold, 7.58 seconds warm, 10.04 seconds after the comment edit. Three further warm runs took 7.44–7.47 seconds. Both SQL extensions passed clean runtime checks.
- Docker Linux x86_64 through Rosetta, PostGIS, four allocated CPUs: verified source downloads took 56.22 seconds separately; the cold build took 188.18 seconds. A main-script edit rebuilt PostGIS in 176.78 seconds while retaining its private dependencies. After avoiding repeated configuration, an unchanged repeat took 72.50 seconds with no C recompilation. The archive and all five supplied SQL extension probes passed; clean verification took 64.17 seconds. System geospatial libraries were already installed.
- Lume macOS ARM64, four vCPUs and 8 GiB RAM: Address Standardizer took 19.61 seconds cold, 3.22 warm and 7.01 after the edit. PostGIS took 417.41, 48.71 and 51.61 seconds respectively. PostGIS used an existing conda package-download cache but prepared a fresh installed environment and SFCGAL build.
- In the same Mac VM, pg_jsonschema took 68.72 seconds with an empty Cargo target directory, 8.45 warm and 9.54 after the edit. Rust and the Cargo registry were already installed. Before fixing repeated pgrx initialisation and identical-file rewrites, warm iterations took about 45 seconds. A small SQL-generation helper still recompiles each time.

The PostGIS trial found that retaining dependencies alone did not make its own build incremental: configuration rewrote a shared header and `make` treated the revision header as phony. An unchanged Linux x86 repeat took 161.18 seconds and recompiled 344 C files. The Linux and Mac build scripts now retain successful configuration within the harness-managed source tree and use upstream's `--without-phony-revision` option. Input changes still refresh that source tree. Installation, staging and archive production account for the remaining warm-build time.

Applying that fix in the Mac VM took 50.34 seconds for the first build after the script change and 30.02 seconds for an unchanged repeat, versus the earlier 48.71-second warm baseline. The dependency key and SFCGAL library checksum and modification time stayed unchanged. The warm archive passed clean-VM runtime and SQL verification. Only the Mac build script was transferred into the earlier isolated source snapshot; this measures iteration rather than current release-candidate consistency.

The Mac archives passed SQL probes together in a separate clean VM: 201 Mach-O files checked, no findings, 29.22 seconds for the final verification run. These results establish that retained dependency state helps iteration. Parallels could not be measured because of its activation gate, and local macOS x86_64 translation still needs licence approval.

Earlier native Windows GitHub trials provide historical comparison: six small packages repeated in 10.00–14.68 seconds, Address Standardizer took 40.40 seconds initially and 13.73 on repeat, and pg_jsonschema took 585.19 and 33.33 seconds. Rust and cargo-pgrx setup was included in the first Rust build. Workspace keys and SQL checks passed. These uncontrolled hosted measurements use different allocations and revisions from the local Fusion trials.

PowerShell 7.4.2 syntax-check processes in an amd64 container repeatedly crashed with a Rosetta assertion after reporting successful parses; isolated checks also passed. These checks do not establish compatibility with Windows PowerShell 5.1, which runs the native Windows trials. The measured Linux C builds did not encounter this translation failure.

### Starting another Linux agent

A fresh ARM64 container took 0.61 seconds to provision from the existing Docker image and cached APT layer, with no manual steps. Its initially empty source cache was populated during an Address Standardizer build taking 13.60 seconds. Repeat and post-restart builds took 3.39 and 3.42 seconds. This measures another agent joining an established installation, rather than fresh-machine setup.

Recreating that trial container against its retained host work directory preserved the complete cache manifest. A subsequent build took 3.43 seconds and passed archive checks; the PCRE2 library's checksum, modification time and dependency key were unchanged. The retained work directory occupied 268 MiB. New development containers use Docker's `--init`: stopping the trial then took 0.08 seconds with SIGTERM, compared with 3.12 seconds and a forced kill without it. Existing containers retain their creation settings.

A new agent can also receive a copy of prepared work. An APFS clone of the stopped trial's work directory took 0.52 seconds; provisioning a separate four-CPU container took 0.58 seconds. Its first build took 3.48 seconds and repeat 3.45 seconds, with unchanged dependency keys, PCRE2 checksum and modification time. Clean SQL verification passed. The combined copy, provision and first build took 4.58 seconds. This proves reuse for Address Standardizer, not a cold-machine setup or a dependency-heavy workload.

The source container must be stopped with no workspace lock. Copy its work directory into a new agent-owned directory, mount that directory at the same `/work` path, and use the normal helper. On this Mac, the tested copy was:

```sh
mkdir -p out/local-environments/pg-binaries-linux-arm64-cache-clone-trial
cp -cR out/local-environments/pg-binaries-linux-arm64-iteration-trial/. \
  out/local-environments/pg-binaries-linux-arm64-cache-clone-trial/
```

`PG_BINARIES_LINUX_WORK` selects the copied directory when creating the new named container. Its normal cache-key checks still apply. APFS shares unchanged file extents; reported directory sizes do not measure unique disk consumption. Both trial containers were confirmed stopped afterwards.

### Concurrent builds

One Linux ARM64 trial built HypoPG and pgvector in separate workspaces. Serial execution took 6.57 seconds using 16 allocated CPUs; two concurrent containers with eight CPUs each took 4.35 seconds, about 34% less wall time. Both scenarios passed archive checks. The serial container peaked at 528 MiB; the concurrent containers peaked individually at 299 and 252 MiB. Their peaks were not necessarily simultaneous and exclude the Docker VM's overhead.

This demonstrates useful two-package concurrency for small native builds. It does not establish a safe limit for PostGIS, Rust or whole VMs. Docker's VM had 16 CPUs and about 47 GiB available, with no per-container memory limit; actual CPU affinity constrained concurrent jobs even though the guest CPU-count query still reported 16.

The separate x86 PostGIS container peaked at 906 MiB across its cold, repeat, edit and diagnostic runs. This cgroup measurement includes charged file cache and excludes Docker's VM overhead. It used preinstalled geospatial libraries and does not measure the memory needed to compile that dependency stack from source.

A host snapshot attributed an 8.01 GiB memory footprint to the running Lume Mac VM and 30.07 GiB to Docker Desktop's Linux VM. The Docker VM had a larger allocation and retained state; these were not matched fresh environments. The figures describe this machine at that moment, rather than minimum requirements or an intrinsic Docker overhead. The host has 128 GiB RAM and 18 logical CPUs.

In the four-vCPU, 8 GiB Mac VM, warm PostGIS and pg_jsonschema builds took 51.88 seconds serially and 49.54 seconds together in separate workspaces. Both succeeded and retained their dependency keys; their archives passed checks together with PostgreSQL. Guest memory pressure reported 79% free before and after, with no swap. The single trial's 2.34-second difference does not establish a reliable throughput improvement. It shows that these two warm builds can share a VM without needing separate environments. The trial used the earlier isolated Mac recipe snapshot, excluding subsequent Windows metadata and helper additions.

The x86_64 clean-verification helper passed the Address Standardizer SQL checks in 39.77 seconds, including a cached verifier-image build and container setup. The development container remained stopped afterwards and retained its cache.

## GitHub dependency caching

The recommendation is to defer a separate hosted compiled-dependency cache. All nine Windows extension packages now build locally, and Linux and Mac ARM builds already have retained local state. The current workflows can retry one extension using an existing PostgreSQL archive, and archive selection can reuse unchanged packages. Those mechanisms address the usual iteration loop without adding a remote cache backend. Local Mac x86 translation remains a licence-dependent gap; repeated hosted work for that target could change this recommendation.

The expensive remaining case is rebuilding a changed dependency-heavy package. A previous native Intel macOS run spent 1,945 seconds in the PostGIS job and 1,077 seconds in pg_jsonschema; the complete run took 4,559 seconds. Those are whole-job timings from an earlier revision, including setup and downloads, rather than measured dependency-compilation savings. Local repeat-build results suggest useful savings are possible, but do not establish hosted cache transfer cost or expected hit rate.

GitHub exposed step states while Windows jobs ran but withheld full logs until completion, delaying diagnosis of silent setup failures. Fresh hosted PostgreSQL builds took between 18 minutes 24 seconds and 30 minutes 7 seconds across trials, including dependency preparation, compilation and packaging. These are uncontrolled whole-step timings.

Reusing those PostgreSQL archives took six seconds for selection and three seconds for staging and input checks in one subsequent run. The runtime checkpoint still ran. This avoided another PostgreSQL build while diagnosing Windows verification problems, although each hosted retry still needed runner startup and tool preparation.

If hosted iteration remains necessary, PostGIS is the first candidate for a measured cache experiment. The dependency phase gives the harness a reusable boundary without adding cache logic to individual build scripts. Hosted reuse would still need a stable installation path or verified relocation, complete invalidation and a timed cache restore. No hosted compiled-dependency cache is currently configured.

## Initial Parallels setup

The existing `Windows 11` VM has its downloaded installation ISO and unattended setup image ready. Starting it, creating a Linux VM and listing snapshots have each failed with “available only in Parallels Desktop for Mac Pro or Business Edition.” Activation needs resolving before command-line provisioning can be evaluated. Computer use briefly connected after permission approval, but subsequent attempts failed with a native-pipe startup error. These are setup blockers, not performance results.

Separate macOS and full-x86 Linux guest-creation attempts returned the same edition error. The latter used the vendor's documented `prlctl create NAME -d ubuntu --cpu-type x86` command. No comparison guest was created. Parallels documents a one-vCPU, 8 GiB limit for full-x86 emulation; its actual project performance remains unmeasured. [Full-x86 guest setup and limitations](https://kb.parallels.com/en/130217).

Routine lifecycle and guest work use command-line tools and APIs. Computer-use permissions are recorded in [AGENTS.md](../AGENTS.md#repository-operations).

The command-line client is `/Applications/Parallels Desktop.app/Contents/MacOS/prlctl`. In this agent's sandbox, service queries require an approved execution outside the sandbox. A sandbox-only “Unable to connect to Parallels Service” error does not establish that Parallels needs restarting.

Linux builds in a Parallels guest must use the guest's own filesystem: Parallels documents limitations on `mmap()` in Linux shared folders. Source and archive transfer must be tested separately from build execution. [Shared-folder limitations](https://kb.parallels.com/en/128914).

## Evidence

The earlier four-target package validation is recorded in [IMPLEMENTATION_STATUS.md](../IMPLEMENTATION_STATUS.md). New local-iteration timings and machine-readable evidence belong under `out/local-iteration/`; this document records their interpretation and the commands needed to reproduce them.
