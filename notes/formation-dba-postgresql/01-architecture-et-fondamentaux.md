# Module 01 — Architecture et fondamentaux

## Objectifs

- Définir le rôle et les responsabilités d'un DBA.
- Distinguer **instance** et **base de données**, **cluster** et **base**.
- Décrire les processus, les zones mémoire et les fichiers de PostgreSQL.
- Expliquer le principe du **Write-Ahead Logging** et la reprise après crash.
- Suivre le parcours complet d'une requête, de la connexion au résultat.
- Identifier les premières surfaces d'attaque d'un SGBD.

---

## 1. Le métier de DBA

Le **DBA** (*Database Administrator*) est responsable de la disponibilité, de l'intégrité, de la performance et de la sécurité des données. On distingue souvent :

| Profil | Missions principales |
|--------|----------------------|
| **DBA système / production** | Installation, configuration, sauvegardes, haute disponibilité, montées de version, supervision, incidents |
| **DBA d'études / applicatif** | Modélisation, optimisation des requêtes, revue du code SQL, conseil aux développeurs |
| **DBA sécurité** | Gestion des accès, chiffrement, audit, conformité (RGPD, loi 09-08), réponse aux incidents de sécurité |

Dans la réalité, surtout en PME, une seule personne cumule ces trois profils.

### Les responsabilités, par ordre d'importance

1. **Ne jamais perdre de données** : sauvegardes testées, réplication.
2. **Garantir la disponibilité** : la base doit répondre quand l'application en a besoin.
3. **Protéger les données** : confidentialité, intégrité, traçabilité.
4. **Assurer la performance** : temps de réponse acceptables sous charge.
5. **Anticiper** : capacité disque, croissance, fin de support des versions.

Un DBA qui optimise brillamment des requêtes mais n'a jamais testé une restauration a échoué à sa mission n°1.

---

## 2. Rappel : qu'est-ce qu'un SGBD relationnel ?

Un **SGBD** (Système de Gestion de Bases de Données) est le logiciel qui stocke les données et en contrôle l'accès. Un **SGBDR** (relationnel) organise les données en **tables** (relations), manipulées en **SQL**, avec des garanties fortes :

- **Intégrité** : contraintes (`PRIMARY KEY`, `FOREIGN KEY`, `CHECK`, `NOT NULL`, `UNIQUE`).
- **Transactions ACID** : Atomicité, Cohérence, Isolation, Durabilité (détaillé au module 05).
- **Concurrence** : de nombreux utilisateurs simultanés sans corruption.
- **Contrôle d'accès** : qui peut lire ou modifier quoi.

### Pourquoi PostgreSQL ?

- Open source (licence PostgreSQL, proche de BSD/MIT), sans coût de licence.
- Très conforme au standard SQL, extensible (types, fonctions, index, extensions).
- Robuste, utilisé en production critique (banques, télécoms, administrations).
- Écosystème riche : PostGIS, TimescaleDB, pgvector, Citus…
- Nouvelle version majeure chaque année (septembre/octobre), **supportée 5 ans**, versions mineures correctives environ tous les trimestres.

---

## 3. Instance, cluster et bases de données

### 3.1 Vocabulaire PostgreSQL

| Terme | Définition |
|-------|------------|
| **Cluster** (ou *cluster de bases*) | Un ensemble de bases de données gérées par **une seule instance**, stockées dans **un seul répertoire de données** (PGDATA) et écoutant sur **un seul port**. Rien à voir avec un cluster de serveurs. |
| **Instance** | Les processus et la mémoire partagée qui font vivre un cluster. Elle existe seulement quand le serveur tourne. |
| **Base de données** | Un espace de nommage au sein du cluster. Un client se connecte toujours à **une** base précise et ne voit pas les tables des autres bases. |
| **Schéma** | Un espace de nommage au sein d'une base (équivalent d'un dossier). Une table s'écrit complètement `base.schema.table`. |

Hiérarchie :

