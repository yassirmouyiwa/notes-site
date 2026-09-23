-- =====================================================================
--  audit_securite.sql — Audit de sécurité d'une instance PostgreSQL
--  Formation DBA — exécuter en superutilisateur : psql -d banque -f ...
--  Chaque section signale les points à vérifier. Compatible PG 12+.
-- =====================================================================

\pset pager off

\echo '########################################################'
\echo '#  AUDIT DE SECURITE POSTGRESQL'
\echo '########################################################'
SELECT version();
SELECT current_setting('server_version_num') AS version_num,
       CASE WHEN current_setting('server_version_num')::int < 130000
            THEN 'ATTENTION : version potentiellement en fin de support'
            ELSE 'ok' END AS support;

\echo ''
\echo '=== 1. Superutilisateurs (doivent etre rares et nominatifs) ==='
SELECT rolname, rolcanlogin
FROM pg_roles WHERE rolsuper ORDER BY rolname;

\echo ''
\echo '=== 2. Roles a attributs sensibles (CREATEROLE / CREATEDB / REPLICATION / BYPASSRLS) ==='
SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls
FROM pg_roles
WHERE rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication OR rolbypassrls
ORDER BY rolname;

\echo ''
\echo '=== 3. Roles pouvant se connecter SANS mot de passe (hors LDAP/cert : a verifier) ==='
SELECT rolname
FROM pg_authid
WHERE rolcanlogin AND rolpassword IS NULL
ORDER BY rolname;

\echo ''
\echo '=== 4. Mots de passe stockes en MD5 (migrer vers SCRAM) ==='
SELECT rolname,
       CASE WHEN rolpassword LIKE 'md5%' THEN 'MD5 (faible)'
            WHEN rolpassword LIKE 'SCRAM-SHA-256%' THEN 'SCRAM (ok)'
            ELSE 'autre' END AS type_hachage
FROM pg_authid
WHERE rolcanlogin AND rolpassword IS NOT NULL
ORDER BY 2, 1;
SELECT current_setting('password_encryption') AS password_encryption_actuel;

\echo ''
\echo '=== 5. Comptes avec date d''expiration (VALID UNTIL) ==='
SELECT rolname, rolvaliduntil
FROM pg_roles
WHERE rolvaliduntil IS NOT NULL
ORDER BY rolvaliduntil;

\echo ''
\echo '=== 6. Privileges accordes a PUBLIC sur les schemas ==='
SELECT nspname AS schema,
       coalesce(nullif(array_to_string(nspacl, E'\n'), ''), '(defaut)') AS acl
FROM pg_namespace
WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema'
  AND array_to_string(nspacl, ',') LIKE '%=%';

\echo '   -> Le schema public NE doit PAS laisser CREATE a PUBLIC (=UC/...). Depuis PG15 c''est le defaut.'

\echo ''
\echo '=== 7. Tables accessibles par PUBLIC (privileges directs) ==='
-- grantee = 0 dans l'ACL explosee designe PUBLIC
SELECT n.nspname AS schema, c.relname AS table_,
       string_agg(DISTINCT ae.privilege_type, ', ') AS public_privs
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
CROSS JOIN LATERAL aclexplode(c.relacl) AS ae
WHERE c.relkind IN ('r','p','v','m')
  AND n.nspname NOT IN ('pg_catalog','information_schema')
  AND ae.grantee = 0
GROUP BY 1, 2
ORDER BY 1, 2;
\echo '   -> Idealement AUCUNE ligne : PUBLIC ne doit pas avoir de privileges directs sur les tables.'

\echo ''
\echo '=== 8. Membres des roles predefinis sensibles ==='
SELECT r.rolname AS role_predefini,
       string_agg(m.rolname, ', ' ORDER BY m.rolname) AS membres
FROM pg_auth_members am
JOIN pg_roles r ON r.oid = am.roleid
JOIN pg_roles m ON m.oid = am.member
WHERE r.rolname IN ('pg_read_server_files','pg_write_server_files',
                    'pg_execute_server_program','pg_read_all_data',
                    'pg_write_all_data','pg_monitor')
GROUP BY r.rolname
ORDER BY r.rolname;

\echo ''
\echo '=== 9. Chiffrement TLS ==='
SELECT current_setting('ssl') AS ssl_active;
SELECT count(*) FILTER (WHERE ssl) AS sessions_tls,
       count(*) FILTER (WHERE NOT ssl) AS sessions_sans_tls
FROM pg_stat_ssl JOIN pg_stat_activity USING (pid)
WHERE backend_type = 'client backend';

\echo ''
\echo '=== 10. Ecoute reseau et connexions ==='
SELECT current_setting('listen_addresses') AS listen_addresses,
       current_setting('port') AS port;
\echo '   -> listen_addresses = ''*'' sans pare-feu strict est a risque.'

\echo ''
\echo '=== 11. Regles pg_hba faibles (necessite droits superuser ; PG10+) ==='
-- pg_hba_file_rules liste les regles telles que chargees
SELECT line_number, type, database, user_name, address, auth_method
FROM pg_hba_file_rules
WHERE auth_method IN ('trust', 'password', 'md5', 'ident')
ORDER BY line_number;
\echo '   -> trust = AUCUNE auth ; password = mot de passe EN CLAIR ; md5 = faible. A corriger.'

\echo ''
\echo '=== 12. Fonctions SECURITY DEFINER sans search_path fige ==='
SELECT n.nspname AS schema, p.proname AS fonction,
       pg_get_userbyid(p.proowner) AS proprietaire,
       coalesce(array_to_string(p.proconfig, ', '), '(AUCUN search_path fige !)') AS config
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE p.prosecdef
  AND n.nspname NOT IN ('pg_catalog','information_schema')
  AND (p.proconfig IS NULL
       OR NOT EXISTS (SELECT 1 FROM unnest(p.proconfig) c WHERE c LIKE 'search_path=%'))
ORDER BY 1, 2;
\echo '   -> Toute fonction SECURITY DEFINER doit figer son search_path (SET search_path).'

\echo ''
\echo '=== 13. Extensions installees (surface d''attaque additionnelle) ==='
SELECT extname, extversion,
       (SELECT nspname FROM pg_namespace WHERE oid = extnamespace) AS schema
FROM pg_extension ORDER BY extname;

\echo ''
\echo '=== 14. Tables sans RLS contenant potentiellement des donnees sensibles ==='
SELECT schemaname, tablename, rowsecurity AS rls_active
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog','information_schema')
ORDER BY rls_active, schemaname, tablename;

\echo ''
\echo '=== 15. Parametres de journalisation de securite ==='
SELECT name, setting FROM pg_settings
WHERE name IN ('log_connections','log_disconnections','log_statement',
               'log_line_prefix','log_min_duration_statement',
               'password_encryption','ssl','shared_preload_libraries')
ORDER BY name;

\echo ''
\echo '########################################################'
\echo '#  FIN DE L''AUDIT — analyser chaque section ci-dessus'
\echo '########################################################'
