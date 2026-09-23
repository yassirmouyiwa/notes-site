# Module 08 — Haute disponibilité et réplication

## Objectifs

- Distinguer réplication physique et logique, synchrone et asynchrone.
- Mettre en place une réplique physique en flux (*streaming replication*) avec slot.
- Superviser le retard de réplication.
- Réaliser une bascule (*failover*) et une reconstruction avec `pg_rewind`.
- Comprendre le risque de *split-brain* et le rôle des outils de bascule automatique (Patroni).
- Mettre en place une réplication logique entre deux clusters.

---

## 1. Concepts

### 1.1 Disponibilité

| Disponibilité | Indisponibilité maximale par an |
|---------------|---------------------------------|
| 99 % | 3,65 jours |
| 99,9 % | 8,8 heures |
| 99,99 % | 53 minutes |
| 99,999 % | 5 minutes |

Au-delà de 99,9 %, une intervention humaine est trop lente : il faut une **bascule automatique**.

### 1.2 Vocabulaire

| Terme | Définition |
|-------|------------|
| **Primaire** (*primary*) | Instance qui accepte les écritures |
| **Réplique / secondaire** (*standby*) | Instance qui rejoue les modifications du primaire |
| **Hot standby** | Réplique accessible en **lecture seule** |
| **Promotion** | Transformation d'une réplique en primaire |
| **Bascule planifiée** (*switchover*) | Inversion volontaire des rôles, sans perte |
| **Bascule sur incident** (*failover*) | Promotion d'une réplique après la perte du primaire |
| **Split-brain** | Deux instances se croient primaires et acceptent des écritures divergentes |

### 1.3 Réplication physique ou logique

| | Physique (streaming) | Logique |
|---|---|---|
| Ce qui est répliqué | Le flux WAL, **octet par octet** | Les **changements de lignes** décodés du WAL |
| Portée | **Tout le cluster** | Tables choisies (publications) |
| Réplique | Lecture seule, copie identique | Base indépendante, accessible en écriture |
| Versions | Même version majeure, même architecture | Versions majeures différentes possibles |
| DDL | Répliqué | **Non répliqué** (à appliquer des deux côtés) |
| Usages | Haute disponibilité, répartition des lectures, sauvegarde | Migration de version majeure, consolidation, alimentation d'un entrepôt, réplication partielle |

---

## 2. Réplication physique en flux

### 2.1 Fonctionnement

```
PRIMAIRE                                            RÉPLIQUE
┌─────────────────────┐    connexion de      ┌─────────────────────┐
│ backends → WAL      │    réplication       │                     │
│         │           │ ◄──────────────────── │ walreceiver         │
│         ▼           │   flux WAL continu   │      │              │
│   walsender ────────┼─────────────────────►│      ▼              │
│                     │                      │ startup (rejoue WAL)│
│  pg_wal/            │                      │  pg_wal/  données   │
└─────────────────────┘                      └─────────────────────┘
```