```
Serveur Linux
└── Cluster (PGDATA=/var/lib/postgresql/16/main, port 5432)  ← 1 instance
    ├── Base "postgres"          (base d'administration par défaut)
    ├── Base "template1"         (modèle copié par CREATE DATABASE)
    ├── Base "template0"         (modèle vierge, jamais modifié)
    └── Base "banque"
        ├── Schéma "public"
        ├── Schéma "bank"
        │   ├── Table clients
        │   └── Table comptes …
        └── Schéma "pg_catalog"  (catalogue système)
```

Certains objets sont **globaux au cluster** : les **rôles** (utilisateurs), les **tablespaces** et la liste des bases. Un rôle créé existe donc pour toutes les bases du cluster.

### 3.2 Instance ≠ base de données

C'est la distinction fondamentale :

- La **base de données** (au sens physique) est un ensemble de **fichiers sur disque**. Elle persiste quand le serveur est arrêté.
- L'**instance** est ce qui tourne **en mémoire** : processus + mémoire partagée. Elle disparaît à l'arrêt.

Démarrer PostgreSQL, c'est démarrer une instance qui ouvre les fichiers d'un cluster. On peut avoir **plusieurs clusters** sur la même machine (versions différentes, ou même version sur des ports différents) : c'est ce qu'on fera au module 08 pour la réplication.

---

## 4. Architecture des processus

PostgreSQL utilise un modèle **multi-processus** : chaque tâche est un processus Linux distinct, communiquant par mémoire partagée.

```
                         Client (psql, application)
                                    │  TCP 5432 ou socket Unix
                                    ▼
┌──────────────────────────────────────────────────────────────────┐
│  postmaster (processus père)                                     │
│   │ fork() à chaque connexion                                    │
│   ├── backend (client 1)   ─┐                                    │
│   ├── backend (client 2)   ─┤                                    │
│   ├── backend (client n)   ─┤    lisent / écrivent               │
│   │                         ▼                                    │
│   │        ┌──────────── MÉMOIRE PARTAGÉE ─────────────┐         │
│   │        │ shared_buffers │ WAL buffers │ verrous …  │         │
│   │        └───────────────────────────────────────────┘         │
│   │                         ▲                                    │
│   ├── checkpointer        ──┤                                    │
│   ├── background writer   ──┤                                    │
│   ├── walwriter           ──┤                                    │
│   ├── autovacuum launcher ──┤  (+ autovacuum workers)            │
│   ├── logical replication launcher                               │
│   ├── archiver (si archive_mode=on)                              │
│   └── walsender / walreceiver (si réplication)                   │
└──────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                      Fichiers : données, WAL, config
```

### 4.1 Rôle de chaque processus

| Processus | Rôle |
|-----------|------|
| **postmaster** | Processus père. Écoute les connexions, lance (`fork`) un backend par client, surveille les autres processus et relance l'instance en cas de plantage d'un fils. |
| **backend** | Un par connexion cliente. Analyse, planifie et exécute les requêtes de ce client. |
| **checkpointer** | Réalise les **checkpoints** : écrit sur disque toutes les pages modifiées en mémoire, pour limiter la durée de la reprise après crash. |
| **background writer** | Écrit progressivement des pages modifiées pour que les backends trouvent toujours des pages libres en mémoire. |
| **walwriter** | Écrit régulièrement le contenu des WAL buffers dans les fichiers WAL. |
| **autovacuum launcher / workers** | Nettoient automatiquement les anciennes versions de lignes et mettent à jour les statistiques (module 05). |
| **archiver** | Copie les fichiers WAL terminés vers un stockage d'archive (module 06). |
| **walsender / walreceiver** | Envoient / reçoivent le flux WAL pour la réplication (module 08). |
| **logical replication launcher** | Gère les processus de réplication logique (module 08). |

### 4.2 Conséquences pratiques du modèle multi-processus

