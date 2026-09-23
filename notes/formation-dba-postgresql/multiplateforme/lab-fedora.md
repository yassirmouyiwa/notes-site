# Mise en place du laboratoire — Fedora / RHEL

> Équivalent Fedora du **module 00**. À faire une fois, avant de suivre les modules 01 à 11. À lire avec `equivalences-plateformes.md` à côté.

Deux chemins possibles. Choisis-en un :

- **A — Paquet natif Fedora** (le plus simple) : tu obtiens la version PostgreSQL de ta release Fedora (17 sur Fedora 42, 16 sur Fedora 40). Chemins : `/var/lib/pgsql/data/`, service `postgresql`.
- **B — Dépôt PGDG** (pour épingler PostgreSQL 16, comme la formation) : chemins versionnés `/usr/pgsql-16/…`, service `postgresql-16`.

Si tu débutes, prends **A** et remplace mentalement « 16 » par ta version. Si tu veux coller exactement à la formation, prends **B**.

---

## Option A — Paquet natif Fedora

```bash
# 1. Installer serveur + modules contrib (pg_stat_statements, pgcrypto…)
sudo dnf install -y postgresql-server postgresql-contrib

# 2. Initialiser le cluster (NON automatique sur Fedora/RHEL)
sudo postgresql-setup --initdb

# 3. Activer au démarrage et lancer
sudo systemctl enable --now postgresql

# 4. Vérifier
sudo systemctl status postgresql
psql --version
```

Le répertoire de données est `/var/lib/pgsql/data/` ; `postgresql.conf` et `pg_hba.conf` y sont **directement** (pas de `/etc/postgresql/…`).

---

## Option B — Dépôt PGDG (PostgreSQL 16 épinglé)

```bash
# 1. Ajouter le dépôt PGDG pour Fedora (adapte F-42 à ta version de Fedora)
sudo dnf install -y https://download.postgresql.org/pub/repos/yum/reporpms/F-42-x86_64/pgdg-fedora-repo-latest.noarch.rpm

# 2. Installer PostgreSQL 16
sudo dnf install -y postgresql16-server postgresql16-contrib

# 3. Initialiser (le binaire d'init est versionné)
sudo /usr/pgsql-16/bin/postgresql-16-setup initdb

# 4. Activer et lancer (service versionné)
sudo systemctl enable --now postgresql-16
sudo systemctl status postgresql-16
```

Ici : données dans `/var/lib/pgsql/16/data/`, binaires dans `/usr/pgsql-16/bin/`, service `postgresql-16`.

> Ajoute les binaires au PATH pour la session si besoin :
> ```bash
> echo 'export PATH=/usr/pgsql-16/bin:$PATH' >> ~/.bash_profile && source ~/.bash_profile
> ```

---

## Étapes communes (A ou B)

### 1. Définir un mot de passe superutilisateur et tester

```bash
sudo -u postgres psql
```

Dans psql :

```sql
\password postgres        -- définit le mot de passe (haché SCRAM côté client)
SELECT version();
\q
```

### 2. Ouvrir le pare-feu (seulement si accès distant nécessaire)

```bash
sudo firewall-cmd --add-service=postgresql --permanent
sudo firewall-cmd --reload
```

Pour un lab purement local, **ne pas** ouvrir le pare-feu : on reste sur `127.0.0.1`.

### 3. Note SELinux

SELinux est actif et n'entrave **pas** une installation standard. Il n'intervient que si tu **changes le port** ou **déplaces le répertoire de données** — voir la section SELinux de `equivalences-plateformes.md`. Garde-le **en mode enforcing** (ne le désactive pas : c'est justement une bonne pratique de sécurité, cohérente avec le module 09).

### 4. Charger le jeu de données « banque »

Récupère le dépôt de la formation, puis :

```bash
# le script SQL est identique à celui de la formation (portable)
sudo -u postgres psql -f scripts/sql/01_jeu_de_donnees_banque.sql
```

Vérifie :

```bash
sudo -u postgres psql -d banque -c "\dt bank.*"
sudo -u postgres psql -d banque -c "SELECT count(*) FROM bank.operations;"
```

### 5. Activer pg_stat_statements (pour le module 07)

Édite `postgresql.conf` (emplacement selon l'option A ou B) :

```ini
shared_preload_libraries = 'pg_stat_statements'
```

Puis redémarre et crée l'extension :

```bash
sudo systemctl restart postgresql        # ou postgresql-16 en option B
sudo -u postgres psql -d banque -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"
```

---

## Correspondance rapide avec les modules

| Le module dit (Debian)… | Sur Fedora, fais… |
|--------------------------|-------------------|
| `sudo pg_ctlcluster 16 main restart` | `sudo systemctl restart postgresql` (ou `postgresql-16`) |
| Éditer `/etc/postgresql/16/main/postgresql.conf` | Éditer `/var/lib/pgsql/data/postgresql.conf` (ou `…/16/data/…`) |
| `/var/log/postgresql/postgresql-16-main.log` | `journalctl -u postgresql` ou `/var/lib/pgsql/data/log/*.log` |
| Outils dans `/usr/lib/postgresql/16/bin/` | `/usr/bin` (A) ou `/usr/pgsql-16/bin` (B) |
| `pg_lsclusters` | `systemctl status postgresql` |

Le reste des modules (SQL, rôles, sauvegarde, sécurité, supervision…) s'applique **sans changement**. Passe ensuite à `config-fedora.md` pour les détails du module 02, puis déroule la formation.
