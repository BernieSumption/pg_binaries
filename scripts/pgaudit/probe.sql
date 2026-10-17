\set ON_ERROR_STOP on
CREATE EXTENSION pgaudit;
SET pgaudit.log = 'ddl,write,read';
CREATE TABLE public.pgaudit_probe (id integer PRIMARY KEY, payload text NOT NULL);
INSERT INTO public.pgaudit_probe VALUES (1, 'audit payload');
SELECT payload FROM public.pgaudit_probe WHERE id = 1;
DO $$
BEGIN
  IF (SELECT payload FROM public.pgaudit_probe WHERE id = 1) <> 'audit payload' THEN
    RAISE EXCEPTION 'pgAudit probe row mismatch';
  END IF;
END
$$;
