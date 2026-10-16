CREATE EXTENSION sslinfo;
DO $$
BEGIN
    IF ssl_is_used() IS DISTINCT FROM true
       OR ssl_client_cert_present() IS DISTINCT FROM true
       OR ssl_client_dn_field('CN') IS DISTINCT FROM current_user
       OR ssl_version() IS NULL
       OR ssl_cipher() IS NULL THEN
        RAISE EXCEPTION 'sslinfo did not report the authenticated TLS connection';
    END IF;
END
$$;
