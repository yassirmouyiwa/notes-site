# Module 02 — Installation et configuration

## Objectifs

- Créer un cluster à la main avec `initdb` et en comprendre les options.
- Gérer plusieurs clusters avec les outils Debian (`pg_createcluster`, `pg_ctlcluster`).
- Maîtriser les fichiers `postgresql.conf`, `postgresql.auto.conf`, `pg_hba.conf` et `pg_ident.conf`.
- Savoir quand un paramètre nécessite un rechargement ou un redémarrage.
- Configurer une journalisation exploitable.
- Réaliser un premier dimensionnement mémoire cohérent.

---

## 1. Les modes d'installation

| Mode | Avantages | Inconvénients |
|------|-----------|---------------|
| Paquets de la distribution | Simple, mises à jour de sécurité intégrées | Version parfois ancienne |
| Dépôt officiel PGDG (apt.postgresql.org, yum.postgresql.org) | Toutes les versions supportées, correctifs rapides | Dépôt tiers à gérer |
| Compilation depuis les sources | Options de compilation sur mesure (taille de bloc…) | Maintenance manuelle, mises à jour à la main |
| Conteneurs (Docker, Kubernetes avec un opérateur comme CloudNativePG) | Déploiement reproductible | Stockage persistant et HA plus complexes |
| Services managés (RDS, Cloud SQL, Azure) | Pas d'administration système | Pas d'accès superutilisateur ni aux fichiers, coût |

En production sur serveur, la recommandation habituelle est le **dépôt PGDG**, pour choisir sa version et recevoir les versions mineures correctives rapidement.

### Versions majeures et mineures

Depuis PostgreSQL 10, le numéro de version s'écrit `MAJEURE.MINEURE` (exemple : `16.4`).

- **Version mineure** (16.3 → 16.4) : uniquement des corrections de bugs et de **failles de sécurité**. Même format de fichiers : il suffit de mettre à jour les binaires et de redémarrer. **À appliquer systématiquement.**
- **Version majeure** (16 → 17) : nouvelles fonctionnalités, format interne potentiellement différent. Nécessite une migration (`pg_upgrade`, dump/restore ou réplication logique, module 10).

---

## 2. Créer un cluster avec `initdb`

`initdb` crée un nouveau répertoire de données : catalogue système, bases `template0`, `template1` et `postgres`, fichiers de configuration par défaut.

### 2.1 Options importantes

| Option | Rôle |
|--------|------|
| `-D <répertoire>` | Emplacement du répertoire de données |
| `--auth-local=<méthode>` / `--auth-host=<méthode>` | Méthodes d'authentification initiales dans `pg_hba.conf` (défaut : `trust`, **à ne jamais garder**) |
| `-U <nom>` | Nom du superutilisateur initial (défaut : utilisateur système courant) |
| `--pwprompt` / `--pwfile` | Définir le mot de passe du superutilisateur |
| `-E UTF8` | Encodage par défaut des bases |
| `--locale=fr_FR.UTF-8` | Paramètres régionaux (tri, format) |
| `-k` / `--data-checksums` | Active les **sommes de contrôle** des pages, qui détectent la corruption silencieuse (activé par défaut à partir de PostgreSQL 18) |
| `--wal-segsize=<Mo>` | Taille des segments WAL (défaut 16 Mo), fixée à la création |

> 🔐 **Angle sécurité**
> Par défaut, `initdb` sans option génère un `pg_hba.conf` en méthode **`trust`** : n'importe quel utilisateur local peut se connecter en superutilisateur sans mot de passe. Un message d'avertissement s'affiche, mais il est souvent ignoré. Précise toujours `--auth-local=peer --auth-host=scram-sha-256`.

> Les **checksums** détectent une page corrompue (disque défaillant, bug de contrôleur, modification malveillante des fichiers) au moment de sa lecture. Le surcoût CPU est faible. Active-les toujours sur un nouveau cluster. Sur un cluster existant arrêté, l'outil `pg_checksums --enable` permet de les activer.

### 2.2 TP : créer un cluster « à la main »

On crée un cluster de test indépendant sur le port 5440, sans les outils Debian, pour comprendre ce qu'ils automatisent.

