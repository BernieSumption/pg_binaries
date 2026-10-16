CREATE EXTENSION citext;
CREATE TABLE builtin_citext (value citext UNIQUE);
INSERT INTO builtin_citext VALUES ('Hello');
DO $$
BEGIN
    IF 'HELLO'::citext <> (SELECT value FROM builtin_citext) THEN
        RAISE EXCEPTION 'citext comparison is not case insensitive';
    END IF;
    BEGIN
        INSERT INTO builtin_citext VALUES ('hello');
        RAISE EXCEPTION 'citext unique constraint accepted a case-only duplicate';
    EXCEPTION WHEN unique_violation THEN
        NULL;
    END;
END
$$;

CREATE EXTENSION hstore;
CREATE TABLE builtin_hstore (attributes hstore);
INSERT INTO builtin_hstore VALUES ('color => blue, size => large'::hstore);
DO $$
BEGIN
    IF (SELECT attributes -> 'color' FROM builtin_hstore) <> 'blue'
       OR NOT (SELECT attributes ? 'size' FROM builtin_hstore) THEN
        RAISE EXCEPTION 'hstore key lookup failed';
    END IF;
END
$$;

CREATE EXTENSION ltree;
CREATE TABLE builtin_ltree (path ltree);
INSERT INTO builtin_ltree VALUES ('Top.Science.Astronomy'::ltree);
DO $$
BEGIN
    IF (SELECT count(*) FROM builtin_ltree WHERE path <@ 'Top.Science'::ltree) <> 1
       OR (SELECT nlevel(path) FROM builtin_ltree) <> 3 THEN
        RAISE EXCEPTION 'ltree hierarchy query failed';
    END IF;
END
$$;

CREATE EXTENSION pg_trgm;
CREATE TABLE builtin_trigram (value text);
INSERT INTO builtin_trigram VALUES ('word');
CREATE INDEX builtin_trigram_gin ON builtin_trigram USING gin (value gin_trgm_ops);
DO $$
BEGIN
    IF similarity((SELECT value FROM builtin_trigram), 'word') <> 1.0
       OR NOT EXISTS (
           SELECT 1 FROM pg_indexes
           WHERE indexname = 'builtin_trigram_gin'
       ) THEN
        RAISE EXCEPTION 'pg_trgm similarity or index creation failed';
    END IF;
END
$$;

CREATE EXTENSION unaccent;
CREATE TABLE builtin_unaccent (source text, normalized text);
INSERT INTO builtin_unaccent VALUES ('Hôtel', unaccent('Hôtel'));
DO $$
BEGIN
    IF (SELECT normalized FROM builtin_unaccent) <> 'Hotel' THEN
        RAISE EXCEPTION 'unaccent normalization failed';
    END IF;
END
$$;

CREATE EXTENSION pgcrypto;
CREATE TABLE builtin_pgcrypto (source text, checksum text);
INSERT INTO builtin_pgcrypto VALUES ('abc', encode(digest('abc', 'sha256'), 'hex'));
DO $$
BEGIN
    IF (SELECT checksum FROM builtin_pgcrypto)
       <> 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad' THEN
        RAISE EXCEPTION 'pgcrypto SHA-256 digest failed';
    END IF;
END
$$;

CREATE EXTENSION "uuid-ossp";
CREATE TABLE builtin_uuid_ossp (id uuid DEFAULT uuid_generate_v4());
INSERT INTO builtin_uuid_ossp DEFAULT VALUES;
DO $$
BEGIN
    IF (SELECT id FROM builtin_uuid_ossp) IS NULL
       OR substring((SELECT id::text FROM builtin_uuid_ossp) FROM 15 FOR 1) <> '4' THEN
        RAISE EXCEPTION 'uuid-ossp version 4 UUID generation failed';
    END IF;
END
$$;

CREATE EXTENSION btree_gist;
CREATE TABLE builtin_btree_gist (
    room text,
    occupied tstzrange,
    EXCLUDE USING gist (room WITH =, occupied WITH &&)
);
INSERT INTO builtin_btree_gist VALUES ('blue', '[2026-01-01 10:00+00, 2026-01-01 11:00+00)');
DO $$
BEGIN
    BEGIN
        INSERT INTO builtin_btree_gist VALUES ('blue', '[2026-01-01 10:30+00, 2026-01-01 11:30+00)');
        RAISE EXCEPTION 'btree_gist exclusion constraint accepted an overlapping range';
    EXCEPTION WHEN exclusion_violation THEN
        NULL;
    END;
END
$$;

CREATE EXTENSION cube;
CREATE TABLE builtin_cube (bounds cube);
INSERT INTO builtin_cube VALUES (cube(ARRAY[0.0, 0.0], ARRAY[2.0, 2.0]));
DO $$
BEGIN
    IF NOT (SELECT bounds @> cube(ARRAY[1.0, 1.0]) FROM builtin_cube)
       OR (SELECT bounds @> cube(ARRAY[3.0, 1.0]) FROM builtin_cube) THEN
        RAISE EXCEPTION 'cube containment failed';
    END IF;
END
$$;

CREATE EXTENSION intarray;
CREATE TABLE builtin_intarray (values integer[]);
INSERT INTO builtin_intarray VALUES (ARRAY[1, 2, 3]);
DO $$
BEGIN
    IF NOT (SELECT values @> ARRAY[2, 3] FROM builtin_intarray)
       OR NOT (SELECT values && ARRAY[3, 4] FROM builtin_intarray)
       OR (SELECT values @> ARRAY[4] FROM builtin_intarray) THEN
        RAISE EXCEPTION 'intarray containment or overlap failed';
    END IF;
END
$$;

CREATE EXTENSION tablefunc;
DO $check$
BEGIN
    IF (SELECT a FROM crosstab(
            $$SELECT 'row1'::text, 'a'::text, 10 UNION ALL
              SELECT 'row1', 'b', 20 ORDER BY 1, 2$$,
            $$SELECT unnest(ARRAY['a', 'b'])$$
        ) AS result(row_name text, a integer, b integer)) <> 10
       OR (SELECT b FROM crosstab(
            $$SELECT 'row1'::text, 'a'::text, 10 UNION ALL
              SELECT 'row1', 'b', 20 ORDER BY 1, 2$$,
            $$SELECT unnest(ARRAY['a', 'b'])$$
        ) AS result(row_name text, a integer, b integer)) <> 20 THEN
        RAISE EXCEPTION 'tablefunc crosstab result failed';
    END IF;
END
$check$;
