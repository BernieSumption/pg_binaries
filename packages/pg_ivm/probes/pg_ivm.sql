\set ON_ERROR_STOP on

CREATE TABLE public.ivm_probe (id integer PRIMARY KEY, amount integer NOT NULL);
INSERT INTO public.ivm_probe VALUES (1, 10), (2, 20);

SELECT pgivm.create_immv(
  'public.ivm_probe_totals',
  'SELECT count(*) AS rows, sum(amount) AS total FROM public.ivm_probe'
);

DO $$
BEGIN
  IF (SELECT rows FROM public.ivm_probe_totals) IS DISTINCT FROM 2 OR
     (SELECT total FROM public.ivm_probe_totals) IS DISTINCT FROM 30 THEN
    RAISE EXCEPTION 'initial IMMV contents are incorrect';
  END IF;
END
$$;

INSERT INTO public.ivm_probe VALUES (3, 7);
DO $$
BEGIN
  IF (SELECT rows FROM public.ivm_probe_totals) IS DISTINCT FROM 3 OR
     (SELECT total FROM public.ivm_probe_totals) IS DISTINCT FROM 37 THEN
    RAISE EXCEPTION 'IMMV was not incrementally maintained after INSERT';
  END IF;
END
$$;

UPDATE public.ivm_probe SET amount = 11 WHERE id = 1;
DO $$
BEGIN
  IF (SELECT rows FROM public.ivm_probe_totals) IS DISTINCT FROM 3 OR
     (SELECT total FROM public.ivm_probe_totals) IS DISTINCT FROM 38 THEN
    RAISE EXCEPTION 'IMMV was not incrementally maintained after UPDATE';
  END IF;
END
$$;

DELETE FROM public.ivm_probe WHERE id = 2;
DO $$
BEGIN
  IF (SELECT rows FROM public.ivm_probe_totals) IS DISTINCT FROM 2 OR
     (SELECT total FROM public.ivm_probe_totals) IS DISTINCT FROM 18 THEN
    RAISE EXCEPTION 'IMMV was not incrementally maintained after DELETE';
  END IF;
END
$$;