- **Isolation** : un backend qui plante (bug d'extension, erreur mémoire) ne corrompt pas directement la mémoire privée des autres. Cependant, par précaution, le postmaster **redémarre toute l'instance** si un backend meurt anormalement, car la mémoire partagée pourrait être incohérente.
- **Coût par connexion** : chaque connexion est un processus (quelques Mo de mémoire, coût de `fork`). Des milliers de connexions directes dégradent les performances. On utilise alors un **pooler** comme **PgBouncer** (module 07).
- **Visibilité système** : chaque backend est visible avec `ps`, et son titre indique l'utilisateur, la base, l'adresse du client et l'état. On peut le tuer côté PostgreSQL avec `pg_terminate_backend(pid)`.

> 🔐 **Angle sécurité**
> Le titre des processus (`ps -ef`) révèle quel utilisateur est connecté à quelle base, depuis quelle IP. Tout utilisateur local du serveur peut le lire. C'est une fuite d'information mineure mais réelle sur un serveur partagé : un serveur de base de données ne doit héberger **aucun autre service** accessible à des utilisateurs non administrateurs.

---

## 5. Architecture mémoire

### 5.1 Mémoire partagée (commune à tous les processus)

| Zone | Paramètre | Rôle |
|------|-----------|------|
| **Shared buffers** | `shared_buffers` (défaut 128 Mo) | Cache des pages de données (tables, index). Toute lecture ou écriture passe par là. |
| **WAL buffers** | `wal_buffers` (défaut : auto, 1/32 de shared_buffers, plafonné à 16 Mo) | Tampon des enregistrements WAL avant écriture sur disque. |
| **Table des verrous** | `max_locks_per_transaction` | Verrous posés par les transactions en cours. |
| **CLOG / état des transactions** | — | Statut (validée, annulée, en cours) de chaque transaction récente. |

### 5.2 Mémoire privée (propre à chaque backend)

| Zone | Paramètre | Rôle |
|------|-----------|------|
| **work_mem** | défaut 4 Mo | Mémoire pour **chaque opération** de tri, hachage, etc. Une requête complexe peut en utiliser plusieurs fois. |
| **maintenance_work_mem** | défaut 64 Mo | Opérations de maintenance : `VACUUM`, `CREATE INDEX`, `ALTER TABLE ADD FOREIGN KEY`. |
| **temp_buffers** | défaut 8 Mo | Cache des tables temporaires. |

**Piège classique** : `work_mem` s'applique **par opération et par connexion**. Avec `work_mem = 256MB`, 200 connexions et 3 tris par requête, la consommation théorique atteint 150 Go. Il faut donc raisonner en pire cas.

### 5.3 Le double cache

PostgreSQL ne gère pas le disque directement : il passe par le système de fichiers, qui a son propre cache (le **page cache** Linux). Une page peut donc être en mémoire deux fois : dans `shared_buffers` et dans le cache du noyau. C'est pourquoi on ne donne pas toute la RAM à `shared_buffers` : la règle de départ est **25 % de la RAM**, le reste profitant au cache du système. Le paramètre `effective_cache_size` indique au planificateur la taille totale de cache disponible (shared_buffers + cache OS), sans rien allouer.

---

## 6. Organisation des fichiers

### 6.1 Le répertoire de données (PGDATA)

```
/var/lib/postgresql/16/main/
├── base/                 ← une sous-arborescence par base (nommée par OID)
│   ├── 1/                   template1
│   ├── 4/                   template0
│   ├── 5/                   postgres
│   └── 16384/               banque  → fichiers des tables et index
├── global/               ← objets partagés : rôles, liste des bases, pg_control
├── pg_wal/               ← journal de transactions (WAL), segments de 16 Mo
├── pg_xact/              ← état des transactions (validée / annulée)
├── pg_multixact/         ← verrous partagés multiples sur une ligne
├── pg_subtrans/          ← sous-transactions (SAVEPOINT)
├── pg_tblspc/            ← liens symboliques vers les tablespaces
├── pg_stat/              ← statistiques persistées à l'arrêt
├── pg_replslot/          ← slots de réplication
├── pg_logical/           ← données de réplication logique
├── PG_VERSION            ← version majeure du cluster
├── postmaster.pid        ← PID du postmaster, présent quand l'instance tourne
└── postgresql.auto.conf  ← paramètres modifiés par ALTER SYSTEM
```

Sur Debian/Ubuntu, `postgresql.conf`, `pg_hba.conf` et `pg_ident.conf` sont dans `/etc/postgresql/16/main/`. Sur une installation « standard » (compilée, RHEL, Docker), ils sont directement dans PGDATA.

> ⚠️ **Règle d'or** : on ne modifie **jamais** à la main le contenu de `base/`, `pg_wal/` ou `pg_xact/`. Supprimer des fichiers WAL « pour libérer de la place » est l'erreur qui détruit le plus de bases en production.

### 6.2 Tables et index sur disque

Chaque table et chaque index est stocké dans un ou plusieurs fichiers nommés par un numéro (*relfilenode*), découpés en segments de 1 Go. Chaque fichier est une suite de **pages** (ou **blocs**) de **8 Ko**. Le module 03 détaille cette structure.

```sql
banque=# SELECT pg_relation_filepath('bank.clients');
 pg_relation_filepath
----------------------
 base/16384/16398
```

---

## 7. Le journal de transactions (WAL)

### 7.1 Le problème à résoudre

Une transaction peut modifier des dizaines de pages dispersées sur le disque. Si le serveur s'arrête brutalement au milieu de leur écriture (coupure de courant, noyau qui plante), les fichiers de données deviennent **incohérents**. Écrire toutes les pages sur disque à chaque `COMMIT` résoudrait le problème, mais au prix de très nombreuses écritures aléatoires, donc de performances catastrophiques.

### 7.2 La solution : Write-Ahead Logging

Le principe du **WAL** tient en une règle :

> **Toute modification est d'abord décrite dans le journal, et ce journal est écrit sur disque *avant* que la modification soit considérée comme validée.**

Déroulement d'un `UPDATE` suivi d'un `COMMIT` :

1. Le backend charge la page concernée dans `shared_buffers` (si elle n'y est pas déjà).
2. Il modifie la page **en mémoire** (elle devient « sale », *dirty*).
3. Il écrit un **enregistrement WAL** décrivant la modification dans les WAL buffers.
4. Au `COMMIT`, les enregistrements WAL de la transaction sont écrits **et synchronisés** (`fsync`) sur disque dans `pg_wal/`.
5. Le client reçoit la confirmation du `COMMIT`.
6. Plus tard, le background writer ou le checkpointer écrit la page modifiée dans le fichier de données.

L'écriture du WAL est **séquentielle** (on ajoute à la fin d'un fichier), donc très rapide, même sur disque mécanique. Les écritures aléatoires des pages de données sont regroupées et différées.

### 7.3 La reprise après crash

Au redémarrage après un arrêt brutal :

1. PostgreSQL lit le fichier `global/pg_control` pour trouver la position du **dernier checkpoint**.
2. Il relit le WAL à partir de ce point et **rejoue** (*redo*) toutes les modifications.
3. Les transactions validées sont ainsi restaurées ; celles qui n'étaient pas validées restent invisibles (grâce au MVCC, module 05).

C'est la garantie de **durabilité** (le « D » de ACID).

### 7.4 Les checkpoints

Un **checkpoint** est un point où toutes les pages modifiées en mémoire ont été écrites sur disque. Après un checkpoint, le WAL antérieur n'est plus nécessaire à la reprise après crash et peut être recyclé.

| Paramètre | Défaut | Effet |
|-----------|--------|-------|
| `checkpoint_timeout` | 5 min | Durée maximale entre deux checkpoints |
| `max_wal_size` | 1 Go | Volume de WAL déclenchant un checkpoint anticipé |
| `checkpoint_completion_target` | 0.9 | Étale les écritures sur 90 % de l'intervalle pour lisser la charge disque |

Compromis : des checkpoints fréquents raccourcissent la reprise après crash mais augmentent les écritures ; des checkpoints espacés font l'inverse.

### 7.5 Le WAL sert à bien plus que la reprise après crash

Le même flux WAL est la base de :

- l'**archivage continu** et la **restauration à un instant donné** (PITR, module 06) ;
- la **réplication physique** (module 08) ;
- la **réplication logique** (décodage du WAL, module 08).

> 🔐 **Angle sécurité**
> Le WAL contient les **nouvelles valeurs** de chaque ligne modifiée, en clair. Un attaquant qui obtient une copie de `pg_wal/` ou de l'archive WAL peut reconstituer les données sensibles, sans jamais interroger la base. Les archives WAL et les sauvegardes doivent donc être protégées **au même niveau que la base elle-même** (droits d'accès, chiffrement). Symétriquement, le WAL est précieux en investigation (*forensics*) : il permet de retrouver ce qui a été modifié et quand.

