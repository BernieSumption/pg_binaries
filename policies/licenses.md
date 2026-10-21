# Licence decisions

Clients receive PostgreSQL and extension archives containing upstream code and data. The [functional specification](../specs/functional.md#maintain-a-list-of-all-licenses-and-link-to-it-in-downloads) defines which licences are acceptable and how downloads link to the central `LICENSES.md`. This policy records the decisions used when applying that rule. Archive packaging and publication are described in [releases.md](releases.md).

## Declared project licences

Take upstream and package-manager licence declarations at face value. For an extension support decision, its declared licence is sufficient evidence that its ordinary dependencies are intended to be freely redistributable unless an explicit dependency term says otherwise. Do not investigate an upstream project's chain of title or write a separate legal analysis for each transitive package. The central [`LICENSES.md`](../LICENSES.md) records each shipped project, including statically linked code, with its declared licence and links to source and the declaration. When a distribution or package manager changes the source used in a build, link that provider as well. A project already listed does not need a new licence decision merely because another archive includes it.

When a repository states a licence for the project and gives no separate terms for a data file it contains, apply the repository licence to that file and outputs derived from it. Do not investigate whether upstream had the right to license the data's earlier sources. Explicit separate file or dataset terms require their own review.

An upstream licence declaration is sufficient evidence of a project's licence even if its package omits the licence text. Record the declared licence and a link to the declaration in `LICENSES.md`; do not create a substitute licence text. This applies to the Seahash 4.1.0 crate, which declares MIT but omits the text from its package.

## Microsoft Visual C++ runtime

The user reviewed Microsoft's [Visual Studio 2022 licence terms](https://visualstudio.microsoft.com/license-terms/) and [redistributable-file list](https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution#visual-c-runtime-files) and determined that the Visual C++ toolset may be used for this open-source build and its listed, unmodified runtime DLLs may be redistributed with it. This is the human-reviewed alternative allowed by the functional specification. The review found no requirement to include a copy of Microsoft's licence file. The central [`LICENSES.md`](../LICENSES.md) records Microsoft and its applicable terms. Downloads link to that inventory through the `LICENCE` pointer required by the functional specification.
