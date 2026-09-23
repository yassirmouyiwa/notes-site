# Module 07 — Performance et optimisation

## Objectifs

- Adopter une méthode de diagnostic rigoureuse plutôt que des réglages au hasard.
- Lire et interpréter un plan d'exécution (`EXPLAIN ANALYZE`).
- Comprendre le rôle des statistiques dans les choix du planificateur.
- Choisir le bon type d'index et savoir quand un index est inutile, voire nuisible.
- Identifier les requêtes coûteuses avec `pg_stat_statements` et `auto_explain`.
- Régler les paramètres d'instance qui comptent vraiment.
- Mesurer avec `pgbench` et dimensionner les connexions avec un pooler.

---

## 1. Méthode

L'optimisation suit toujours le même cycle :

```
1. MESURER      → quelle requête / quelle ressource pose problème ? (pas d'intuition)
2. COMPRENDRE   → pourquoi ? (plan d'exécution, attentes, statistiques)
3. CORRIGER     → une seule modification à la fois
4. VÉRIFIER     → la mesure s'est-elle améliorée ? sans effet de bord ?
```

Ordre d'efficacité habituel des leviers :

1. **La requête et le modèle** (requête mal écrite, N+1, colonne mal typée) : gains de ×10 à ×1000.
2. **Les index** : gains de ×10 à ×1000 sur les requêtes sélectives.
3. **Les statistiques et la maintenance** (ANALYZE, VACUUM, bloat).
4. **La configuration** de l'instance : gains de quelques dizaines de pourcents.
5. **Le matériel** : en dernier recours, et souvent le plus coûteux.

---

## 2. Le planificateur et les coûts

### 2.1 Modèle de coût

Pour chaque requête, le planificateur énumère des plans possibles, estime leur **coût** et retient le moins cher. Le coût est une unité arbitraire, calculée à partir de constantes :

| Paramètre | Défaut | Signification |
|-----------|--------|---------------|
| `seq_page_cost` | 1.0 | Lire une page en séquentiel |
| `random_page_cost` | 4.0 | Lire une page en accès aléatoire (**1.1 sur SSD**) |
| `cpu_tuple_cost` | 0.01 | Traiter une ligne |
| `cpu_index_tuple_cost` | 0.005 | Traiter une entrée d'index |
| `cpu_operator_cost` | 0.0025 | Évaluer un opérateur ou une fonction |
| `effective_cache_size` | 4GB | Taille de cache supposée (influence le choix des index) |

Avec `random_page_cost = 4` sur un SSD, le planificateur surestime le coût des accès par index et préfère à tort les parcours séquentiels. C'est l'un des premiers réglages à corriger.

### 2.2 Les estimations reposent sur les statistiques

Le coût dépend surtout du **nombre de lignes estimé** à chaque étape. Ces estimations viennent des statistiques collectées par `ANALYZE` dans `pg_statistic` (lisible via la vue `pg_stats`) :

| Colonne de `pg_stats` | Contenu |
|-----------------------|---------|
| `null_frac` | Proportion de NULL |
| `n_distinct` | Nombre de valeurs distinctes (négatif = proportion du nombre de lignes) |
| `most_common_vals` / `most_common_freqs` | Valeurs les plus fréquentes et leur fréquence |
| `histogram_bounds` | Bornes d'un histogramme des autres valeurs |
| `correlation` | Corrélation entre l'ordre physique des lignes et l'ordre des valeurs (−1 à 1) |

**Règle** : quand les estimations sont fausses, les plans le sont aussi. La première chose à vérifier dans un plan lent est l'écart entre lignes **estimées** et lignes **réelles**.

Améliorer les statistiques :

```sql
ANALYZE bank.operations;                                                   -- rafraîchir
ALTER TABLE bank.operations ALTER COLUMN id_compte SET STATISTICS 1000;    -- plus d'échantillons (défaut 100)
CREATE STATISTICS st_ville_region (dependencies, ndistinct) ON ville, region FROM bank.agences;
```

