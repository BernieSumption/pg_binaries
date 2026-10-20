# PostgreSQL binaries project

This repository supplies portable PostgreSQL and extension binaries for tools that apply and inspect database schemas. A separate client library uses the catalogue to choose downloads, start PostgreSQL and expose a connection.

## Understanding the project

This project is specified by humans and implemented by AI.

- `specs/functional.md` - what this project provides
- `specs/testing.md` - how everything is tested and how testing guarantees that the functional requirements are met 
- `policies/*.md` - AI managed records documenting exact behaviour how implementation decisions followed the specifications 

For a bounded new-extension trial, follow [Adding an extension](docs/adding-an-extension.md).

## Licence

Original repository code and documentation use the [MIT licence](LICENSE). Distributed PostgreSQL, extensions and third-party dependencies retain their own licences and notices.
