# Module 06 — Sauvegarde et restauration

## Objectifs

- Définir une stratégie de sauvegarde à partir des objectifs RPO et RTO.
- Réaliser des sauvegardes logiques (`pg_dump`, `pg_dumpall`) et les restaurer finement.
- Réaliser des sauvegardes physiques (`pg_basebackup`) et les vérifier.
- Mettre en place l'archivage continu des WAL.
- Restaurer une base à un instant précis (PITR).
- Connaître les sauvegardes incrémentales et les outils professionnels (pgBackRest, Barman).
- Protéger les sauvegardes elles-mêmes (chiffrement, isolement, rançongiciels).

---

## 1. Stratégie avant technique

### 1.1 RPO et RTO

| Indicateur | Question | Exemple |
|------------|----------|---------|
| **RPO** (*Recovery Point Objective*) | Quelle quantité de données peut-on perdre au maximum ? | 5 minutes de transactions |
| **RTO** (*Recovery Time Objective*) | En combien de temps le service doit-il être rétabli ? | 1 heure |

Ces objectifs sont fixés **par le métier**, pas par le DBA. Ils déterminent la technique :

| Besoin | Technique minimale |
|--------|--------------------|
| RPO 24 h, RTO de quelques heures | `pg_dump` quotidien |
| RPO de quelques minutes | Sauvegarde physique + **archivage WAL** (PITR) |
| RPO ≈ 0, RTO de quelques minutes | Réplication (synchrone pour RPO nul) + PITR (module 08) |

> ⚠️ **La réplication n'est pas une sauvegarde.** Un `DROP TABLE` ou un `DELETE` sans `WHERE` est répliqué instantanément sur toutes les répliques. Seule une sauvegarde avec historique (PITR) permet de revenir **avant** l'erreur.

### 1.2 La règle 3-2-1 (et ses extensions)

- **3** copies des données (la production + 2 sauvegardes) ;
- sur **2** supports différents ;
- dont **1** hors site.

Version moderne face aux rançongiciels : **3-2-1-1-0**, avec **1** copie hors ligne ou immuable, et **0** erreur lors des tests de restauration.

### 1.3 Une sauvegarde non testée n'existe pas

La seule preuve qu'une sauvegarde fonctionne est une **restauration réussie**, mesurée en temps. Une stratégie sérieuse prévoit des restaurations de test **automatisées et régulières** (au minimum mensuelles), avec vérification du contenu.

---

## 2. Vue d'ensemble des méthodes

| Méthode | Outil | Contenu | Granularité de restauration | Cohérence | Avantages | Limites |
|---------|-------|---------|------------------------------|-----------|-----------|---------|
| **Logique** | `pg_dump`, `pg_dumpall` | Commandes SQL ou archive d'objets | Base, schéma, table | Instantané transactionnel | Portable entre versions et architectures, restauration sélective | Lent sur grosses bases, pas de PITR, index reconstruits à la restauration |
| **Physique à froid** | `cp`, `rsync`, snapshot | Fichiers du cluster, instance **arrêtée** | Cluster entier | Parfaite si arrêt propre | Simple | Interruption de service |
| **Physique à chaud** | `pg_basebackup`, pgBackRest | Fichiers + WAL, instance en marche | Cluster entier | Via le WAL | Rapide, base du PITR et de la réplication | Même version majeure et architecture, tout ou rien |
| **Archivage continu** | `archive_command` / `archive_library` | Flux WAL | Jusqu'à la transaction | — | RPO de quelques secondes à minutes | Nécessite une sauvegarde physique de base |

---

## 3. Sauvegarde logique : `pg_dump`

### 3.1 Principe

`pg_dump` se connecte comme un client, ouvre une transaction en **Repeatable Read** et exporte le contenu d'**une** base. La sauvegarde est cohérente même si la base est modifiée pendant l'export, et elle **ne bloque pas les écritures** (elle pose des verrous `ACCESS SHARE`, qui ne bloquent que les DDL comme `DROP` ou `ALTER TABLE`).

### 3.2 Formats

| Format | Option | Restauration | Parallélisme | Usage |
|--------|--------|--------------|--------------|-------|
| **Plain** (SQL) | `-Fp` (défaut) | `psql -f` | Non | Lisible, modifiable, petites bases |
| **Custom** | `-Fc` | `pg_restore` | À la restauration | **Format recommandé** : compressé, restauration sélective |
| **Directory** | `-Fd` | `pg_restore` | **Sauvegarde et restauration** (`-j`) | Grosses bases |
| **Tar** | `-Ft` | `pg_restore` | Non | Rarement utile |

