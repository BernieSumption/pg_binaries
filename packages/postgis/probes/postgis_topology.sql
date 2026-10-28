DO $$
BEGIN
  PERFORM topology.CreateTopology('spike2_topology', 4326);
  IF NOT EXISTS (SELECT 1 FROM topology.topology WHERE name = 'spike2_topology') THEN
    RAISE EXCEPTION 'PostGIS topology creation failed';
  END IF;
END $$;
