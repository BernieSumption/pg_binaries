# HypoPG selected Linux publication verification

[GitHub Actions run 39222288263](https://github.com/BernieSumption/pg_binaries/actions/runs/39222288263) tested source revision `de32190cc638fa45cc8b56f779a0e760be4b2f2e` on 2026-10-19. HypoPG 1.4.3 passed the archive suite for PostgreSQL 15.19, 16.15, 17.11 and 18.6 on Linux x86-64 and arm64. The importer checked each selected archive against its SHA-256 sidecar, receipt, verification record and current profile.

All eight core resolution records report `origin: reused`; each reuses build `github-39210758552-1` from run 39210758552. Archive SHA-256 values are from the selected artifacts and matching receipts.

- PostgreSQL 15.19 arm64: core `963060811cbae8e28eb7e83d7ec8d5f2be839556ba016d93792c965efd4e5b60`; HypoPG `f465991b1f57b27cf268789f46da0378a4a6141905ec5aabc06fea668639621e`. Core `reused` from run `39210758552` (build `github-39210758552-1`).
- PostgreSQL 15.19 x86_64: core `9a1baf17d45a729d844b8f9b690ff88714f4bdb4f9077e539ec4ea4abbd1f928`; HypoPG `cbc06591f037e7ef74db21999166661be570cb69267be70e021fed306f09b0a7`. Core `reused` from run `39210758552` (build `github-39210758552-1`).
- PostgreSQL 16.15 arm64: core `723de0a08a7f8ed0eaffce881144143d824ccae8ce1fd3305dd569670bdee144`; HypoPG `6909ea02005f28c99255971f83f1c7f6d8be1700011ba84874ad5f2ca3e88665`. Core `reused` from run `39210758552` (build `github-39210758552-1`).
- PostgreSQL 16.15 x86_64: core `4c272a01ac12db39b379c9d2c311989f9a46ece376ad1a2873f269958260c4da`; HypoPG `8fda991e3e17e3a28e08346ccba7c12990069b425f8a679d3489dfedb0fb9a22`. Core `reused` from run `39210758552` (build `github-39210758552-1`).
- PostgreSQL 17.11 arm64: core `7a37b9a01173f7211d9cef28b713ee49bb7154135e12cb7400353cc47618e775`; HypoPG `bf6f8a33127208fbc9063b748164884fa5e75999baba74ae1c1f703af1efc14a`. Core `reused` from run `39210758552` (build `github-39210758552-1`).
- PostgreSQL 17.11 x86_64: core `6d3b2d74a4024726b444be9668ed063773ad6216fdf79e26e77f822ab9694fac`; HypoPG `d6776ea0d833e7dba3eb70130ba4bd3aee084c08951744b92a651c5305602a9f`. Core `reused` from run `39210758552` (build `github-39210758552-1`).
- PostgreSQL 18.6 arm64: core `b0a8219ae31511e30f1fafb6b4cbcf4fd7ce7bcd6e8a19b363646bf119326266`; HypoPG `c67f2dcc2152949ec8ea6d094e827c9a7591be4a2b0670a0f7789b153166cc92`. Core `reused` from run `39210758552` (build `github-39210758552-1`).
- PostgreSQL 18.6 x86_64: core `8939ccb59a8c38b5f56446fd2f42784bb1df4eacd0a41d0544e78486d08be2d9`; HypoPG `669b54205c1ca28c2b9a69bb3b57d9d6f463ec2000427b22a3a252faa438675a`. Core `reused` from run `39210758552` (build `github-39210758552-1`).

Verification records are in `support/verification/`. Receipts, outcomes and static-analysis reports are retained here by architecture and PostgreSQL version.
