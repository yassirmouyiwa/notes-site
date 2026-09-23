# Équivalences entre plateformes — Debian/Ubuntu ↔ Fedora/RHEL ↔ Windows

> **Document central du volet multiplateforme.** Les douze modules de la formation sont écrits pour **Debian/Ubuntu**. Le SQL, les concepts, les vues système, `psql` et ses méta-commandes sont **identiques partout** : rien à traduire de ce côté. Ce qui change d'un système à l'autre, ce sont les **chemins de fichiers**, la **gestion du service**, l'**installation** et quelques **outils**. Garde cette table sous les yeux : chaque fois qu'un module cite un chemin Debian (`/etc/postgresql/16/main/…`) ou une commande de cluster (`pg_ctlcluster`), lis la colonne correspondant à ton système.

Version de référence : **PostgreSQL 16**. Sur Fedora, adapte le numéro à la version installée (Fedora 42 fournit PG 17 par défaut, Fedora 40 fournit PG 16 ; voir le guide Fedora).

---

## 1. Vue d'ensemble des philosophies

| | Debian/Ubuntu | Fedora/RHEL | Windows (installeur EDB) |
|---|---|---|---|
| **Multi-versions/clusters** | Oui, natif (`pg_lsclusters`) | Un service par version | Un service par version |
| **Configuration** | **Séparée** des données (`/etc/postgresql/…`) | **Dans** le répertoire de données | **Dans** le répertoire de données |
| **Initialisation** | Automatique à l'installation | **Manuelle** (`postgresql-setup`) | Automatique par l'installeur |
| **Démarrage auto** | Activé à l'installation | **Désactivé** par défaut | Activé (service Windows) |
| **Outils versionnés** | `pg_ctlcluster`, `pg_createcluster`… | `systemctl` standard | Services Windows / `pg_ctl` |
| **Sécurité OS notable** | AppArmor (souvent lâche) | **SELinux** (actif, strict) | ACL Windows, pas de socket Unix |

La logique Fedora/RHEL et Windows suit le **PostgreSQL « amont »** (configuration dans le répertoire de données) ; la logique Debian est particulière (configuration déportée, wrappers de cluster). Retenir cela explique 90 % des différences.

---

## 2. Installation et initialisation

