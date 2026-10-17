-- Shared PostgreSQL 15+ schema and migration smoke test.
-- Run with psql -X -v ON_ERROR_STOP=1 -f tests/schema.sql against an empty database.
CREATE SCHEMA pilot;

CREATE TYPE pilot.item_state AS ENUM ('draft', 'active', 'archived');
CREATE DOMAIN pilot.positive_price AS numeric(12, 2) CHECK (VALUE >= 0);
CREATE COLLATION pilot.english_icu (provider = icu, locale = 'en-US');

CREATE TABLE pilot.icu_names (
    name text COLLATE pilot.english_icu NOT NULL
);
CREATE INDEX icu_names_name_idx ON pilot.icu_names (name);
INSERT INTO pilot.icu_names (name) VALUES ('z'), ('a');

CREATE TABLE pilot.accounts (
    account_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE pilot.items (
    item_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id bigint NOT NULL REFERENCES pilot.accounts(account_id),
    state pilot.item_state NOT NULL DEFAULT 'draft',
    title text NOT NULL CHECK (length(title) > 0),
    title_key text GENERATED ALWAYS AS (lower(title)) STORED,
    price pilot.positive_price NOT NULL,
    attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX items_title_key_active_idx ON pilot.items (title_key)
    WHERE state = 'active';
CREATE INDEX items_attributes_idx ON pilot.items USING gin (attributes);

CREATE TABLE pilot.events (
    event_id bigint GENERATED ALWAYS AS IDENTITY,
    occurred_on date NOT NULL,
    item_id bigint NOT NULL,
    payload jsonb NOT NULL,
    PRIMARY KEY (occurred_on, event_id)
) PARTITION BY RANGE (occurred_on);
CREATE TABLE pilot.events_2026 PARTITION OF pilot.events
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');

CREATE FUNCTION pilot.active_item_count(p_account_id bigint) RETURNS bigint
LANGUAGE sql STABLE AS $$
    SELECT count(*) FROM pilot.items
    WHERE account_id = p_account_id AND state = 'active'
$$;

CREATE VIEW pilot.active_items AS
    SELECT item_id, account_id, title, price
    FROM pilot.items
    WHERE state = 'active';

INSERT INTO pilot.accounts (email) VALUES ('pilot@example.test');
INSERT INTO pilot.items (account_id, state, title, price, attributes)
VALUES (1, 'active', 'Portable Database', 12.50, '{"category":"test"}');
INSERT INTO pilot.events (occurred_on, item_id, payload)
VALUES ('2026-10-13', 1, '{"kind":"created"}');

DO $$
BEGIN
    IF pilot.active_item_count(1) <> 1 THEN
        RAISE EXCEPTION 'function or filtered item query failed';
    END IF;
    IF (SELECT title_key FROM pilot.items WHERE item_id = 1) <> 'portable database' THEN
        RAISE EXCEPTION 'generated column failed';
    END IF;
    IF (SELECT count(*) FROM pilot.items WHERE attributes @> '{"category":"test"}') <> 1 THEN
        RAISE EXCEPTION 'JSONB query failed';
    END IF;
    IF (SELECT count(*) FROM pilot.events_2026) <> 1 THEN
        RAISE EXCEPTION 'partition routing failed';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'pilot' AND indexname = 'items_title_key_active_idx'
    ) THEN
        RAISE EXCEPTION 'partial index missing';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_collation
        WHERE collname = 'english_icu'
          AND collnamespace = 'pilot'::regnamespace
          AND collprovider = 'i'
    ) THEN
        RAISE EXCEPTION 'ICU collation missing';
    END IF;
    IF (SELECT string_agg(name, ',' ORDER BY name) FROM pilot.icu_names) <> 'a,z' THEN
        RAISE EXCEPTION 'ICU-backed index ordering failed';
    END IF;
END
$$;
