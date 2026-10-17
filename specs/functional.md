# Functional spec

These guarantees define the product. Agents read these spec files for hard requirements, and manage and edit the files in `policies/` to reflect decisions and interpretations of these specs.

## OS support

We support Mac and Linux on x86-64 and arm64, and Windows on x86-64 only.

A single binary for each platform provides support for all supported OS versions. For each OS we document a support version - releases before this version are not tested or supported. We choose the support version based on:

- negligible usage: we may drop support for versions if the combined estimated usage among developers and CI machines for all versions less than the support version is less than 1%
- very old: we may drop support for anything released more than 10 years ago
- inconvenient to support: we may drop support for older OS releases if supporting them makes it harder to support new OSs or conflicts with our other goals eg on portability or 

Actual supported versions are documented in inventory.json, reasoning behind them captured in `policies/os-support.md`.

## Universal OS support and machine portability

Within a supported platform, we target a truly universal common platform and avoid depending on anything that may vary between machines. Care must be taken when setting up the build configuration to avoid depending on any paths or libraries on the build machine that are not certain to be compatible with every intended target machine.

When dependencies are unavoidable, they are bundled with, or statically linked into, the binaries.

Only depend on truly universal capabilities of platforms, eg the universal C runtime on Windows. Bundle or statically link non-universal.

## Postgres version support

We offer every stable PostgreSQL release in majors 15 and later published on or after 25 September 2025 on all three target platforms. There is no upper major-version limit. Exclude prereleases and PostgreSQL <=14.

## Extension support

Our aim is to provide a wide range of extensions, so that 99%+ of apps can use our distribution.

When deciding whether to support an extension we consider factors for and against.

Factors in favour of support:

- Well known and widely used
- Supported by major Postgres hosting providers

Factors against support:

- Unmaintained, deprecated, or abandoned project
- New project either not recommended for production use by its creators, or in an unstable and early iteration phase - major hosts sometimes support their own experimental projects so it is possible for a project to be both experimental and unsuitable for general use, and supported by a major Postgres hosting provider 
- Incompatible with our supported OS or Postgres versions (extensions that explicitly declare support for a subset of our OSs or Postgres versions but are otherwise worth including are acceptable)
- High cost of supporting eg long build times, fiddly dependencies
- Major hosts have dropped support for it
- License that prevents redistribution, or merely executing `CREATE EXTENSION x` and using the extension's objects in a schema definition depends on data files can't can't be redistributed. Note that we take the license declared by a source repo at face value. If the source repo contains data files that are not explicitly put under a separate licence, they are assumed to be distributed under the same licence as the source code. We have hard prohibition on supporting extensions that Are not licensed for free redistribution.

In the event of conflicting factors, agents may decide that the case for or against overwhelmingly supports one result and make the decision. For example, if a deprecated extension is still widely used and supported by major Postgres hosting providers, and does not have a high cost of supporting, it's probably a good idea to support it. If the balance of factors for and against does not clearly support a decision, for example a widely used extension that is not compatible with our minimum OS support target, then add this to HUMAN_REVIEW_QUEUE.md.

### Extension version support

Different extensions may require different version support policies. The goal is to provide a useful subset of supported versions without an explosion of versions that all have to be build and tested against every new postgres release.

Any client using this project has an intended extension version - this is the version that they intend to execute their SQL against in production. Clients are expected to select the next highest version from the inventory if their intended version is not available.

Our guarantee is: we will provide enough versions of an extension so that DDL written for the intended version will execute correctly in the selected version.

We do _not_ guarantee that DDL written for the selected version will be backwards compatible with the intended version.

Use these criteria to determine backwards compatibility:

- Always include the most recent release before a break in backwards compatibility
- Assume that a major version transition is a break in backwards compatibility
- Research the project documentation because projects do not always follow semantic versioning and it is somewhat common for Postgres extensions to break backwards compatibility in a minor release.
- For projects that have a very slow minor version release cadence, like PostGIS which has historically released around one minor version per year, assume that minors are breaking
- When updating the current supported versions, use version numbers rather than release dates to establish support. So for example, if we support 2.1.7 and 3.0.1, and when checking for new versions we find that 2.1.11 has been release, it would be necessary to support it.

In general we do not support extension releases made before 25 September 2025, but exceptions can be made, for example if there is a widely used incompatible version whose last release was before then, or if the current release was made before then.

### Respect both test evidence and documented compatibility

Always research the documented compatibility of each extension version.

The claimed compatibility for a build output should be the smaller of the documented compatibility and the actual compatibility as checked by tests. For example, if an extension version claims to support Postgres 17.0 - 17.6, and tests indicate that 17.7 also works fine, do not widen the claim made by the documentation.

### Never patch or modify extensions or dependencies

We intend to ship straightforward builds of upstream packages, without porting, patching or otherwise changing them to meet our goals. The extensions we support are expected to be well maintained packages that will build correctly for all of our target platforms and Postgres versions.

If an extension doesn't intend to support certain OS's or Postgres versions, our inventory should reflect that lack of support. If there are other issues that we could work around by modifying source, add an item to HUMAN_REVIEW_QUEUE.md