> ⚠️ **Ne jamais désactiver `fsync`**. Avec `fsync = off`, PostgreSQL ne force plus l'écriture sur disque : un crash peut corrompre définitivement le cluster. Ce paramètre n'est acceptable que pour un chargement jetable qu'on peut refaire intégralement.

---

## 8. Le parcours d'une requête

Suivons `SELECT * FROM bank.clients WHERE cin = 'CIN00000042';` :

```
Client ──► 1. Connexion ──► 2. Authentification ──► 3. Backend dédié
                                                          │
       ┌──────────────────────────────────────────────────┘
       ▼
  4. Parser       : analyse syntaxique → arbre de requête
  5. Analyzer     : résout les noms (table, colonnes, droits) via le catalogue
  6. Rewriter     : applique les règles (vues, politiques RLS)
  7. Planner      : estime le coût des stratégies possibles, choisit le plan
                    (ex. : utiliser l'index unique sur cin plutôt que tout lire)
  8. Executor     : exécute le plan, lit les pages via shared_buffers
  9. Résultat renvoyé au client
```

1. **Connexion** : le client contacte le postmaster (socket Unix local ou TCP).
2. **Authentification** : le postmaster crée un backend, qui consulte `pg_hba.conf` pour savoir si et comment ce client doit s'authentifier.
3. **Backend** : le processus dédié prend en charge toute la session.
4. **Parser** : vérifie la syntaxe SQL.
5. **Analyzer** : vérifie que la table existe et que l'utilisateur a le droit de la lire.
6. **Rewriter** : remplace les vues par leur définition, ajoute les filtres des politiques de sécurité au niveau des lignes (RLS).
7. **Planner / Optimizer** : génère les plans possibles, estime leur coût à l'aide des **statistiques** et retient le moins coûteux (module 07).
8. **Executor** : parcourt le plan ; chaque page lue est cherchée dans `shared_buffers`, puis sur disque si absente.