Les **statistiques étendues** (`CREATE STATISTICS`) informent le planificateur des **corrélations entre colonnes** : sans elles, il suppose que `ville = 'Tétouan'` et `region = 'Tanger-Tétouan-Al Hoceïma'` sont indépendantes et multiplie les sélectivités, ce qui sous-estime fortement le nombre de lignes.

---

## 3. Lire un plan d'exécution

### 3.1 Les variantes d'EXPLAIN

```sql
EXPLAIN SELECT ...;                                  -- plan estimé, requête non exécutée
EXPLAIN (ANALYZE) SELECT ...;                        -- exécute et mesure (attention aux INSERT/UPDATE/DELETE !)
EXPLAIN (ANALYZE, BUFFERS) SELECT ...;               -- + pages lues dans le cache / sur disque
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, WAL) ...;       -- + paramètres modifiés, WAL généré
EXPLAIN (FORMAT JSON) ...;                           -- pour les outils de visualisation
```

`EXPLAIN ANALYZE` **exécute** la requête. Pour analyser une modification sans l'appliquer :

```sql
BEGIN;
EXPLAIN (ANALYZE) DELETE FROM bank.operations WHERE montant < 2;
ROLLBACK;
```

### 3.2 Anatomie d'un nœud

```
Parallel Seq Scan on operations  (cost=0.00..34249.67 rows=6 width=61) (actual time=42.8..170.4 rows=4 loops=3)
  Filter: (id_compte = 4242)
  Rows Removed by Filter: 666663
  Buffers: shared hit=23 read=23810
```

| Élément | Signification |
|---------|---------------|
| `cost=0.00..34249.67` | Coût estimé pour la première ligne .. pour toutes les lignes |
| `rows=6` | Lignes **estimées** (par exécution du nœud) |
| `width=61` | Taille moyenne estimée d'une ligne en octets |
| `actual time=42.8..170.4` | Temps réel (ms) pour la première ligne .. la dernière |
| `rows=4 loops=3` | Lignes réelles **par boucle**, nombre de boucles (total = 4 × 3) |
| `Rows Removed by Filter` | Lignes lues puis rejetées : signe d'un index manquant si élevé |
| `shared hit` / `read` | Pages trouvées dans `shared_buffers` / lues depuis le système |

Un plan se lit **de l'intérieur vers l'extérieur** (des nœuds les plus indentés vers la racine). Chaque nœud consomme les lignes produites par ses enfants.

### 3.3 Les principaux nœuds

**Accès aux tables**

| Nœud | Principe | Quand |
|------|----------|-------|
| `Seq Scan` | Lecture complète de la table | Grande proportion de lignes, petite table, pas d'index utilisable |
| `Index Scan` | Parcours de l'index puis accès à chaque ligne de la table | Peu de lignes |
| `Index Only Scan` | Réponse à partir de l'index seul (+ Visibility Map) | Toutes les colonnes nécessaires sont dans l'index, table bien vacuumée |
| `Bitmap Index Scan` + `Bitmap Heap Scan` | Construit une carte des pages à lire, puis les lit dans l'ordre physique | Nombre moyen de lignes, combinaison de plusieurs index (`BitmapAnd`, `BitmapOr`) |

**Jointures**

| Nœud | Principe | Adapté à |
|------|----------|----------|
| `Nested Loop` | Pour chaque ligne externe, cherche les correspondances (idéalement par index) | Peu de lignes externes |
| `Hash Join` | Construit une table de hachage sur le plus petit ensemble, puis la sonde | Gros volumes, égalité, pas d'index |
| `Merge Join` | Fusionne deux ensembles triés | Gros volumes déjà triés |

**Autres** : `Sort`, `Hash`, `HashAggregate` / `GroupAggregate`, `Limit`, `Gather` (parallélisme), `Materialize`, `Memoize`.

### 3.4 Signaux d'alerte

