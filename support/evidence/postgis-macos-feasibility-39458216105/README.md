# PostGIS macOS arm64 dependency inventory

On 2026-10-20, [run 39458216105](https://github.com/BernieSumption/pg_binaries/actions/runs/39458216105) passed the unmodified PostGIS 3.6.4 source build against the checked PostgreSQL 18.6 macOS arm64 core at source revision `0e97435462f99fb4aa831a42eb12cc5e89fb296e`. The trial used Homebrew GDAL 3.13.3 and wrote a recursive Mach-O dependency inventory for the four installed PostGIS modules.

The inventory found 1,792 module/dependency edges and 89 Homebrew formulae in the combined dependency set. The raster module dominated the result: its recursive closure contained 193 dylib nodes and 88 formulae, compared with 23 nodes and 14 formulae for the core PostGIS module. This is a dependency-discovery result, not a final archive or a licence clearance. The full inventory is retained in the run artifact while it remains available.

The Homebrew GDAL build enables many format drivers outside the schema-focused SQL probe. A separate trial builds unmodified GDAL with its documented minimal-driver options and measures the resulting closure before choosing a macOS packaging recipe. Any reduced driver set must be checked against required PostGIS schema behavior and recorded as a build decision.
