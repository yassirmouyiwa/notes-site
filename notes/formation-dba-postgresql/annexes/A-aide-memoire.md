# Annexe A — Aide-mémoire

Référence condensée des commandes les plus utiles. Chemins Debian/Ubuntu (`/etc/postgresql/16/main/`, `/var/lib/postgresql/16/main/`).

---

## Rappel PATH Debian/Ubuntu

Les binaires courants (`psql`, `pg_dump`, `pg_restore`, `pg_basebackup`, `pgbench`, `vacuumdb`…) sont dans `/usr/bin`. Mais certains outils ne sont **que** dans le répertoire de version :

```
/usr/lib/postgresql/16/bin/
```

C'est le cas de `pg_ctl`, `initdb`, `pg_upgrade`, `pg_rewind`, `pg_waldump`, `pg_verifybackup`, `pg_combinebackup`, `pg_resetwal`, `pg_controldata`.

Ajouter ce répertoire au PATH pour la session :

```bash
export PATH=/usr/lib/postgresql/16/bin:$PATH
# le rendre permanent :
echo 'export PATH=/usr/lib/postgresql/16/bin:$PATH' >> ~/.profile && source ~/.profile
```

Sous Debian/Ubuntu, préférer les **wrappers de cluster** quand ils existent : `pg_ctlcluster`, `pg_createcluster`, `pg_dropcluster`, `pg_upgradecluster`, `pg_lsclusters`.

---

## Gestion du service et du cluster

```bash
pg_lsclusters                                 # lister les clusters et leur état
sudo pg_ctlcluster 16 main start|stop|restart|reload
sudo systemctl start|stop|restart postgresql@16-main
sudo systemctl status postgresql@16-main
pg_isready -h 127.0.0.1 -p 5432               # l'instance répond-elle ?
```

Dans un conteneur sans systemd (lab) :

```bash
pg_ctlcluster 16 main start                   # à relancer si "Connection refused"
```

---

## Connexion avec psql

```bash
psql -U postgres -d banque                    # utilisateur / base
psql -h 127.0.0.1 -p 5432 -U app_banque -d banque
psql "host=localhost dbname=banque user=app_banque sslmode=verify-full sslrootcert=root.crt"
sudo -u postgres psql                          # via l'utilisateur système (peer)
psql -d banque -f script.sql                   # exécuter un fichier
psql -d banque -c "SELECT 1;"                  # exécuter une commande
```

---

## Méta-commandes psql

| Commande | Rôle |
|----------|------|
| `\l` (`\l+`) | Lister les bases (+ tailles) |
| `\c base` | Se connecter à une autre base |
| `\dn` | Lister les schémas |
| `\dt` (`\dt+`) | Lister les tables (+ taille) |
| `\dt bank.*` | Tables du schéma `bank` |
| `\d table` | Décrire une table (colonnes, index, contraintes) |
| `\d+ table` | Description détaillée (+ stockage, description) |
| `\di` / `\dv` / `\dm` | Index / vues / vues matérialisées |
| `\df` | Lister les fonctions |
| `\du` (`\du+`) | Lister les rôles et leurs attributs |
| `\dp` / `\z` | Privilèges sur les tables |
| `\ddp` | Privilèges par défaut |
| `\dx` | Extensions installées |
| `\dconfig` | Paramètres de configuration |
| `\x` | Affichage étendu (une colonne par ligne) — pratique pour les lignes larges |
| `\timing` | Afficher le temps d'exécution |
| `\e` | Éditer la dernière requête dans l'éditeur |
| `\i fichier` | Exécuter un fichier SQL |
| `\o fichier` | Rediriger la sortie vers un fichier |
| `\copy` | Import/export CSV côté client |
| `\watch 5` | Réexécuter la requête toutes les 5 s |
| `\conninfo` | Détails de la connexion courante |
| `\password role` | Changer un mot de passe (haché, sans le mettre en clair) |
| `\! commande` | Exécuter une commande shell |
| `\q` | Quitter |

---

## Administration SQL courante

```sql
-- Rôles
CREATE ROLE lecteur LOGIN PASSWORD '...' CONNECTION LIMIT 10;
CREATE ROLE r_groupe NOLOGIN;
GRANT r_groupe TO lecteur;
ALTER ROLE lecteur VALID UNTIL '2026-12-31';
ALTER ROLE lecteur SET statement_timeout = '30s';
DROP ROLE lecteur;

-- Privilèges
GRANT SELECT, INSERT ON bank.comptes TO r_groupe;
GRANT USAGE ON SCHEMA bank TO r_groupe;
REVOKE ALL ON bank.comptes FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA bank GRANT SELECT ON TABLES TO r_lecture;

-- Bases et schémas
CREATE DATABASE ma_base OWNER banque_owner;
CREATE SCHEMA bank AUTHORIZATION banque_owner;

-- Configuration
SHOW shared_buffers;
ALTER SYSTEM SET work_mem = '32MB';        -- écrit dans postgresql.auto.conf
SELECT pg_reload_conf();                    -- recharge (paramètres SIGHUP)
SELECT name, setting, unit, context FROM pg_settings WHERE name = 'work_mem';
SELECT * FROM pg_file_settings WHERE error IS NOT NULL;   -- erreurs de config

-- Maintenance
VACUUM (VERBOSE, ANALYZE) bank.comptes;
ANALYZE bank.operations;
REINDEX INDEX CONCURRENTLY bank.idx_xxx;
CLUSTER bank.table USING idx;
```