| Signal | Cause probable |
|--------|----------------|
| `rows` estimé très différent de `rows` réel (×10 ou plus) | Statistiques obsolètes ou insuffisantes, colonnes corrélées |
| `Seq Scan` avec beaucoup de `Rows Removed by Filter` | Index manquant ou inutilisable |
| `Sort Method: external merge Disk: …` | `work_mem` insuffisant pour ce tri |
| `Hash … Batches: 8` (plus de 1) | `work_mem` insuffisant pour le hachage |
| `Nested Loop` avec un grand nombre de `loops` | Mauvaise estimation, index manquant côté interne |
| `Heap Fetches` élevé dans un `Index Only Scan` | Visibility Map à jour insuffisante : VACUUM nécessaire |
| `shared read` élevé | Données hors cache (cache froid ou trop petit) |

Outils de visualisation : **explain.dalibo.com** (hébergeable localement), **explain.depesz.com**.

> 🔐 **Angle sécurité**
> Coller un plan d'exécution dans un site public revient à publier des noms de tables, de colonnes, des valeurs de filtres (parfois des données personnelles). Pour des bases sensibles, utiliser une instance locale de l'outil ou anonymiser le plan.

---

## 4. Les index

### 4.1 Principe et coût

Un index est une structure annexe qui accélère la recherche de lignes. Il a un **coût** :

- espace disque ;
- chaque `INSERT`, chaque `DELETE`, et chaque `UPDATE` non HOT met à jour **tous** les index de la table ;
- il empêche les mises à jour HOT si sa colonne est modifiée.

Un index inutile est donc **nuisible**. On indexe pour des requêtes réelles, pas « au cas où ».

### 4.2 Types d'index

| Type | Opérateurs | Usage typique |
|------|------------|---------------|
| **B-tree** (défaut) | `=`, `<`, `<=`, `>`, `>=`, `BETWEEN`, `IN`, `IS NULL`, `LIKE 'abc%'` (avec collation C ou `text_pattern_ops`), tri `ORDER BY` | 90 % des cas |
| **Hash** | `=` uniquement | Rarement plus intéressant qu'un B-tree |
| **GIN** | Contient / appartient (`@>`, `?`, `&&`), recherche plein texte | `jsonb`, tableaux, `tsvector`, trigrammes (`pg_trgm` pour `LIKE '%abc%'`) |
| **GiST** | Géométrie, intervalles, proximité, exclusion | PostGIS, `tsrange`, contraintes d'exclusion (pas de chevauchement de réservations) |
| **SP-GiST** | Structures partitionnées (arbres quaternaires, préfixes) | Adresses IP, points |
| **BRIN** | Résumé min/max par bloc de pages | Très grosses tables dont l'ordre physique **suit** la valeur (horodatage d'insertion) ; minuscule |

### 4.3 Variantes

```sql
-- Index multicolonne : l'ORDRE compte (égalité d'abord, puis intervalle/tri)
CREATE INDEX ON bank.operations (id_compte, date_op);
-- utilisable pour : WHERE id_compte = ?   /   WHERE id_compte = ? AND date_op > ?
-- peu utile pour  : WHERE date_op > ?   seul

-- Index couvrant : colonnes supplémentaires pour permettre l'Index Only Scan
CREATE INDEX ON bank.operations (id_compte, date_op) INCLUDE (montant);

-- Index partiel : seulement les lignes intéressantes
CREATE INDEX ON bank.comptes (id_client) WHERE statut = 'BLOQUE';

-- Index sur expression
CREATE INDEX ON bank.clients (lower(email));
-- utilisé par : WHERE lower(email) = 'client42@exemple.ma'

-- Unicité
CREATE UNIQUE INDEX ON bank.clients (lower(email));
```

### 4.4 Créer un index en production

`CREATE INDEX` bloque les écritures sur la table pendant toute sa construction. En production :

```sql
CREATE INDEX CONCURRENTLY idx_operations_compte ON bank.operations (id_compte);
```

- Ne bloque pas les écritures (mais dure plus longtemps, deux passes).
- Ne peut pas s'exécuter dans une transaction.
- En cas d'échec, laisse un index **INVALID** à supprimer :
  ```sql
  SELECT indexrelid::regclass FROM pg_index WHERE NOT indisvalid;
  ```
- `REINDEX INDEX CONCURRENTLY` (PG 12+) reconstruit un index gonflé sans blocage.

### 4.5 Pourquoi mon index n'est pas utilisé ?

