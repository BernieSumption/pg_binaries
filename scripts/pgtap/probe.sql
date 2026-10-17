\set ON_ERROR_STOP on
CREATE EXTENSION pgtap;
CREATE TABLE public.pgtap_probe (id integer PRIMARY KEY, payload text NOT NULL);
INSERT INTO public.pgtap_probe VALUES (1, 'schema assertion');
SELECT plan(4);
SELECT has_table('public', 'pgtap_probe', 'schema table exists');
SELECT col_type_is('public', 'pgtap_probe', 'id', 'integer', 'id has integer type');
SELECT col_not_null('public', 'pgtap_probe', 'payload', 'payload is required');
SELECT results_eq('SELECT payload FROM public.pgtap_probe WHERE id = 1', ARRAY['schema assertion'::text]);
SELECT * FROM finish();
DROP TABLE public.pgtap_probe;