| Action | Debian/Ubuntu | Fedora (paquet natif) | Windows |
|--------|---------------|-----------------------|---------|
| Installer | `sudo apt install postgresql-16` | `sudo dnf install postgresql-server postgresql-contrib` | Installeur EDB, ou `winget install PostgreSQL.PostgreSQL.16` |
| Initialiser le cluster | *(automatique)* | `sudo postgresql-setup --initdb` | *(automatique par l'installeur)* |
| Activer + démarrer | *(automatique)* | `sudo systemctl enable --now postgresql` | *(service créé et démarré)* |
| Version obtenue | celle du dépôt (16) | celle de la release Fedora (17 sur F42) | celle choisie dans l'installeur |
| Version **précise** (ex. 16) | dépôt PGDG apt | **dépôt PGDG yum** → `/usr/pgsql-16/…` | choisie au téléchargement |

> Sur Fedora, pour épingler PostgreSQL 16 quelle que soit la version par défaut, utiliser le dépôt PGDG (voir le guide Fedora) : les chemins deviennent versionnés (`/usr/pgsql-16/bin`, `/var/lib/pgsql/16/data`, service `postgresql-16`).

---

## 3. Chemins de fichiers (le cœur des différences)

| Élément | Debian/Ubuntu | Fedora (natif) | Fedora (PGDG 16) | Windows |
|---------|---------------|----------------|------------------|---------|
| **PGDATA** (données) | `/var/lib/postgresql/16/main/` | `/var/lib/pgsql/data/` | `/var/lib/pgsql/16/data/` | `C:\Program Files\PostgreSQL\16\data\` |
| **postgresql.conf** | `/etc/postgresql/16/main/postgresql.conf` | `/var/lib/pgsql/data/postgresql.conf` | `/var/lib/pgsql/16/data/postgresql.conf` | `…\PostgreSQL\16\data\postgresql.conf` |
| **conf.d/** (surcharges) | `/etc/postgresql/16/main/conf.d/` | à créer + `include_dir` | idem | à créer + `include_dir` |
| **pg_hba.conf** | `/etc/postgresql/16/main/pg_hba.conf` | `/var/lib/pgsql/data/pg_hba.conf` | `/var/lib/pgsql/16/data/pg_hba.conf` | `…\PostgreSQL\16\data\pg_hba.conf` |
| **postgresql.auto.conf** | dans PGDATA | dans PGDATA | dans PGDATA | dans PGDATA |
| **WAL** | `…/16/main/pg_wal/` | `/var/lib/pgsql/data/pg_wal/` | `/var/lib/pgsql/16/data/pg_wal/` | `…\16\data\pg_wal\` |
| **Journaux serveur** | `/var/log/postgresql/postgresql-16-main.log` | `/var/lib/pgsql/data/log/*.log` **ou** `journalctl -u postgresql` | `/var/lib/pgsql/16/data/log/` | `…\16\data\log\*.log` |
| **Binaires courants** (`psql`, `pg_dump`…) | `/usr/bin` | `/usr/bin` | `/usr/pgsql-16/bin` | `…\PostgreSQL\16\bin` |
| **Binaires « cachés »** (`pg_rewind`, `pg_waldump`, `initdb`, `pg_upgrade`…) | `/usr/lib/postgresql/16/bin/` | `/usr/bin` (pas de séparation) | `/usr/pgsql-16/bin` | `…\PostgreSQL\16\bin` (tout au même endroit) |
| **Fichier `.pgpass`** | `~/.pgpass` (chmod 600) | `~/.pgpass` (chmod 600) | `~/.pgpass` | `%APPDATA%\postgresql\pgpass.conf` |
| **Certificats SSL par défaut** | dans PGDATA | dans PGDATA | dans PGDATA | dans PGDATA |

> **Point qui surprend souvent (rappel du module 06 / annexe A).** Sur Debian, certains outils ne sont **que** dans `/usr/lib/postgresql/16/bin/` et doivent être ajoutés au PATH. Sur **Fedora natif et Windows, tous les binaires sont au même endroit** : ce piège Debian **disparaît**. Sur Fedora PGDG, tout est dans `/usr/pgsql-16/bin`.

---

## 4. Gestion du service

| Action | Debian/Ubuntu | Fedora | Windows (cmd/PowerShell élevé) |
|--------|---------------|--------|-------------------------------|
| Démarrer | `sudo pg_ctlcluster 16 main start` **ou** `sudo systemctl start postgresql@16-main` | `sudo systemctl start postgresql` | `net start postgresql-x64-16` |
| Arrêter | `sudo pg_ctlcluster 16 main stop` | `sudo systemctl stop postgresql` | `net stop postgresql-x64-16` |
| Redémarrer | `sudo pg_ctlcluster 16 main restart` | `sudo systemctl restart postgresql` | `Restart-Service postgresql-x64-16` |
| Recharger (SIGHUP) | `sudo pg_ctlcluster 16 main reload` | `sudo systemctl reload postgresql` | `pg_ctl reload -D "…\16\data"` **ou** `Restart-Service` |
| État | `pg_lsclusters` | `systemctl status postgresql` | `Get-Service postgresql*` |
| Journaux du service | `/var/log/postgresql/…` | `journalctl -u postgresql -f` | Observateur d'événements + `…\data\log\` |
| Nom du service | `postgresql@16-main` | `postgresql` (natif) / `postgresql-16` (PGDG) | `postgresql-x64-16` |

Le **rechargement par SQL** fonctionne **partout, à l'identique**, et évite ces différences :

```sql
SELECT pg_reload_conf();     -- recharge les paramètres SIGHUP, quel que soit l'OS
```

---

## 5. Se connecter en administrateur

| | Debian/Ubuntu | Fedora | Windows |
|---|---|---|---|
| Compte système `postgres` | oui (auth `peer` locale) | oui (auth `peer` locale) | **non** — pas de socket Unix ni de `peer` |
| Ouvrir psql en superutilisateur | `sudo -u postgres psql` | `sudo -u postgres psql` | `psql -U postgres` (**mot de passe** défini à l'installation) |
| Exécuter un script en superutilisateur | `sudo -u postgres psql -f fichier.sql` | `sudo -u postgres psql -f fichier.sql` | `psql -U postgres -f fichier.sql` |
| Authentification locale par défaut | `peer` (socket) | `peer` (socket) / `ident` | `scram-sha-256` (TCP, pas de socket) |

> Conséquence Windows : les lignes `local …` de `pg_hba.conf` ne servent à rien (pas de socket Unix) ; tout passe par TCP `127.0.0.1`. Il n'y a pas de `sudo -u postgres` : on se connecte avec `-U postgres` et le mot de passe choisi lors de l'installation.

---

## 6. Administration système autour de la base

| Besoin | Debian/Ubuntu | Fedora | Windows |
|--------|---------------|--------|---------|
| Gestionnaire de paquets / MAJ | `apt` | `dnf` | installeur EDB / `winget` |
| Pare-feu — ouvrir 5432 | `sudo ufw allow …` | `sudo firewall-cmd --add-service=postgresql --permanent && sudo firewall-cmd --reload` | `New-NetFirewallRule -DisplayName PostgreSQL -Direction Inbound -LocalPort 5432 -Protocol TCP -Action Allow` |
| Sécurité obligatoire (MAC) | AppArmor | **SELinux** (voir ci-dessous) | ACL NTFS |
| Éditer une config | `nano`/`vim` | `nano`/`vim` | Bloc-notes **en administrateur** (fichier dans `Program Files`) |
| Tâches planifiées | `cron` | `cron` (`cronie`) | **Planificateur de tâches** / `pg_cron` |
| Scripts d'exploitation | **bash** | **bash** (identiques) | **PowerShell** (voir `scripts/powershell/`) |

### SELinux (spécifique Fedora/RHEL)

SELinux est **actif et strict** par défaut. Il n'entrave pas une installation standard, mais il **bloque** deux changements courants tant qu'on ne l'informe pas :

```bash
# Changer le port d'écoute (ex. 5433) : autoriser ce port pour PostgreSQL
sudo semanage port -a -t postgresql_port_t -p tcp 5433

# Déplacer PGDATA vers un montage dédié : réétiqueter le nouveau chemin
sudo semanage fcontext -a -t postgresql_db_t "/data/pgsql(/.*)?"
sudo restorecon -Rv /data/pgsql
```

(`semanage` vient du paquet `policycoreutils-python-utils`.) C'est le principal ajout de sécurité à connaître sur Fedora par rapport aux modules, qui n'en parlent pas.

---

## 7. Ce qui ne change PAS (l'essentiel de la formation)

Tout ceci est **identique sur les trois systèmes** — donc tous les modules s'appliquent directement :

- **Tout le SQL** : `CREATE ROLE`, `GRANT`, RLS, `SECURITY DEFINER`, transactions, MVCC, `VACUUM`, `EXPLAIN`, index, partitionnement…
- **Les vues système** : `pg_stat_activity`, `pg_stat_replication`, `pg_replication_slots`, `pg_stat_statements`, `pg_hba_file_rules`, `pg_settings`…
- **`psql` et ses méta-commandes** : `\l \c \dt \d+ \du \dp \dn \df \x \timing \e \i \watch \conninfo \password \q`.
- **Les paramètres de configuration** : mêmes noms, mêmes valeurs (`shared_buffers`, `work_mem`, `wal_level`, `ssl`, `password_encryption`, `pgaudit.*`…). Seul l'**emplacement du fichier** change.
- **Les scripts SQL** de la formation (`requetes_supervision.sql`, `audit_securite.sql`, `01_jeu_de_donnees_banque.sql`) : exécutables tels quels partout.
- **Les concepts** : sauvegarde, PITR, réplication, sécurité, supervision, performance — indépendants de l'OS.
- **pgAdmin** et les extensions (`pg_stat_statements`, `pgcrypto`, `pgaudit`, `pg_partman`, `pg_cron`) : disponibles partout.

---

## 8. L'option qui gomme toutes les différences : Docker

Si tu veux **le même environnement exact** quel que soit ton poste (Fedora, Windows, macOS), utilise le conteneur fourni : `scripts/lab/docker-compose.yml`. Docker Desktop (Windows/macOS) ou le moteur natif (Fedora) font tourner **la même image** `postgres`, avec les chemins Linux internes au conteneur. C'est souvent le choix le plus simple pour **apprendre**, en gardant à l'esprit qu'en production tu retrouveras les spécificités de ton OS cible — d'où l'utilité de cette table.

---

## Par où continuer

- **Fedora** → `lab-fedora.md` (mise en place) puis `config-fedora.md` (spécificités du module 02).
- **Windows** → `lab-windows.md` (mise en place) puis `config-windows.md` (spécificités du module 02).
- Ensuite, **suis les modules 01 à 11 normalement**, cette table à côté pour traduire chemins et commandes.
