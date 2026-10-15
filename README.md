# PostgreSQL binaries project

This repository supplies portable PostgreSQL and extension binaries for tools that apply and inspect database schemas. A separate client library uses the catalogue to choose downloads, start PostgreSQL and expose a connection.

## Reading order

Review these assets together:

1. [Functional policy](specs/functional/functional-policy.md) — Use case, concrete guarantees and their reasons.
2. [Inventory](specs/functional/functional-inventory.json) — Intended versions, platforms and features; the [format reference](specs/functional/functional-inventory-format.md) explains the fields.
3. [Testing policy](specs/testing/testing-policy.md) — Evidence required for those guarantees, with a [requirement map](specs/testing/testing-notes.md#requirement-map).

Then consult the area relevant to the work:

| Board | Policy | Notes and items |
| --- | --- | --- |
| Functional | [Product guarantees](specs/functional/functional-policy.md) | [Technical context](specs/functional/functional-notes.md); [implementation items](specs/functional/items/) |
| Build | [Inclusion criteria](specs/build/build-policy.md) | [Option research](specs/build/build-notes.md); [feature items](specs/build/items/) |
| Extensions | [Selection and packaging](specs/extensions/extensions-policy.md) | [Dependency and resource research](specs/extensions/extensions-notes.md); [extension items](specs/extensions/items/) |
| Testing | [Acceptance rules](specs/testing/testing-policy.md) | [Requirement map and gaps](specs/testing/testing-notes.md); [test procedures](specs/testing/items/) |

The [architecture](specs/functional/functional-architecture.md) describes component boundaries and the delivery pipeline. [Pilot evidence](specs/testing/testing-evidence.md) records existing passes and their limits. The inventory defines intended coverage; generated verification and download records establish actual results.

## Human review

Each board's `items/proposed/` folder is its human review queue:

- [Functional proposals](specs/functional/items/proposed/)
- [Build proposals](specs/build/items/proposed/)
- [Extension proposals](specs/extensions/items/proposed/)
- [Testing proposals](specs/testing/items/proposed/)

The [board format in AGENTS.md](AGENTS.md#specification-boards) defines policy, notes and the five workflow folders. [style.md](style.md) defines the writing conventions.

## Licence

Original repository code and documentation use the [MIT licence](LICENSE). Distributed PostgreSQL, extensions and third-party dependencies retain their own licences and notices.
