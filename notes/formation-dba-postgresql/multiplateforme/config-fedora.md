# Module 02 sur Fedora — spécificités

> À lire **en complément** du module 02 (Installation et configuration), pas à la place. Seuls les points qui diffèrent de Debian/Ubuntu sont traités ici ; tout le reste du module s'applique tel quel.

---

## 1. Où sont les fichiers de configuration

Contrairement à Debian, Fedora suit le PostgreSQL amont : **la configuration est dans le répertoire de données**.

| Fichier | Paquet natif | Dépôt PGDG 16 |
|---------|--------------|---------------|
| `postgresql.conf` | `/var/lib/pgsql/data/postgresql.conf` | `/var/lib/pgsql/16/data/postgresql.conf` |
| `pg_hba.conf` | `/var/lib/pgsql/data/pg_hba.conf` | `/var/lib/pgsql/16/data/pg_hba.conf` |
| `pg_ident.conf` | idem, même dossier | idem |

Il n'y a **pas** de `conf.d/` par défaut. Pour garder l'approche modulaire recommandée par le module 02, crée-le et active-le :

```bash
sudo -u postgres mkdir -p /var/lib/pgsql/data/conf.d
# dans postgresql.conf, décommente/ajoute :
#   include_dir = 'conf.d'
sudo -u postgres tee -a /var/lib/pgsql/data/postgresql.conf <<< "include_dir = 'conf.d'"
```

Tu peux alors déposer tes surcharges (ex. `50-durcissement.conf`) dans ce dossier, comme dans le module.

## 2. initdb et checksums

Le module recommande `initdb --data-checksums`. Sur Fedora, l'initialisation passe par `postgresql-setup`, auquel on transmet les options via `PGSETUP_INITDB_OPTIONS` :

```bash
# paquet natif
sudo PGSETUP_INITDB_OPTIONS="--data-checksums --auth-host=scram-sha-256 --auth-local=scram-sha-256" \
     postgresql-setup --initdb

# dépôt PGDG
sudo PGSETUP_INITDB_OPTIONS="--data-checksums" \
     /usr/pgsql-16/bin/postgresql-16-setup initdb
```

À faire **avant** le premier démarrage (l'initialisation ne se fait qu'une fois).

## 3. Recharger / redémarrer

| Module (Debian) | Fedora |
|-----------------|--------|
| `pg_ctlcluster 16 main reload` | `sudo systemctl reload postgresql` |
| `pg_ctlcluster 16 main restart` | `sudo systemctl restart postgresql` |

(`postgresql-16` avec le dépôt PGDG.) Le rechargement par SQL `SELECT pg_reload_conf();` marche à l'identique.

## 4. Vérifier la configuration (identique au module)

Ces requêtes sont portables et fonctionnent telles quelles :

```sql
SELECT name, setting, context FROM pg_settings WHERE name = 'shared_buffers';
SELECT * FROM pg_file_settings WHERE error IS NOT NULL;   -- erreurs de postgresql.conf
TABLE pg_hba_file_rules;                                   -- règles pg_hba chargées
```

## 5. Journalisation

Par défaut, Fedora envoie souvent les journaux vers **journald** :

```bash
journalctl -u postgresql -f          # suivi en direct
```

Pour obtenir des fichiers exploitables par pgBadger (module 10), active le collecteur dans `postgresql.conf`, comme dans le module :

```ini
logging_collector = on
log_directory = 'log'                # → /var/lib/pgsql/data/log/
log_filename = 'postgresql-%Y-%m-%d.log'
log_line_prefix = '%m [%p] %q%u@%d %h '
```

## 6. SELinux (ajout spécifique Fedora)

Deux cas où SELinux, actif par défaut, doit être informé — sinon le service refuse de démarrer ou de se lier :

```bash
# Changer le port (ex. 5433) déclaré dans postgresql.conf
sudo semanage port -a -t postgresql_port_t -p tcp 5433

# Déplacer PGDATA vers un montage dédié
sudo semanage fcontext -a -t postgresql_db_t "/data/pgsql(/.*)?"
sudo restorecon -Rv /data/pgsql
```

Ne désactive pas SELinux : le laisser en *enforcing* est cohérent avec l'esprit du module 09.

## 7. TLS (module 02 / module 09)

Les certificats se placent, comme partout, dans le répertoire de données (ou ailleurs avec un chemin absolu). La clé privée doit appartenir à `postgres` et être en `0600` :

```bash
sudo -u postgres bash -c 'cd /var/lib/pgsql/data && \
  openssl req -new -x509 -days 365 -nodes -text -out server.crt \
    -keyout server.key -subj "/CN=$(hostname)" && chmod 600 server.key'
```

Puis dans `postgresql.conf` : `ssl = on` (le reste du module s'applique). Le pare-feu se gère avec `firewall-cmd` (voir `lab-fedora.md`).

---

Le reste du module 02 (structure de `pg_hba.conf`, méthodes d'authentification, ordre des règles, paramètres mémoire, modes d'arrêt, `ALTER SYSTEM`…) est **identique** sur Fedora.