| Cause | Exemple | Correction |
|-------|---------|------------|
| Fonction appliquée à la colonne | `WHERE lower(email) = …` avec un index sur `email` | Index sur expression |
| Conversion de type implicite | `WHERE cin = 12345` sur une colonne `text` | Utiliser le bon type dans la requête |
| Requête peu sélective | `WHERE type_op = 'DEPOT'` (20 % des lignes) | Normal : le Seq Scan est plus rapide |
| Mauvais ordre de colonnes | Index `(id_compte, date_op)`, filtre sur `date_op` seul | Autre index |
| `LIKE '%motif'` | Joker en tête | Index GIN trigrammes (`pg_trgm`) |
| Statistiques obsolètes | Table chargée sans `ANALYZE` | `ANALYZE` |
| `OR` sur des colonnes différentes | `WHERE a = 1 OR b = 2` | Index sur chaque colonne (BitmapOr) ou `UNION` |
| Petite table | Quelques pages | Normal |

### 4.6 Index manquants et inutiles

```sql
-- Tables lues surtout par Seq Scan : candidates à un index
SELECT relname, seq_scan, seq_tup_read, idx_scan,
       seq_tup_read / nullif(seq_scan, 0) AS lignes_par_seq_scan
FROM pg_stat_user_tables
ORDER BY seq_tup_read DESC LIMIT 10;

-- Index jamais utilisés depuis la remise à zéro des statistiques
SELECT s.schemaname, s.relname AS table_, s.indexrelname AS index_, s.idx_scan,
       pg_size_pretty(pg_relation_size(s.indexrelid)) AS taille
FROM pg_stat_user_indexes s
JOIN pg_index i ON i.indexrelid = s.indexrelid
WHERE s.idx_scan = 0 AND NOT i.indisunique AND NOT i.indisprimary
ORDER BY pg_relation_size(s.indexrelid) DESC;
```

Avant de supprimer un index « inutilisé », vérifier qu'il ne sert pas sur une **réplique** (les statistiques sont propres à chaque instance) ou lors d'un traitement mensuel.

**Règle** : indexer les **clés étrangères** côté enfant. Sans index sur `operations.id_compte`, chaque jointure `comptes ⋈ operations` et chaque suppression d'un compte parcourt toute la table `operations`.

---

## 5. Mémoire et paramètres d'exécution

### 5.1 `work_mem`

Quand un tri ou un hachage dépasse `work_mem`, il déborde sur disque (fichiers temporaires). On le détecte par `Sort Method: external merge` dans les plans, `log_temp_files = 0` dans les journaux, ou :

```sql
SELECT datname, temp_files, pg_size_pretty(temp_bytes) FROM pg_stat_database;
```

Plutôt que d'augmenter `work_mem` globalement (risque mémoire, module 01), on l'augmente **pour les traitements qui en ont besoin** :

```sql
ALTER ROLE r_reporting SET work_mem = '256MB';
-- ou dans la session / transaction
SET LOCAL work_mem = '512MB';
```

### 5.2 Parallélisme

| Paramètre | Défaut | Rôle |
|-----------|--------|------|
| `max_worker_processes` | 8 | Plafond global de processus de travail |
| `max_parallel_workers` | 8 | Plafond des workers pour les requêtes parallèles |
| `max_parallel_workers_per_gather` | 2 | Workers par nœud `Gather` |
| `max_parallel_maintenance_workers` | 2 | Pour `CREATE INDEX`, `VACUUM` |

Utile pour les requêtes analytiques sur gros volumes ; peu d'intérêt pour les petites requêtes transactionnelles.

### 5.3 JIT

La compilation à la volée (`jit = on`) accélère les requêtes analytiques longues, mais ajoute un surcoût de quelques dizaines de millisecondes qui peut **ralentir** des requêtes courtes mal estimées. Si des requêtes courtes affichent une section `JIT:` dans leur plan, on peut relever `jit_above_cost` ou désactiver le JIT pour le rôle concerné.

---

## 6. Trouver les requêtes à optimiser

### 6.1 `pg_stat_statements`

