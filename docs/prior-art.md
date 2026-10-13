# Prior art and source notes

Checked 2026-10-13. These notes explain choices in the specification; they are not a claim that another project's artifact satisfies this project's release contract.

| Project/provider | Observed distribution pattern | Relevant lesson |
| --- | --- | --- |
| [Theseus PostgreSQL binaries](https://github.com/theseus-rs/postgresql-binaries/releases) | GitHub Releases with per-version, per-target archives and checksums | Strong precedent for direct, language-neutral asset URLs. Its archive contents and extension coverage need independent validation against our schema-focused contract. |
| [Zonky embedded Postgres binaries](https://github.com/zonkyio/embedded-postgres-binaries) | Platform binaries published as Maven artifacts; its [Java consumer](https://github.com/zonkyio/embedded-postgres) selects versions through a BOM | Useful precedent for exact version/platform coordinates, but Maven is tailored to Java consumers. |
| [Postgres.app](https://github.com/PostgresApp/PostgresApp) | Downloadable macOS package, including PostGIS and pgvector; [older GitHub releases](https://github.com/PostgresApp/PostgresApp/releases) | Evidence for a richer bundled extension set. It does not cover Linux or Windows. |
| [4mGLn PostgreSQL Portable](https://github.com/4mGLn/postgresql-portable) | Relocatable Linux/Windows archives and separate extension overlays | Useful implementation precedent for dependency bundling and overlay packaging; inspect recipes before adopting any specific mechanism. |
| [PostGIS Windows bundles](https://postgis.net/documentation/getting_started/install_windows/enabling_postgis/) | Public bundles include core, raster, SFCGAL, topology, and related extensions | Candidate completeness target, with actual three-platform feasibility to be proven. |

Supporting references:

- [GitHub Releases limits](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases): 1,000 assets per release, each under 2 GiB; no stated total-size or bandwidth quota.
- [PostgreSQL build requirements](https://www.postgresql.org/docs/current/install-requirements.html): ICU, LZ4, Zstandard, SSL, and other optional dependencies.
- [PostgreSQL Meson installation options](https://www.postgresql.org/docs/current/install-meson.html): default rpath may point to an absolute installation directory; relocatable builds require separate handling.
- [PostgreSQL collation support](https://www.postgresql.org/docs/18/collation.html): ICU support must be compiled in; libc and ICU providers differ.
- [PostGIS installation requirements](https://postgis.net/docs/postgis_installation.html): GEOS/PROJ and optional-component dependency details.
- [PROJ resource search](https://proj.org/en/stable/resource_files.html): runtime data such as `proj.db` must be available after relocation.
- [Apple bundled-library guidance](https://developer.apple.com/documentation/xcode/embedding-nonstandard-code-structures-in-a-bundle), [Linux loader guidance](https://man7.org/linux/man-pages/man8/ld.so.8.html), and [Windows DLL search order](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-search-order): target-specific dependency closure.