1. La réplique démarre à partir d'une **copie physique** du primaire (`pg_basebackup`).
2. Son processus **walreceiver** se connecte au primaire, qui lance un **walsender** dédié.
3. Le walsender envoie le WAL au fur et à mesure de sa production.
4. Le processus **startup** de la réplique rejoue le WAL en continu (c'est une reprise après crash qui ne se termine jamais).

### 2.2 Configuration côté primaire

| Paramètre | Valeur | Remarque |
|-----------|--------|----------|
| `wal_level` | `replica` (ou `logical`) | Défaut `replica` |
| `max_wal_senders` | 10 | Défaut suffisant |
| `max_replication_slots` | 10 | Défaut suffisant |
| `wal_keep_size` | 0 (ou quelques Go) | WAL conservé pour les répliques sans slot |
| `hot_standby` | `on` | Sur la réplique : autorise la lecture |

Un rôle dédié et une règle `pg_hba.conf` avec le mot-clé `replication` :

```sql
CREATE ROLE replicator LOGIN REPLICATION;
```
```
hostssl  replication  replicator  10.0.0.12/32  scram-sha-256
```

### 2.3 Configuration côté réplique

La réplique est identifiée par la présence du fichier **`standby.signal`** dans son PGDATA, et configurée par :

```ini
primary_conninfo = 'host=10.0.0.11 port=5432 user=replicator sslmode=verify-full application_name=replique1'
primary_slot_name = 'slot_replique1'
```

`pg_basebackup -R` crée automatiquement `standby.signal` et écrit `primary_conninfo` dans `postgresql.auto.conf`.

### 2.4 Slots de réplication

Sans slot, le primaire peut **recycler** un WAL que la réplique n'a pas encore reçu (réplique arrêtée longtemps, réseau coupé). La réplique est alors désynchronisée et doit être reconstruite.

Un **slot de réplication** oblige le primaire à conserver tout le WAL non encore consommé par la réplique.

```sql
SELECT pg_create_physical_replication_slot('slot_replique1');
SELECT slot_name, slot_type, active, restart_lsn,
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS wal_retenu
FROM pg_replication_slots;
```

> ⚠️ **Danger** : un slot dont la réplique a disparu retient le WAL **indéfiniment** jusqu'à saturer le disque du primaire et l'arrêter. Protection : `max_slot_wal_keep_size` (par exemple `50GB`), au-delà duquel le slot est invalidé plutôt que de laisser le disque se remplir. Et supervision de `wal_retenu`. Supprimer un slot abandonné : `SELECT pg_drop_replication_slot('slot_replique1');`

### 2.5 Synchrone ou asynchrone

Par défaut, la réplication est **asynchrone** : le primaire valide la transaction sans attendre la réplique. En cas de perte du primaire, les dernières transactions non encore transmises sont **perdues** (RPO de quelques millisecondes à quelques secondes).

En **synchrone**, le `COMMIT` attend la confirmation d'une ou plusieurs répliques :

```ini
synchronous_standby_names = 'FIRST 1 (replique1, replique2)'   # la première disponible dans la liste
# ou
synchronous_standby_names = 'ANY 1 (replique1, replique2)'     # n'importe laquelle (quorum)
```

Le niveau d'attente est réglé par `synchronous_commit` :

| Valeur | Le COMMIT attend que la réplique ait… | RPO si perte du primaire |
|--------|---------------------------------------|--------------------------|
| `remote_write` | reçu le WAL et l'ait écrit (pas forcément sur disque) | ≈ 0 sauf crash simultané des deux OS |
| `on` | écrit **et synchronisé** le WAL sur disque | 0 |
| `remote_apply` | **rejoué** le WAL (visible en lecture sur la réplique) | 0, lecture cohérente immédiate |

Coûts : la latence de chaque `COMMIT` augmente de l'aller-retour réseau ; et si **aucune** réplique synchrone ne répond, les `COMMIT` **bloquent**. C'est pourquoi on prévoit au moins deux répliques candidates (`ANY 1 (r1, r2)`).

### 2.6 Répliques en lecture et conflits

Une réplique `hot_standby` exécute des requêtes en lecture. Conflit possible : le primaire a nettoyé (VACUUM) des lignes qu'une longue requête sur la réplique lit encore. La réplique doit alors soit **retarder le rejeu**, soit **annuler la requête**.

| Paramètre (réplique) | Effet |
|----------------------|-------|
| `max_standby_streaming_delay` (30 s) | Durée maximale de retard du rejeu avant d'annuler les requêtes en conflit |
| `hot_standby_feedback = on` | La réplique informe le primaire des lignes encore utiles : moins d'annulations, mais **bloat** possible sur le primaire |

### 2.7 Répliques en cascade et différées

- **Cascade** : une réplique alimente d'autres répliques (réduit la charge réseau du primaire, utile entre sites).
- **Réplique différée** : `recovery_min_apply_delay = '4h'` : la réplique applique le WAL avec 4 heures de retard. En cas de `DROP TABLE` accidentel, on dispose de 4 heures pour l'arrêter et récupérer les données, bien plus vite qu'un PITR complet.

---

## 3. Supervision de la réplication

Sur le **primaire** :

```sql
SELECT application_name, client_addr, state, sync_state,
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), sent_lsn))   AS retard_envoi,
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn)) AS retard_rejeu,
       write_lag, flush_lag, replay_lag
FROM pg_stat_replication;
```

Sur la **réplique** :

```sql
SELECT pg_is_in_recovery();                                  -- true
SELECT status, sender_host, received_lsn, latest_end_time FROM pg_stat_wal_receiver;
SELECT now() - pg_last_xact_replay_timestamp() AS retard_temporel;
```

> Le retard temporel est trompeur quand le primaire n'écrit rien : il augmente alors que la réplique est à jour. Le retard en octets (LSN) est plus fiable.

---

## 4. Bascule

### 4.1 Promotion d'une réplique

```sql
SELECT pg_promote();            -- depuis la réplique
```
ou
```bash
pg_ctlcluster 16 replique promote
```

La réplique termine le rejeu, crée une nouvelle **timeline** et accepte les écritures.

### 4.2 Le problème de l'ancien primaire

Après un failover, l'ancien primaire ne peut **pas** simplement redevenir réplique : il a peut-être écrit des WAL qui n'ont jamais atteint la nouvelle primaire (divergence de timelines). Deux options :

1. Le reconstruire entièrement avec `pg_basebackup` (lent pour une grosse base).
2. Le resynchroniser avec **`pg_rewind`**, qui ne recopie que les blocs modifiés depuis la divergence.

`pg_rewind` exige `wal_log_hints = on` **ou** les checksums de données activés sur le cluster (encore une raison d'activer les checksums à l'`initdb`).

```bash
pg_rewind --target-pgdata=/var/lib/postgresql/16/main \
          --source-server='host=10.0.0.12 user=postgres dbname=postgres' \
          --progress
```

Puis créer `standby.signal`, configurer `primary_conninfo` vers la nouvelle primaire, démarrer.

### 4.3 Le split-brain et le fencing

Scénario : le réseau entre les deux serveurs est coupé. La réplique ne voit plus le primaire et se fait promouvoir. Mais l'ancien primaire fonctionne toujours et les applications qui le voient encore continuent d'y écrire. Deux bases divergentes, **toutes deux fausses** : c'est le **split-brain**, le pire scénario en HA.

Protections :

- **Consensus** : la décision de bascule est prise par une majorité (quorum) d'arbitres (etcd, Consul, ZooKeeper), jamais par une réplique seule.
- **Fencing** (isolement) : s'assurer que l'ancien primaire est **arrêté** ou **coupé** avant de promouvoir (STONITH : *Shoot The Other Node In The Head*, via IPMI, API cloud…).
- **Watchdog** : un primaire qui perd le contact avec le quorum s'arrête lui-même.

### 4.4 Outils de bascule automatique

| Outil | Principe |
|-------|----------|
| **Patroni** | Référence : chaque nœud est piloté par un agent qui s'appuie sur un magasin de consensus distribué (etcd, Consul, ZooKeeper, Kubernetes). Gère la bascule, le fencing via watchdog, la reconstruction, la configuration. Expose une API REST. |
| **repmgr** | Plus simple ; gestion des répliques et bascule ; sans consensus distribué natif, plus exposé au split-brain |
| **pg_auto_failover** | Un nœud « moniteur » arbitre ; simple à déployer |
| **CloudNativePG** | Opérateur Kubernetes |

Architecture Patroni typique :

```
            ┌──────── etcd (3 nœuds, quorum) ────────┐
            │                                         │
   ┌────────┴───────┐   ┌────────────────┐   ┌───────┴────────┐
   │ Patroni + PG   │   │ Patroni + PG   │   │ Patroni + PG   │
   │ (primaire)     │   │ (réplique)     │   │ (réplique)     │
   └────────▲───────┘   └────────▲───────┘   └────────▲───────┘
            └──────────── HAProxy / VIP ──────────────┘
                              ▲
                         Applications
```

### 4.5 Rediriger les applications

- **Adresse IP virtuelle** (VIP, keepalived) qui suit le primaire.
- **HAProxy** qui interroge l'API de Patroni (`/primary`, `/replica`) pour router.
- **libpq multi-hôtes** : le pilote essaie les serveurs dans l'ordre et ne garde que celui qui accepte les écritures :
  ```
  postgresql://app@srv1:5432,srv2:5432/banque?target_session_attrs=read-write
  ```

> 🔐 **Angle sécurité**
> Le flux de réplication contient **toutes** les modifications de données : il doit être chiffré (`hostssl` + `sslmode=verify-full`). Le rôle `REPLICATION` permet de copier l'intégralité du cluster avec `pg_basebackup`, y compris les hachages de mots de passe de `pg_authid` : c'est un privilège à protéger comme un superutilisateur (mot de passe fort ou certificat, restriction d'adresse IP stricte). Les répliques doivent recevoir les mêmes durcissements que le primaire : un attaquant cherchera le maillon le plus faible.

---

## 5. Réplication logique

### 5.1 Principe

Le primaire **décode** son WAL en changements de lignes (INSERT/UPDATE/DELETE) grâce à `wal_level = logical`, et les envoie aux abonnés.

- **Publication** (côté source) : un ensemble de tables à diffuser.
- **Souscription** (côté destination) : connexion à une publication ; copie initiale des données, puis flux continu.

```sql
-- Source (wal_level = logical, redémarrage nécessaire)
CREATE PUBLICATION pub_referentiel FOR TABLE bank.agences, bank.clients;
-- ou : FOR TABLES IN SCHEMA bank (PG 15+), FOR ALL TABLES
-- PG 15+ : filtrage des lignes et des colonnes
CREATE PUBLICATION pub_tetouan FOR TABLE bank.clients (id_client, nom, prenom, id_agence) WHERE (id_agence = 1);

-- Destination (les tables doivent déjà exister)
CREATE SUBSCRIPTION sub_referentiel
    CONNECTION 'host=10.0.0.11 dbname=banque user=replicator_logique sslmode=verify-full'
    PUBLICATION pub_referentiel;
```

### 5.2 Limites à connaître

- Le **DDL** n'est pas répliqué : toute modification de structure doit être appliquée sur la destination (d'abord) et sur la source.
- Les **séquences** ne sont pas synchronisées (à recaler lors d'une migration).
- Les tables sans clé primaire ne peuvent répliquer `UPDATE`/`DELETE` qu'avec `REPLICA IDENTITY FULL` (lent).
- Un conflit (clé déjà présente sur la destination) **arrête** la souscription jusqu'à résolution manuelle.
- Un slot logique est créé sur la source : même danger de rétention de WAL qu'en physique.

### 5.3 Cas d'usage phare : migration de version majeure quasi sans interruption

1. Installer la nouvelle version, créer la structure (`pg_dump -s`).
2. Publication sur l'ancienne, souscription sur la nouvelle.
3. Attendre la synchronisation, vérifier.
4. Couper l'application quelques secondes, recaler les séquences, basculer les connexions.

---

## TP 8 — Construire une architecture répliquée

On utilise trois clusters sur la même VM :

| Cluster | Port | Rôle |
|---------|------|------|
| `16/main` | 5432 | Primaire |
| `16/replique` | 5433 | Réplique physique |
| `16/analytique` | 5434 | Destination de réplication logique |

> Snapshot de la VM avant de commencer. Si tu as fait le TP 6, la ligne `replication` de `pg_hba.conf`, le rôle `replicator` et le fichier `~/.pgpass` du compte `postgres` sont déjà en place. Sinon, reprends la partie B du TP 6.

### Partie A — Préparer le primaire

Les checksums ne peuvent pas être activés à chaud. S'ils sont désactivés sur ton cluster, active `wal_log_hints`, indispensable à `pg_rewind` (partie F) :

```sql
postgres=# SHOW data_checksums;
postgres=# SHOW wal_level;
postgres=# ALTER SYSTEM SET wal_log_hints = on;       -- nécessaire à pg_rewind si pas de checksums
postgres=# ALTER SYSTEM SET max_slot_wal_keep_size = '2GB';
```

```bash
$ sudo systemctl restart postgresql@16-main
```

```sql
postgres=# SELECT pg_create_physical_replication_slot('slot_replique');
```

### Partie B — Créer la réplique

```bash
$ sudo pg_createcluster 16 replique --port 5433
$ sudo rm -rf /var/lib/postgresql/16/replique/*
$ sudo -u postgres pg_basebackup -h 127.0.0.1 -p 5432 -U replicator \
       -D /var/lib/postgresql/16/replique -Fp -Xs -P -R -S slot_replique
$ sudo cat /var/lib/postgresql/16/replique/postgresql.auto.conf
$ sudo ls /var/lib/postgresql/16/replique/standby.signal
```

`-R` a écrit `primary_conninfo` et `primary_slot_name` dans `postgresql.auto.conf`, et créé `standby.signal`.

Les fichiers de configuration Debian de la réplique (`/etc/postgresql/16/replique/`) sont indépendants : copie les réglages utiles du primaire (journalisation, `pg_hba.conf`) :

```bash
$ sudo cp /etc/postgresql/16/main/pg_hba.conf /etc/postgresql/16/replique/pg_hba.conf
$ sudo cp /etc/postgresql/16/main/conf.d/10-formation.conf /etc/postgresql/16/replique/conf.d/
$ sudo chown -R postgres:postgres /etc/postgresql/16/replique
$ sudo pg_ctlcluster 16 replique start
$ pg_lsclusters
```

> Si tu as activé l'archivage (TP 6), la réplique a hérité `archive_mode` du fichier `conf.d/20-archivage.conf` seulement si tu l'as copié : ne le copie pas, deux instances ne doivent pas archiver dans le même répertoire.

### Partie C — Vérifier la réplication

**Primaire** (port 5432) :

```sql
postgres=# SELECT application_name, state, sync_state, replay_lag FROM pg_stat_replication;
postgres=# SELECT slot_name, active FROM pg_replication_slots;
```

**Réplique** :

```bash
$ sudo -u postgres psql -p 5433 -d banque
```
```sql
banque=# SELECT pg_is_in_recovery();
banque=# SELECT count(*) FROM bank.agences;
banque=# INSERT INTO bank.agences VALUES (7, 'Oujda', 'Oriental');
-- ERROR: cannot execute INSERT in a read-only transaction
```

**Primaire** :

```sql
banque=# INSERT INTO bank.agences VALUES (7, 'Oujda', 'Oriental');
```

**Réplique** : l'agence 7 est visible quasi instantanément.

### Partie D — Retard et slot

Arrête la réplique, génère de l'activité, observe le WAL retenu par le slot :

```bash
$ sudo pg_ctlcluster 16 replique stop
```
```sql
-- primaire
banque=# UPDATE bank.comptes SET solde = solde + 0;
banque=# SELECT slot_name, active,
                pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS wal_retenu
         FROM pg_replication_slots;
```
```bash
$ sudo pg_ctlcluster 16 replique start
```

Observe le rattrapage dans `pg_stat_replication` (`state` passe de `catchup` à `streaming`).

### Partie E — Réplication synchrone

Le nom à placer dans `synchronous_standby_names` est l'`application_name` de la réplique. Faute de valeur explicite dans `primary_conninfo`, la réplique utilise son paramètre `cluster_name`, que Debian règle à `16/replique`. Vérifie-le :

```sql
-- primaire
postgres=# SELECT application_name, sync_state FROM pg_stat_replication;
postgres=# ALTER SYSTEM SET synchronous_standby_names = '"16/replique"';   -- guillemets doubles : le nom contient un /
postgres=# SELECT pg_reload_conf();
postgres=# SELECT application_name, sync_state FROM pg_stat_replication;   -- sync
```

Arrête la réplique, puis tente une écriture sur le primaire :

```bash
$ sudo pg_ctlcluster 16 replique stop
```
```sql
banque=# INSERT INTO bank.agences VALUES (8, 'Agadir', 'Souss-Massa');   -- bloque !
```

Dans une autre session, annule la requête bloquée ou redémarre la réplique. Constat : sans réplique synchrone disponible, les écritures s'arrêtent. Remets la réplication en asynchrone :

```sql
postgres=# ALTER SYSTEM RESET synchronous_standby_names;
postgres=# SELECT pg_reload_conf();
```

```bash
$ sudo pg_ctlcluster 16 replique start
```

### Partie F — Failover et pg_rewind

Simule la perte du primaire :

```bash
$ sudo pg_ctlcluster 16 main stop -m immediate
$ sudo -u postgres psql -p 5433 -c "SELECT pg_promote();"
$ sudo -u postgres psql -p 5433 -c "SELECT pg_is_in_recovery();"      # false
$ sudo -u postgres psql -p 5433 -d banque -c "INSERT INTO bank.agences VALUES (9, 'Nador', 'Oriental');"
```

La réplique est devenue primaire (port 5433). Reconstruis l'ancien primaire comme réplique de la nouvelle primaire avec `pg_rewind` :

```bash
$ sudo -u postgres /usr/lib/postgresql/16/bin/pg_rewind \
       --target-pgdata=/var/lib/postgresql/16/main \
       --source-server='host=127.0.0.1 port=5433 user=postgres dbname=postgres' \
       --progress
```

`pg_rewind` se connecte en `postgres` sur le port 5433 : la règle `host all all 127.0.0.1/32 scram-sha-256` exige un mot de passe pour `postgres`. Définis-le (`\password postgres`) et ajoute-le au `~/.pgpass`, ou lance plutôt la connexion par socket : `--source-server='host=/var/run/postgresql port=5433 user=postgres dbname=postgres'` (méthode `peer`).

`pg_rewind` a recopié les fichiers de configuration du répertoire de données de la source, dont son `postgresql.auto.conf` : il contient encore `primary_conninfo` et `primary_slot_name` pointant vers l'ancien primaire (5432, c'est-à-dire lui-même). Réécris ce fichier (instance arrêtée) et configure l'ancien primaire en réplique :

```bash
$ sudo -u postgres cat /var/lib/postgresql/16/main/postgresql.auto.conf
$ sudo -u postgres tee /var/lib/postgresql/16/main/postgresql.auto.conf > /dev/null <<'EOF'
# Réécrit après pg_rewind
wal_log_hints = 'on'
max_slot_wal_keep_size = '2GB'
primary_conninfo = 'host=127.0.0.1 port=5433 user=replicator application_name=main'
EOF
$ sudo -u postgres touch /var/lib/postgresql/16/main/standby.signal
$ sudo pg_ctlcluster 16 main start
$ sudo -u postgres psql -p 5433 -c "SELECT application_name, state FROM pg_stat_replication;"
$ sudo -u postgres psql -p 5432 -d banque -c "SELECT * FROM bank.agences WHERE id_agence = 9;"
```

L'ancien primaire est maintenant réplique et a reçu l'agence 9.

**Retour à la situation initiale (switchover)** : arrête proprement la primaire actuelle (5433), promeus `main` (5432), puis reconfigure `replique` comme réplique de `main` (avec `pg_rewind` si nécessaire). Recrée le slot `slot_replique` sur `main` et ajoute `primary_slot_name`. C'est un excellent exercice pour vérifier ta compréhension : écris chaque commande avant de l'exécuter.

### Partie G — Réplication logique

```sql
-- primaire (5432)
postgres=# ALTER SYSTEM SET wal_level = logical;
```
```bash
$ sudo systemctl restart postgresql@16-main
$ sudo pg_createcluster 16 analytique --port 5434 --start
```

Rôle de réplication logique (sur le primaire) et règle `pg_hba.conf` : les connexions de réplication logique visent une **base précise** et sont couvertes par les règles de base normales (pas par le mot-clé `replication`) :

```sql
-- primaire
banque=# CREATE ROLE replicator_logique LOGIN REPLICATION;
banque=# \password replicator_logique
banque=# GRANT CONNECT ON DATABASE banque TO replicator_logique;
banque=# GRANT USAGE ON SCHEMA bank TO replicator_logique;
banque=# GRANT SELECT ON bank.agences, bank.operations TO replicator_logique;
banque=# CREATE PUBLICATION pub_analytique FOR TABLE bank.agences, bank.operations;
```

La règle `host all all 127.0.0.1/32 scram-sha-256` couvre déjà cette connexion.

Destination (5434) : créer la base et la structure, puis s'abonner :

```bash
$ sudo -u postgres createdb -p 5434 banque_analytique
$ sudo -u postgres pg_dump -p 5432 -d banque -s -t bank.agences -t bank.operations \
    | sudo -u postgres psql -p 5434 -d banque_analytique
```

Le `pg_dump -s` contient des `ALTER … OWNER TO banque_owner` et des `GRANT` vers des rôles qui n'existent pas sur ce cluster : des erreurs s'affichent, sans conséquence ici. Ajoute l'option `--no-owner --no-privileges` pour les éviter.

```sql
-- destination (5434), base banque_analytique
banque_analytique=# CREATE SUBSCRIPTION sub_analytique
    CONNECTION 'host=127.0.0.1 port=5432 dbname=banque user=replicator_logique password=<mot_de_passe>'
    PUBLICATION pub_analytique;
banque_analytique=# SELECT * FROM pg_stat_subscription;
banque_analytique=# SELECT count(*) FROM bank.operations;
```

> Le mot de passe dans `CONNECTION` est stocké dans le catalogue `pg_subscription`, lisible par les superutilisateurs de la destination. En production, préférer un fichier `.pgpass` du compte système ou l'authentification par certificat.

Teste : insère une agence sur le primaire, vérifie qu'elle arrive sur `analytique`. Crée ensuite sur `analytique` une table ou un index propre à l'analyse (possible, car la base est accessible en écriture), ce qui est impossible sur une réplique physique.

Provoque un conflit : insère sur `analytique` une agence d'identifiant 10, puis la même sur le primaire. Observe l'erreur dans le journal du cluster `analytique` et l'arrêt de l'application des changements. Résous-le en supprimant la ligne en conflit côté destination.

Nettoyage en fin de TP (dans l'ordre) :

```sql
-- destination
banque_analytique=# DROP SUBSCRIPTION sub_analytique;     -- supprime aussi le slot sur la source
```
```bash
$ sudo pg_dropcluster 16 analytique --stop
```

Garde la réplique physique : elle servira au projet final.

---

## Exercices

1. Un client exige « zéro perte de données et bascule en moins de 30 secondes » pour deux datacenters distants de 300 km. Propose une architecture et discute du coût en latence de la réplication synchrone.
2. Le disque du primaire est plein. `pg_wal` occupe 180 Go. Quelles sont les causes possibles liées à la réplication et à l'archivage, et comment les diagnostiquer ?
3. Explique, avec un schéma temporel, comment un split-brain peut se produire avec deux nœuds et une bascule déclenchée par un simple script de surveillance.
4. Pourquoi `hot_standby_feedback = on` peut-il provoquer du bloat sur le primaire ?
5. Rédige la procédure de migration de PostgreSQL 16 vers 17 par réplication logique, avec les points de vérification et le plan de retour arrière.

---

## Quiz

1. Quelle est la différence fondamentale entre réplication physique et logique ?
2. Quel fichier indique à une instance qu'elle est une réplique ?
3. Quel est le rôle d'un slot de réplication et quel est son danger ?
4. Quel paramètre limite le WAL retenu par un slot ?
5. Que se passe-t-il si la seule réplique synchrone tombe ?
6. Que fait `pg_rewind` et quelle est sa condition préalable ?
7. Qu'est-ce que le split-brain et comment Patroni l'évite-t-il ?
8. Le DDL est-il répliqué en réplication logique ?
9. Pourquoi une réplique différée est-elle utile ?
10. Pourquoi le rôle `REPLICATION` est-il sensible du point de vue sécurité ?

*Corrigés : [annexe D](annexes/D-corriges.md#module-08).*

---

## À retenir

- Physique = copie du cluster entier en lecture seule (HA) ; logique = tables choisies, base indépendante (migrations, intégration).
- Slots : indispensables mais à surveiller, avec `max_slot_wal_keep_size`.
- Synchrone = RPO nul mais latence et risque de blocage : au moins deux répliques candidates.
- Bascule automatique uniquement avec consensus et fencing (Patroni + etcd) ; `pg_rewind` pour réintégrer l'ancien primaire.
- Réplication chiffrée, rôle `REPLICATION` protégé, répliques durcies comme le primaire.
