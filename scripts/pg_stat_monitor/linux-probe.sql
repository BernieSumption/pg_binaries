CREATE EXTENSION pg_stat_monitor;
CREATE TABLE public.pg_stat_monitor_probe (value integer NOT NULL);
INSERT INTO public.pg_stat_monitor_probe VALUES (7);
DO $$
BEGIN
  IF (SELECT count(*) FROM public.pg_stat_monitor_probe) <> 1 THEN
    RAISE EXCEPTION 'probe table query returned the wrong result';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_stat_monitor
    WHERE query LIKE '%pg_stat_monitor_probe%' AND calls > 0
  ) THEN
    RAISE EXCEPTION 'pg_stat_monitor did not record the probe workload';
  END IF;
END
$$;
