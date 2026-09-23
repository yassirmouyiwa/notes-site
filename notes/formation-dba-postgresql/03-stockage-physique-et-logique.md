# Module 03 — Stockage physique et logique

## Objectifs

- Relier les objets logiques (bases, schémas, tables) à leurs fichiers physiques.
- Décrire la structure d'une page de 8 Ko et d'une ligne (tuple).
- Comprendre TOAST, les « forks » (FSM, VM) et le fillfactor.
- Créer et utiliser des tablespaces.
- Mesurer l'espace occupé par chaque objet.
- Mettre en œuvre le partitionnement déclaratif.
- Choisir des types de données adaptés et optimiser l'ordre des colonnes.

---

## 1. Du logique au physique

| Niveau logique | Niveau physique |
|----------------|-----------------|
| Cluster | Répertoire PGDATA |
| Base de données | Sous-répertoire `base/<oid_base>/` (ou dans un tablespace) |
| Schéma | **Aucun** : purement logique, n'existe que dans le catalogue |
| Table, index, vue matérialisée, séquence | Un ou plusieurs fichiers `<relfilenode>` |
| Ligne | Un *tuple* dans une page |

### 1.1 Schémas

Un **schéma** est un espace de nommage : il regroupe des objets et permet de gérer les droits par ensemble.

```sql
CREATE SCHEMA compta AUTHORIZATION compta_owner;
CREATE TABLE compta.factures (...);
```

Le paramètre `search_path` définit l'ordre dans lequel PostgreSQL cherche un objet dont le schéma n'est pas précisé :

```sql
SHOW search_path;            -- "$user", public
SET search_path = bank, public;
SELECT * FROM clients;       -- trouvé dans bank
```

`"$user"` désigne un schéma portant le nom de l'utilisateur connecté, s'il existe.

> 🔐 **Angle sécurité**
> Le `search_path` est une source classique de vulnérabilités. Si un utilisateur peut créer des objets dans un schéma cherché **avant** le schéma légitime, il peut créer une fonction ou un opérateur homonyme qui sera appelé à la place de l'original, avec les droits de la victime. C'est la vulnérabilité **CVE-2018-1058**, qui a conduit PostgreSQL 15 à retirer par défaut le droit `CREATE` sur le schéma `public` pour tous les utilisateurs. On y revient aux modules 04 et 09.

### 1.2 Retrouver les fichiers d'une table

```sql
SELECT oid, relname, relfilenode, relkind, relpages, reltuples
FROM pg_class WHERE relname = 'clients';

SELECT pg_relation_filepath('bank.clients');
```

Le `relfilenode` est souvent égal à l'OID, mais il **change** quand la table est réécrite (`TRUNCATE`, `VACUUM FULL`, `CLUSTER`, certains `ALTER TABLE`). Les fichiers sont nommés d'après le `relfilenode`, pas d'après l'OID.

`relkind` : `r` table, `i` index, `S` séquence, `v` vue, `m` vue matérialisée, `p` table partitionnée, `t` table TOAST, `f` table étrangère.

---

## 2. Fichiers d'une relation : les « forks »

Chaque table ou index peut avoir plusieurs fichiers, appelés *forks* :

| Fichier | Fork | Contenu |
|---------|------|---------|
| `16398` | main | Les données elles-mêmes |
| `16398.1`, `16398.2`… | main | Segments suivants (un fichier par tranche de **1 Go**) |
| `16398_fsm` | Free Space Map | Espace libre disponible dans chaque page, pour placer les nouvelles lignes |
| `16398_vm` | Visibility Map | Pour chaque page : toutes les lignes sont-elles visibles par tous ? toutes sont-elles « gelées » ? Utilisée par VACUUM et par les *index-only scans* |
| `16398_init` | init | Uniquement pour les tables `UNLOGGED` : modèle vide restauré après un crash |

Le découpage en segments de 1 Go date d'une époque où certains systèmes de fichiers limitaient la taille des fichiers.

