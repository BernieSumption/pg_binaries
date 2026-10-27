\set ON_ERROR_STOP on

SET pgaudit.log = 'ddl,write,read';

CREATE TABLE public.pgaudit_probe (
  id integer PRIMARY KEY,
  payload text NOT NULL
);

INSERT INTO public.pgaudit_probe VALUES (1, 'audit payload');
SELECT payload FROM public.pgaudit_probe WHERE id = 1;

DO $$
BEGIN
  IF current_setting('pgaudit.log') IS DISTINCT FROM 'ddl,write,read' THEN
    RAISE EXCEPTION 'pgAudit log classes were not enabled for this session';
  END IF;

  IF (SELECT payload FROM public.pgaudit_probe WHERE id = 1) IS DISTINCT FROM 'audit payload' THEN
    RAISE EXCEPTION 'pgAudit probe row mismatch';
  END IF;
END
$$;

DROP TABLE public.pgaudit_probe;