Extension indispensable : elle agrège les statistiques de **toutes** les requêtes exécutées (normalisées : les constantes sont remplacées par `$1`, `$2`…).

```ini
# postgresql.conf — redémarrage nécessaire
shared_preload_libraries = 'pg_stat_statements'
pg_stat_statements.track = all
```

```sql
CREATE EXTENSION pg_stat_statements;

-- Top 10 par temps total (ce qui charge le plus le serveur)
SELECT round(total_exec_time::numeric, 0) AS total_ms,
       calls,
       round(mean_exec_time::numeric, 2) AS moyen_ms,
       rows,
       round(100 * shared_blks_hit::numeric / nullif(shared_blks_hit + shared_blks_read, 0), 1) AS pct_cache,
       left(query, 100) AS requete
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;

SELECT pg_stat_statements_reset();   -- remise à zéro, par exemple avant un test
```

Trier par `total_exec_time` fait ressortir les requêtes qui **coûtent le plus au total** : une requête de 5 ms exécutée 2 millions de fois par jour pèse plus qu'un rapport de 30 s exécuté une fois.

> 🔐 **Angle sécurité**
> `pg_stat_statements` normalise les constantes, mais le texte des requêtes peut révéler la structure de l'application. Seuls les superutilisateurs et les membres de `pg_read_all_stats` voient le texte des requêtes des autres rôles. La même vue est aussi un outil de **détection** : une requête inhabituelle (`SELECT` massif sur `clients`, fonctions système) exécutée par le rôle applicatif peut signaler une injection SQL en cours.

### 6.2 `auto_explain`

Journalise automatiquement le **plan** des requêtes lentes, tel qu'il a été exécuté en production :

```ini
shared_preload_libraries = 'pg_stat_statements,auto_explain'
auto_explain.log_min_duration = '2s'
auto_explain.log_analyze = on          # temps réels (surcoût notable si on journalise tout)
auto_explain.log_buffers = on
```

### 6.3 Les attentes (wait events)

Une requête lente n'est pas toujours en train de calculer : elle peut **attendre** (verrou, I/O, réseau, client).

```sql
SELECT wait_event_type, wait_event, count(*)
FROM pg_stat_activity
WHERE state = 'active' AND pid <> pg_backend_pid()
GROUP BY 1, 2 ORDER BY 3 DESC;
```

| `wait_event_type` | Signification |
|-------------------|---------------|
| (NULL) | Utilise le CPU |
| `Lock` | Attend un verrou (module 05) |
| `LWLock` | Contention interne (buffers, WAL) |
| `IO` | Attend le disque |
| `Client` | Attend le client (application lente à lire les résultats) |
| `IPC` | Attend un autre processus (parallélisme, réplication synchrone) |

---

## 7. Anti-patterns applicatifs fréquents

| Anti-pattern | Symptôme | Correction |
|--------------|----------|------------|
| **N+1 requêtes** (ORM) | Des milliers de petites requêtes identiques | Jointure ou chargement groupé (`IN`, `ANY($1)`) |
| `SELECT *` | Lecture des colonnes TOAST inutiles, pas d'Index Only Scan | Lister les colonnes |
| Pagination par `OFFSET 100000` | Lit et jette 100 000 lignes | Pagination par clé : `WHERE id > $dernier ORDER BY id LIMIT 50` |
| `count(*)` exact sur une grande table | Parcours complet | Estimation (`reltuples`) si l'exactitude n'est pas requise |
| Fonctions sur colonnes indexées | Index ignoré | Index sur expression, réécriture |
| Transactions longues | Bloat, verrous | Transactions courtes |
| Une connexion par requête | Coût de `fork` + authentification | Pool de connexions |
| Requêtes non paramétrées | Pas de réutilisation des plans, **injection SQL** | Requêtes préparées |

---

## 8. Connexions et pooling

Chaque connexion est un processus. Au-delà de quelques centaines de connexions **actives**, les performances baissent (commutations de contexte, contention). La règle empirique pour le nombre de connexions réellement actives : environ **2 à 4 × le nombre de cœurs**.

**PgBouncer** place un pool léger devant PostgreSQL :