```bash
$ sudo -i -u postgres
postgres$ export PATH=/usr/lib/postgresql/16/bin:$PATH
postgres$ initdb -D /var/lib/postgresql/test_manuel \
            --auth-local=peer --auth-host=scram-sha-256 \
            -E UTF8 --data-checksums --pwprompt
```

Observe la sortie : création des répertoires, choix automatique de `max_connections` et `shared_buffers` selon la machine, création des bases modèles.

```bash
postgres$ ls -l /var/lib/postgresql/test_manuel
postgres$ grep -v '^#' /var/lib/postgresql/test_manuel/pg_hba.conf | grep -v '^$'
postgres$ pg_ctl -D /var/lib/postgresql/test_manuel -o "-p 5440" -l /tmp/test_manuel.log start
postgres$ psql -p 5440 -c "SHOW data_checksums;"
postgres$ psql -p 5440 -c "SHOW port;"
postgres$ pg_ctl -D /var/lib/postgresql/test_manuel stop -m fast
postgres$ exit
```

### 2.3 Les modes d'arrêt

| Mode | Commande | Comportement |
|------|----------|--------------|
| **smart** | `pg_ctl stop -m smart` | Attend que tous les clients se déconnectent. Peut ne jamais se terminer. |
| **fast** (défaut) | `pg_ctl stop -m fast` | Annule les transactions en cours, déconnecte les clients, fait un checkpoint, s'arrête proprement. |
| **immediate** | `pg_ctl stop -m immediate` | Arrêt brutal sans checkpoint. Le prochain démarrage fera une **reprise après crash**. À réserver aux urgences. |

---

## 3. Les outils Debian / Ubuntu

Debian ajoute une couche de gestion multi-versions et multi-clusters autour des outils standards.

| Commande | Rôle |
|----------|------|
| `pg_lsclusters` | Liste les clusters, leur version, port, statut et chemins |
| `pg_createcluster 16 nom --port 5433` | Crée un cluster (appelle `initdb`, place la config dans `/etc/postgresql/16/nom/`) |
| `pg_ctlcluster 16 nom start\|stop\|restart\|reload\|status` | Pilote un cluster (appelle `pg_ctl`) |
| `pg_dropcluster 16 nom --stop` | Supprime un cluster **et ses données** |
| `pg_upgradecluster 16 main` | Migre un cluster vers une version majeure plus récente |
| `systemctl start postgresql@16-nom` | Pilotage par systemd (équivalent recommandé) |

Organisation des fichiers sur Debian/Ubuntu :

| Élément | Chemin |
|---------|--------|
| Binaires | `/usr/lib/postgresql/16/bin/` |
| Données | `/var/lib/postgresql/16/main/` |
| Configuration | `/etc/postgresql/16/main/` |
| Journaux | `/var/log/postgresql/postgresql-16-main.log` |
| Socket Unix | `/var/run/postgresql/.s.PGSQL.5432` |

```bash
$ sudo pg_createcluster 16 essai --port 5433 -- --data-checksums
$ sudo pg_ctlcluster 16 essai start
$ pg_lsclusters
$ sudo -u postgres psql -p 5433 -c "SELECT current_setting('port'), current_setting('data_directory');"
$ sudo pg_dropcluster 16 essai --stop
```

Les options après `--` sont transmises à `initdb`.

---

## 4. `postgresql.conf` : la configuration générale

### 4.1 Syntaxe

```ini
# commentaire
shared_buffers = 1GB            # unités acceptées : kB, MB, GB, TB / us, ms, s, min, h, d
listen_addresses = 'localhost'  # chaînes entre apostrophes
log_connections = on            # booléens : on/off, true/false, yes/no, 1/0
include_dir = 'conf.d'          # inclut tous les fichiers .conf d'un répertoire
```

