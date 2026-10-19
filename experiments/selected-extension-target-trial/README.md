# Selected extension target request trial

Created 19 October 2026 to test a scoped request path for selected extension publication from `spike`. GitHub cannot manually dispatch this workflow while its definition exists only on a non-default branch, so changing `request.json` invokes the shared planner and requests one selected target.

The question is whether a request committed on a non-default branch can invoke exactly one selected publication target through the shared workflow. The workflow code is needed to carry a JSON request into existing planning and routing when manual dispatch is unavailable. Its input is `request.json`, currently pg_jsonschema 0.3.4 for PostgreSQL 18.6 on Windows x86_64 with retry enabled; the shared planner validates the target and prerequisites. Retire this experiment and its push trigger when normal dispatch replaces branch-based requests.
