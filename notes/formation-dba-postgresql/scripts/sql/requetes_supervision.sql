-- =====================================================================
--  requetes_supervision.sql — Boîte à outils de supervision PostgreSQL
--  Formation DBA — à exécuter section par section (psql -d banque -f ...)
--  Compatible PostgreSQL 12+ (notes de version indiquées le cas échéant)
-- =====================================================================

\echo '=== 1. Activité : sessions par état ==='
SELECT state,
       count(*)                                             AS sessions,
       max(now() - state_change)                            AS plus_ancienne
FROM pg_stat_activity
WHERE backend_type = 'client backend'
GROUP BY state
ORDER BY sessions DESC;

\echo '=== 2. Connexions utilisées vs max_connections ==='
SELECT count(*)                                             AS connexions,
       current_setting('max_connections')::int             AS max_connections,
       round(100.0 * count(*) / current_setting('max_connections')::int, 1) AS pct
FROM pg_stat_activity;

\echo '=== 3. Requetes actives depuis plus de 30 s ==='
SELECT pid, usename, client_addr,
       now() - query_start                                  AS duree,
       wait_event_type, wait_event,
       left(regexp_replace(query, '\s+', ' ', 'g'), 80)     AS requete
FROM pg_stat_activity
WHERE state = 'active' AND now() - query_start > interval '30 s'
  AND pid <> pg_backend_pid()
ORDER BY duree DESC;

\echo '=== 4. Sessions idle in transaction ==='
SELECT pid, usename, client_addr,
       now() - state_change                                 AS inactif_depuis,
       left(regexp_replace(query, '\s+', ' ', 'g'), 60)     AS derniere_requete
FROM pg_stat_activity
WHERE state = 'idle in transaction'
ORDER BY inactif_depuis DESC;

\echo '=== 5. Verrous : qui bloque qui ==='
SELECT bloque.pid          AS pid_bloque,
       bloque_par.pid      AS pid_bloqueur,
       bloque.usename      AS bloque_user,
       bloque_par.usename  AS bloqueur_user,
       left(bloque.query, 50)     AS requete_bloquee,
       left(bloque_par.query, 50) AS requete_bloqueuse
FROM pg_stat_activity AS bloque
JOIN pg_stat_activity AS bloque_par
     ON bloque_par.pid = ANY(pg_blocking_pids(bloque.pid))
WHERE cardinality(pg_blocking_pids(bloque.pid)) > 0;

\echo '=== 6. Cache hit ratio et compteurs par base ==='
SELECT datname,
       round(100.0 * blks_hit / nullif(blks_hit + blks_read, 0), 2) AS cache_hit_pct,
       xact_commit, xact_rollback, deadlocks,
       temp_files, pg_size_pretty(temp_bytes)               AS temp_total
FROM pg_stat_database
WHERE datname NOT LIKE 'template%' AND datname <> ''
ORDER BY blks_hit + blks_read DESC;

\echo '=== 7. Tables les plus volumineuses ==='
SELECT schemaname, relname,
       pg_size_pretty(pg_total_relation_size(relid))        AS taille_totale,
       pg_size_pretty(pg_relation_size(relid))              AS table_seule,
       pg_size_pretty(pg_total_relation_size(relid) - pg_relation_size(relid)) AS index_toast
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 15;

\echo '=== 8. Tables a fort taux de tuples morts (candidates VACUUM) ==='
SELECT schemaname, relname,
       n_live_tup, n_dead_tup,
       round(100.0 * n_dead_tup / nullif(n_live_tup + n_dead_tup, 0), 1) AS pct_morts,
       last_autovacuum, last_vacuum
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000
ORDER BY n_dead_tup DESC
LIMIT 15;

\echo '=== 9. Tables lues surtout en Seq Scan (index manquant ?) ==='
SELECT schemaname, relname, seq_scan, idx_scan,
       seq_tup_read,
       seq_tup_read / nullif(seq_scan, 0)                   AS lignes_par_seq_scan
FROM pg_stat_user_tables
WHERE seq_scan > 0
ORDER BY seq_tup_read DESC
LIMIT 15;

\echo '=== 10. Index jamais utilises (hors PK et unique) ==='
SELECT s.schemaname, s.relname AS table_, s.indexrelname AS index_,
       s.idx_scan,
       pg_size_pretty(pg_relation_size(s.indexrelid))       AS taille
FROM pg_stat_user_indexes s
JOIN pg_index i ON i.indexrelid = s.indexrelid
WHERE s.idx_scan = 0 AND NOT i.indisunique AND NOT i.indisprimary
ORDER BY pg_relation_size(s.indexrelid) DESC
LIMIT 20;

\echo '=== 11. Age des XID (risque de wraparound) ==='
SELECT datname,
       age(datfrozenxid)                                    AS age_xid,
       round(100.0 * age(datfrozenxid) /
             current_setting('autovacuum_freeze_max_age')::bigint, 1) AS pct_seuil_autovacuum
FROM pg_database
ORDER BY age(datfrozenxid) DESC;

\echo '   (tables les plus agees dans la base courante)'
SELECT c.relname,
       age(c.relfrozenxid)                                  AS age_xid
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'm', 't') AND n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY age(c.relfrozenxid) DESC
LIMIT 10;

\echo '=== 12. Replication (a executer sur le primaire) ==='
SELECT application_name, client_addr, state, sync_state,
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), sent_lsn))   AS retard_envoi,
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn)) AS retard_rejeu,
       write_lag, flush_lag, replay_lag
FROM pg_stat_replication;

\echo '   (slots de replication et WAL retenu)'
SELECT slot_name, slot_type, active,
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS wal_retenu
FROM pg_replication_slots;

\echo '=== 13. Archivage des WAL ==='
SELECT archived_count, last_archived_wal, last_archived_time,
       failed_count, last_failed_wal, last_failed_time
FROM pg_stat_archiver;

\echo '=== 14. Requetes les plus couteuses (necessite pg_stat_statements) ==='
-- Decommente si l'extension est installee :
-- SELECT round(total_exec_time::numeric, 0)  AS total_ms,
--        calls,
--        round(mean_exec_time::numeric, 2)   AS moyen_ms,
--        rows,
--        left(query, 80)                      AS requete
-- FROM pg_stat_statements
-- ORDER BY total_exec_time DESC
-- LIMIT 15;

\echo '=== Fin des requetes de supervision ==='
