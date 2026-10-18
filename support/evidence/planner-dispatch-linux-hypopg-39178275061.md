# Planner-driven HypoPG Linux trial

The [planner coordinator run 39178275061](https://github.com/BernieSumption/pg_binaries/actions/runs/39178275061) selected one declared HypoPG 1.4.3, PostgreSQL 17.11, Linux x86-64 request. Its plan job passed and called the selected HypoPG workflow from the same commit, `11a51e6f678b9a9bcb70c9e025c97ae99769e39a`. The called workflow reused a checksum-verified PostgreSQL core candidate with matching source, run and builder inputs, then built HypoPG and passed the relocated Alpine 3.22 archive suite.

The downloaded artifact was independently imported. The retained verification record matches the CI artifact byte for byte. It binds PostgreSQL SHA-256 `dcda10d41f048d3c638dbd71f23645d9815f889c323cae9020d8c2c9de120ecd` to HypoPG SHA-256 `7b3ec2ff5b5d08300754c2e96bf1662b04a215d39a88fadea0932c70b987a8e9` under profile revision `a04c7e49a83aa1ad6a162794a86cbd270b7f1940a0498ac15cdb0976a0401e29`.

This proves one planner-to-workflow route and checked reuse of a core artifact from an earlier selected workflow. A further run must check that an artifact uploaded under the coordinator can itself be discovered and reused. Other project and platform routes remain unimplemented.
