# Module 02 sur Windows — spécificités

> À lire **en complément** du module 02 (Installation et configuration), pas à la place. Seuls les points qui diffèrent de Debian/Ubuntu sont traités ici ; tout le reste du module s'applique tel quel (le SQL et les paramètres sont identiques).

---

## 1. Où sont les fichiers de configuration

Comme sur Fedora, Windows suit le PostgreSQL amont : **la configuration est dans le répertoire de données**.

| Fichier | Chemin |
|---------|--------|
| `postgresql.conf` | `C:\Program Files\PostgreSQL\16\data\postgresql.conf` |
| `pg_hba.conf` | `C:\Program Files\PostgreSQL\16\data\pg_hba.conf` |
| `pg_ident.conf` | même dossier |
| `postgresql.auto.conf` | même dossier (écrit par `ALTER SYSTEM`) |

> Ces fichiers sont sous `Program Files` : pour les éditer, ouvre le **Bloc-notes en administrateur** (clic droit → Exécuter en tant qu'administrateur), sinon l'enregistrement est refusé. Localiser le fichier actif depuis psql : `SHOW config_file;`

Pour l'approche modulaire du module (dossier `conf.d/`), crée-le et ajoute dans `postgresql.conf` :

```ini
include_dir = 'conf.d'
```

## 2. initdb et checksums

L'installeur EDB exécute `initdb` automatiquement, **sans** `--data-checksums`. Si tu veux les sommes de contrôle (recommandé par le module), il faut créer un **cluster séparé** à la main, car on ne réinitialise pas celui de l'installeur :

```powershell
& "C:\Program Files\PostgreSQL\16\bin\initdb" `
  -D "C:\pglab\data" -U postgres --data-checksums `
  --auth-host=scram-sha-256 -E UTF8
```

Puis on le démarre ponctuellement avec `pg_ctl` (voir §3) ou on l'enregistre comme service (`pg_ctl register`). Pour un simple lab, le cluster de l'installeur suffit ; retiens surtout **où** régler les checksums.

## 3. Gérer le service et recharger

| Module (Debian) | Windows (console **administrateur**) |
|-----------------|--------------------------------------|
| `pg_ctlcluster 16 main start` | `net start postgresql-x64-16` |
| `pg_ctlcluster 16 main stop` | `net stop postgresql-x64-16` |
| `pg_ctlcluster 16 main restart` | `Restart-Service postgresql-x64-16` |
| `pg_ctlcluster 16 main reload` | `& "C:\Program Files\PostgreSQL\16\bin\pg_ctl" reload -D "C:\Program Files\PostgreSQL\16\data"` |
| `pg_lsclusters` | `Get-Service postgresql*` |

Le rechargement par SQL `SELECT pg_reload_conf();` est identique et évite ces différences.

## 4. pg_hba.conf : pas de socket, tout en TCP

Différence importante : **Windows n'a pas de socket Unix ni d'authentification `peer`**. Les lignes `local …` sont **sans effet**. Les connexions locales passent par `127.0.0.1` :

```
# pg_hba.conf typique sur Windows
host    all    all    127.0.0.1/32    scram-sha-256
host    all    all    ::1/128         scram-sha-256
```

Toutes les règles du module 02 restent valables (ordre, `hostssl`, `scram-sha-256`, `reject` final) ; simplement, il n'y a pas de ligne `local` à considérer. Vérification identique :

```sql
TABLE pg_hba_file_rules;
```

## 5. Vérifier la configuration (identique)

```sql
SELECT name, setting, context FROM pg_settings WHERE name = 'shared_buffers';
SELECT * FROM pg_file_settings WHERE error IS NOT NULL;
SHOW config_file;      -- utile pour retrouver le bon fichier
SHOW hba_file;
```

## 6. Journalisation

Les journaux sont dans `C:\Program Files\PostgreSQL\16\data\log\`. Le collecteur est en général déjà actif. Pour un format exploitable par pgBadger (module 10), même réglage que le module :

```ini
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d.log'
log_line_prefix = '%m [%p] %q%u@%d %h '
log_min_duration_statement = 1000
```

## 7. TLS

Génère les certificats avec l'`openssl` fourni par l'installeur (dans `…\16\bin`), place-les dans le répertoire de données, puis `ssl = on`. Sur Windows, les permissions de la clé se gèrent par **ACL NTFS** (et non `chmod`) : restreins l'accès de `server.key` au compte de service (`NT AUTHORITY\NetworkService` ou le compte `postgres` choisi). Exemple :

```powershell
icacls "C:\Program Files\PostgreSQL\16\data\server.key" /inheritance:r
icacls "C:\Program Files\PostgreSQL\16\data\server.key" /grant:r "NT AUTHORITY\NetworkService:(R)"
```

Le reste (modes `sslmode`, `verify-full`, `hostssl`) est identique au module 02/09.

## 8. Mises à jour

Pas d'`apt`/`dnf` : les versions **mineures** (16.x) s'installent en relançant l'installeur EDB de la nouvelle mineure, ou via `winget upgrade`. Le service est arrêté puis les binaires remplacés ; les données restent en place. Pour une version **majeure** (16 → 17), voir le module 10 (`pg_upgrade`), dont la logique s'applique avec les chemins Windows.

---

Le reste du module 02 (structure de `pg_hba.conf`, méthodes d'authentification, ordre des règles, paramètres mémoire, `ALTER SYSTEM`, modes d'arrêt…) est **identique** sur Windows.
