# Mise en place du laboratoire — Windows

> Équivalent Windows du **module 00**. À faire une fois, avant de suivre les modules 01 à 11. À lire avec `equivalences-plateformes.md` à côté.

Deux approches. Choisis selon ton objectif :

- **A — Installeur natif Windows (EDB)** : PostgreSQL tourne comme **service Windows**. C'est l'expérience « Windows » authentique (chemins `C:\Program Files\PostgreSQL\16\`, service `postgresql-x64-16`). **Recommandé** si ta cible de production est Windows.
- **B — WSL2 (Ubuntu)** : tu installes une vraie Ubuntu dans Windows et tu suis **la formation d'origine sans rien traduire**. Idéal si ta cible est Linux mais que ton poste est sous Windows.

---

## Approche A — Installeur natif (EDB)

### 1. Installer

**Interface graphique** : télécharge l'installeur PostgreSQL 16 (EDB) depuis `https://www.postgresql.org/download/windows/`, lance-le **en administrateur**. Pendant l'assistant :

- Répertoire d'installation : laisser `C:\Program Files\PostgreSQL\16` (le laisser par défaut évite des bugs de service).
- Composants : PostgreSQL Server, pgAdmin 4, Command Line Tools (garder au moins les deux premiers).
- Répertoire de données : `C:\Program Files\PostgreSQL\16\data` (par défaut).
- **Mot de passe du superutilisateur `postgres`** : choisis-en un et **note-le** (il n'y a pas d'auth `peer` sur Windows, ce mot de passe est indispensable).
- Port : `5432`. Locale : par défaut.

**En ligne de commande** (équivalent, non interactif) :

```powershell
winget install PostgreSQL.PostgreSQL.16
```

### 2. Ajouter les outils au PATH (l'installeur ne le fait pas)

C'est la cause n°1 de « `psql` n'est pas reconnu ». En PowerShell (ta session utilisateur), puis **redémarre le terminal** :

```powershell
[Environment]::SetEnvironmentVariable(
  "Path", $env:Path + ";C:\Program Files\PostgreSQL\16\bin", "User")
```

### 3. Vérifier l'installation et le service

```powershell
Get-Service postgresql*            # doit afficher postgresql-x64-16 : Running
psql --version
```

### 4. Se connecter en superutilisateur

Il n'y a **pas** de `sudo -u postgres`. On se connecte par TCP avec mot de passe :

```powershell
psql -U postgres -h localhost
```

(ou via le menu Démarrer → « SQL Shell (psql) »). Dans psql :

```sql
SELECT version();
\conninfo
\q
```

### 5. Gérer le service

Console **en administrateur** :

```powershell
net start postgresql-x64-16
net stop  postgresql-x64-16
Restart-Service postgresql-x64-16
```

Ou l'interface graphique : `services.msc` → `postgresql-x64-16`.

Recharger la configuration sans redémarrer :

```powershell
& "C:\Program Files\PostgreSQL\16\bin\pg_ctl" reload -D "C:\Program Files\PostgreSQL\16\data"
```

…ou, indépendant de l'OS, depuis psql : `SELECT pg_reload_conf();`

### 6. Pare-feu (seulement si accès distant)

PowerShell **en administrateur** :

```powershell
New-NetFirewallRule -DisplayName "PostgreSQL" -Direction Inbound `
  -LocalPort 5432 -Protocol TCP -Action Allow
```

Pour un lab local, ne rien ouvrir : on reste sur `localhost`.

### 7. Charger le jeu de données « banque »

Le script SQL est **identique** à celui de la formation (portable). Depuis le dossier du dépôt :

```powershell
psql -U postgres -h localhost -f scripts\sql\01_jeu_de_donnees_banque.sql
```

Vérifier :

```powershell
psql -U postgres -h localhost -d banque -c "\dt bank.*"
psql -U postgres -h localhost -d banque -c "SELECT count(*) FROM bank.operations;"
```

### 8. Emplacements utiles sur Windows

| Élément | Chemin |
|---------|--------|
| Données (PGDATA) | `C:\Program Files\PostgreSQL\16\data\` |
| `postgresql.conf`, `pg_hba.conf` | **dans** `…\16\data\` |
| Journaux | `…\16\data\log\*.log` |
| Binaires (tous) | `C:\Program Files\PostgreSQL\16\bin\` |
| `.pgpass` (équivalent) | `%APPDATA%\postgresql\pgpass.conf` |

> Éditer `postgresql.conf` : ouvre le Bloc-notes **en administrateur** (le fichier est sous `Program Files`), sinon l'enregistrement échoue.

### 9. Particularités Windows à connaître

- **Pas de socket Unix ni de `peer`** : toute connexion locale passe par TCP `127.0.0.1` avec mot de passe (`scram-sha-256`). Les lignes `local …` de `pg_hba.conf` sont sans effet.
- **Scripts d'exploitation** : les `.sh` de la formation ne s'exécutent pas nativement. Utilise les équivalents **PowerShell** fournis : `scripts/powershell/verifier_sante.ps1` et `scripts/powershell/sauvegarde_logique.ps1`.
- **Planification** : à la place de `cron`, utilise le **Planificateur de tâches** Windows (ou l'extension `pg_cron` côté base).
- **Authentification intégrée** Windows possible via `sspi` (hors périmètre de ce lab).

---

## Approche B — WSL2 (Ubuntu dans Windows)

Si ta cible est Linux, c'est le plus simple : tu suis **la formation d'origine telle quelle**.

```powershell
# PowerShell en administrateur
wsl --install -d Ubuntu
# redémarrer, créer l'utilisateur Ubuntu, puis DANS la session Ubuntu :
```

```bash
sudo apt update && sudo apt install -y postgresql-16
# … et tu suis le module 00 d'origine sans aucune traduction.
```

> ⚠️ **Deux mondes séparés.** PostgreSQL installé dans WSL2 et PostgreSQL installé nativement sur Windows sont indépendants (données séparées) et peuvent **tous deux** réclamer le port 5432. Si un `psql` te connecte à un serveur inattendu, vérifie lequel avec `SELECT version();` : la version Windows mentionne *Visual C++*, la version WSL mentionne *gcc*. Choisis-en **un seul** pour ton lab et arrête le service de l'autre.

---

## Correspondance rapide avec les modules (approche A)

| Le module dit (Debian)… | Sur Windows, fais… |
|--------------------------|--------------------|
| `sudo -u postgres psql` | `psql -U postgres -h localhost` (mot de passe) |
| `sudo pg_ctlcluster 16 main restart` | `Restart-Service postgresql-x64-16` (admin) |
| Éditer `/etc/postgresql/16/main/postgresql.conf` | Éditer `…\PostgreSQL\16\data\postgresql.conf` (Bloc-notes admin) |
| `/var/log/postgresql/…` | `…\PostgreSQL\16\data\log\*.log` |
| Scripts `.sh` | `scripts/powershell/*.ps1` |
| `~/.pgpass` | `%APPDATA%\postgresql\pgpass.conf` |

Passe ensuite à `config-windows.md` pour les détails du module 02, puis déroule la formation (tout le SQL s'applique sans changement).