---

## 3. Structure d'une page

Chaque fichier est une suite de pages de **8 Ko** (valeur fixée à la compilation).

```
┌──────────────────────────────────────────────────────────┐
│ En-tête de page (24 octets) : LSN, checksum, pointeurs   │
├──────────────────────────────────────────────────────────┤
│ Pointeurs de lignes (4 octets chacun) → lp1 lp2 lp3 …    │
│                     ↓ (croissent vers le bas)            │
│                                                          │
│                 ESPACE LIBRE                             │
│                                                          │
│                     ↑ (croissent vers le haut)           │
│ … tuple 3 │ tuple 2 │ tuple 1                            │
├──────────────────────────────────────────────────────────┤
│ Zone spéciale (utilisée par les index)                   │
└──────────────────────────────────────────────────────────┘
```

- L'**en-tête** contient notamment le **LSN** du dernier enregistrement WAL ayant modifié la page (utilisé lors de la reprise) et la **somme de contrôle**.
- Les **pointeurs de lignes** (*line pointers*) indiquent la position de chaque tuple dans la page. Une ligne est identifiée par son **ctid** = (numéro de page, numéro de pointeur), par exemple `(0,3)`.
- Les **tuples** sont écrits depuis la fin de la page.

### 3.1 Structure d'un tuple

Chaque ligne commence par un **en-tête de 23 octets** (aligné à 24) qui contient :

| Champ | Rôle |
|-------|------|
| `t_xmin` | Identifiant de la transaction qui a **créé** cette version de ligne |
| `t_xmax` | Identifiant de la transaction qui l'a **supprimée** ou verrouillée (0 sinon) |
| `t_ctid` | Pointeur vers la version plus récente de la ligne (après un `UPDATE`) |
| `t_infomask` | Indicateurs (valeurs NULL présentes, transaction validée, etc.) |
| Bitmap des NULL | Une valeur NULL n'occupe **aucune place** dans les données, seulement un bit |

Les champs `xmin` / `xmax` sont le cœur du **MVCC** (module 05). On peut les voir directement :

```sql
SELECT ctid, xmin, xmax, id_agence, ville FROM bank.agences;
```

### 3.2 Alignement et ordre des colonnes

Les valeurs sont **alignées** en mémoire selon leur type : un `bigint` (8 octets) doit commencer à une adresse multiple de 8. Placer un `smallint` (2 octets) avant un `bigint` crée 6 octets de remplissage (*padding*) perdus.

```sql
SELECT pg_column_size(ROW(1::smallint, 1::bigint, 1::smallint, 1::bigint)) AS mal_ordonne,
       pg_column_size(ROW(1::bigint, 1::bigint, 1::smallint, 1::smallint)) AS bien_ordonne;
```

Règle pratique pour les grosses tables : placer les colonnes de taille fixe **de la plus grande à la plus petite** (`bigint`, `timestamptz`, `double precision` → `integer`, `date` → `smallint`, `boolean`), puis les colonnes de taille variable (`text`, `numeric`, `jsonb`). Sur des centaines de millions de lignes, le gain atteint souvent 10 à 20 %.

---

## 4. TOAST : les grandes valeurs

Une ligne doit tenir dans une page de 8 Ko. Pour les valeurs volumineuses (`text` long, `jsonb`, `bytea`), PostgreSQL utilise **TOAST** (*The Oversized-Attribute Storage Technique*) :

1. Quand une ligne dépasse environ **2 Ko**, PostgreSQL tente d'abord de **compresser** les grandes valeurs.
2. Si c'est insuffisant, il les **déplace** dans une table TOAST associée, découpées en morceaux, et ne garde qu'un pointeur dans la ligne.

Chaque colonne a une **stratégie** :

