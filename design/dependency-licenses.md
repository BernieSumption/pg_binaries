# Dependency licences

PostgreSQL and extension archives contain code, native libraries and sometimes data from several projects. Recipients find their declared terms through one source-controlled `LICENSES.md`, linked from every download. An OSI-approved open-source licence is accepted; alternative terms need a recorded human decision before the affected files enter a public download.

## Central licence inventory

`LICENSES.md` has one entry per redistributed project, naming its declared licence and linking to its source and licence declaration. A project appears once even when several archives contain its files. Its entry retains the terms and source links needed to describe older public downloads. When a distribution or package manager supplies changed source, the entry links to that provider too.

### Declared project licences

We take licence declarations from project maintainers and package managers at face value. When a project compiles dependencies into its own binary, its declared licence is sufficient evidence that those dependencies are compatible with it; list the project, without separate entries for the compiled dependencies. When our build scripts copy a dependency library into an archive, record that library's project in the central `LICENSES.md`, with its declared licence and links to source and the declaration. Do not investigate a project's chain of title or write a separate legal analysis for each transitive package. When a distribution or package manager changes the source used in a build, link that provider as well. A project already listed does not need a new licence decision merely because another archive includes it.

When a repository states a licence for the project and gives no separate terms for a data file it contains, apply the repository licence to that file and outputs derived from it. Do not investigate whether the project maintainers had the right to license the data's earlier sources. Explicit separate file or dataset terms require their own review.

A licence declaration published by the project is sufficient evidence of its licence even if its package omits the licence text. Record the declared licence and a link to the declaration in `LICENSES.md`; do not create a substitute licence text.

### Dependency review during development

Adding or updating an extension package, PostgreSQL or a packaging recipe includes reviewing the libraries and data it redistributes against `LICENSES.md`. The agent inspects the recipe and packaged files, applies the declared-project rules above, and adds projects that are missing from the central file. Existing entries are updated when selected terms or source links change. A project already recorded under applicable terms needs no new approval merely because another extension uses it.

The review includes separately copied runtime dependencies and data, including any separately declared terms. It uses the licence declared by the project for dependencies compiled into that project’s binary as described above. Automated checks confirm recorded entries and archive pointers exist; they do not independently determine the legal terms of every binary. A concern outside the accepted licences and decisions below goes into the human review queue before publication.

## Human-reviewed alternative terms

The user has reviewed and approved the following terms for the uses described:

- SQLite: [public-domain blessing](https://www.sqlite.org/copyright.html) for the bundled runtime.
- libjpeg-turbo: [Independent JPEG Group licence](https://github.com/libjpeg-turbo/libjpeg-turbo/blob/main/README.ijg) for JPEG code in bundled libraries.
- bzip2/libbzip2: [bzip2 licence](https://gitlab.com/bzip2/bzip2/-/blob/bzip2-1.0.8/LICENSE) for the bundled runtime library.
- Qhull: [Qhull licence](https://github.com/qhull/qhull/blob/master/COPYING.txt) for the bundled runtime library.
- libcom_err: MIT-style [e2fsprogs `lib/et` source-file terms](https://github.com/tytso/e2fsprogs/blob/master/lib/et/et_name.c) for the bundled library. The [project notice](https://github.com/tytso/e2fsprogs/blob/master/NOTICE) identifies `lib/et` as an exception to the filesystem utilities’ GPLv2 licence.
- Microsoft Visual C++: [Visual Studio 2022 licence terms](https://visualstudio.microsoft.com/license-terms/) and [redistributable-file list](https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution#visual-c-runtime-files) covering toolset use for this open-source build and redistribution of the listed, unmodified runtime DLLs, without an accompanying copy of Microsoft’s licence file.

## Licence information in downloads

Every PostgreSQL and extension archive contains the same `postgresql/LICENCE` file, linking to `https://github.com/BernieSumption/pg_binaries/blob/main/LICENSES.md`. Ordinary extraction installs the pointer with the rest of the archive. Before publication, its public URL serves entries for the projects selected for that download.

We take linking to the central `LICENSES.md` to satisfy the selected licences’ distribution requirements, including requirements to include a licence or attribution notice. This is the distribution’s licence-delivery mechanism; archives do not carry additional licence-text or attribution files, and publication does not add a separate corresponding-source provision process.