### 3.3 Commandes courantes

```bash
# Base complète, format custom
pg_dump -Fc -d banque -f banque_$(date +%F).dump

# Grosse base en parallèle (4 processus)
pg_dump -Fd -j 4 -d banque -f banque_$(date +%F).dir

# Un schéma, une table, structure seule, données seules
pg_dump -Fc -d banque -n bank -f bank_schema.dump
pg_dump -Fc -d banque -t bank.clients -f clients.dump
pg_dump -s -d banque -f structure.sql          # --schema-only
pg_dump -a -d banque -t bank.agences           # --data-only

# Exclure une table volumineuse de journaux
pg_dump -Fc -d banque --exclude-table-data='bank.journal_*' -f banque.dump

# Compression (PG 16+ : gzip, lz4, zstd)
pg_dump -Fc -Z zstd:5 -d banque -f banque.dump
```

### 3.4 `pg_dumpall` : les objets globaux

`pg_dump` ne sauvegarde **pas** les rôles ni les tablespaces (objets globaux au cluster). Sans eux, la restauration échoue sur les `GRANT` et `ALTER … OWNER`.

```bash
pg_dumpall --globals-only -f globals_$(date +%F).sql     # rôles + tablespaces
pg_dumpall --roles-only -f roles.sql
```

Stratégie logique complète : `pg_dumpall --globals-only` + un `pg_dump -Fc` par base.

> 🔐 **Angle sécurité**
> Le fichier des globaux contient les **hachages de mots de passe** de tous les rôles (`ALTER ROLE … PASSWORD 'SCRAM-SHA-256$…'`). Un attaquant peut tenter de les casser hors ligne. L'option `--no-role-passwords` les exclut (il faudra alors redéfinir les mots de passe après restauration).

### 3.5 Restauration avec `pg_restore`

```bash
# Créer la base puis restaurer
createdb banque_restauree
pg_restore -d banque_restauree -j 4 banque.dump

# Recréer la base d'origine (option -C : CREATE DATABASE inclus)
pg_restore -C -d postgres banque.dump

# Restaurer dans un environnement sans les mêmes rôles
pg_restore -d banque_test --no-owner --no-privileges banque.dump

# Une seule table (structure + données)
pg_restore -d banque_restauree -t clients -n bank banque.dump
```

### 3.6 Restauration sélective par liste

```bash
pg_restore -l banque.dump > contenu.txt     # table des matières de l'archive
# éditer contenu.txt : commenter (préfixe ;) les éléments à ignorer
pg_restore -L contenu.txt -d banque_restauree banque.dump
```

C'est la technique pour ne restaurer, par exemple, que les données d'une table supprimée par erreur, sans toucher au reste.

### 3.7 Options de fiabilité

| Option | Intérêt |
|--------|---------|
| `pg_restore --exit-on-error` | Arrêter à la première erreur au lieu de continuer silencieusement |
| `pg_restore --single-transaction` | Tout ou rien (incompatible avec `-j`) |
| `pg_dump --serializable-deferrable` | Garantit un instantané sans anomalie de sérialisation |
| `psql -v ON_ERROR_STOP=1` | Pour les restaurations au format SQL |

---

## 4. Sauvegarde physique : `pg_basebackup`

### 4.1 Principe

`pg_basebackup` copie **tous les fichiers du cluster** pendant qu'il fonctionne, via le protocole de réplication. Comme les fichiers changent pendant la copie, la sauvegarde est incohérente en soi : elle est rendue cohérente par le **WAL** généré pendant la copie, que `pg_basebackup` récupère aussi.

Prérequis :

- un rôle avec l'attribut `REPLICATION` ;
- une ligne `replication` dans `pg_hba.conf` ;
- `wal_level = replica` (défaut) et `max_wal_senders` > 0 (défaut 10).

```bash
pg_basebackup -h 127.0.0.1 -U replicator \
    -D /var/lib/postgresql/sauvegardes/base_$(date +%F_%H%M) \
    -Fp -Xs -P -c fast
```