| Stratégie | Compression | Stockage externe | Usage |
|-----------|-------------|------------------|-------|
| `PLAIN` | Non | Non | Types de taille fixe |
| `MAIN` | Oui | En dernier recours | — |
| `EXTERNAL` | Non | Oui | Données déjà compressées (images) ; accès rapide aux sous-chaînes |
| `EXTENDED` | Oui | Oui | Défaut pour `text`, `jsonb`, `bytea` |

```sql
ALTER TABLE ma_table ALTER COLUMN photo SET STORAGE EXTERNAL;
ALTER TABLE ma_table ALTER COLUMN doc SET COMPRESSION lz4;   -- PG 14+, plus rapide que pglz
```

Le paramètre `default_toast_compression` choisit l'algorithme par défaut (`pglz` ou `lz4`).

Conséquence pratique : `SELECT *` sur une table avec de gros documents JSON lit aussi la table TOAST. Sélectionner uniquement les colonnes nécessaires évite ce coût.

---

## 5. Fillfactor et mises à jour HOT

Le **fillfactor** est le pourcentage de remplissage d'une page lors des insertions (défaut 100 % pour les tables, 90 % pour les index B-tree).

```sql
ALTER TABLE bank.comptes SET (fillfactor = 85);
```

L'espace laissé libre permet les mises à jour **HOT** (*Heap-Only Tuple*) : quand un `UPDATE` ne modifie **aucune colonne indexée** et qu'il reste de la place dans **la même page**, la nouvelle version de ligne est écrite dans cette page **sans modifier les index**. C'est beaucoup plus rapide et cela limite la croissance des index.

Pour une table très souvent mise à jour (soldes de comptes, compteurs), un fillfactor de 70 à 90 est pertinent. On mesure l'efficacité avec :

```sql
SELECT relname, n_tup_upd, n_tup_hot_upd,
       round(100.0 * n_tup_hot_upd / nullif(n_tup_upd, 0), 1) AS pct_hot
FROM pg_stat_user_tables ORDER BY n_tup_upd DESC;
```

---

## 6. Tables UNLOGGED et temporaires

| Type | WAL | Après un crash | Répliquée | Usage |
|------|-----|----------------|-----------|-------|
| Normale | Oui | Conservée | Oui | Données métier |
| `UNLOGGED` | **Non** | **Vidée** | **Non** | Données de travail reconstructibles, caches, tables de chargement |
| `TEMPORARY` | Non | Disparaît (fin de session) | Non | Calculs intermédiaires d'une session |

```sql
CREATE UNLOGGED TABLE bank.import_brut (...);
```

Les tables `UNLOGGED` sont nettement plus rapides en écriture, mais leurs données ne sont **pas** dans les sauvegardes physiques ni sur les répliques.

---

## 7. Tablespaces

Un **tablespace** est un répertoire du système de fichiers où PostgreSQL peut stocker des objets. Il permet de répartir les données sur plusieurs disques.

```bash
$ sudo mkdir -p /srv/pg_rapide
$ sudo chown postgres:postgres /srv/pg_rapide
$ sudo chmod 700 /srv/pg_rapide
```

```sql
CREATE TABLESPACE rapide OWNER postgres LOCATION '/srv/pg_rapide';
CREATE TABLE bank.chaud (...) TABLESPACE rapide;
CREATE INDEX ... TABLESPACE rapide;
ALTER TABLE bank.operations SET TABLESPACE rapide;      -- réécrit la table, verrou exclusif !
ALTER DATABASE banque SET TABLESPACE rapide;            -- base inutilisée pendant l'opération
SET default_tablespace = rapide;
SET temp_tablespaces = 'rapide';                        -- fichiers temporaires (tris sur disque)
```

Deux tablespaces existent toujours : `pg_default` (dans `base/`) et `pg_global` (dans `global/`).

Dans PGDATA, `pg_tblspc/` contient des **liens symboliques** vers les répertoires des tablespaces.

### Usages pertinents

- Placer les **index** ou les tables les plus sollicitées sur un stockage plus rapide.
- Placer les **fichiers temporaires** sur un disque dédié.
- Gérer un disque plein en déplaçant une grosse table.