Les étapes 4 à 7 expliquent pourquoi les **requêtes préparées** sont à la fois plus rapides (la planification peut être réutilisée) et plus sûres (les paramètres ne sont jamais interprétés comme du SQL, module 09).

---

## 9. Le catalogue système

PostgreSQL décrit tous ses objets dans des tables système, dans le schéma `pg_catalog` : c'est le **catalogue**. Tout ce que tu vois avec `\dt` ou `\du` dans psql provient de requêtes sur ces tables.

| Table / vue | Contenu |
|-------------|---------|
| `pg_database` | Bases du cluster |
| `pg_class` | Tables, index, séquences, vues (toutes les « relations ») |
| `pg_attribute` | Colonnes |
| `pg_namespace` | Schémas |
| `pg_roles` / `pg_authid` | Rôles (`pg_authid` contient les hachages de mots de passe, lisible seulement par les superutilisateurs) |
| `pg_settings` | Paramètres de configuration et leur valeur courante |
| `pg_stat_activity` | Sessions en cours |
| `pg_locks` | Verrous posés |

Chaque objet est identifié par un **OID** (*Object Identifier*), un entier interne.

```sql
SELECT oid, datname FROM pg_database;
SELECT oid, relname, relkind FROM pg_class WHERE relnamespace = 'bank'::regnamespace;
```

