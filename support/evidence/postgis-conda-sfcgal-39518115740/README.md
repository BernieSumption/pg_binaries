# macOS arm64 SFCGAL source-build trial

[Run 39518115740](https://github.com/BernieSumption/pg_binaries/actions/runs/39518115740) at revision `3d0affae52d287e6b4aac9124dd784f9be4f3630` resolved the selected PostgreSQL 18.6 core and configured unmodified SFCGAL 2.2.0 source pinned to commit `d1ba2619e8fa8ce2f6ff6bab7fe0d51fbc9413a0`. Its [configure log](sfcgal-configure.log) reports CGAL **5.6.1**. The [build log](sfcgal-build.log) stops in the conda-forge CGAL `boost/graph/iterator.h` header: Apple Clang reports that `Halfedge_around_source_iterator` and `Halfedge_around_face_iterator` have no `base` member. The trial never built PostGIS or tested the fourth SQL extension.

The separate [three-extension trial](../postgis-conda-macos-arm64-build-39516965034/README.md) remains passing. Investigate a compatible unmodified upstream SFCGAL/CGAL combination before repeating this source-build path; the project's source rule prohibits writing a local patch for the dependency.
