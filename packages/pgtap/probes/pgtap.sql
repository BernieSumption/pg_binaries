\set ON_ERROR_STOP on

CREATE TABLE public.pgtap_probe (id integer PRIMARY KEY, payload text NOT NULL);
INSERT INTO public.pgtap_probe VALUES (1, 'schema assertion');
SELECT plan(4);

DO $$
DECLARE
    result text;
BEGIN
    result := has_table('public', 'pgtap_probe');
    IF result IS NULL OR result NOT LIKE 'ok %' THEN
        RAISE EXCEPTION 'pgTAP has_table assertion failed';
    END IF;
    result := col_type_is('public', 'pgtap_probe', 'id', 'integer');
    IF result IS NULL OR result NOT LIKE 'ok %' THEN
        RAISE EXCEPTION 'pgTAP col_type_is assertion failed';
    END IF;
    result := col_not_null('public', 'pgtap_probe', 'payload');
    IF result IS NULL OR result NOT LIKE 'ok %' THEN
        RAISE EXCEPTION 'pgTAP col_not_null assertion failed';
    END IF;
    result := results_eq(
        'SELECT payload FROM public.pgtap_probe WHERE id = 1',
        ARRAY['schema assertion'::text]
    );
    IF result IS NULL OR result NOT LIKE 'ok %' THEN
        RAISE EXCEPTION 'pgTAP results_eq assertion failed';
    END IF;
END
$$;

SELECT * FROM finish();
DROP TABLE public.pgtap_probe;