| Mode | Connexion serveur attribuée | Compatibilité |
|------|-----------------------------|---------------|
| `session` | Pour toute la session client | Totale, gain limité |
| `transaction` | Pour une transaction | **Le plus utilisé** ; incompatible avec les fonctionnalités liées à la session (`SET` hors transaction, verrous consultatifs de session, `LISTEN`) ; requêtes préparées gérées depuis PgBouncer 1.21 |
| `statement` | Pour une instruction | Interdit les transactions multi-instructions |

Extrait de `pgbouncer.ini` :

```ini
[databases]
banque = host=127.0.0.1 port=5432 dbname=banque

[pgbouncer]
listen_addr = 127.0.0.1
listen_port = 6432
auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 2000
default_pool_size = 20
```

---

## 9. Mesurer avec `pgbench`

`pgbench` est l'outil de test de charge fourni avec PostgreSQL.

```bash
createdb bench
pgbench -i -s 50 bench                     # initialise (~750 Mo, 5 millions de comptes)
pgbench -c 10 -j 2 -T 60 -P 10 bench       # 10 clients, 2 threads, 60 s, progression toutes les 10 s
pgbench -c 10 -j 2 -T 60 -S bench          # lecture seule
pgbench -c 10 -j 2 -T 60 -f mon_script.sql bench   # scénario personnalisé
```

Résultats à lire : **tps** (transactions par seconde) et **latence moyenne**. Toujours comparer des mesures faites dans les **mêmes conditions** (cache chaud, même durée, plusieurs exécutions).

---

## TP 7 — Optimiser la base `banque`

### Étape 1 : préparer l'observation

```bash
$ sudo tee /etc/postgresql/16/main/conf.d/30-performance.conf > /dev/null <<'EOF'
shared_preload_libraries = 'pg_stat_statements,auto_explain'
pg_stat_statements.track = all
auto_explain.log_min_duration = '1s'
auto_explain.log_analyze = on
auto_explain.log_buffers = on
random_page_cost = 1.1
EOF
$ sudo systemctl restart postgresql@16-main
```

```sql
banque=# CREATE EXTENSION pg_stat_statements;
banque=# \timing on
```

### Étape 2 : l'index manquant sur une clé étrangère

```sql
banque=# EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM bank.operations WHERE id_compte = 4242;
```

Relève : type de parcours, lignes retirées par le filtre, pages lues, temps.

```sql
banque=# CREATE INDEX CONCURRENTLY idx_operations_compte ON bank.operations (id_compte);
banque=# EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM bank.operations WHERE id_compte = 4242;
```

Compare. Le gain est typiquement de deux ordres de grandeur.

Jointure :

```sql
banque=# EXPLAIN (ANALYZE, BUFFERS)
         SELECT c.id_client, sum(o.montant)
         FROM bank.comptes c JOIN bank.operations o USING (id_compte)
         WHERE c.id_client = 77
         GROUP BY c.id_client;
```

Le parcours séquentiel reste sur `comptes` : il manque aussi l'index sur `comptes.id_client`. Crée-le et compare.

### Étape 3 : index multicolonne et couvrant

Requête : les 20 dernières opérations d'un compte.

```sql
banque=# EXPLAIN (ANALYZE, BUFFERS)
         SELECT date_op, montant FROM bank.operations
         WHERE id_compte = 4242 ORDER BY date_op DESC LIMIT 20;
banque=# CREATE INDEX idx_operations_compte_date ON bank.operations (id_compte, date_op DESC) INCLUDE (montant);
banque=# VACUUM bank.operations;
banque=# EXPLAIN (ANALYZE, BUFFERS)
         SELECT date_op, montant FROM bank.operations
         WHERE id_compte = 4242 ORDER BY date_op DESC LIMIT 20;
```

Observe `Index Only Scan` et `Heap Fetches: 0` (grâce au VACUUM qui a mis à jour la Visibility Map). L'index `idx_operations_compte` est maintenant **redondant** : le nouvel index commence par la même colonne. Supprime-le et vérifie que la requête de l'étape 2 reste rapide.