Si un paramètre apparaît plusieurs fois, **la dernière occurrence l'emporte**. La bonne pratique consiste à laisser `postgresql.conf` d'origine intact et à placer ses réglages dans des fichiers dédiés sous `conf.d/` (Debian l'inclut déjà) : c'est plus lisible et plus facile à versionner.

### 4.2 Ordre de priorité des sources

Du plus faible au plus fort :

1. Valeur compilée par défaut
2. `postgresql.conf` (et fichiers inclus)
3. `postgresql.auto.conf` (écrit par `ALTER SYSTEM`)
4. Options de ligne de commande du serveur (`-c param=valeur`)
5. `ALTER DATABASE … SET` (pour une base)
6. `ALTER ROLE … SET` (pour un rôle)
7. `ALTER ROLE … IN DATABASE … SET` (rôle dans une base)
8. `SET` dans la session (ou `SET LOCAL` dans une transaction)

```sql
ALTER SYSTEM SET work_mem = '16MB';                    -- écrit dans postgresql.auto.conf
ALTER DATABASE banque SET work_mem = '32MB';           -- pour toutes les sessions sur banque
ALTER ROLE analyste SET statement_timeout = '5min';    -- pour ce rôle
SET work_mem = '256MB';                                -- pour la session courante
ALTER SYSTEM RESET work_mem;                           -- retire la ligne de postgresql.auto.conf
```

> 🔐 **Angle sécurité**
> `ALTER SYSTEM` permet à un superutilisateur de modifier la configuration **sans accès au système de fichiers**. Une application compromise connectée en superutilisateur peut ainsi changer `shared_preload_libraries` ou d'autres paramètres sensibles. Depuis PostgreSQL 17, le paramètre `allow_alter_system = off` désactive cette commande (utile quand la configuration est gérée par Ansible ou Patroni ; ce n'est pas une barrière de sécurité absolue contre un superutilisateur).

### 4.3 Contexte des paramètres : recharger ou redémarrer ?

La colonne `context` de `pg_settings` indique quand un changement prend effet.

| Contexte | Prise en compte | Exemples |
|----------|-----------------|----------|
| `postmaster` | **Redémarrage** obligatoire | `shared_buffers`, `max_connections`, `listen_addresses`, `port`, `shared_preload_libraries`, `wal_level`, `archive_mode` |
| `sighup` | **Rechargement** (`reload`) | `pg_hba.conf`, `log_*`, `archive_command`, `autovacuum_*`, `checkpoint_timeout` |
| `superuser` / `superuser-backend` | Modifiable en session par un superutilisateur | `log_statement`, `session_preload_libraries` |
| `user` | Modifiable par tout utilisateur dans sa session | `work_mem`, `statement_timeout`, `search_path` |
| `backend` | Fixé à l'ouverture de la connexion | `log_connections` (pour la session) |
| `internal` | Non modifiable (fixé à la compilation ou à `initdb`) | `block_size`, `data_checksums`, `wal_segment_size` |

Recharger la configuration :

```bash
$ sudo systemctl reload postgresql@16-main
```
ou depuis SQL :
```sql
SELECT pg_reload_conf();
```

Vérifier ce qui est en attente de redémarrage et détecter les erreurs de syntaxe :

```sql
SELECT name, setting, pending_restart FROM pg_settings WHERE pending_restart;
SELECT sourcefile, sourceline, name, setting, applied, error FROM pg_file_settings WHERE error IS NOT NULL OR NOT applied;
```

`pg_file_settings` lit les fichiers **tels qu'ils sont sur disque** : consulte-la **avant** de recharger pour repérer une faute de frappe.

### 4.4 Paramètres essentiels par catégorie

**Connexions**

| Paramètre | Défaut | Recommandation |
|-----------|--------|----------------|
| `listen_addresses` | `localhost` | Uniquement les interfaces nécessaires, jamais `*` sans pare-feu |
| `port` | 5432 | Changer de port n'est **pas** une mesure de sécurité (simple réduction du bruit des scans) |
| `max_connections` | 100 | Rester modéré (100 à 300), utiliser un pooler au-delà |
| `superuser_reserved_connections` | 3 | Garde des connexions pour l'administrateur quand l'instance est saturée |

**Mémoire** : voir section 7.

**WAL et checkpoints**

| Paramètre | Défaut | Rôle |
|-----------|--------|------|
| `wal_level` | `replica` | `minimal`, `replica` (sauvegarde physique et réplication), `logical` (réplication logique) |
| `fsync` | `on` | **Ne jamais désactiver** |
| `synchronous_commit` | `on` | Attendre l'écriture du WAL avant de confirmer le `COMMIT` |
| `full_page_writes` | `on` | Protège contre les pages partiellement écrites, **ne pas désactiver** |
| `max_wal_size` | 1GB | À augmenter sur une base active (4 à 16 Go) pour espacer les checkpoints |
| `checkpoint_timeout` | 5min | Souvent porté à 15 min |

**Délais (protection contre les sessions bloquantes)**