### Pièges

- Un tablespace fait **partie intégrante du cluster**. Il ne se sauvegarde pas indépendamment ; perdre son disque, c'est perdre le cluster.
- Ne jamais placer un tablespace sur un stockage éphémère (tmpfs, disque local d'une instance cloud).
- Ne jamais placer un tablespace **à l'intérieur** de PGDATA.
- Avec les SSD et le stockage en réseau modernes, le gain des tablespaces est plus limité qu'autrefois.

---

## 8. Mesurer l'espace disque

| Fonction | Mesure |
|----------|--------|
| `pg_database_size('banque')` | Taille d'une base |
| `pg_relation_size('t')` | Fork principal d'une table **seule** |
| `pg_table_size('t')` | Table + TOAST + FSM + VM (sans les index) |
| `pg_indexes_size('t')` | Tous les index de la table |
| `pg_total_relation_size('t')` | Tout : table, TOAST, index |
| `pg_tablespace_size('rapide')` | Taille d'un tablespace |
| `pg_size_pretty(...)` | Affichage lisible |

Top 10 des tables les plus volumineuses :

```sql
SELECT n.nspname AS schema, c.relname AS table_,
       pg_size_pretty(pg_table_size(c.oid))          AS donnees,
       pg_size_pretty(pg_indexes_size(c.oid))        AS index_,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS total
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'p', 'm')
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(c.oid) DESC
LIMIT 10;
```

### Le « bloat » (gonflement)

À cause du MVCC, les `UPDATE` et `DELETE` laissent des versions mortes de lignes. `VACUUM` rend leur espace **réutilisable**, mais ne le rend pas au système (sauf en fin de fichier). Une table peut donc occuper beaucoup plus d'espace que ses données vivantes : c'est le **bloat**. Il se traite au module 05 (`VACUUM FULL`, `pg_repack`).

---

## 9. Partitionnement déclaratif

### 9.1 Principe

Une **table partitionnée** est une table logique dont les données sont réparties dans plusieurs **partitions** (des tables physiques) selon une clé.

| Méthode | Principe | Exemple |
|---------|----------|---------|
| `RANGE` | Intervalles de valeurs | Une partition par mois ou par année |
| `LIST` | Liste de valeurs | Une partition par région ou par pays |
| `HASH` | Modulo d'un hachage | Répartition uniforme sur N partitions |

### 9.2 Avantages

- **Élagage de partitions** (*partition pruning*) : une requête filtrant sur la clé ne lit que les partitions concernées.
- **Purge instantanée** : supprimer un mois de données = `DROP` ou `DETACH` d'une partition, au lieu d'un énorme `DELETE` qui génère du WAL et du bloat.
- **Maintenance par morceaux** : VACUUM et index sur des tables plus petites.
- **Archivage** : détacher une ancienne partition et la déplacer vers un tablespace lent.

### 9.3 Contraintes

- La clé primaire et les contraintes d'unicité doivent **inclure la clé de partitionnement**.
- Trop de partitions (plusieurs milliers) dégradent la planification.
- Une requête qui ne filtre pas sur la clé lit toutes les partitions.

### 9.4 Exemple

```sql
CREATE TABLE bank.operations_part (
    id_operation  bigint NOT NULL,
    id_compte     bigint NOT NULL,
    type_op       text NOT NULL,
    montant       numeric(12,2) NOT NULL,
    date_op       timestamptz NOT NULL,
    libelle       text,
    PRIMARY KEY (id_operation, date_op)
) PARTITION BY RANGE (date_op);

CREATE TABLE bank.operations_2023 PARTITION OF bank.operations_part
    FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');
CREATE TABLE bank.operations_2024 PARTITION OF bank.operations_part
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
CREATE TABLE bank.operations_2025 PARTITION OF bank.operations_part
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');
CREATE TABLE bank.operations_defaut PARTITION OF bank.operations_part DEFAULT;
```

La borne inférieure est **incluse**, la borne supérieure **exclue**. La partition `DEFAULT` reçoit les lignes qui ne correspondent à aucune autre (sans elle, l'insertion échoue).

Un index créé sur la table partitionnée est automatiquement créé sur chaque partition.

Opérations de gestion :

```sql
-- Détacher une partition (elle devient une table indépendante)
ALTER TABLE bank.operations_part DETACH PARTITION bank.operations_2023;
-- PG 14+ : sans bloquer les requêtes concurrentes
ALTER TABLE bank.operations_part DETACH PARTITION bank.operations_2023 CONCURRENTLY;

-- Attacher une table existante comme partition
ALTER TABLE bank.operations_part ATTACH PARTITION bank.operations_2023
    FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');
```

Astuce : avant un `ATTACH`, ajouter sur la table une contrainte `CHECK` correspondant exactement aux bornes évite que PostgreSQL parcoure toute la table pour valider les données.

L'extension **pg_partman** automatise la création des futures partitions et la purge des anciennes.

---

## 10. Choisir ses types de données

| Besoin | Bon choix | À éviter | Raison |
|--------|-----------|----------|--------|
| Montant financier | `numeric(p,s)` | `real`, `double precision`, `money` | Les flottants sont inexacts (0,1 + 0,2 ≠ 0,3) ; `money` dépend de la locale |
| Horodatage | `timestamptz` | `timestamp` | `timestamptz` stocke un instant absolu (UTC) et convertit selon le fuseau de la session |
| Texte | `text` ou `varchar(n)` si limite métier | `char(n)` | `char(n)` complète avec des espaces ; aucun gain de performance |
| Identifiant | `bigint GENERATED ALWAYS AS IDENTITY` | `serial` | `serial` est l'ancienne syntaxe ; `bigint` évite l'épuisement à 2,1 milliards |
| Identifiant non prévisible | `uuid` (v7 conseillé pour l'ordre d'insertion, `uuidv7()` en PG 18) | entier séquentiel exposé publiquement | Un identifiant séquentiel dans une URL permet l'énumération des ressources (faille IDOR) |
| Booléen | `boolean` | `char(1)`, `int` | Lisibilité, contraintes |
| Adresse IP | `inet`, `cidr` | `text` | Validation, opérateurs réseau (`<<=`, appartenance à un sous-réseau) |
| Document semi-structuré | `jsonb` | `json`, `text` | `jsonb` est indexable (GIN) et plus rapide à interroger |

> 🔐 **Angle sécurité**
> Les types natifs sont une première validation des entrées : une colonne `inet` refuse une valeur qui n'est pas une adresse IP, une contrainte `CHECK` refuse un montant négatif. Les contraintes en base protègent l'intégrité **même si l'application est contournée**.

---

## TP 3 — Explorer le stockage

### Étape 1 : fichiers d'une table

```sql
banque=# SELECT relname, relfilenode, relpages, reltuples::bigint
         FROM pg_class
         WHERE relnamespace = 'bank'::regnamespace AND relkind = 'r';
banque=# SELECT pg_relation_filepath('bank.operations');
```

```bash
$ sudo ls -lh /var/lib/postgresql/16/main/base/<oid>/<relfilenode>*
```

Tu dois voir le fichier principal, ses segments `.1`, `.2`… si la table dépasse 1 Go, et les fichiers `_fsm` et `_vm`.

Vérifie que `relpages × 8 Ko` correspond à la taille réelle du fichier.

### Étape 2 : le relfilenode change après réécriture

```sql
banque=# CREATE TABLE bank.demo AS SELECT g AS id, md5(g::text) AS h FROM generate_series(1, 10000) g;
banque=# SELECT oid, relfilenode FROM pg_class WHERE relname = 'demo';
banque=# VACUUM FULL bank.demo;
banque=# SELECT oid, relfilenode FROM pg_class WHERE relname = 'demo';
```

L'OID est inchangé, le relfilenode a changé : `VACUUM FULL` a écrit une nouvelle copie de la table.

### Étape 3 : inspecter une page avec `pageinspect`

```sql
banque=# CREATE EXTENSION pageinspect;
banque=# SELECT * FROM page_header(get_raw_page('bank.agences', 0));
banque=# SELECT lp, lp_off, lp_len, t_xmin, t_xmax, t_ctid
         FROM heap_page_items(get_raw_page('bank.agences', 0));
```

Tu remarqueras probablement des `t_xmax` **non nuls** alors qu'aucune agence n'a été modifiée ni supprimée. Ce ne sont pas des suppressions : `xmax` sert aussi à enregistrer les **verrous de ligne**. Lors du chargement des clients, chaque contrôle de clé étrangère vers `agences` a posé un verrou `FOR KEY SHARE` sur l'agence référencée (module 05). Les bits de `t_infomask` distinguent un verrou d'une suppression.

Modifie une ligne, puis réinspecte la page :

```sql
banque=# UPDATE bank.agences SET ville = 'Tetouan' WHERE id_agence = 1;
banque=# SELECT lp, t_xmin, t_xmax, t_ctid
         FROM heap_page_items(get_raw_page('bank.agences', 0));
```

Observe : l'ancienne version (lp 1) a maintenant un `t_xmax` et un `t_ctid` pointant vers une **nouvelle** version (lp 7). Les deux coexistent physiquement. C'est le MVCC en action.

```sql
banque=# UPDATE bank.agences SET ville = 'Tétouan' WHERE id_agence = 1;
```

> 🔐 **Angle sécurité (forensics)**
> Les anciennes versions restent physiquement présentes dans les pages jusqu'au passage de VACUUM et à la réutilisation de l'espace. Une donnée « supprimée » par `DELETE` ou écrasée par `UPDATE` peut donc être récupérée par lecture directe des fichiers. C'est utile en investigation, et c'est un risque pour l'effacement de données personnelles (droit à l'effacement) : une suppression logique n'est pas un effacement physique immédiat.

### Étape 4 : alignement des colonnes

```sql
banque=# CREATE TABLE bank.mal_ordonne (a boolean, b bigint, c boolean, d bigint, e boolean, f bigint);
banque=# CREATE TABLE bank.bien_ordonne (b bigint, d bigint, f bigint, a boolean, c boolean, e boolean);
banque=# INSERT INTO bank.mal_ordonne  SELECT true, g, true, g, true, g FROM generate_series(1, 1000000) g;
banque=# INSERT INTO bank.bien_ordonne SELECT g, g, g, true, true, true FROM generate_series(1, 1000000) g;
banque=# SELECT pg_size_pretty(pg_relation_size('bank.mal_ordonne'))  AS mal,
                pg_size_pretty(pg_relation_size('bank.bien_ordonne')) AS bien;
banque=# DROP TABLE bank.mal_ordonne, bank.bien_ordonne, bank.demo;
```

Calcule le pourcentage d'espace gagné.

### Étape 5 : tablespace

Crée le tablespace `rapide` (section 7), puis :

```sql
banque=# CREATE TABLE bank.test_tbs (id int) TABLESPACE rapide;
banque=# SELECT pg_relation_filepath('bank.test_tbs');
```

```bash
$ sudo ls -l /var/lib/postgresql/16/main/pg_tblspc/
$ sudo find /srv/pg_rapide -type f
```

Observe le lien symbolique et l'arborescence créée dans le tablespace (sous-répertoire propre à la version).

```sql
banque=# DROP TABLE bank.test_tbs;
banque=# DROP TABLESPACE rapide;
```

### Étape 6 : partitionnement et élagage

Crée `bank.operations_part` (section 9.4), puis :

```sql
banque=# INSERT INTO bank.operations_part
         SELECT id_operation, id_compte, type_op, montant, date_op, libelle
         FROM bank.operations;
banque=# SELECT tableoid::regclass AS partition, count(*)
         FROM bank.operations_part GROUP BY 1 ORDER BY 1;
banque=# EXPLAIN SELECT sum(montant) FROM bank.operations_part
         WHERE date_op >= '2024-03-01' AND date_op < '2024-04-01';
banque=# EXPLAIN SELECT sum(montant) FROM bank.operations_part
         WHERE montant > 4000;
```

Dans le premier plan, seule `operations_2024` est lue. Dans le second, toutes les partitions le sont.

Mesure la différence entre une purge par `DELETE` et par `DETACH`/`DROP` :

```sql
banque=# \timing on
banque=# SELECT pg_current_wal_lsn() AS avant \gset
banque=# DELETE FROM bank.operations_part WHERE date_op < '2024-01-01';
banque=# SELECT pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), :'avant')) AS wal_genere;
```

Recharge les données 2023 dans la partition :

```sql
banque=# INSERT INTO bank.operations_part
         SELECT id_operation, id_compte, type_op, montant, date_op, libelle
         FROM bank.operations WHERE date_op < '2024-01-01';
```

Puis compare avec une purge par détachement :

```sql
banque=# SELECT pg_current_wal_lsn() AS avant \gset
banque=# ALTER TABLE bank.operations_part DETACH PARTITION bank.operations_2023;
banque=# DROP TABLE bank.operations_2023;
banque=# SELECT pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), :'avant')) AS wal_genere;
```

La méta-commande `\gset` stocke le résultat d'une requête dans une variable psql.

---

## Exercices

1. La table `logs_web` reçoit 50 millions de lignes par mois ; on conserve 12 mois. Propose une stratégie de partitionnement, la procédure mensuelle de maintenance et justifie tes choix.
2. Pourquoi une clé primaire sur une table partitionnée par date doit-elle contenir la colonne de date ? Quelle conséquence sur l'unicité de `id_operation` ?
3. Une table `sessions_web` est mise à jour 500 fois par seconde (colonne `derniere_activite`, non indexée). Quel réglage de stockage proposes-tu et comment mesures-tu son efficacité ?
4. Un développeur propose de stocker les montants en `double precision`. Rédige un argumentaire de trois lignes, avec un exemple SQL démontrant le problème.
5. Explique pourquoi un identifiant séquentiel exposé dans une URL (`/facture/1042`) peut poser un problème de sécurité et propose une solution côté base.

---

## Quiz

1. Un schéma correspond-il à un répertoire sur disque ?
2. Quelle est la taille maximale d'un fichier de segment de table ?
3. Que contiennent les forks `_fsm` et `_vm` ?
4. Qu'est-ce qu'un `ctid` ?
5. Que stockent `xmin` et `xmax` dans l'en-tête d'un tuple ?
6. À partir de quelle taille approximative de ligne TOAST intervient-il ?
7. Qu'est-ce qu'une mise à jour HOT et quelle condition doit-elle remplir ?
8. Que devient le contenu d'une table `UNLOGGED` après un crash ?
9. Quelle fonction mesure la taille totale d'une table, index et TOAST compris ?
10. Qu'est-ce que l'élagage de partitions ?

*Corrigés : [annexe D](annexes/D-corriges.md#module-03).*

---

## À retenir

- Base → répertoire ; table/index → fichiers `relfilenode` de 1 Go max ; pages de 8 Ko ; lignes identifiées par `ctid`.
- Chaque ligne porte `xmin`/`xmax` : les anciennes versions restent physiquement présentes jusqu'au VACUUM.
- TOAST gère les grandes valeurs ; le fillfactor favorise les mises à jour HOT.
- Tablespaces : utiles mais indissociables du cluster.
- Partitionnement : élagage des requêtes et purge instantanée, à condition de filtrer sur la clé.
- Types adaptés = intégrité, performance et sécurité.