```sql
banque=# DROP INDEX bank.idx_operations_compte;
```

### Étape 4 : index sur expression et conversion implicite

```sql
banque=# CREATE INDEX idx_clients_email ON bank.clients (email);
banque=# EXPLAIN ANALYZE SELECT * FROM bank.clients WHERE email = 'client4242@exemple.ma';
banque=# EXPLAIN ANALYZE SELECT * FROM bank.clients WHERE lower(email) = 'client4242@exemple.ma';
```

Le second plan n'utilise pas l'index. Remplace-le par un index sur `lower(email)` et compare.

### Étape 5 : index partiel

```sql
banque=# EXPLAIN ANALYZE SELECT id_compte, id_client FROM bank.comptes WHERE statut = 'BLOQUE';
banque=# CREATE INDEX idx_comptes_bloques ON bank.comptes (id_compte) INCLUDE (id_client) WHERE statut = 'BLOQUE';
banque=# EXPLAIN ANALYZE SELECT id_compte, id_client FROM bank.comptes WHERE statut = 'BLOQUE';
banque=# SELECT indexrelname, pg_size_pretty(pg_relation_size(indexrelid))
         FROM pg_stat_user_indexes WHERE relname = 'comptes';
```

Compare la taille de l'index partiel à celle de la clé primaire.

### Étape 6 : BRIN et corrélation

```sql
banque=# SELECT attname, correlation FROM pg_stats
         WHERE schemaname = 'bank' AND tablename = 'operations';
```

`date_op` a une corrélation proche de 0 : les dates ont été générées aléatoirement, sans lien avec l'ordre physique. Un index BRIN y serait inutile. Crée une copie triée par date, comme le serait une vraie table de journal alimentée au fil de l'eau :

```sql
banque=# CREATE TABLE bank.operations_chrono AS SELECT * FROM bank.operations ORDER BY date_op;
banque=# ANALYZE bank.operations_chrono;
banque=# SELECT correlation FROM pg_stats WHERE tablename = 'operations_chrono' AND attname = 'date_op';

banque=# CREATE INDEX idx_chrono_brin  ON bank.operations_chrono USING brin (date_op);
banque=# CREATE INDEX idx_chrono_btree ON bank.operations_chrono (date_op);
banque=# SELECT indexrelname, pg_size_pretty(pg_relation_size(indexrelid))
         FROM pg_stat_user_indexes WHERE relname = 'operations_chrono';

banque=# EXPLAIN (ANALYZE, BUFFERS) SELECT sum(montant) FROM bank.operations_chrono
         WHERE date_op >= '2024-06-01' AND date_op < '2024-06-08';
banque=# DROP INDEX bank.idx_chrono_btree;
banque=# EXPLAIN (ANALYZE, BUFFERS) SELECT sum(montant) FROM bank.operations_chrono
         WHERE date_op >= '2024-06-01' AND date_op < '2024-06-08';
banque=# DROP TABLE bank.operations_chrono;
```

