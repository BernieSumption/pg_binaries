# SFCGAL 2.3 dependency resolution

[Run 39518733089](https://github.com/BernieSumption/pg_binaries/actions/runs/39518733089) tried unmodified SFCGAL 2.3.0 with conda-forge `cgal-cpp=6.1.1` on macOS arm64. It stopped in the conda solver before source download: the requested `boost` meta-package pulled older Boost variants, while the available CGAL 6.1.1 package required a newer `libboost`. The next trial requests `libboost-devel` directly so the solver can choose a version compatible with CGAL. No SFCGAL or PostGIS compilation occurred in this run.
