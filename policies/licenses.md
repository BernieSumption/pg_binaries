# Licence decisions

Clients receive PostgreSQL and extension archives containing upstream code and data. The [functional specification](../specs/functional.md#maintain-a-list-of-all-licenses-and-link-to-it-in-downloads) defines which licences are acceptable and how downloads link to the central `LICENSES.md`. This policy records the decisions used when applying that rule. Archive packaging and publication are described in [releases.md](releases.md).

## Declared project licences

Take upstream and package-manager licence declarations at face value. When a project compiles dependencies into its own binary, its declared licence is sufficient evidence that those dependencies are compatible with it; list the project, without separate entries for the compiled dependencies. When our build scripts copy a dependency library into an archive, record that library's project in the central [`LICENSES.md`](../LICENSES.md), with its declared licence and links to source and the declaration. Do not investigate an upstream project's chain of title or write a separate legal analysis for each transitive package. When a distribution or package manager changes the source used in a build, link that provider as well. A project already listed does not need a new licence decision merely because another archive includes it.

When a repository states a licence for the project and gives no separate terms for a data file it contains, apply the repository licence to that file and outputs derived from it. Do not investigate whether upstream had the right to license the data's earlier sources. Explicit separate file or dataset terms require their own review.

An upstream licence declaration is sufficient evidence of a project's licence even if its package omits the licence text. Record the declared licence and a link to the declaration in `LICENSES.md`; do not create a substitute licence text.

## Human-reviewed alternative terms

The user accepts [SQLite's public-domain blessing](https://www.sqlite.org/copyright.html) for the SQLite runtime copied into a download. The user also accepts the [Independent JPEG Group licence](https://github.com/libjpeg-turbo/libjpeg-turbo/blob/main/README.ijg) for JPEG code in copied libjpeg-turbo libraries. The user has reviewed and approved the declared [bzip2/libbzip2 licence](https://gitlab.com/bzip2/bzip2/-/blob/bzip2-1.0.8/LICENSE) and [Qhull licence](https://github.com/qhull/qhull/blob/master/COPYING.txt) for their separately copied runtime libraries. These are human-reviewed alternatives under the functional specification; their project declarations remain linked in [`LICENSES.md`](../LICENSES.md).

## Microsoft Visual C++ runtime

The user reviewed Microsoft's [Visual Studio 2022 licence terms](https://visualstudio.microsoft.com/license-terms/) and [redistributable-file list](https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution#visual-c-runtime-files) and determined that the Visual C++ toolset may be used for this open-source build and its listed, unmodified runtime DLLs may be redistributed with it. This is the human-reviewed alternative allowed by the functional specification. The review found no requirement to include a copy of Microsoft's licence file. The central [`LICENSES.md`](../LICENSES.md) records Microsoft and its applicable terms. Downloads link to that inventory through the `LICENCE` pointer required by the functional specification.