This also applies to Postgres' own dependencies required to enable certain build options.

### Documenting extension support decisions

Document extension support decisions in `policies/extensions.md`, with one heading per project containing its name and the decision, for example `pg_biscuit — include`.

Use the following labelled paragraphs, in this order:

- `Description:` What the project provides, its SQL extension name(s) and a project link.
- `For inclusion:` Adoption, hosting support, maintenance and other reasons to include it.
- `Against inclusion:` Build cost, dependencies, platform limitations, security or redistribution concerns. Say “None identified” when appropriate.
- `Version policy:` Which release lines to support and why, including relevant compatibility breaks.
- `Target support:` Intended PostgreSQL versions, operating systems and architectures, with any restrictions. Verified coverage belongs in the inventory and test records.
- `Sources:` Links supporting the findings and decisions.

Keep findings brief and follow `style.md`; detailed research belongs elsewhere.

There should be a single section listing all the built-in extensions. We do not need version information for these. They come with the releases that support them. inventory.json contains the facts of which releases support which extensions. These should be extracted from the build output, not researched.

Additional labelled paragraphs may be included when they contain equally relevant information. Built-in extensions need only the shared list described above.

Example format

    ## pg_biscuit — include
    
    Description: [pg_biscuit](https://example.org/pg_biscuit) provides biscuit types and functions for calculating safe tea-dunking durations. Its SQL extension name is pg_biscuit.
    
    For inclusion: Actively maintained and offered by CrumbCloud and Dunkbase, two major managed PostgreSQL providers in the competitive biscuit industry. Build requirements are modest, and the extension and its bundled library use BSD licences. No external datasets, service or startup configuration are required. Actual biscuits are not required for schema creation.
    
    Against inclusion: Adds a native dependency, libcrumb, which we must build and bundle. Its small size and standard build process make this an acceptable cost.
    
    Version policy: Support the latest release in each compatible version line. Upstream documents backwards-compatible minor and patch releases, but 3.0 replaced dunk_seconds() with dunk_milliseconds(). Retain the latest 2.x release alongside the latest 3.x release so older CHECK constraints and generated columns still work. Both lines have releases after our cutoff.
    
    Target support: PostgreSQL 15–18 on Linux, macOS and Windows, on x86-64 and arm64, matching upstream's declared support. Build separately for each PostgreSQL major, reusing builds across minors only after verification. Broader PostgreSQL support requires further upstream evidence and testing.
    
    Sources: [release and compatibility policy](https://example.org/pg_biscuit/releases), [installation requirements and licence](https://example.org/pg_biscuit/install).

Note: This policy document, as specified above, requires that decisions about whether to include or exclude extensions are made at the project level. If we identify a project where we would like to include some SQL extensions but exclude others, add the proposed exception and its reasoning to HUMAN_REVIEW_QUEUE.md.

### Minimise the number of extension builds

For every extension version we support, we provide enough downloads to cover every Postgres version we support (except in the case of extensions that genuinely do not support all of our Postgres versions). An extension built against version 15 of Postgres will not necessarily be compatible with version 18. Sometimes there may be breaks within a chain of minor releases, So for example perhaps one build is required to support 18.0-18.6 and another to support 18.6+.

Avoid building the entire matrix of every Postgres version against every extension version. Researching compatibility in upstream docs, Make a minimal set of extension builds, and ensure that the correct tests exist to verify that a given extension build does in fact work as expected in every version it claims support for.

## Declared support drives builds, tests and releases

There must be a clear, documented process for adding supported PostgreSQL versions, extensions, extension versions and platforms.

Express intended support in one authoritative place, separate from the inventory of available downloads. inventory.json should be generated from or validated against this source. Routine additions must not require independently updating build lists, test lists and release lists. For example, adding an extension release should identify the required builds and checks without manually enumerating them in several workflows.

The delivery process must:

- Detect when intended support lacks a verified download and report the requirement as unmet.
- Determine which builds and tests are needed, reusing existing artifacts and applicable verification results.
- Run the required builds and checks on appropriate GitHub Actions runners.
- Publish verified archives and update the inventory, preserving references to unchanged downloads.

Incomplete or failed work must remain visible until resolved. It must not disappear from coverage reporting merely because it has not been added to the public inventory.

Document this process in `policies/delivery-process.md`. Explain what an agent edits to request new support, how that change produces unmet coverage checks, how builds and tests are selected and run, and how verified results become published downloads. Include a worked example. Agents choose the metadata format, orchestration and implementation.

## Documented release layout

Document the layout and publication of GitHub releases in `policies/releases.md`. Explain how release tags, archive names and URLs identify downloads, where clients find the current inventory, and how releases containing only new or changed binaries refer to unchanged downloads in earlier releases.

Download URLs must be immutable: an existing URL must never serve different bytes. Publish corrections at new URLs and update the inventory. Clients must be able to cache by URL and verify downloads using the inventory's checksums.

Describe how publication ensures that every download referenced by a new inventory is available before clients receive it, and how older assets remain available while referenced by the current inventory.

## Documented process for installing

The process for unpacking and installing PostgreSQL and extensions is documented in `policies/install-process.md`.

Binaries for postgres and extensions are installed using standard file copy or download-and-unzip and be immediately executable using standard shell tools and process management APIs.

The Postgres release and extensions are packaged as .tar.gz files within a release. They should be entirely self-contained, to the extent possible no steps are required after downloading to make them work.

Most extensions should be installed using a simple common process, which is shared by all extensions, e.g. Unzipping and copying to a defined location.

Some extensions may require basic configuration of Postgres, for example, adding to pg_stat_statements. It is acceptable to document metadata included with each extension that indicates requirements like this.

Do not create complicated installation requirements, like executable scripts or a rich set of installation configuration options. It is assumed and desirable that these are not going to be required. If they would be useful for some extensions that we want to support, add a request to HUMAN_REVIEW_QUEUE.md.

## Postgres option support

Our aim is to include the PostgreSQL features needed to create, execute and inspect schemas, including functionality used by supported extensions. In addition, some users may find unexpected uses for our downloaded binaries, so we should not needlessly restrict features.

Include an option when:

- It enables schema operations involving types, collations, defaults, constraints, indexes, views, functions or procedures. Being able to query a feature's settings through SQL does not make it necessary for schema inspection. The criteria is: Are there plausible schemas that an application might write that need to invoke this functionality?
- It is required by a supported extension or a tool we provide.
- Upstream's supported build configuration enables it together with a required feature. Keep that combination rather than maintaining a custom split. For example, OpenSSL supports `pgcrypto` and also enables TLS.
- There is low cost to supporting it, and it is enabled by default common to be enabled

Exclude an optional feature when

- it is expensive in terms of binary size, built time or project complexity
- it conflicts with portability, os support, or another guarantee
- it is commonly disabled or known to cause issues that could affect our users
- it is disabled by default and there's no good reason to depart from that default

If a single option has factors arguing for and against enabling it, agents are authorised to make a call one way or the other if the evidence clearly favours one decision. If the case each way is strong, add it to HUMAN_REVIEW_QUEUE.md

### Documenting option support decisions

Record decisions in `policies/postgres-options.md`, with a brief description of what each option enables, whether we include it, the reason and supporting sources. Several options may enable one feature, and one option may enable several features. Record key version or platform differences. Do not document options that purely relate to the mechanics of the build process, such as specifying library paths or compiler flags. These are left open as implementation details.

## After compatibility guarantees are satisfied, optimise for download size

For example if static linking vs bundling a dependency has no implications for functionality or support, choose the one that results in lower download sizes.

## Available downloads are advertised in inventory.json

inventory.json in the repo root records what downloads are available.

The file format is JSON, this code block shows it in YAML for readability:

```yaml
schema_version: 1

os_support:
  macos:
    minimum_version: "major.minor"
  windows:
    minimum_version: "major.minor.build.revision"
  linux:
    minimum_version: "major.minor" # linux uses kernel versioning

postgresql:
  "18.6":
    included_extensions: ["citext", "hstore", etc...] # extensions provided by this release
    downloads:
      linux-x86_64:
        url: "https://github.com/BernieSumption/pg_binaries/releases/download/<tag>/...path..."
        sha256: "<archive checksum>"

extensions:
  vector: # the sql name as passed in `CREATE EXTENSION <name>;`
    "0.8.7":
      requires: [] # Array of extension name strings
      downloads:
        linux-x86_64:
          - postgresql_support:
              from: "18.6" # lowest supported version
              to: "18.6" # highest supported version
            url: "https://github.com/BernieSumption/pg_binaries/releases/download/<tag>/...path..."
            sha256: "<archive checksum>"
```

The inventory is downloaded from `https://github.com/BernieSumption/pg_binaries/releases/latest/download/inventory.json`

Each GitHub release only uploads binaries that are added or changed as a result of that release. The release's `inventory.json` refers to older release download URLs.

## Standard tools and schema operations should work

Include `postgres`, `initdb`, `pg_ctl`, `psql`, `pg_dump` and `pg_restore` with their support files. They must initialize UTF-8 databases, run under an ordinary user, accept connections, apply representative DDL, expose its definitions through PostgreSQL catalogues and stop cleanly.

## Downloads include redistribution obligations

Downloads must be free and public without authentication. Include applicable licence texts, notices and component/version mappings, plus any required source offers or source links. Resolve redistribution obligations before advertising a component.

## Allow debugging of failures

Assume that failures will happen, both in our own testing and on the machines of users. Both system-level errors like dynamic libraries failing to load and processes crashing or aborting with errors; and application-level errors like extension errors or missing files that are captured in log files.

Anticipate these errors, and document how to capture them. This will partly be the responsibility of the client that loads these binaries, but our responsibility is to configure the build appropriately, configure log file location, and document what clients need to collect and provide to allow us to debug issues.

How can we enable an excellent feedback loop where issues in our binaries can be fed back to us, with appropriate information for us to eg resolve symbols in stack traces.

Document the plan to achieve this in `policies/debugging.md`
