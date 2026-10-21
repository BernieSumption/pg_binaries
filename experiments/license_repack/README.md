# Licence archive repack trial

Created 2026-10-21. This one-off migration experiment asks whether a project-rooted tar.gz can gain the central licence pointer while selected old licence text files are removed, with every other archive member preserved.

Run `repack.py INPUT COMPONENT OUTPUT REPORT --remove MEMBER` once per explicitly selected legacy licence text. The trial input is the retained pgaudit Linux x86-64 archive; its `pgaudit/LICENSES/pgAudit.txt` text is removed while the project inventory stays in the archive. Outputs go under the ignored `out/` directory.

Focused fixtures pass. The retained HypoPG 1.4.3 Windows x86-64 archive for PostgreSQL 18.6 was repacked with its old licence text removed; all 18 retained members were identical, and the new pointer passed archive verification. The checked PostgreSQL 18.6 Windows x86-64 archive from Actions run 39562140440 was repacked with the pointer added; all 2,206 original members were identical. Its original SHA-256 was `dc6b7bbc1df71183ea79cc7a36c1f410d495446aaef4f96ab1adab3b547b7b17` and the repacked SHA-256 was `bffed09f75b396801c776e8376c8f3ea88f7c611e5d37e12309f2ee2ce0320f4`. These are local trials, not published artifacts or transferred verification records.

Retire this directory after its result informs the production archive migration; move code elsewhere only if a production caller needs it. Reassess by 2027-01-21.