| Option | Rôle |
|--------|------|
| `-D` | Répertoire de destination (doit être vide ou inexistant) |
| `-Fp` / `-Ft` | Format plain (arborescence) ou tar |
| `-Xs` | Récupère le WAL **en flux** pendant la copie (défaut) : la sauvegarde est autonome |
| `-P` | Affiche la progression |
| `-c fast` | Checkpoint immédiat au début (sinon attend le prochain checkpoint) |
| `-z` / `--compress` | Compression (format tar) |
| `-R` | Écrit la configuration de réplique (module 08) |
| `--manifest-checksums=SHA256` | Sommes de contrôle dans le manifeste |

### 4.2 Vérifier une sauvegarde physique

Depuis PG 13, `pg_basebackup` produit un fichier `backup_manifest` listant chaque fichier et sa somme de contrôle.

```bash
pg_verifybackup /var/lib/postgresql/sauvegardes/base_2026-09-23_1030
```

Cela détecte un fichier manquant, modifié ou corrompu **sans restaurer**. Ce n'est pas un test de restauration complet, mais un contrôle rapide à automatiser après chaque sauvegarde.

### 4.3 Sauvegarde de bas niveau

Pour les outils de snapshot de stockage (LVM, SAN, cloud), on encadre la copie par :

```sql
SELECT pg_backup_start('snapshot_nuit', fast => true);   -- PG 15+ (avant : pg_start_backup)
-- snapshot / copie des fichiers ; la session doit rester ouverte
SELECT * FROM pg_backup_stop();                           -- renvoie le label à sauvegarder avec les fichiers
```

À réserver aux cas où l'on sait précisément ce que l'on fait ; `pg_basebackup` ou pgBackRest sont préférables.

---

## 5. Archivage continu des WAL

### 5.1 Principe

Chaque segment WAL de 16 Mo, une fois rempli, est copié vers un stockage d'archive par la commande `archive_command`. Une sauvegarde physique de base + **tous** les WAL archivés depuis permettent de reconstruire le cluster à **n'importe quel instant** postérieur à la sauvegarde de base.

```
Sauvegarde de base (dimanche 02:00)
    │
    ▼
 [WAL 1][WAL 2][WAL 3] … [WAL n]  ← archivés en continu
                               │
         Erreur mardi 14:32 ───┘  → restauration à mardi 14:31:59
```

### 5.2 Configuration

```ini
wal_level = replica
archive_mode = on                     # redémarrage nécessaire
archive_command = 'test ! -f /var/lib/postgresql/archive_wal/%f && cp %p /var/lib/postgresql/archive_wal/%f'
archive_timeout = 60                  # force un changement de segment au moins toutes les 60 s
```

| Motif | Remplacé par |
|-------|--------------|
| `%p` | Chemin du fichier WAL à archiver (relatif à PGDATA) |
| `%f` | Nom du fichier seul |

Règles impératives pour `archive_command` :

1. Renvoyer **0 uniquement si l'archivage a réussi**. Tant que la commande échoue, PostgreSQL conserve le WAL et réessaie.
2. **Ne jamais écraser** un fichier existant (d'où `test ! -f`).
3. Idéalement, s'assurer que la copie est **durable** (synchronisée sur disque) et placée **sur une autre machine**.

`archive_timeout` borne le RPO en période creuse : sans lui, un segment peu rempli peut attendre des heures avant d'être archivé.

> ⚠️ **Danger** : si l'archivage échoue en permanence (disque d'archive plein, montage réseau perdu), les WAL s'accumulent dans `pg_wal/` jusqu'à **remplir le disque et arrêter l'instance**. L'archivage se **supervise** :
> ```sql
> SELECT archived_count, last_archived_wal, last_archived_time,
>        failed_count, last_failed_wal, last_failed_time
> FROM pg_stat_archiver;
> ```

---

## 6. Restauration à un instant donné (PITR)

### 6.1 Paramètres de restauration

Depuis PG 12, la restauration se configure dans `postgresql.conf` (ou `postgresql.auto.conf`) et se déclenche par la présence d'un fichier **`recovery.signal`** dans PGDATA.

| Paramètre | Rôle |
|-----------|------|
| `restore_command` | Commande pour récupérer un WAL archivé : `cp /archive/%f %p` |
| `recovery_target_time` | Instant cible, ex. `'2026-09-23 14:31:59+01'` |
| `recovery_target_xid` | Identifiant de transaction cible |
| `recovery_target_lsn` | Position WAL cible |
| `recovery_target_name` | Point nommé créé par `SELECT pg_create_restore_point('avant_migration')` |
| `recovery_target = 'immediate'` | S'arrêter dès que la cohérence est atteinte |
| `recovery_target_inclusive` | Inclure (défaut) ou non la transaction cible |
| `recovery_target_action` | `pause` (défaut), `promote`, `shutdown` |
| `recovery_target_timeline` | `latest` (défaut) ou numéro de timeline |

