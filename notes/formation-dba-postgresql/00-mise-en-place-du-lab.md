# Module 00 — Mise en place du laboratoire

## Objectifs

- Disposer d'une machine Linux dédiée à la formation, sauvegardable par snapshot.
- Installer PostgreSQL et ses extensions de travail.
- Charger le jeu de données `banque` utilisé dans tous les modules.
- Vérifier que tout fonctionne avant de commencer.

---

## 1. Pourquoi une VM plutôt que ton poste

Un DBA apprend en provoquant des pannes : arrêt brutal, suppression de fichiers, corruption, saturation disque, bascule de réplication. Tu ne veux pas faire ça sur ton système principal. Une machine virtuelle offre deux avantages décisifs :

- **Les snapshots** : tu reviens à un état propre en quelques secondes.
- **L'isolement** : les tests réseau et sécurité (ouverture de ports, capture de trafic) restent confinés.

### Configuration recommandée

| Ressource | Minimum | Confortable |
|-----------|---------|-------------|
| Système | Ubuntu Server 24.04 LTS | idem |
| vCPU | 2 | 4 |
| RAM | 4 Go | 8 Go |
| Disque | 30 Go | 50 Go |
| Réseau | NAT + réseau hôte privé (host-only) | idem |

Hyperviseur : VirtualBox, VMware Workstation/Player, KVM/virt-manager ou Hyper-V. Le réseau host-only te permettra de te connecter à la base depuis ton poste hôte (utile au module 09 pour les tests TLS).

> **Réflexe à prendre** : snapshot nommé `00-lab-propre` dès que ce module est terminé, puis un snapshot au début de chaque module.

---

## 2. Installation de PostgreSQL

Deux possibilités. Choisis-en une et tiens-t'y pour toute la formation.

### Option 1 — Version fournie par Ubuntu (la plus simple)

```bash
$ sudo apt update
$ sudo apt install -y postgresql postgresql-contrib
```

Ubuntu 24.04 fournit PostgreSQL 16. Les chemins de la formation utilisent `16`.

### Option 2 — Dernière version via le dépôt officiel PGDG

Le PostgreSQL Global Development Group maintient un dépôt APT avec toutes les versions supportées.

```bash
$ sudo apt install -y postgresql-common
$ sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh
$ sudo apt install -y postgresql-17        # ou la dernière version majeure disponible
```

Remplace alors `16` par ta version dans tous les chemins.

### Extensions et outils complémentaires

```bash
$ VER=16   # adapte à ta version
$ sudo apt install -y postgresql-$VER-pgaudit      # audit (module 09)
$ sudo apt install -y pgbackrest pgbadger           # sauvegarde (06) et analyse de logs (10)
$ sudo apt install -y tmux tcpdump openssl git      # outils de travail
```

`pg_stat_statements`, `pgcrypto`, `pageinspect`, `auth_delay` et `passwordcheck` sont déjà inclus dans le paquet principal (anciennement appelé « contrib »).

---

## 3. Premiers pas

### Vérifier le service

```bash
$ sudo systemctl status postgresql
$ pg_lsclusters
```

`pg_lsclusters` est un outil propre à Debian/Ubuntu. Sortie attendue :

```
Ver Cluster Port Status Owner    Data directory              Log file
16  main    5432 online postgres /var/lib/postgresql/16/main /var/log/postgresql/postgresql-16-main.log
```

Retiens ces deux chemins : le **répertoire de données** et le **fichier de journal**. Sur Debian/Ubuntu, les fichiers de configuration sont à part, dans `/etc/postgresql/16/main/`.

### Se connecter

```bash
$ sudo -u postgres psql
```

```sql
postgres=# SELECT version();
postgres=# \conninfo
postgres=# \q
```

Tu te connectes sans mot de passe grâce à la méthode d'authentification `peer` : le noyau Linux certifie que le processus client appartient à l'utilisateur système `postgres`, qui correspond au rôle PostgreSQL du même nom. On l'étudiera au module 02.

---

## 4. tmux : indispensable pour les TP de concurrence

Plusieurs TP demandent deux ou trois sessions psql simultanées. `tmux` permet de découper un terminal.

| Action | Raccourci |
|--------|-----------|
| Lancer | `tmux` |
| Découper verticalement | `Ctrl-b` puis `%` |
| Découper horizontalement | `Ctrl-b` puis `"` |
| Changer de panneau | `Ctrl-b` puis flèche |
| Se détacher (session conservée) | `Ctrl-b` puis `d` |
| Se rattacher | `tmux attach` |

---

## 5. Chargement du jeu de données `banque`

Le script `scripts/sql/01_jeu_de_donnees_banque.sql` crée une base bancaire fictive :

| Table | Lignes | Rôle |
|-------|--------|------|
| `bank.agences` | 6 | Agences (Tétouan, Tanger, Rabat…) |
| `bank.clients` | 100 000 | Clients avec CIN, e-mail, téléphone |
| `bank.comptes` | ≈ 150 000 | Comptes courants et épargne |
| `bank.operations` | 2 000 000 | Opérations sur 3 ans |

Ces volumes sont choisis pour que les différences de performance soient **visibles** au module 07.

Copie le projet sur la VM (par `git`, `scp` ou dossier partagé), puis :

```bash
$ cd formation-dba-postgresql
$ sudo -u postgres psql < scripts/sql/01_jeu_de_donnees_banque.sql
```

On utilise la redirection `<` plutôt que `-f` : c'est ton shell qui lit le fichier, donc l'utilisateur `postgres` n'a pas besoin d'accéder à ton répertoire personnel (sous Ubuntu 24.04, les répertoires personnels sont en mode 750).

Durée : 1 à 3 minutes selon la machine.

### Vérification

```bash
$ sudo -u postgres psql -d banque
```

```sql
banque=# \dt bank.*
banque=# SELECT count(*) FROM bank.operations;
banque=# SELECT pg_size_pretty(pg_database_size('banque'));
```

Tu dois obtenir 2 000 000 d'opérations et une base d'environ 250 à 350 Mo.

---

## 6. Alternative : Docker

Si tu ne peux pas créer de VM, le fichier `scripts/lab/docker-compose.yml` lance PostgreSQL dans un conteneur.

```bash
$ cd scripts/lab
$ docker compose up -d
$ docker compose exec pg psql -U postgres
```

**Limites** : pas de `systemd`, pas des outils Debian (`pg_createcluster`, `pg_ctlcluster`), chemins différents (`/var/lib/postgresql/data`). Les TP de réplication (module 08) et de PITR (module 06) devront être adaptés. La VM reste fortement recommandée.

---

## 7. Checklist de fin de module

- [ ] VM créée, snapshot `00-lab-propre` pris
- [ ] `pg_lsclusters` affiche un cluster `online`
- [ ] `sudo -u postgres psql` fonctionne
- [ ] La base `banque` contient 2 000 000 d'opérations
- [ ] `tmux` est installé et tu sais découper l'écran
- [ ] Tu connais l'emplacement du répertoire de données, de la configuration et du journal
