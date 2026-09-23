# Module 05 — Transactions, concurrence et MVCC

## Objectifs

- Expliquer les propriétés ACID et les illustrer.
- Comprendre le fonctionnement du MVCC (`xmin`, `xmax`, instantanés).
- Distinguer les niveaux d'isolation et les anomalies qu'ils préviennent.
- Identifier les verrous, les situations de blocage et les deadlocks.
- Comprendre le rôle de VACUUM, de l'autovacuum et le risque de *wraparound*.
- Diagnostiquer une session bloquante et la traiter.

---

## 1. Transactions et ACID

Une **transaction** est un ensemble d'opérations traitées comme une unité indivisible.

| Propriété | Signification | Mécanisme PostgreSQL |
|-----------|---------------|----------------------|
| **Atomicité** | Tout ou rien | Une transaction annulée laisse ses versions de lignes invisibles |
| **Cohérence** | La base passe d'un état valide à un autre | Contraintes (`CHECK`, clés, `NOT NULL`), triggers |
| **Isolation** | Les transactions concurrentes ne se perturbent pas (selon le niveau choisi) | MVCC, verrous, SSI |
| **Durabilité** | Une transaction validée survit à un crash | WAL + `fsync` (module 01) |

### 1.1 Syntaxe

```sql
BEGIN;                                    -- ou START TRANSACTION
UPDATE bank.comptes SET solde = solde - 500 WHERE id_compte = 1;
UPDATE bank.comptes SET solde = solde + 500 WHERE id_compte = 2;
COMMIT;                                   -- ou ROLLBACK pour tout annuler
```

Sans `BEGIN`, chaque instruction est une transaction à elle seule (**autocommit**).

### 1.2 Erreur dans une transaction

Dans PostgreSQL, dès qu'une instruction échoue dans une transaction, **toute la transaction est en échec** : les instructions suivantes sont refusées (`current transaction is aborted, commands ignored until end of transaction block`) jusqu'au `ROLLBACK`. C'est plus strict que certains autres SGBD, et c'est une garantie d'atomicité.

### 1.3 Points de sauvegarde

```sql
BEGIN;
INSERT INTO bank.operations (...) VALUES (...);
SAVEPOINT avant_risque;
UPDATE ... ;                              -- échoue
ROLLBACK TO SAVEPOINT avant_risque;       -- on revient au point de sauvegarde
INSERT ... ;                              -- la transaction continue
COMMIT;
```

psql propose `\set ON_ERROR_ROLLBACK interactive` : il pose automatiquement un savepoint avant chaque commande, pour qu'une faute de frappe n'annule pas toute la transaction en cours.

> ⚠️ Les savepoints ont un coût : au-delà de 64 sous-transactions actives dans une même transaction, les performances se dégradent fortement sur les systèmes chargés. Certains ORM en créent un par ligne : à surveiller.

---

## 2. Le MVCC

### 2.1 Principe

Le **MVCC** (*Multi-Version Concurrency Control*) consiste à **ne jamais modifier une ligne en place** :

- `INSERT` crée une version de ligne avec `xmin` = identifiant de la transaction (XID) créatrice.
- `DELETE` ne supprime rien physiquement : il écrit son XID dans `xmax` de la version existante.
- `UPDATE` = `DELETE` de l'ancienne version + `INSERT` d'une nouvelle version.

Chaque transaction lit la base à travers un **instantané** (*snapshot*) : la liste des transactions validées à un moment donné. Une version de ligne est visible si sa transaction créatrice (`xmin`) est validée et visible dans l'instantané, et si sa transaction de suppression (`xmax`) ne l'est pas.

### 2.2 Conséquence fondamentale

> **Les lecteurs ne bloquent pas les écrivains, et les écrivains ne bloquent pas les lecteurs.**

Un `SELECT` long ne bloque pas les `UPDATE`, et un `UPDATE` en cours ne bloque pas les `SELECT` : ils lisent l'ancienne version. Seuls deux écrivains sur **la même ligne** doivent s'attendre.