Avec `recovery_target_action = 'pause'`, l'instance s'arrête au point cible en **lecture seule** : on vérifie les données, puis on valide avec `SELECT pg_wal_replay_resume();` (qui promeut l'instance) ou on ajuste la cible et on recommence.

### 6.2 Timelines

Après une restauration PITR, l'instance crée une nouvelle **timeline** (branche d'historique) : les WAL générés ensuite portent un nouveau numéro de timeline (préfixe du nom de fichier) et un fichier `.history` est archivé. Cela évite que le nouvel historique se mélange à l'ancien dans l'archive, et permet même de restaurer plusieurs fois à des instants différents.

### 6.3 Points de restauration nommés

Avant une opération risquée (migration, chargement massif) :

```sql
SELECT pg_create_restore_point('avant_migration_v2');
```

---

## 7. Sauvegardes incrémentales (PostgreSQL 17+)

PG 17 introduit les sauvegardes incrémentales natives : seuls les blocs modifiés depuis une sauvegarde précédente sont copiés.

```ini
summarize_wal = on          # PG 17+ : résume les blocs modifiés
```

```bash
pg_basebackup -D /sauv/complete -c fast
pg_basebackup -D /sauv/incr_lundi --incremental=/sauv/complete/backup_manifest
pg_basebackup -D /sauv/incr_mardi --incremental=/sauv/incr_lundi/backup_manifest

# Reconstituer une sauvegarde complète avant de restaurer
pg_combinebackup /sauv/complete /sauv/incr_lundi /sauv/incr_mardi -o /sauv/reconstituee
```

---

## 8. Outils professionnels

En production, on utilise rarement `pg_basebackup` + `cp` seuls. Les outils dédiés apportent parallélisme, compression, chiffrement, rétention, vérification, stockage objet (S3, Azure, GCS) et sauvegardes incrémentales.

| Outil | Points forts |
|-------|--------------|
| **pgBackRest** | Référence du marché : complet/différentiel/incrémental, parallélisme, chiffrement AES-256, S3/Azure/GCS, vérification, restauration en mode *delta* |
| **Barman** (EDB) | Serveur de sauvegarde centralisé pour de nombreux clusters, intégration avec la réplication en flux |
| **WAL-G** | Orienté cloud, léger, utilisé dans de nombreuses architectures Kubernetes |

### Aperçu de pgBackRest

`/etc/pgbackrest/pgbackrest.conf` :

```ini
[global]
repo1-path=/var/lib/pgbackrest
repo1-retention-full=2
repo1-cipher-type=aes-256-cbc
repo1-cipher-pass=<phrase_secrète_longue_et_aléatoire>
process-max=2
start-fast=y

[main]
pg1-path=/var/lib/postgresql/16/main
```

`postgresql.conf` :

```ini
archive_mode = on
archive_command = 'pgbackrest --stanza=main archive-push %p'
```

```bash
sudo -u postgres pgbackrest --stanza=main stanza-create
sudo -u postgres pgbackrest --stanza=main check
sudo -u postgres pgbackrest --stanza=main --type=full backup
sudo -u postgres pgbackrest --stanza=main --type=incr backup
sudo -u postgres pgbackrest --stanza=main info
# PITR (instance arrêtée)
sudo -u postgres pgbackrest --stanza=main --delta --type=time \
     "--target=2026-09-23 14:31:59+01" --target-action=promote restore
```

---

## 9. Protéger les sauvegardes