Astuce : `\set ECHO_HIDDEN on` dans psql affiche les requêtes sur le catalogue exécutées par les méta-commandes comme `\dt`. C'est la meilleure façon d'apprendre le catalogue.

---

## 10. Première cartographie de la surface d'attaque

Chaque composant vu dans ce module est un point d'entrée potentiel. Cette carte sera complétée au module 09.

| Composant | Menace | Protection (module) |
|-----------|--------|---------------------|
| Port TCP 5432 | Scan, force brute, exploitation de vulnérabilités | Pare-feu, `listen_addresses`, mises à jour (02, 09) |
| Authentification (`pg_hba.conf`) | Méthode `trust`, mots de passe faibles | scram-sha-256, certificats (02, 09) |
| Rôles et privilèges | Excès de droits, superutilisateur applicatif | Moindre privilège (04) |
| Requêtes SQL | Injection SQL | Requêtes paramétrées (09) |
| Fichiers de données | Vol de disque, accès système | Droits 0700, chiffrement disque (03, 09) |
| WAL et archives | Lecture des données en clair | Protection et chiffrement des archives (06, 09) |
| Sauvegardes | Exfiltration, rançongiciel | Chiffrement, copies hors ligne (06) |
| Journaux (logs) | Fuite de mots de passe ou de données | Paramétrage de la journalisation (02, 09) |
| Réplication | Interception du flux | TLS, rôle dédié (08) |

---

## TP 1 — Observer l'architecture

### Étape 1 : les processus

```bash
$ ps -ef --forest | grep -v grep | grep postgres
```

Identifie le postmaster (le parent), puis chacun des processus d'arrière-plan décrits en section 4.

### Étape 2 : un backend par connexion

Dans tmux, ouvre deux panneaux.

**Panneau 1 :**
```bash
$ sudo -u postgres psql -d banque
```
```sql
banque=# SELECT pg_backend_pid();
```

**Panneau 2 :**
```bash
$ ps -ef --forest | grep -v grep | grep postgres
```

Un nouveau processus fils du postmaster est apparu ; son PID correspond à `pg_backend_pid()`. Son titre ressemble à `postgres: 16/main: postgres banque [local] idle`.

### Étape 3 : vue interne des processus

```sql
banque=# SELECT pid, backend_type, usename, datname, state
         FROM pg_stat_activity
         ORDER BY backend_type;
```

Compare avec la sortie de `ps`.

### Étape 4 : paramètres mémoire

```sql
banque=# SELECT name, setting, unit, context
         FROM pg_settings
         WHERE name IN ('shared_buffers', 'work_mem', 'maintenance_work_mem',
                        'wal_buffers', 'effective_cache_size', 'max_connections');
```

Note l'unité : `shared_buffers` est exprimé en **pages de 8 Ko** (16384 × 8 Ko = 128 Mo). Utilise `SHOW shared_buffers;` pour une valeur lisible.

### Étape 5 : le répertoire de données

```sql
banque=# SHOW data_directory;
banque=# SELECT oid, datname FROM pg_database;
banque=# SELECT pg_relation_filepath('bank.clients');
```

```bash
$ sudo ls -l /var/lib/postgresql/16/main/
$ sudo ls -l /var/lib/postgresql/16/main/pg_wal/
$ sudo cat /var/lib/postgresql/16/main/PG_VERSION
$ sudo ls -l /var/lib/postgresql/16/main/base/<oid_de_banque>/ | head
```

Vérifie que le fichier renvoyé par `pg_relation_filepath` existe bien et note sa taille.

### Étape 6 : observer le WAL progresser

