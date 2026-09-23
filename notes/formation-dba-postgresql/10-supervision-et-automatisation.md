# Module 10 — Supervision et automatisation

## Objectifs

- Définir les métriques clés à surveiller et leurs seuils.
- Exploiter les vues de statistiques de PostgreSQL.
- Mettre en place une supervision (Prometheus + Grafana) et des contrôles de santé.
- Automatiser les tâches récurrentes de maintenance.
- Analyser les journaux avec pgBadger.
- Conduire une montée de version majeure.
- Disposer d'une méthode et de runbooks pour les incidents.

---

## 1. Que surveiller ?

### 1.1 Les quatre familles

| Famille | Exemples de métriques | Pourquoi |
|---------|----------------------|----------|
| **Disponibilité** | L'instance répond-elle ? réplication active ? | Détecter une panne |
| **Saturation** | Connexions / max, disque, RAM, CPU, WAL en attente | Anticiper la panne |
| **Performance** | Débit (tps), latence, cache hit ratio, requêtes lentes | Qualité de service |
| **Santé interne** | Tuples morts, âge des XID, bloat, retard de réplication | Prévenir les incidents lents |

### 1.2 Signaux à seuil (à alerter)

| Métrique | Requête / source | Seuil d'alerte usuel |
|----------|------------------|----------------------|
| Instance injoignable | `pg_isready` | immédiat |
| Connexions utilisées | `pg_stat_activity` / `max_connections` | > 80 % |
| Espace disque du volume de données | OS | > 80 % / > 90 % |
| Retard de réplication | `pg_stat_replication` (LSN) | > seuil métier |
| Âge des XID (wraparound) | `age(datfrozenxid)` | 500 M / 1 Md |
| Sessions `idle in transaction` longues | `pg_stat_activity` | > 5 min |
| Attente de verrou longue | `pg_stat_activity` / `pg_locks` | > 30 s |
| Échec d'archivage WAL | `pg_stat_archiver.last_failed_time` | tout échec récent |
| Cache hit ratio | `pg_stat_database` | < 95 % (indicatif) |
| Tuples morts sur grosse table | `pg_stat_user_tables` | > 20 % |

---

## 2. Les vues de statistiques

PostgreSQL expose son état par un riche ensemble de vues.

| Vue | Contenu |
|-----|---------|
| `pg_stat_activity` | Sessions : requête, état, attentes, durée |
| `pg_stat_database` | Par base : commits, rollbacks, cache, tuples lus/écrits, deadlocks, fichiers temporaires |
| `pg_stat_user_tables` | Par table : scans, tuples, tuples morts, dates de (auto)vacuum/analyze |
| `pg_stat_user_indexes` | Par index : utilisation |
| `pg_statio_user_tables` | Entrées/sorties par table (cache vs disque) |
| `pg_stat_replication` | Réplication côté primaire |
| `pg_stat_wal_receiver` | Réplication côté réplique |
| `pg_stat_archiver` | Archivage WAL |
| `pg_stat_bgwriter` / `pg_stat_checkpointer` (PG 17+) | Checkpoints, écritures d'arrière-plan |
| `pg_stat_statements` | Requêtes agrégées (module 07) |
| `pg_stat_progress_*` | Progression : `vacuum`, `analyze`, `create_index`, `basebackup`, `copy` |

Cache hit ratio :

```sql
SELECT datname,
       round(100.0 * blks_hit / nullif(blks_hit + blks_read, 0), 2) AS cache_hit_pct,
       xact_commit, xact_rollback, deadlocks, temp_files,
       pg_size_pretty(temp_bytes) AS temp
FROM pg_stat_database
WHERE datname NOT LIKE 'template%'
ORDER BY blks_hit + blks_read DESC;
```

> Un cache hit ratio faible n'est pas toujours un problème (parcours analytiques légitimes) ; un ratio élevé ne garantit pas de bonnes performances. À interpréter avec le contexte.

Le fichier `scripts/sql/requetes_supervision.sql` regroupe ces requêtes prêtes à l'emploi.

---

## 3. Contrôles de santé

### 3.1 Contrôle rapide

```bash
pg_isready -h 127.0.0.1 -p 5432        # code retour 0 si prêt
```

### 3.2 Script au format monitoring

Le script `scripts/bash/verifier_sante.sh` renvoie les codes de sortie standard (0 OK, 1 WARNING, 2 CRITICAL) attendus par Nagios/Icinga, et vérifie : accessibilité, connexions, retard de réplication, âge des XID, échec d'archivage, sessions bloquées longues.

### 3.3 check_postgres et pgwatch

- **check_postgres** : script de référence couvrant des dizaines de contrôles (bloat, âge des XID, connexions, réplication…), intégrable à Nagios/Icinga.
- **pgwatch**, **pgmonitor** : solutions de supervision plus complètes.

