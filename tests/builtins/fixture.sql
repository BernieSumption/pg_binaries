CREATE EXTENSION dict_xsyn;
CREATE TEXT SEARCH DICTIONARY builtin_xsyn (
    TEMPLATE = xsyn_template,
    RULES = 'xsyn_sample'
);
DO $$
BEGIN
    IF ts_lexize('builtin_xsyn', 'supernova')
       IS DISTINCT FROM ARRAY['supernova', 'sn', 'sne', '1987a']::text[] THEN
        RAISE EXCEPTION 'dict_xsyn did not read the packaged synonym rules';
    END IF;
END
$$;

CREATE EXTENSION file_fdw;
CREATE SERVER builtin_file_server FOREIGN DATA WRAPPER file_fdw;
CREATE FOREIGN TABLE builtin_file_probe (id integer, value text)
    SERVER builtin_file_server
    OPTIONS (filename '/tests/builtins/file_fdw.csv', format 'csv');
DO $$
BEGIN
    IF (SELECT count(*) FROM builtin_file_probe) <> 1
       OR (SELECT id FROM builtin_file_probe) IS DISTINCT FROM 42
       OR (SELECT value FROM builtin_file_probe) IS DISTINCT FROM 'hello' THEN
        RAISE EXCEPTION 'file_fdw did not read the CSV fixture';
    END IF;
END
$$;