```sql
banque=# SELECT pg_current_wal_lsn(), pg_walfile_name(pg_current_wal_lsn());
banque=# UPDATE bank.comptes SET solde = solde + 1;   -- ~150 000 lignes modifiées
banque=# SELECT pg_current_wal_lsn(), pg_walfile_name(pg_current_wal_lsn());
banque=# SELECT pg_size_pretty(pg_wal_lsn_diff('<LSN_après>', '<LSN_avant>'));
```

Le **LSN** (*Log Sequence Number*) est la position dans le flux WAL. La différence entre deux LSN donne le volume de WAL généré : tu mesures ainsi le coût en journal d'une opération.

### Étape 7 : provoquer et observer une reprise après crash

> Fais un snapshot de ta VM avant cette étape.

```sql
banque=# CREATE TABLE bank.test_crash (id int, t text);
banque=# INSERT INTO bank.test_crash SELECT g, 'ligne ' || g FROM generate_series(1, 100000) g;
banque=# SELECT count(*) FROM bank.test_crash;
```

Simule un crash brutal en tuant le postmaster avec le signal KILL (aucune chance de s'arrêter proprement) :

```bash
$ sudo head -1 /var/lib/postgresql/16/main/postmaster.pid     # PID du postmaster
$ sudo kill -9 <PID>
$ sudo systemctl restart postgresql@16-main
$ sudo tail -20 /var/log/postgresql/postgresql-16-main.log
```

Dans le journal, repère les messages indiquant que le système n'a pas été arrêté proprement, le début de la phase **redo** et sa fin. Vérifie ensuite que les 100 000 lignes sont bien là :

```sql
banque=# SELECT count(*) FROM bank.test_crash;
banque=# DROP TABLE bank.test_crash;
```

Les données validées ont survécu, bien que leurs pages n'aient peut-être jamais été écrites dans les fichiers de données : elles ont été reconstruites à partir du WAL.

---

## Exercices

1. Un collègue affirme : « Pour accélérer la base, il suffit de mettre `shared_buffers` à 90 % de la RAM. » Explique pourquoi c'est une mauvaise idée.
2. Calcule la consommation mémoire maximale théorique d'un serveur avec `max_connections = 300`, `work_mem = 64MB` et des requêtes faisant jusqu'à 4 opérations de tri/hachage. Qu'en conclus-tu ?
3. Explique pourquoi un `COMMIT` peut être plus rapide que l'écriture de toutes les pages modifiées par la transaction.
4. Un administrateur système a supprimé des fichiers dans `pg_wal/` pour libérer de l'espace. Quelles sont les conséquences possibles ?
5. Un serveur héberge deux clusters : PostgreSQL 15 sur le port 5432 et PostgreSQL 16 sur le port 5433. Combien d'instances tournent ? Un rôle créé sur le premier existe-t-il sur le second ?

---

## Quiz

1. Quelle est la différence entre une instance et une base de données ?
2. Quel processus crée un backend pour chaque nouvelle connexion ?
3. Quelle est la taille par défaut d'une page PostgreSQL ?
4. Dans quel répertoire se trouve le journal de transactions ?
5. Que se passe-t-il, dans l'ordre, lors d'un `COMMIT` ?
6. Quel est le rôle d'un checkpoint ?
7. Pourquoi le WAL doit-il être protégé comme les données elles-mêmes ?
8. Les rôles sont-ils propres à une base ou globaux au cluster ?
9. Pourquoi utilise-t-on un pooler de connexions comme PgBouncer ?
10. Que contient la table `pg_authid`, et qui peut la lire ?

*Corrigés : [annexe D](annexes/D-corriges.md#module-01).*

---

## À retenir

- Un **cluster** = une instance + un répertoire de données + un port, contenant plusieurs bases.
- L'**instance** (processus + mémoire) est volatile ; les **fichiers** sont persistants.
- Un **backend** par connexion : attention au nombre de connexions.
- **WAL** : on écrit le journal avant de valider ; c'est la base de la durabilité, de la sauvegarde continue et de la réplication.
- Le WAL, les sauvegardes et les journaux contiennent des données sensibles : ils font partie de la surface d'attaque.