---

## Inspection et diagnostic

```sql
-- Tailles
SELECT pg_size_pretty(pg_database_size('banque'));
SELECT pg_size_pretty(pg_total_relation_size('bank.operations'));
SELECT pg_size_pretty(pg_relation_size('bank.operations'));

-- Activité et verrous
SELECT pid, usename, state, wait_event, query FROM pg_stat_activity WHERE state <> 'idle';
SELECT pg_blocking_pids(pid), pid, query FROM pg_stat_activity WHERE cardinality(pg_blocking_pids(pid)) > 0;
SELECT pg_cancel_backend(pid);              -- annuler la requête
SELECT pg_terminate_backend(pid);           -- fermer la session

-- Plans
EXPLAIN SELECT ...;                          -- plan estimé
EXPLAIN (ANALYZE, BUFFERS) SELECT ...;       -- plan réel + I/O (exécute la requête)

-- Réplication (primaire)
SELECT * FROM pg_stat_replication;
SELECT slot_name, active, restart_lsn FROM pg_replication_slots;
-- Réplication (réplique)
SELECT pg_is_in_recovery();                  -- true sur une réplique
SELECT * FROM pg_stat_wal_receiver;
```

---

## Outils en ligne de commande

```bash
# Sauvegarde / restauration logique
pg_dump -Fc -d banque -f banque.dump               # format custom (recommandé)
pg_dump -Fp -d banque -f banque.sql                # format SQL texte
pg_dumpall --globals-only -f roles.sql             # rôles et paramètres globaux
pg_restore -d banque_restore --clean --if-exists banque.dump
pg_restore -l banque.dump                          # lister le contenu d'un dump custom

# Sauvegarde physique
pg_basebackup -D /chemin -Fp -Xs -P -R -h primaire -U replicator   # -R : génère la conf de réplique
pg_verifybackup /chemin/sauvegarde                 # (dans /usr/lib/postgresql/16/bin)

# WAL et contrôle (dans /usr/lib/postgresql/16/bin)
pg_waldump 0000000100000000000000AB                # inspecter un segment WAL
pg_controldata /var/lib/postgresql/16/main         # état du cluster
pg_rewind --target-pgdata=... --source-server=...  # resynchroniser un ancien primaire

# Divers
vacuumdb --all --analyze-in-stages                 # après une migration majeure
reindexdb --concurrently -d banque
pgbench -i -s 50 banque                             # initialiser un jeu de test
pgbench -c 10 -T 60 banque                          # test de charge
createdb / dropdb / createuser / dropuser
```

---

## Fichiers importants (Debian/Ubuntu)

| Fichier | Rôle |
|---------|------|
| `/etc/postgresql/16/main/postgresql.conf` | Configuration principale |
| `/etc/postgresql/16/main/conf.d/*.conf` | Surcharges modulaires (recommandé) |
| `/etc/postgresql/16/main/pg_hba.conf` | Contrôle d'accès client |
| `/etc/postgresql/16/main/pg_ident.conf` | Correspondances d'identité |
| `/var/lib/postgresql/16/main/` | PGDATA (données) |
| `/var/lib/postgresql/16/main/postgresql.auto.conf` | Écrit par `ALTER SYSTEM` |
| `/var/lib/postgresql/16/main/pg_wal/` | Journaux WAL |
| `/var/log/postgresql/postgresql-16-main.log` | Journal du serveur |
| `~/.pgpass` | Mots de passe (mode `0600`) : `hôte:port:base:user:mdp` |
| `~/.psqlrc` | Configuration personnelle de psql |

Format `.pgpass` (le port peut être un joker `*`) :

```
127.0.0.1:*:*:replicator:motdepasse
```

---

## Sauvegarde/restauration : mémo PITR

```bash
# 1. Sauvegarde de base + archivage WAL en continu (archive_command configuré)
pg_basebackup -D /sauv/base -Fp -Xs -P

# 2. Restauration à un instant précis :
#    - restaurer la sauvegarde de base dans PGDATA
#    - fournir restore_command dans postgresql.conf
#    - définir la cible :
#        recovery_target_time = '2026-09-23 14:30:00+01'
#        recovery_target_action = 'promote'
#    - créer le fichier signal :
touch /var/lib/postgresql/16/main/recovery.signal
#    - démarrer : PostgreSQL rejoue les WAL jusqu'à la cible
```

Voir le module 06 pour la procédure complète et le runbook.
