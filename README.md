# PostgreSQL binaries project

This repository supplies portable PostgreSQL and extension binaries for tools that apply and inspect database schemas. A separate client library will use the catalogue to choose downloads, start PostgreSQL and expose a connection.

## Project documents

- [Specification guide](spec/README.md) — purpose, review order and document authority.
- [Intended inventory](spec/inventory.json) and [format](spec/inventory-format.md) — version ranges, platforms, capabilities and metadata.
- [Functional specification](spec/functional.md) — concrete guarantees and why they exist.
- [Testing specifications](spec/testing/README.md) — evidence required for each guarantee.
- [Extension profiles](spec/extensions/README.md) — support research, version transitions and data requirements.
- [Architecture](spec/architecture.md) and [implementation decisions](spec/implementation-decisions.md) — responsibilities and AI-maintained technical reasoning.
- [Product decisions](spec/product-decisions.md) — human review queue for scope and guarantees.
- [Pilot evidence](spec/evidence.md) — passing combinations and their limits.

The specification defines the project contract. Its inventory describes intended coverage; [verification evidence](spec/evidence.md) records results and remaining gaps.

## Licence

Original repository code and documentation use the [MIT licence](LICENSE). Distributed PostgreSQL, extensions and third-party dependencies retain their own licences and notices.