---

## 4. Supervision avec Prometheus et Grafana

Architecture standard :

```
PostgreSQL ──► postgres_exporter ──► Prometheus ──► Grafana (tableaux de bord)
                                          │
                                     Alertmanager ──► e-mail / Slack / astreinte
```

- **postgres_exporter** interroge les vues de statistiques et expose des métriques au format Prometheus.
- **Prometheus** collecte et stocke les séries temporelles.
- **Grafana** affiche des tableaux de bord (des modèles PostgreSQL prêts à l'emploi existent).
- **Alertmanager** déclenche les alertes selon des règles.

Le compte de supervision utilise `pg_monitor`, jamais un superutilisateur (module 04) :

```sql
CREATE ROLE exporter LOGIN PASSWORD '...' CONNECTION LIMIT 5;
GRANT pg_monitor TO exporter;
```

> 🔐 L'endpoint de métriques (`:9187/metrics`) expose des informations sur la base (noms, volumes, activité) : il doit être sur un réseau d'administration, pas exposé publiquement.

---

## 5. Automatisation de la maintenance

### 5.1 Ce qui est déjà automatique

L'**autovacuum** gère VACUUM et ANALYZE (module 05). On l'ajuste, on ne le remplace pas.

### 5.2 Tâches à planifier

| Tâche | Fréquence | Outil |
|-------|-----------|-------|
| Sauvegarde logique / physique | quotidien / continu | cron, pgBackRest (module 06) |
| Test de restauration | mensuel | script automatisé |
| Vérification de sauvegarde | à chaque sauvegarde | `pg_verifybackup` |
| Réindexation d'index gonflés | selon bloat | `REINDEX … CONCURRENTLY` |
| Rafraîchissement de vues matérialisées | selon besoin | `REFRESH … CONCURRENTLY` |
| Purge de partitions anciennes | mensuel | `DROP`/`DETACH` (module 03), pg_partman |
| Rotation et archivage des journaux | quotidien | logrotate |
| Rapport pgBadger | quotidien | cron |
| Contrôle de santé | continu | monitoring |

### 5.3 Planification : cron ou pg_cron

**cron** (côté système) pour les tâches d'exploitation :

```cron
30 1 * * *   /usr/local/bin/sauvegarde_logique.sh banque >> /var/log/postgresql/sauvegarde.log 2>&1
0  3 * * 0   psql -d banque -c "REINDEX INDEX CONCURRENTLY bank.idx_operations_compte_date;"
*/5 * * * *  /usr/local/bin/verifier_sante.sh || echo "ALERTE santé" | mail -s "PG" astreinte@exemple.ma
```

**pg_cron** (extension) pour planifier des tâches **en base**, pratique en environnement managé :

```sql
CREATE EXTENSION pg_cron;
SELECT cron.schedule('purge-journaux', '0 2 * * *',
                     $$ DELETE FROM bank.journal WHERE date_op < now() - interval '90 days' $$);
SELECT * FROM cron.job;
```

### 5.4 Infrastructure as Code

En production sérieuse, la configuration n'est pas éditée à la main mais gérée par **Ansible**, **Terraform** ou un opérateur Kubernetes (CloudNativePG). Avantages : reproductibilité, revue, versionnage, cohérence entre environnements. Le paramètre `allow_alter_system = off` (PG 17+) empêche alors qu'un `ALTER SYSTEM` diverge de la configuration gérée.

---

## 6. Analyse des journaux avec pgBadger

**pgBadger** transforme les journaux PostgreSQL en rapport HTML détaillé : requêtes les plus lentes et les plus fréquentes, pics d'activité, erreurs, attentes de verrous, connexions, checkpoints, fichiers temporaires.

Prérequis dans la configuration (module 02) : un `log_line_prefix` complet et `log_min_duration_statement` actif.

```bash
pgbadger /var/log/postgresql/postgresql-16-main.log -o rapport.html
# Journaux compressés et multiples, sur une période
pgbadger /var/log/postgresql/*.log.* -o rapport_$(date +%F).html
# Mode incrémental quotidien
pgbadger -I -O /var/www/pgbadger/ /var/log/postgresql/postgresql-16-main.log
```

À planifier quotidiennement pour disposer d'une vue de l'activité et repérer les tendances.

---

## 7. Montée de version majeure

### 7.1 Rappel

- **Mineure** (16.3 → 16.4) : remplacer les binaires, redémarrer. Rapide, sans conversion.
- **Majeure** (16 → 17) : format interne potentiellement différent, migration nécessaire.

### 7.2 Trois méthodes

| Méthode | Interruption | Retour arrière | Cas d'usage |
|---------|--------------|----------------|-------------|
| **dump / restore** | Longue (taille de la base) | Facile (l'ancien reste intact) | Petites bases, changement d'architecture |
| **pg_upgrade** | Courte (surtout avec `--link`) | Prévoir une sauvegarde | Grosses bases, même serveur |
| **Réplication logique** | Quasi nulle (module 08) | Facile | Forte exigence de disponibilité |

### 7.3 pg_upgrade

```bash
# Installer la nouvelle version en parallèle, créer le nouveau cluster
sudo pg_upgradecluster 16 main        # outil Debian qui orchestre pg_upgrade
# ou manuellement :
/usr/lib/postgresql/17/bin/pg_upgrade \
    --old-datadir=/var/lib/postgresql/16/main \
    --new-datadir=/var/lib/postgresql/17/main \
    --old-bindir=/usr/lib/postgresql/16/bin \
    --new-bindir=/usr/lib/postgresql/17/bin \
    --check          # d'abord en mode vérification, sans rien modifier
```

L'option `--link` crée des liens durs au lieu de copier : très rapide et peu gourmand en disque, mais l'ancien cluster n'est plus utilisable ensuite (pas de retour arrière simple sans sauvegarde).

Après migration : lancer le script `analyze_new_cluster` (ou `vacuumdb --all --analyze-in-stages`), car les **statistiques ne sont pas transférées** ; sans elles, les premiers plans sont mauvais.

### 7.4 Checklist de migration

1. Lire les **notes de version** de chaque version intermédiaire (changements incompatibles).
2. Tester la migration sur une **copie**.
3. Vérifier la compatibilité des **extensions**.
4. **Sauvegarder** avant.
5. Migrer, puis **ANALYZE**.
6. Tester l'application ; garder l'ancien cluster jusqu'à validation.
7. Prévoir le **retour arrière**.

---

## 8. Gestion des incidents

### 8.1 Méthode

1. **Constater** : quel symptôme, depuis quand, quel périmètre ?
2. **Préserver** : ne pas aggraver ; capturer l'état (`pg_stat_activity`, journaux) avant d'agir.
3. **Diagnostiquer** : de l'observable vers la cause.
4. **Corriger** : la plus petite action qui rétablit le service.
5. **Rétablir** puis **analyser à froid** (*post-mortem*) sans chercher de coupable.

### 8.2 Incidents fréquents et premières actions

| Symptôme | Pistes | Première action |
|----------|--------|-----------------|
| « Trop de connexions » (`too many clients`) | Fuite de connexions, absence de pooler, pic | Connexions réservées (`superuser_reserved_connections`), identifier et terminer les sessions inutiles, PgBouncer |
| Requêtes soudainement lentes | Statistiques obsolètes, plan changé, verrou, bloat | `pg_stat_activity`, `EXPLAIN`, `ANALYZE` |
| Disque plein | WAL non archivé, slot abandonné, bloat, journaux | Identifier la cause (`pg_wal`, slots), **ne jamais supprimer un WAL à la main** |
| Base bloquée en écriture | Wraparound imminent | `age(datfrozenxid)`, VACUUM ciblé d'urgence |
| Réplique décrochée | Slot manquant, WAL recyclé, réseau | `pg_stat_wal_receiver`, journaux, reconstruire si nécessaire |
| Instance ne démarre pas | `pg_hba.conf`/`postgresql.conf` invalide, disque plein, corruption | Journal de démarrage, `pg_file_settings` |
| Corruption détectée (checksum) | Disque, mémoire défaillante | Isoler, restaurer depuis une sauvegarde saine, `pg_amcheck` |

### 8.3 Terminer des sessions en masse (avec prudence)

```sql
-- Sessions idle in transaction depuis plus de 30 min (les inspecter d'abord)
SELECT pid, usename, client_addr, now() - state_change AS inactif, left(query, 60)
FROM pg_stat_activity
WHERE state = 'idle in transaction' AND now() - state_change > interval '30 min';

-- Après vérification, les terminer
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle in transaction' AND now() - state_change > interval '30 min';
```

### 8.4 Runbooks

Un **runbook** est une procédure écrite, testée, exécutable sous stress par l'astreinte. Chaque incident critique (perte du primaire, disque plein, wraparound, restauration PITR) doit avoir le sien : symptômes, diagnostic, actions, vérifications, escalade. Le module 06 en fournit un exemple pour la restauration PITR.

---

## TP 10 — Superviser et automatiser

### Étape 1 : tableau de bord SQL

Ouvre `scripts/sql/requetes_supervision.sql`, exécute chaque section sur ta base et interprète les résultats : activité, cache, tables les plus actives, index inutilisés, tuples morts, âge des XID, réplication (si le TP 8 est en place).

### Étape 2 : contrôle de santé

Installe le script et teste-le dans des conditions normales, puis dégradées :

```bash
$ sudo cp scripts/bash/verifier_sante.sh /usr/local/bin/ && sudo chmod +x /usr/local/bin/verifier_sante.sh
$ /usr/local/bin/verifier_sante.sh ; echo "code retour = $?"
```

Provoque un WARNING : ouvre une transaction `idle in transaction` (Session A : `BEGIN; SELECT 1;`) et attends que le script la détecte (ajuste temporairement le seuil dans le script pour ne pas attendre). Provoque un état CRITICAL en arrêtant la réplique (si TP 8).

### Étape 3 : rapport pgBadger

```bash
$ sudo apt install -y pgbadger
# génère de l'activité puis :
$ sudo -u postgres pgbadger /var/log/postgresql/postgresql-16-main.log -o /tmp/rapport.html
```

Ouvre le rapport (copie-le via le dossier partagé) et repère : requêtes les plus lentes, les plus fréquentes, erreurs, attentes de verrou.

### Étape 4 : automatiser avec cron

Mets en place, pour le compte `postgres`, une sauvegarde quotidienne (script du module 06) et un contrôle de santé toutes les 5 minutes. Vérifie le lendemain que la sauvegarde s'est exécutée et lis son journal.

### Étape 5 (optionnelle) : pg_cron

```sql
banque=# CREATE EXTENSION IF NOT EXISTS pg_cron;   -- nécessite shared_preload_libraries = 'pg_cron' + redémarrage
banque=# SELECT cron.schedule('analyze-nuit', '0 4 * * *', 'ANALYZE');
banque=# SELECT jobid, schedule, command FROM cron.job;
```

### Étape 6 : simuler et résoudre un incident « disque plein WAL »

> Snapshot avant.

Provoque une accumulation de WAL avec un slot abandonné :

```sql
banque=# SELECT pg_create_physical_replication_slot('slot_fantome');
banque=# -- génère du WAL
banque=# UPDATE bank.comptes SET solde = solde + 0;
banque=# SELECT slot_name, active,
                pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS wal_retenu
         FROM pg_replication_slots;
```

Diagnostique (le slot est `active = false` et retient du WAL), puis résous :

```sql
banque=# SELECT pg_drop_replication_slot('slot_fantome');
```

Rédige le mini-runbook correspondant : symptôme (`pg_wal` grossit), diagnostic (slots inactifs, archivage), action (supprimer le slot / réparer l'archivage), prévention (`max_slot_wal_keep_size`, supervision).

---

## Exercices

1. Définis un tableau de dix métriques à superviser pour la base `banque`, avec pour chacune la source, le seuil WARNING, le seuil CRITICAL et l'action associée.
2. Écris une requête qui liste les sessions actives depuis plus de 5 minutes avec leur requête et ce qu'elles attendent, triées par durée.
3. Un `pg_upgrade --link` a été lancé sans sauvegarde et échoue à mi-parcours. Quelle est la situation, et qu'est-ce que cela t'apprend sur la préparation ?
4. Conçois un plan de montée de version 16 → 18 pour une base de 2 To avec un RTO de 15 minutes. Quelle méthode et pourquoi ?
5. Rédige le runbook complet de l'incident « too many clients already ».

---

## Quiz

1. Cite les quatre familles de métriques à surveiller.
2. Quel rôle prédéfini utilise-t-on pour un compte de supervision ?
3. Que renvoie `pg_isready` ?
4. Quelle est la différence entre une version mineure et une version majeure du point de vue de la mise à jour ?
5. Pourquoi faut-il lancer ANALYZE après un `pg_upgrade` ?
6. Que fait l'option `--link` de `pg_upgrade` et quel est son inconvénient ?
7. Quel outil produit un rapport HTML à partir des journaux, et de quoi a-t-il besoin en amont ?
8. Que ne faut-il jamais faire quand `pg_wal` remplit le disque ?
9. Différence entre cron et pg_cron ?
10. Qu'est-ce qu'un runbook et pourquoi est-il indispensable ?

*Corrigés : [annexe D](annexes/D-corriges.md#module-10).*

---

## À retenir

- Superviser : disponibilité, saturation, performance, santé interne — avec des seuils.
- Les vues `pg_stat_*` sont la source ; `pg_monitor` pour le compte de supervision.
- Prometheus + Grafana + Alertmanager pour la supervision continue ; pgBadger pour l'analyse des journaux.
- Automatiser sauvegardes, tests de restauration, maintenance ; Infrastructure as Code en production.
- Montée de version : tester, sauvegarder, ANALYZE après ; prévoir le retour arrière.
- Incidents : constater, préserver, diagnostiquer, corriger a minima, post-mortem ; des runbooks écrits.