> 🔐 **Angle sécurité — les sauvegardes sont une cible prioritaire**
>
> 1. **Elles contiennent toutes les données**, souvent avec moins de protections que la base de production. Un fichier `.dump` oublié sur un serveur web ou un bucket S3 public est une fuite de données massive.
> 2. **Les rançongiciels les ciblent en premier** : avant de chiffrer la production, les attaquants cherchent et détruisent les sauvegardes accessibles depuis le réseau.
>
> Mesures :
>
> | Mesure | Détail |
> |--------|--------|
> | **Chiffrer** | Chiffrement asymétrique de préférence (GPG, age) : le serveur de base ne détient que la **clé publique**, la clé privée est conservée hors ligne. Un attaquant qui compromet le serveur ne peut pas déchiffrer les anciennes sauvegardes. |
> | **Isoler** | Le serveur de sauvegarde **tire** les données (mode *pull*) ; la production ne doit pas pouvoir supprimer les sauvegardes. |
> | **Immuabilité** | Stockage objet avec verrouillage (*Object Lock* / WORM), bandes, disques déconnectés. |
> | **Restreindre les accès** | Répertoires en 0700, comptes dédiés, fichier `~/.pgpass` en 0600 (sinon ignoré par libpq). |
> | **Contrôler l'intégrité** | Sommes de contrôle (`backup_manifest`, SHA-256) pour détecter une altération. |
> | **Tester** | Restauration régulière dans un environnement isolé. |
> | **Rétention et effacement** | Conserver selon les obligations légales, puis supprimer : une donnée personnelle effacée en production subsiste dans les sauvegardes jusqu'à leur expiration (à documenter pour la conformité). |

Chiffrement asymétrique d'un dump avec GPG :

```bash
# Une seule fois, sur un poste sûr : créer la paire de clés, exporter la clé publique
gpg --full-generate-key
gpg --export --armor sauvegarde@exemple.ma > cle_publique_sauvegarde.asc

# Sur le serveur : importer uniquement la clé publique
gpg --import cle_publique_sauvegarde.asc

# Sauvegarde chiffrée à la volée (aucun fichier en clair sur le disque)
pg_dump -Fc -d banque | gpg --encrypt --recipient sauvegarde@exemple.ma \
    --trust-model always -o banque_$(date +%F).dump.gpg

# Restauration (sur une machine disposant de la clé privée)
gpg --decrypt banque_2026-09-23.dump.gpg | pg_restore -d banque_restauree
```

Le script `scripts/bash/sauvegarde_logique.sh` automatise ce processus.

---

## TP 6 — Sauvegarder, casser, restaurer

> Prends un snapshot de la VM avant de commencer.

### Partie A — Sauvegarde et restauration logique

Sur Debian/Ubuntu, seuls les outils les plus courants (`psql`, `pg_dump`, `pg_basebackup`…) sont dans le `PATH`. Les autres (`pg_verifybackup`, `pg_waldump`, `pg_combinebackup`, `pg_ctl`) sont dans `/usr/lib/postgresql/16/bin/`. Ajoute ce répertoire au `PATH` du compte `postgres` :

```bash
$ sudo -i -u postgres
postgres$ echo 'export PATH=/usr/lib/postgresql/16/bin:$PATH' >> ~/.profile && source ~/.profile
postgres$ mkdir -p ~/sauvegardes && cd ~/sauvegardes
postgres$ pg_dumpall --globals-only -f globals.sql
postgres$ time pg_dump -Fc -d banque -f banque.dump
postgres$ time pg_dump -Fd -j 2 -d banque -f banque.dir
postgres$ ls -lh banque.dump && du -sh banque.dir
postgres$ pg_restore -l banque.dump | head -40
```

Restauration complète dans une nouvelle base :

```bash
postgres$ createdb banque_copie
postgres$ time pg_restore -d banque_copie -j 2 banque.dump
postgres$ psql -d banque_copie -c "SELECT count(*) FROM bank.operations;"
```

Scénario : un collègue supprime la table des agences.

```bash
postgres$ psql -d banque_copie -c "DROP TABLE bank.agences CASCADE;"
```

Observe ce que `CASCADE` a supprimé en plus (les clés étrangères de `clients` et `conseillers`). Restaure uniquement la table, ses données, ses privilèges et les contraintes perdues :

```bash
postgres$ pg_restore -l banque.dump | grep -E "agences|id_agence_fkey" > liste_agences.txt
postgres$ cat liste_agences.txt
postgres$ pg_restore -d banque_copie -L liste_agences.txt banque.dump
postgres$ psql -d banque_copie -c "\d bank.agences"
postgres$ psql -d banque_copie -c "\d bank.clients"
```

La liste contient la table, ses données, sa clé primaire, ses privilèges (`ACL`) et les clés étrangères qui pointent vers elle (`FK CONSTRAINT … id_agence_fkey`). Vérifie que ces contraintes ont bien été recréées sur `clients` et `conseillers`.

```bash
postgres$ dropdb banque_copie
```

### Partie B — Mise en place de l'archivage WAL