| Paramètre | Rôle |
|-----------|------|
| `statement_timeout` | Annule une requête trop longue |
| `lock_timeout` | Annule une requête qui attend un verrou trop longtemps |
| `idle_in_transaction_session_timeout` | Ferme une session restée dans une transaction ouverte sans activité |
| `transaction_timeout` (PG 17+) | Durée maximale d'une transaction complète |

Ces délais sont en général fixés **par rôle** plutôt que globalement.

---

## 5. `pg_hba.conf` : le contrôle d'accès réseau

`pg_hba.conf` (*host-based authentication*) décide **qui peut se connecter, à quelle base, depuis où, et avec quelle méthode d'authentification**. C'est le premier pare-feu de PostgreSQL.

### 5.1 Format d'une ligne

```
TYPE        BASE        UTILISATEUR     ADRESSE             MÉTHODE        [OPTIONS]
local       all         postgres                            peer
hostssl     banque      app_banque      10.0.1.0/24         scram-sha-256
hostssl     all         all             0.0.0.0/0           reject
```

| Champ | Valeurs possibles |
|-------|-------------------|
| **TYPE** | `local` (socket Unix), `host` (TCP, avec ou sans TLS), `hostssl` (TCP **avec** TLS uniquement), `hostnossl` (TCP **sans** TLS), `hostgssenc` / `hostnogssenc` (chiffrement GSSAPI) |
| **BASE** | `all`, un nom, une liste séparée par des virgules, `sameuser`, `samerole`, `replication` (connexions de réplication physique), `@fichier` |
| **UTILISATEUR** | `all`, un nom, `+groupe` (membres d'un rôle), liste, `@fichier` |
| **ADRESSE** | CIDR (`192.168.1.0/24`, `::1/128`), `samehost`, `samenet`, nom d'hôte. Absent pour `local`. |
| **MÉTHODE** | voir tableau suivant |

### 5.2 Méthodes d'authentification

| Méthode | Principe | Usage |
|---------|----------|-------|
| `trust` | Aucune vérification | **Jamais**, sauf lab jetable |
| `reject` | Refus systématique | Bloquer explicitement une combinaison |
| `scram-sha-256` | Défi-réponse, le mot de passe ne circule pas et le hachage stocké est salé et itéré | **Méthode par mot de passe recommandée** |
| `md5` | Ancien défi-réponse basé sur MD5 | Obsolète, **déprécié à partir de PostgreSQL 18**, à migrer |
| `password` | Mot de passe envoyé **en clair** | À éviter (acceptable seulement sous TLS, et encore) |
| `peer` | Le noyau fournit l'identité de l'utilisateur système (socket Unix local uniquement) | Administration locale |
| `ident` | Interroge un serveur ident sur le client (TCP) | Obsolète, facilement usurpable |
| `cert` | Certificat client TLS, le CN doit correspondre au rôle | Authentification forte (module 09) |
| `gss` / `sspi` | Kerberos / Active Directory | Entreprise, authentification unique |
| `ldap` / `radius` / `pam` | Délégation à un annuaire ou à PAM | Entreprise |
| `oauth` (PG 18+) | Jeton OAuth 2.0 | Intégration avec un fournisseur d'identité |

### 5.3 Règles d'évaluation

1. Les lignes sont lues **de haut en bas**.
2. La **première ligne qui correspond** (type, base, utilisateur, adresse) est appliquée.
3. Si l'authentification échoue avec cette ligne, **les lignes suivantes ne sont pas essayées** : la connexion est refusée.
4. Si aucune ligne ne correspond, la connexion est refusée.

Conséquence : on place les règles **les plus spécifiques en haut** et un `reject` générique en bas.

### 5.4 `pg_ident.conf` : correspondance d'identités

Avec `peer`, `ident`, `cert` ou `gss`, on peut faire correspondre une identité externe à un rôle PostgreSQL différent :

```
# pg_ident.conf
# MAP        IDENTITÉ-SYSTÈME     RÔLE-POSTGRESQL
admins       yassine              postgres
admins       salma                postgres
```

```
# pg_hba.conf
local   all   postgres   peer   map=admins
```

Les utilisateurs Linux `yassine` et `salma` peuvent alors se connecter au rôle `postgres` sans mot de passe, via le socket local.

### 5.5 Vérifier sa configuration

```sql
SELECT line_number, type, database, user_name, address, netmask, auth_method, error
FROM pg_hba_file_rules;
```

Comme `pg_file_settings`, cette vue lit le fichier sur disque : les erreurs apparaissent **avant** le rechargement. Un `pg_hba.conf` invalide est ignoré au rechargement (l'ancien reste actif) mais **empêche le démarrage** de l'instance.

> 🔐 **Angle sécurité**
> Des milliers d'instances PostgreSQL sont exposées sur Internet avec `listen_addresses = '*'` et une règle `host all all 0.0.0.0/0 md5`, voire `trust`. Des campagnes automatisées les attaquent par force brute pour y installer des mineurs de cryptomonnaie via les fonctionnalités d'exécution de programmes réservées aux superutilisateurs. Les trois lignes de défense : ne pas exposer le port (pare-feu, VPN), restreindre `pg_hba.conf` aux réseaux et rôles nécessaires, ne jamais autoriser le superutilisateur à distance.

---

## 6. Journalisation

Un DBA passe beaucoup de temps dans les journaux. Une journalisation mal configurée rend le diagnostic et l'investigation impossibles.

### 6.1 Où vont les journaux

| Paramètre | Rôle |
|-----------|------|
| `logging_collector` | `on` : un processus dédié écrit les journaux dans des fichiers et gère la rotation |
| `log_destination` | `stderr`, `csvlog`, `jsonlog` (PG 15+), `syslog` |
| `log_directory`, `log_filename` | Emplacement et nom des fichiers |
| `log_rotation_age`, `log_rotation_size` | Rotation |
| `log_file_mode` | Droits des fichiers (défaut `0600`) |

Sur Debian, `logging_collector` est désactivé : c'est le script de démarrage qui redirige la sortie vers `/var/log/postgresql/`, avec rotation par `logrotate`.

Le format `jsonlog` est pratique pour envoyer les journaux vers un SIEM (Elastic, Wazuh, Splunk).

### 6.2 Quoi journaliser

| Paramètre | Recommandation | Intérêt |
|-----------|----------------|---------|
| `log_line_prefix` | `'%m [%p] %q user=%u db=%d app=%a client=%h '` | Horodatage, PID, utilisateur, base, application, IP : **indispensable** pour l'investigation |
| `log_connections` | `on` | Trace chaque connexion (IP, utilisateur, méthode) |
| `log_disconnections` | `on` | Durée des sessions |
| `log_min_duration_statement` | `1s` (à adapter) | Journalise les requêtes lentes avec leur durée |
| `log_statement` | `ddl` | Trace toutes les modifications de structure (`CREATE`, `ALTER`, `DROP`) |
| `log_lock_waits` | `on` | Signale les attentes de verrou supérieures à `deadlock_timeout` |
| `log_temp_files` | `0` | Signale les fichiers temporaires (manque de `work_mem`) |
| `log_checkpoints` | `on` (défaut depuis PG 15) | Fréquence et durée des checkpoints |
| `log_autovacuum_min_duration` | `10min` (défaut depuis PG 15, abaisser si besoin) | Activité de l'autovacuum |
| `log_min_messages` | `warning` | Niveau minimal des messages serveur |

Codes utiles dans `log_line_prefix` : `%m` horodatage en millisecondes, `%p` PID, `%u` utilisateur, `%d` base, `%a` nom d'application, `%h` hôte client, `%r` hôte et port, `%x` identifiant de transaction, `%q` arrête le préfixe pour les processus hors session.

> 🔐 **Angle sécurité**
> Avec `log_statement = 'all'`, une commande `ALTER ROLE alice PASSWORD 'Secret2026!'` est écrite **en clair** dans les journaux. Il en va de même pour des requêtes contenant des données personnelles ou des clés de chiffrement. Recommandations : `log_statement = 'ddl'` au maximum, changer les mots de passe avec la méta-commande psql `\password` (qui envoie un hachage, jamais le mot de passe en clair), protéger les fichiers de journaux (mode 0600), et utiliser `pgaudit` pour un audit maîtrisé (module 09).

---

## 7. Premier dimensionnement

Il n'existe pas de configuration universelle, mais des valeurs de départ raisonnables pour un serveur dédié. L'exemple ci-dessous suppose 16 Go de RAM, disques SSD et une charge transactionnelle (OLTP).

| Paramètre | Formule de départ | Exemple 16 Go |
|-----------|-------------------|---------------|
| `shared_buffers` | 25 % de la RAM | `4GB` |
| `effective_cache_size` | 50 à 75 % de la RAM | `12GB` |
| `work_mem` | (RAM − shared_buffers) / (max_connections × 3), puis ajuster | `32MB` |
| `maintenance_work_mem` | 5 à 10 % de la RAM, plafonné à 1 à 2 Go | `1GB` |
| `max_connections` | Selon besoin réel, avec pooler | `200` |
| `max_wal_size` | Selon volume d'écriture | `8GB` |
| `checkpoint_timeout` | — | `15min` |
| `random_page_cost` | 1.1 sur SSD (4 sur disque mécanique) | `1.1` |
| `effective_io_concurrency` | 200 sur SSD | `200` |

Ensuite, **on mesure et on ajuste** (module 07). Des outils comme PGTune fournissent des valeurs de départ, mais ne remplacent pas l'observation.

### Paramètres du noyau Linux à connaître

| Réglage | Recommandation |
|---------|----------------|
| `vm.overcommit_memory` | `2` sur serveur dédié, pour éviter que l'OOM killer tue le postmaster |
| `vm.swappiness` | Faible (1 à 10) |
| Transparent Huge Pages | Désactiver (`never`) |
| Huge pages | Configurer `vm.nr_hugepages` et `huge_pages = try` pour de gros `shared_buffers` |
| Système de fichiers | ext4 ou XFS, option `noatime` |

---

## TP 2 — Configurer l'instance du lab

### Étape 1 : explorer la configuration active

```sql
postgres=# SELECT name, setting, unit, context, source, sourcefile
           FROM pg_settings
           WHERE source NOT IN ('default', 'override')
           ORDER BY name;
```

Tu vois tous les paramètres modifiés par rapport aux valeurs par défaut et leur origine.

### Étape 2 : créer un fichier de configuration dédié

```bash
$ sudo tee /etc/postgresql/16/main/conf.d/10-formation.conf > /dev/null <<'EOF'
# --- Formation DBA : journalisation ---
log_line_prefix = '%m [%p] %q user=%u db=%d app=%a client=%h '
log_connections = on
log_disconnections = on
log_min_duration_statement = 500ms
log_statement = 'ddl'
log_lock_waits = on
log_temp_files = 0

# --- Mémoire (VM 4 Go) ---
shared_buffers = 1GB
effective_cache_size = 3GB
work_mem = 16MB
maintenance_work_mem = 256MB

# --- WAL ---
max_wal_size = 2GB
EOF
$ sudo chown postgres:postgres /etc/postgresql/16/main/conf.d/10-formation.conf
```

### Étape 3 : vérifier avant d'appliquer

```sql
postgres=# SELECT name, setting, applied, error
           FROM pg_file_settings
           WHERE sourcefile LIKE '%10-formation%';
```

Introduis volontairement une erreur (par exemple `work_mem = 16MBB`), observe la colonne `error`, puis corrige.

### Étape 4 : recharger, puis redémarrer

```sql
postgres=# SELECT pg_reload_conf();
postgres=# SELECT name, setting, pending_restart FROM pg_settings WHERE pending_restart;
```

`shared_buffers` apparaît en attente de redémarrage, contrairement aux paramètres de journalisation, déjà actifs.

```bash
$ sudo systemctl restart postgresql@16-main
$ sudo -u postgres psql -c "SHOW shared_buffers;"
```

### Étape 5 : observer la journalisation

```bash
$ sudo tail -f /var/log/postgresql/postgresql-16-main.log
```

Dans un autre panneau, connecte-toi, exécute une requête lente et un DDL :

```sql
banque=# SELECT pg_sleep(1);
banque=# CREATE TABLE bank.essai_log (id int);
banque=# DROP TABLE bank.essai_log;
```

Repère dans le journal : la connexion, la requête lente avec sa durée, les deux DDL, la déconnexion.

### Étape 6 : `pg_hba.conf` durci pour le lab

Consulte le fichier actuel :

```sql
postgres=# SELECT line_number, type, database, user_name, address, auth_method FROM pg_hba_file_rules;
```

Remplace son contenu par une version commentée (garde une copie de l'original) :

```bash
$ sudo cp /etc/postgresql/16/main/pg_hba.conf /etc/postgresql/16/main/pg_hba.conf.orig
$ sudo tee /etc/postgresql/16/main/pg_hba.conf > /dev/null <<'EOF'
# TYPE   BASE          UTILISATEUR   ADRESSE          MÉTHODE
# Administration locale par le compte système postgres uniquement
local    all           postgres                       peer
# Autres connexions locales par socket : mot de passe
local    all           all                            scram-sha-256
# Boucle locale TCP : mot de passe
host     all           all           127.0.0.1/32     scram-sha-256
host     all           all           ::1/128          scram-sha-256
# Réplication locale (utilisée au module 08)
host     replication   replicator    127.0.0.1/32     scram-sha-256
# Tout le reste est refusé explicitement
host     all           all           0.0.0.0/0        reject
host     all           all           ::/0             reject
EOF
$ sudo -u postgres psql -c "SELECT line_number, auth_method, error FROM pg_hba_file_rules;"
$ sudo -u postgres psql -c "SELECT pg_reload_conf();"
```

### Étape 7 : tester les règles

```sql
postgres=# CREATE ROLE etudiant LOGIN;
postgres=# \password etudiant
```

```bash
$ psql -h 127.0.0.1 -U etudiant -d postgres     # mot de passe demandé : OK
$ psql -U etudiant -d postgres                   # socket local : mot de passe demandé
```

Consulte le journal : chaque connexion est tracée avec l'IP et la méthode d'authentification.

---

## Exercices

1. Écris les lignes `pg_hba.conf` pour : (a) l'application `app_web` depuis les serveurs 10.10.0.0/24 vers la base `boutique`, TLS obligatoire ; (b) les analystes (membres du rôle `analystes`) depuis le VPN 172.16.0.0/16 vers `entrepot`, TLS obligatoire ; (c) refus de tout le reste.
2. Un étudiant a placé `host all all 0.0.0.0/0 scram-sha-256` en **première** ligne, puis `host banque app 10.0.0.5/32 cert` en dessous. Que se passe-t-il pour l'application connectée depuis 10.0.0.5 ?
3. Parmi ces paramètres, lesquels nécessitent un redémarrage : `work_mem`, `max_connections`, `log_min_duration_statement`, `shared_preload_libraries`, `archive_command`, `wal_level` ? Vérifie avec `pg_settings`.
4. Propose une configuration mémoire de départ pour un serveur dédié de 64 Go de RAM, SSD, 300 connexions via PgBouncer.
5. Pourquoi faut-il éviter `log_statement = 'all'` en production ? Cite deux raisons.

---

## Quiz

1. Quelle option d'`initdb` active les sommes de contrôle des pages ?
2. Quel est le danger de lancer `initdb` sans options d'authentification ?
3. Quelle est la différence entre `host` et `hostssl` ?
4. Dans `pg_hba.conf`, que se passe-t-il si la première ligne correspondante échoue à authentifier l'utilisateur ?
5. Quelle méthode d'authentification par mot de passe faut-il utiliser ?
6. Comment savoir si un paramètre nécessite un redémarrage ?
7. Quelle vue permet de détecter une erreur de syntaxe dans `pg_hba.conf` avant rechargement ?
8. Quelle est la différence entre les modes d'arrêt `fast` et `immediate` ?
9. Où `ALTER SYSTEM` écrit-il ses modifications ?
10. Pourquoi changer le port 5432 n'est-il pas une vraie mesure de sécurité ?

*Corrigés : [annexe D](annexes/D-corriges.md#module-02).*

---

## À retenir

- `initdb` : toujours avec checksums et sans `trust`.
- Configuration : `postgresql.conf` + fichiers dans `conf.d/` + `postgresql.auto.conf` ; vérifier avec `pg_file_settings` et `pg_hba_file_rules` avant de recharger.
- `pg_hba.conf` : première ligne correspondante, règles spécifiques en haut, `reject` en bas, `scram-sha-256` minimum, `hostssl` pour le réseau.
- Journalisation : un bon `log_line_prefix`, les connexions, les DDL et les requêtes lentes ; jamais de secrets dans les journaux.
- Dimensionnement : 25 % de RAM en `shared_buffers`, `work_mem` raisonné en pire cas, puis mesure.