### 2.3 Le prix à payer

- Les anciennes versions (**tuples morts**) s'accumulent et doivent être nettoyées : c'est le rôle de **VACUUM**.
- Une transaction ouverte longtemps empêche le nettoyage de toutes les versions qu'elle pourrait encore voir, **dans toute la base**.

### 2.4 Observer le MVCC

```sql
SELECT pg_current_xact_id();                           -- XID de la transaction courante (PG 13+)
SELECT xmin, xmax, ctid, id_compte, solde FROM bank.comptes WHERE id_compte = 1;
SELECT pg_current_snapshot();                          -- xmin:xmax:liste des XID en cours
```

---

## 3. Niveaux d'isolation

### 3.1 Les anomalies

| Anomalie | Description |
|----------|-------------|
| **Lecture sale** (*dirty read*) | Lire des données d'une transaction non validée |
| **Lecture non répétable** | Relire une ligne et obtenir une valeur différente (modifiée et validée entre-temps) |
| **Lecture fantôme** (*phantom*) | Réexécuter une requête et obtenir un ensemble de lignes différent |
| **Mise à jour perdue** (*lost update*) | Deux transactions lisent puis écrivent la même valeur ; l'une écrase l'autre |
| **Anomalie de sérialisation** (*write skew*) | Deux transactions valides individuellement produisent ensemble un état impossible en exécution séquentielle |

### 3.2 Les niveaux dans PostgreSQL

| Niveau | Lecture sale | Non répétable | Fantôme | Sérialisation |
|--------|:------------:|:-------------:|:-------:|:-------------:|
| Read Uncommitted | Impossible* | Possible | Possible | Possible |
| **Read Committed** (défaut) | Impossible | Possible | Possible | Possible |
| Repeatable Read | Impossible | Impossible | Impossible* | Possible |
| Serializable | Impossible | Impossible | Impossible | Impossible |

\* PostgreSQL est plus strict que le standard : Read Uncommitted se comporte comme Read Committed, et Repeatable Read empêche aussi les fantômes.

| Niveau | Instantané | Comportement en cas de conflit d'écriture |
|--------|-----------|-------------------------------------------|
| **Read Committed** | Nouveau à **chaque instruction** | Attend la fin de l'autre transaction, puis réévalue la ligne |
| **Repeatable Read** | Un seul, pris à la **première instruction** de la transaction | Erreur `could not serialize access due to concurrent update` |
| **Serializable** | Idem + détection des dépendances dangereuses (SSI) | Erreur de sérialisation, parfois au `COMMIT` |

```sql
BEGIN ISOLATION LEVEL REPEATABLE READ;
...
COMMIT;

SET default_transaction_isolation = 'serializable';   -- pour la session
```

### 3.3 Conséquence pour les développeurs

En Repeatable Read et Serializable, l'application **doit** intercepter les erreurs de sérialisation (SQLSTATE `40001`) et **rejouer** la transaction. Ce n'est pas un bug, c'est le contrat de ces niveaux.

### 3.4 Éviter les mises à jour perdues en Read Committed