```bash
postgres$ mkdir -p /var/lib/postgresql/archive_wal && chmod 700 /var/lib/postgresql/archive_wal
postgres$ exit
$ sudo tee /etc/postgresql/16/main/conf.d/20-archivage.conf > /dev/null <<'EOF'
archive_mode = on
archive_command = 'test ! -f /var/lib/postgresql/archive_wal/%f && cp %p /var/lib/postgresql/archive_wal/%f'
archive_timeout = 60
EOF
$ sudo systemctl restart postgresql@16-main
```

Crée le rôle de réplication (la ligne `pg_hba.conf` correspondante a été ajoutée au module 02) :

```sql
postgres=# CREATE ROLE replicator LOGIN REPLICATION;
postgres=# \password replicator
```

Enregistre le mot de passe dans `~/.pgpass` du compte `postgres` :

```bash
$ sudo -i -u postgres
postgres$ echo "127.0.0.1:*:*:replicator:<mot_de_passe>" >> ~/.pgpass
postgres$ echo "localhost:*:*:replicator:<mot_de_passe>" >> ~/.pgpass
postgres$ chmod 600 ~/.pgpass
```

Format : `hôte:port:base:utilisateur:mot_de_passe`. Le joker `*` sur le port servira au module 08 (plusieurs clusters) ; sur la base, il couvre aussi les connexions de réplication.

Force un changement de segment et vérifie l'archivage :

```bash
postgres$ psql -c "SELECT pg_switch_wal();"
postgres$ sleep 2 && ls -l /var/lib/postgresql/archive_wal/
postgres$ psql -c "SELECT * FROM pg_stat_archiver;"
```

### Partie C — Sauvegarde de base

```bash
postgres$ mkdir -p ~/sauvegardes/physiques
postgres$ pg_basebackup -h 127.0.0.1 -U replicator \
            -D ~/sauvegardes/physiques/base_1 -Fp -Xs -P -c fast
postgres$ ls ~/sauvegardes/physiques/base_1
postgres$ pg_verifybackup ~/sauvegardes/physiques/base_1
```

Altère volontairement la sauvegarde pour voir le contrôle échouer, puis refais-la :

```bash
postgres$ echo "x" >> ~/sauvegardes/physiques/base_1/PG_VERSION
postgres$ pg_verifybackup ~/sauvegardes/physiques/base_1        # erreur détectée
postgres$ rm -rf ~/sauvegardes/physiques/base_1
postgres$ pg_basebackup -h 127.0.0.1 -U replicator \
            -D ~/sauvegardes/physiques/base_1 -Fp -Xs -P -c fast
```

### Partie D — La catastrophe

```bash
postgres$ psql -d banque
```

```sql
banque=# CREATE TABLE bank.contrats (id int PRIMARY KEY, client text, signe_le timestamptz DEFAULT now());
banque=# INSERT INTO bank.contrats SELECT g, 'Client ' || g, now() FROM generate_series(1, 1000) g;
banque=# SELECT pg_sleep(2);
banque=# SELECT now() AS instant_sain;      -- NOTE CETTE VALEUR EXACTE
banque=# SELECT pg_sleep(2);
banque=# DROP TABLE bank.contrats;          -- l'erreur
banque=# DELETE FROM bank.operations WHERE montant > 100;   -- et une deuxième, pour faire bonne mesure
banque=# SELECT pg_switch_wal();            -- s'assure que le WAL contenant l'erreur est archivé
banque=# \q
```

### Partie E — Restauration PITR

Arrête l'instance et mets de côté le répertoire de données endommagé (ne jamais le supprimer avant d'avoir réussi la restauration) :

```bash
postgres$ exit
$ sudo systemctl stop postgresql@16-main
$ sudo mv /var/lib/postgresql/16/main /var/lib/postgresql/16/main.endommage
$ sudo -u postgres cp -a /var/lib/postgresql/sauvegardes/physiques/base_1 /var/lib/postgresql/16/main
$ sudo chmod 700 /var/lib/postgresql/16/main
```