Compare la taille des deux index (rapport de l'ordre de 1 à 1000) et leurs performances.

### Étape 7 : `work_mem` et tris sur disque

```sql
banque=# SET work_mem = '4MB';
banque=# EXPLAIN (ANALYZE) SELECT id_compte, montant FROM bank.operations ORDER BY montant DESC LIMIT 100000;
banque=# SET work_mem = '128MB';
banque=# EXPLAIN (ANALYZE) SELECT id_compte, montant FROM bank.operations ORDER BY montant DESC LIMIT 100000;
banque=# RESET work_mem;
```

Repère `Sort Method: external merge Disk` puis `quicksort Memory` (ou `top-N heapsort`), et l'écart de temps.

### Étape 8 : statistiques faussées

```sql
banque=# CREATE TABLE bank.stats_demo (id int, statut text);
banque=# ALTER TABLE bank.stats_demo SET (autovacuum_enabled = false);
banque=# INSERT INTO bank.stats_demo SELECT g, 'OK' FROM generate_series(1, 1000) g;
banque=# ANALYZE bank.stats_demo;
banque=# INSERT INTO bank.stats_demo SELECT g, 'ERREUR' FROM generate_series(1001, 500000) g;
banque=# EXPLAIN ANALYZE SELECT * FROM bank.stats_demo WHERE statut = 'ERREUR';
```

Compare `rows` estimé et `rows` réel. Lance `ANALYZE bank.stats_demo;` puis réexécute. Supprime la table.

### Étape 9 : pg_stat_statements

Génère une charge variée :

```bash
$ sudo -u postgres pgbench -n -c 4 -j 2 -T 30 -f - banque <<'EOF'
\set c random(1, 150000)
SELECT * FROM bank.operations WHERE id_compte = :c ORDER BY date_op DESC LIMIT 20;
SELECT count(*) FROM bank.operations WHERE montant BETWEEN 1000 AND 1001;
EOF
```

Puis exécute la requête « Top 10 » de la section 6.1. Identifie la requête la plus coûteuse, propose et crée l'index adapté, remets les statistiques à zéro, relance la charge et compare.

### Étape 10 : pgbench et configuration

```bash
$ sudo -u postgres createdb bench
$ sudo -u postgres pgbench -i -s 20 bench
$ sudo -u postgres pgbench -c 8 -j 2 -T 60 -P 10 bench
```

Note le tps. Modifie **un seul** paramètre (par exemple `synchronous_commit = off` pour le test, ou `shared_buffers`), redémarre si nécessaire, relance le même test. Documente chaque essai dans un tableau (paramètre, valeur, tps, latence). Remets les paramètres d'origine à la fin et supprime la base `bench`.

---

## Exercices

1. Pour chacune des requêtes suivantes sur `bank.operations`, propose l'index optimal ou justifie qu'aucun index n'est utile :
   (a) `WHERE type_op = 'RETRAIT'` ; (b) `WHERE id_compte = $1 AND type_op = 'PAIEMENT_CB' AND date_op > now() - interval '30 days'` ; (c) `WHERE libelle ILIKE '%loyer%'` ; (d) `WHERE date_op::date = '2024-05-01'`.
2. Un plan montre `Nested Loop (rows=1) (actual rows=250000 loops=1)`. Que s'est-il probablement passé et comment le corriger ?
3. Une table a 14 index pour 3 requêtes fréquentes. Les insertions sont lentes. Quelle démarche proposes-tu ?
4. Une application affiche les résultats page par page avec `OFFSET`. La page 5 000 met 4 secondes. Réécris la requête.
5. Un collègue veut mettre `work_mem = 1GB` globalement avec `max_connections = 400`. Réponds-lui chiffres à l'appui et propose une alternative.

---

## Quiz

1. Pourquoi faut-il baisser `random_page_cost` sur SSD ?
2. Que faut-il regarder en premier dans un plan lent ?
3. Quelle est la différence entre `EXPLAIN` et `EXPLAIN ANALYZE` ? Quel risque présente le second ?
4. Que signifie `loops=3` dans un nœud ?
5. Dans quel cas un index BRIN est-il pertinent ?
6. Pourquoi l'ordre des colonnes d'un index multicolonne est-il important ?
7. Quel est l'intérêt de `CREATE INDEX CONCURRENTLY` et que faire s'il échoue ?
8. Pourquoi trier `pg_stat_statements` par `total_exec_time` plutôt que par `mean_exec_time` ?
9. Quel indicateur d'un plan révèle un manque de `work_mem` ?
10. Quel mode de PgBouncer est le plus utilisé et quelle est sa principale contrainte ?

*Corrigés : [annexe D](annexes/D-corriges.md#module-07).*

---

## À retenir

- Mesurer avant de modifier ; une modification à la fois.
- Plans : comparer lignes estimées et réelles ; statistiques à jour et suffisantes.
- Index : pour des requêtes réelles ; clés étrangères indexées ; ordre des colonnes ; `CONCURRENTLY` en production ; supprimer les inutiles.
- `pg_stat_statements` + `auto_explain` = la boîte noire de la production.
- `work_mem` ciblé par rôle ; `random_page_cost = 1.1` sur SSD ; un pooler au-delà de quelques centaines de connexions.