Mauvais (lecture puis écriture calculée par l'application) :

```sql
SELECT solde FROM bank.comptes WHERE id_compte = 1;      -- l'appli lit 1000
UPDATE bank.comptes SET solde = 900 WHERE id_compte = 1; -- l'appli écrit 1000 - 100
```

Bons :

```sql
-- 1. Mise à jour atomique relative
UPDATE bank.comptes SET solde = solde - 100 WHERE id_compte = 1 AND solde >= 100;

-- 2. Verrouillage explicite de la ligne lue
BEGIN;
SELECT solde FROM bank.comptes WHERE id_compte = 1 FOR UPDATE;
UPDATE bank.comptes SET solde = ... WHERE id_compte = 1;
COMMIT;

-- 3. Verrouillage optimiste (colonne de version)
UPDATE t SET ..., version = version + 1 WHERE id = 1 AND version = 7;
-- 0 ligne modifiée = quelqu'un est passé avant : recommencer
```

> 🔐 **Angle sécurité**
> Les problèmes de concurrence sont des vulnérabilités à part entière : les **attaques par condition de course** (*race conditions*) exploitent les fenêtres entre lecture et écriture pour retirer deux fois le même solde, utiliser deux fois un bon de réduction, ou dépasser une limite. Des outils de test d'intrusion envoient des dizaines de requêtes simultanées précisément pour cela. La protection se fait en base : mises à jour atomiques, `SELECT … FOR UPDATE`, contraintes `CHECK (solde >= 0)`, contraintes d'unicité, niveau Serializable.

---

## 4. Les verrous

### 4.1 Verrous de table

Même un simple `SELECT` pose un verrou de table (le plus faible). Les verrous servent surtout à empêcher qu'on modifie la **structure** d'une table pendant qu'on l'utilise.

| Mode | Posé par | Bloque |
|------|----------|--------|
| `ACCESS SHARE` | `SELECT` | `ACCESS EXCLUSIVE` seulement |
| `ROW SHARE` | `SELECT … FOR UPDATE/SHARE` | `EXCLUSIVE`, `ACCESS EXCLUSIVE` |
| `ROW EXCLUSIVE` | `INSERT`, `UPDATE`, `DELETE`, `MERGE` | `SHARE` et plus forts |
| `SHARE UPDATE EXCLUSIVE` | `VACUUM` (non FULL), `ANALYZE`, `CREATE INDEX CONCURRENTLY`, certains `ALTER TABLE` | Lui-même et plus forts |
| `SHARE` | `CREATE INDEX` (non concurrent) | Les écritures |
| `SHARE ROW EXCLUSIVE` | `CREATE TRIGGER`, certains `ALTER TABLE` | Écritures et lui-même |
| `EXCLUSIVE` | `REFRESH MATERIALIZED VIEW CONCURRENTLY` | Tout sauf `ACCESS SHARE` |
| `ACCESS EXCLUSIVE` | `DROP`, `TRUNCATE`, `VACUUM FULL`, `CLUSTER`, la plupart des `ALTER TABLE`, `LOCK TABLE` par défaut | **Tout**, y compris `SELECT` |

À retenir : les opérations de maintenance lourdes (`VACUUM FULL`, `ALTER TABLE … ALTER COLUMN TYPE`, `CREATE INDEX` non concurrent) **bloquent l'application**.

### 4.2 Le piège de la file d'attente des verrous

Scénario classique d'incident en production :

1. Une requête analytique longue lit `bank.operations` (`ACCESS SHARE`, 10 minutes).
2. Un DBA lance `ALTER TABLE bank.operations ADD COLUMN …` : il demande `ACCESS EXCLUSIVE` et **attend** la fin de la requête 1.
3. Toutes les requêtes suivantes sur la table, même de simples `SELECT`, se mettent **en file derrière le `ALTER`**.
4. L'application est bloquée pendant 10 minutes, alors que l'`ALTER` lui-même prendrait quelques millisecondes.

Protection : toujours fixer un délai d'attente avant un DDL en production, et réessayer :

```sql
SET lock_timeout = '3s';
ALTER TABLE bank.operations ADD COLUMN canal text;
```

### 4.3 Verrous de ligne

| Mode | Usage |
|------|-------|
| `FOR UPDATE` | On va modifier ou supprimer la ligne |
| `FOR NO KEY UPDATE` | On va modifier sans toucher la clé (posé par un `UPDATE` ordinaire) |
| `FOR SHARE` | Empêcher la modification pendant qu'on lit |
| `FOR KEY SHARE` | Empêcher la suppression / modification de clé (posé par les vérifications de clé étrangère) |

Options utiles :

```sql
SELECT * FROM taches WHERE statut = 'A_FAIRE'
ORDER BY id LIMIT 1
FOR UPDATE SKIP LOCKED;       -- file de travail : ignore les lignes déjà prises

SELECT ... FOR UPDATE NOWAIT; -- erreur immédiate au lieu d'attendre
```

Les verrous de ligne ne sont pas stockés en mémoire partagée mais **dans la ligne elle-même** (champ `xmax`) : on peut donc verrouiller des millions de lignes sans saturer la table des verrous.

### 4.4 Verrous consultatifs (advisory locks)

Verrous applicatifs sans lien avec un objet, identifiés par un entier :

```sql
SELECT pg_try_advisory_lock(42);   -- true si obtenu
SELECT pg_advisory_unlock(42);
SELECT pg_advisory_xact_lock(42);  -- libéré automatiquement en fin de transaction
```

Usage : garantir qu'un seul exemplaire d'un traitement planifié tourne à la fois.

### 4.5 Deadlocks

Un **deadlock** (interblocage) survient quand deux transactions s'attendent mutuellement :

```
Transaction A : verrouille ligne 1 … puis demande ligne 2 (attend B)
Transaction B : verrouille ligne 2 … puis demande ligne 1 (attend A)
```

PostgreSQL vérifie la présence d'un cycle après `deadlock_timeout` (1 s par défaut) et **annule l'une des deux transactions** (`ERROR: deadlock detected`). L'autre continue.

Prévention : toujours verrouiller les ressources **dans le même ordre** (par exemple, par identifiant croissant). Dans la fonction de virement, verrouiller d'abord le compte au plus petit identifiant.

### 4.6 Diagnostiquer un blocage

```sql
-- Qui est bloqué, par qui ?
SELECT pid,
       pg_blocking_pids(pid) AS bloque_par,
       usename, state, wait_event_type, wait_event,
       now() - xact_start AS duree_transaction,
       left(query, 80) AS requete
FROM pg_stat_activity
WHERE cardinality(pg_blocking_pids(pid)) > 0;

-- Détail des verrous
SELECT l.pid, l.locktype, l.relation::regclass, l.mode, l.granted
FROM pg_locks l
WHERE l.relation IS NOT NULL
ORDER BY l.relation, l.granted DESC;
```

Traitement :

```sql
SELECT pg_cancel_backend(12345);     -- annule la requête en cours (la session reste ouverte)
SELECT pg_terminate_backend(12345);  -- ferme la session (la transaction est annulée)
```

Commencer par `pg_cancel_backend` ; utiliser `pg_terminate_backend` si la session est `idle in transaction` (aucune requête à annuler) ou ne réagit pas.

### 4.7 Les sessions « idle in transaction »

Une session qui a fait `BEGIN`, puis plus rien (application mal écrite, développeur parti déjeuner avec psql ouvert) :

- garde ses verrous, donc peut bloquer d'autres sessions ;
- empêche VACUUM de nettoyer les tuples morts dans toute la base.

```sql
SELECT pid, usename, now() - state_change AS inactive_depuis, left(query, 60)
FROM pg_stat_activity
WHERE state = 'idle in transaction'
ORDER BY state_change;
```

Protection : `idle_in_transaction_session_timeout` (par exemple `10min`, ou moins pour les rôles applicatifs).

---

## 5. VACUUM

### 5.1 Ce que fait VACUUM

| Tâche | Détail |
|-------|--------|
| Récupérer l'espace | Marque les tuples morts (invisibles pour toutes les transactions) comme réutilisables |
| Mettre à jour la Visibility Map | Permet les *index-only scans* et accélère les VACUUM suivants |
| Geler les anciennes lignes | Protège contre le *wraparound* des XID (section 6) |
| Mettre à jour les statistiques | Avec `VACUUM ANALYZE` |

`VACUUM` ordinaire ne bloque **ni les lectures ni les écritures**. Il ne réduit pas la taille du fichier (sauf les pages vides en fin de fichier) : l'espace libéré est réutilisé par les futures insertions.

### 5.2 VACUUM FULL

`VACUUM FULL` **réécrit entièrement** la table dans un nouveau fichier compact et rend l'espace au système. Mais :

- il pose un verrou `ACCESS EXCLUSIVE` : la table est **inaccessible** pendant toute l'opération ;
- il nécessite temporairement **deux fois** l'espace de la table.

Alternative en production : l'extension **`pg_repack`**, qui reconstruit la table en ligne avec un verrou très court.

### 5.3 L'autovacuum

Le démon autovacuum lance automatiquement VACUUM et ANALYZE sur les tables qui en ont besoin.

Une table est traitée par VACUUM quand :

```
tuples morts > autovacuum_vacuum_threshold + autovacuum_vacuum_scale_factor × nombre de lignes
                        (50)                              (0.2)
```

Soit, par défaut, 20 % de lignes mortes. Pour une table de 100 millions de lignes, il faut attendre 20 millions de tuples morts : c'est trop tardif. On règle donc les grosses tables individuellement :

```sql
ALTER TABLE bank.operations SET (autovacuum_vacuum_scale_factor = 0.01,
                                 autovacuum_analyze_scale_factor = 0.005);
```

Paramètres globaux importants :

| Paramètre | Défaut | Rôle |
|-----------|--------|------|
| `autovacuum` | `on` | **Ne jamais désactiver** |
| `autovacuum_max_workers` | 3 | Nombre de VACUUM simultanés |
| `autovacuum_naptime` | 1min | Fréquence de vérification |
| `autovacuum_vacuum_cost_limit` | -1 (= 200) | « Budget » d'I/O avant pause ; à augmenter sur SSD |
| `autovacuum_vacuum_insert_scale_factor` | 0.2 | Déclenchement sur les tables en insertion seule (PG 13+) |

Suivi :

```sql
SELECT relname, n_live_tup, n_dead_tup,
       round(100.0 * n_dead_tup / nullif(n_live_tup + n_dead_tup, 0), 1) AS pct_morts,
       last_vacuum, last_autovacuum, last_analyze, last_autoanalyze
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC LIMIT 10;

SELECT * FROM pg_stat_progress_vacuum;   -- VACUUM en cours
```

### 5.4 Pourquoi VACUUM « ne nettoie rien »

Causes classiques, par ordre de fréquence :

1. Une **transaction longue** ou `idle in transaction` ouverte depuis des heures.
2. Un **slot de réplication** abandonné (module 08).
3. Une **transaction préparée** (`PREPARE TRANSACTION`) oubliée (`pg_prepared_xacts`).
4. Une réplique avec `hot_standby_feedback = on` exécutant une longue requête.

```sql
-- Qui retient l'horizon de nettoyage ?
SELECT pid, usename, state, backend_xmin, age(backend_xmin) AS age_xmin,
       now() - xact_start AS duree
FROM pg_stat_activity
WHERE backend_xmin IS NOT NULL
ORDER BY age(backend_xmin) DESC LIMIT 5;
```

---

## 6. Le wraparound des identifiants de transaction

### 6.1 Le problème

Les XID sont codés sur **32 bits** (environ 4,2 milliards de valeurs) et comparés de manière **circulaire** : pour toute transaction, 2,1 milliards de XID sont « dans le passé » et 2,1 milliards « dans le futur ». Si une ligne ancienne n'est jamais « gelée », son `xmin` finirait par apparaître comme **futur** après 2,1 milliards de transactions : la ligne deviendrait **invisible**, ce qui équivaut à une perte de données.

### 6.2 La protection : le gel (freeze)

VACUUM **gèle** les lignes suffisamment anciennes : il les marque comme visibles par toutes les transactions, quel que soit leur XID. L'autovacuum déclenche un VACUUM « anti-wraparound » obligatoire quand l'âge d'une table dépasse `autovacuum_freeze_max_age` (**200 millions** de transactions par défaut), même si l'autovacuum est désactivé pour cette table.

### 6.3 Ce qui arrive si on laisse faire

Quand l'âge approche de la limite, PostgreSQL émet des avertissements dans les journaux, puis, à quelques millions de XID de la limite, **refuse toute nouvelle transaction d'écriture** pour protéger les données. La base passe de fait en lecture seule jusqu'à un VACUUM complet, qui peut durer des heures sur une grosse base. C'est l'un des incidents les plus graves en exploitation PostgreSQL.

### 6.4 Surveillance

```sql
SELECT datname, age(datfrozenxid) AS age_xid,
       round(100.0 * age(datfrozenxid) / 2000000000, 1) AS pct_vers_limite
FROM pg_database ORDER BY 2 DESC;

SELECT c.oid::regclass AS table_, age(c.relfrozenxid) AS age_xid,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS taille
FROM pg_class c
WHERE c.relkind IN ('r', 'm', 't')
ORDER BY age(c.relfrozenxid) DESC LIMIT 10;
```

Seuils d'alerte usuels : avertissement à 500 millions, critique à 1 milliard.

---

## 7. Réglages de durabilité et de performance du COMMIT

| `synchronous_commit` | Garantie | Performance |
|----------------------|----------|-------------|
| `on` (défaut) | WAL écrit et synchronisé localement (et sur la réplique synchrone s'il y en a une) | Référence |
| `off` | Le `COMMIT` rend la main avant l'écriture du WAL. En cas de crash, les dernières transactions (jusqu'à environ 3 × `wal_writer_delay`, soit ~600 ms) peuvent être **perdues**, mais la base reste **cohérente** | Beaucoup plus rapide pour les petites transactions |
| `local`, `remote_write`, `remote_apply` | Niveaux intermédiaires pour la réplication (module 08) | — |

À la différence de `fsync = off`, `synchronous_commit = off` ne risque **jamais** de corrompre la base : on accepte seulement de perdre les dernières transactions. On peut l'activer **par transaction** pour des données peu critiques (journaux applicatifs, statistiques) :

```sql
BEGIN;
SET LOCAL synchronous_commit = off;
INSERT INTO journal_clics ...;
COMMIT;
```

---

## TP 5 — Concurrence en pratique

Ouvre **deux panneaux tmux**, chacun connecté à `banque` en superutilisateur : **Session A** et **Session B**.

### Étape 1 : MVCC visible

**Session A**
```sql
BEGIN;
SELECT pg_current_xact_id();
SELECT xmin, xmax, ctid, solde FROM bank.comptes WHERE id_compte = 10;
UPDATE bank.comptes SET solde = solde + 1 WHERE id_compte = 10;
SELECT xmin, xmax, ctid, solde FROM bank.comptes WHERE id_compte = 10;
```

**Session B**
```sql
SELECT xmin, xmax, ctid, solde FROM bank.comptes WHERE id_compte = 10;
```

B voit l'**ancienne** version : `xmax` contient le XID de A, le `ctid` est l'ancien. A voit la **nouvelle** version avec un nouveau `ctid`.

**Session A**
```sql
COMMIT;
```

**Session B** : relance la requête ; la nouvelle version est visible.

### Étape 2 : lecture non répétable en Read Committed

**Session A**
```sql
BEGIN;
SELECT solde FROM bank.comptes WHERE id_compte = 20;
```
**Session B**
```sql
UPDATE bank.comptes SET solde = solde + 100 WHERE id_compte = 20;
```
**Session A**
```sql
SELECT solde FROM bank.comptes WHERE id_compte = 20;   -- valeur différente !
COMMIT;
```

### Étape 3 : Repeatable Read

**Session A**
```sql
BEGIN ISOLATION LEVEL REPEATABLE READ;
SELECT solde FROM bank.comptes WHERE id_compte = 20;
```
**Session B**
```sql
UPDATE bank.comptes SET solde = solde + 100 WHERE id_compte = 20;
```
**Session A**
```sql
SELECT solde FROM bank.comptes WHERE id_compte = 20;   -- même valeur qu'avant
UPDATE bank.comptes SET solde = solde - 50 WHERE id_compte = 20;
-- ERROR: could not serialize access due to concurrent update
ROLLBACK;
```

### Étape 4 : mise à jour perdue et sa correction

Simule deux guichets qui lisent puis écrivent. Note d'abord le solde du compte 30 (par exemple 1000).

**Session A** : `BEGIN; SELECT solde FROM bank.comptes WHERE id_compte = 30;`
**Session B** : `BEGIN; SELECT solde FROM bank.comptes WHERE id_compte = 30;`
**Session A** : `UPDATE bank.comptes SET solde = <solde_lu - 100> WHERE id_compte = 30; COMMIT;`
**Session B** : `UPDATE bank.comptes SET solde = <solde_lu - 200> WHERE id_compte = 30; COMMIT;`

Le solde final n'a diminué que de 200 au lieu de 300 : **100 dirhams sont perdus**.

Recommence avec `SELECT … FOR UPDATE` dans les deux sessions : B **attend** que A valide, puis lit le solde à jour.

### Étape 5 : write skew et Serializable

Règle métier : au moins un médecin doit rester de garde.

**Session A**
```sql
BEGIN ISOLATION LEVEL REPEATABLE READ;
SELECT count(*) FROM bank.gardes WHERE de_garde;       -- 2 : je peux partir
```
**Session B**
```sql
BEGIN ISOLATION LEVEL REPEATABLE READ;
SELECT count(*) FROM bank.gardes WHERE de_garde;       -- 2 : je peux partir
```
**Session A** : `UPDATE bank.gardes SET de_garde = false WHERE medecin = 'Amina'; COMMIT;`
**Session B** : `UPDATE bank.gardes SET de_garde = false WHERE medecin = 'Karim'; COMMIT;`

```sql
SELECT * FROM bank.gardes;    -- plus personne de garde !
UPDATE bank.gardes SET de_garde = true;
```

Recommence avec `BEGIN ISOLATION LEVEL SERIALIZABLE;` dans les deux sessions : l'une des deux transactions échoue avec `could not serialize access due to read/write dependencies among transactions`. L'invariant est protégé.

### Étape 6 : deadlock

**Session A** : `BEGIN; UPDATE bank.comptes SET solde = solde + 1 WHERE id_compte = 1;`
**Session B** : `BEGIN; UPDATE bank.comptes SET solde = solde + 1 WHERE id_compte = 2;`
**Session A** : `UPDATE bank.comptes SET solde = solde + 1 WHERE id_compte = 2;` (attend)
**Session B** : `UPDATE bank.comptes SET solde = solde + 1 WHERE id_compte = 1;`

Après environ une seconde, l'une des sessions reçoit `ERROR: deadlock detected`. Fais `ROLLBACK` dans les deux sessions et lis le message détaillé dans le journal du serveur.

### Étape 7 : diagnostiquer un blocage

**Session A**
```sql
BEGIN;
UPDATE bank.comptes SET solde = solde + 1 WHERE id_compte = 5;
-- ne pas valider
```

**Session B**
```sql
UPDATE bank.comptes SET solde = solde - 1 WHERE id_compte = 5;   -- bloqué
```

**Session C** (troisième panneau) : exécute la requête de diagnostic de la section 4.6. Identifie le PID bloquant, puis :

```sql
SELECT pg_cancel_backend(<pid_A>);     -- aucun effet : A est idle in transaction
SELECT pg_terminate_backend(<pid_A>);  -- B est débloqué
```

### Étape 8 : piège de la file d'attente des verrous

**Session A** : `BEGIN; SELECT count(*) FROM bank.agences;` (ne pas valider)
**Session B** : `ALTER TABLE bank.agences ADD COLUMN telephone text;` (attend)
**Session C** : `SELECT * FROM bank.agences;` (**bloqué**, alors que c'est un simple `SELECT`)

Libère A (`COMMIT`), puis recommence avec, en Session B :

```sql
SET lock_timeout = '2s';
ALTER TABLE bank.agences ADD COLUMN telephone text;   -- échoue proprement après 2 s
```

Supprime la colonne à la fin si elle a été créée.

### Étape 9 : bloat et VACUUM

```sql
CREATE TABLE bank.demo_vacuum AS SELECT g AS id, md5(g::text) AS h FROM generate_series(1, 1000000) g;
ALTER TABLE bank.demo_vacuum SET (autovacuum_enabled = false);
SELECT pg_size_pretty(pg_relation_size('bank.demo_vacuum'));

UPDATE bank.demo_vacuum SET h = upper(h);
SELECT pg_size_pretty(pg_relation_size('bank.demo_vacuum'));    -- environ doublée

SELECT pg_stat_force_next_flush();     -- PG 15+ : publier les statistiques immédiatement
SELECT n_live_tup, n_dead_tup FROM pg_stat_user_tables WHERE relname = 'demo_vacuum';

VACUUM (VERBOSE) bank.demo_vacuum;
SELECT pg_size_pretty(pg_relation_size('bank.demo_vacuum'));    -- inchangée

UPDATE bank.demo_vacuum SET h = lower(h);
SELECT pg_size_pretty(pg_relation_size('bank.demo_vacuum'));    -- peu ou pas d'augmentation : espace réutilisé

VACUUM FULL bank.demo_vacuum;
SELECT pg_size_pretty(pg_relation_size('bank.demo_vacuum'));    -- taille initiale
```

Recommence le premier `UPDATE` **pendant** qu'une Session B garde une transaction Repeatable Read ouverte qui a lu la table : observe dans la sortie de `VACUUM VERBOSE` que les tuples morts ne peuvent pas être supprimés (« dead but not yet removable »).

```sql
DROP TABLE bank.demo_vacuum;
```

### Étape 10 : âge des transactions

Exécute les requêtes de la section 6.4. Note l'âge actuel de chaque base.

---

## Exercices

1. Réécris la fonction `bank.virement` du module 04 pour qu'elle ne puisse jamais provoquer de deadlock quand deux virements croisés (1→2 et 2→1) s'exécutent simultanément.
2. Une application de réservation de places de concert reçoit 10 000 requêtes simultanées pour 500 places. Propose deux conceptions en base qui empêchent la survente, et compare-les.
3. Un traitement nocturne lit toute la base pendant 6 heures dans une seule transaction Repeatable Read. Quels problèmes cela pose-t-il ? Propose des alternatives.
4. La table `evenements` (800 millions de lignes, insertions seules) n'est jamais traitée par l'autovacuum avant PG 13. Quel risque cela pose-t-il et comment le traiter ?
5. Un développeur veut mettre `synchronous_commit = off` pour toute la base « parce que c'est plus rapide ». Quelle est ta réponse argumentée pour une banque ?

---

## Quiz

1. Que contiennent `xmin` et `xmax` ?
2. Pourquoi un `SELECT` ne bloque-t-il jamais un `UPDATE` dans PostgreSQL ?
3. Quel est le niveau d'isolation par défaut ?
4. Quelle erreur une application doit-elle savoir intercepter et rejouer en Serializable ?
5. Quel verrou pose `VACUUM FULL` et quelle conséquence cela a-t-il ?
6. Comment PostgreSQL résout-il un deadlock ?
7. Quelle est la différence entre `pg_cancel_backend` et `pg_terminate_backend` ?
8. Citez trois causes qui empêchent VACUUM de nettoyer les tuples morts.
9. Qu'est-ce que le wraparound et que fait PostgreSQL pour l'éviter ?
10. Quelle est la différence de risque entre `fsync = off` et `synchronous_commit = off` ?

*Corrigés : [annexe D](annexes/D-corriges.md#module-05).*

---

## À retenir

- MVCC : chaque modification crée une nouvelle version ; lecteurs et écrivains ne se bloquent pas.
- Read Committed par défaut ; Repeatable Read et Serializable imposent de rejouer sur erreur `40001`.
- Les verrous forts (`ACCESS EXCLUSIVE`) bloquent tout : `lock_timeout` avant chaque DDL en production.
- Deadlock : ordre de verrouillage constant ; blocage : `pg_blocking_pids`, `pg_cancel_backend`, `pg_terminate_backend`.
- VACUUM est vital : surveiller les tuples morts, les transactions longues, et l'âge des XID.
- Les conditions de course sont des failles de sécurité : les protections se placent en base.