Configure la restauration (remplace l'horodatage par la valeur notée) :

```bash
$ sudo tee /etc/postgresql/16/main/conf.d/90-restauration.conf > /dev/null <<'EOF'
restore_command = 'cp /var/lib/postgresql/archive_wal/%f %p'
recovery_target_time = '2026-09-23 10:15:42.123456+01'
recovery_target_action = 'pause'
EOF
$ sudo -u postgres touch /var/lib/postgresql/16/main/recovery.signal
$ sudo systemctl start postgresql@16-main
$ sudo tail -30 /var/log/postgresql/postgresql-16-main.log
```

Dans le journal, suis la récupération des WAL archivés (`restored log file …`), puis l'arrêt au point cible (`recovery stopping before commit of transaction …` et `pausing at the end of recovery`).

Vérifie les données, en lecture seule :

```sql
banque=# SELECT pg_is_in_recovery();                 -- true
banque=# SELECT count(*) FROM bank.contrats;         -- 1000
banque=# SELECT count(*) FROM bank.operations;       -- 2 000 000 (le DELETE n'a pas eu lieu)
```

Si les données sont correctes, termine la restauration :

```sql
banque=# SELECT pg_wal_replay_resume();
banque=# SELECT pg_is_in_recovery();                 -- false : l'instance accepte les écritures
banque=# SELECT timeline_id FROM pg_control_checkpoint();
```

Nettoie la configuration de restauration **immédiatement** (sinon elle resterait active lors d'une restauration future) :

```bash
$ sudo rm /etc/postgresql/16/main/conf.d/90-restauration.conf
$ sudo ls /var/lib/postgresql/archive_wal/ | tail
```

Observe dans l'archive le fichier `.history` et les nouveaux segments de la timeline 2.

Refais immédiatement une **nouvelle sauvegarde de base** : l'ancienne et la nouvelle timeline coexistent désormais.

Quand tout est validé :

```bash
$ sudo rm -rf /var/lib/postgresql/16/main.endommage
```

**Mesure ton RTO** : combien de temps entre la découverte de l'erreur et la remise en service ?

### Partie F — Sauvegarde chiffrée automatisée

Étudie le script `scripts/bash/sauvegarde_logique.sh`, génère une paire de clés GPG de test, exécute le script, puis restaure la sauvegarde chiffrée dans une base `banque_verif` et compare le nombre de lignes de chaque table.

Planifie-le avec cron (compte `postgres`) :

```bash
postgres$ crontab -e
# Tous les jours à 01:30
30 1 * * * /usr/local/bin/sauvegarde_logique.sh banque >> /var/log/postgresql/sauvegarde.log 2>&1
```

---

## Exercices

1. Une entreprise exige un RPO de 15 minutes et un RTO de 2 heures pour une base de 500 Go. Propose une architecture de sauvegarde complète (outils, fréquences, rétention, emplacement, tests).
2. Pourquoi `pg_dump` de chaque base ne suffit-il pas à restaurer un cluster complet ? Que faut-il ajouter ?
3. Un `DELETE` massif a eu lieu à une heure inconnue « dans l'après-midi ». Comment retrouver l'instant précis pour cibler la restauration ? (Pistes : journaux, `pg_waldump`, `recovery_target_action = 'pause'`.)
4. L'archivage échoue depuis 3 jours sans que personne ne s'en aperçoive. Quelles sont les deux conséquences possibles et comment les éviter ?
5. Rédige la procédure écrite (runbook) de restauration PITR pour l'équipe d'astreinte, étape par étape, avec les vérifications.

---

## Quiz

1. Que signifient RPO et RTO ?
2. Pourquoi la réplication n'est-elle pas une sauvegarde ?
3. Quel format de `pg_dump` permet le parallélisme à la sauvegarde ?
4. Qu'est-ce que `pg_dump` ne sauvegarde pas, et comment le récupérer ?
5. Quelle est la condition impérative sur le code retour de `archive_command` ?
6. Quel fichier déclenche une restauration depuis PG 12 ?
7. Que fait `recovery_target_action = 'pause'` ?
8. À quoi sert `pg_verifybackup` et quelle est sa limite ?
9. Pourquoi préférer le chiffrement asymétrique pour les sauvegardes ?
10. Qu'est-ce qu'une timeline ?

*Corrigés : [annexe D](annexes/D-corriges.md#module-06).*

---

## À retenir

- La stratégie découle du RPO et du RTO ; la réplication ne remplace jamais la sauvegarde.
- Logique (`pg_dump -Fc` + `pg_dumpall --globals-only`) pour la souplesse ; physique + WAL pour le PITR.
- `archive_command` : code retour fiable, pas d'écrasement, et **supervision**.
- PITR : sauvegarde de base + WAL + `recovery.signal` + cible ; vérifier en pause avant de valider.
- Les sauvegardes sont chiffrées, isolées, immuables et **testées**.
