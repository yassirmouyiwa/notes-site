# Module 09 — Sécurité des bases de données

> Ce module rassemble et approfondit le fil rouge sécurité des modules précédents. Il correspond à ton domaine d'études : à la fin, tu dois pouvoir auditer et durcir une instance PostgreSQL comme tu auditerais un système embarqué.

## Objectifs

- Cartographier les menaces sur un SGBD selon le modèle CIA (confidentialité, intégrité, disponibilité).
- Sécuriser le réseau et l'authentification (TLS, SCRAM, certificats).
- Comprendre et prévenir l'injection SQL en profondeur.
- Chiffrer les données au repos, en transit et au niveau colonne.
- Mettre en place un audit exploitable (`pgaudit`).
- Réaliser un audit de sécurité complet et un plan de durcissement.
- Gérer les vulnérabilités (CVE) et la conformité (loi 09-08, RGPD).

---

## 1. Modèle de menaces

### 1.1 CIA appliqué aux bases de données

| Propriété | Menace | Exemple |
|-----------|--------|---------|
| **Confidentialité** | Accès non autorisé, exfiltration | Vol de la base clients, lecture d'un dump non chiffré |
| **Intégrité** | Modification non autorisée | Altération de soldes, effacement de traces |
| **Disponibilité** | Déni de service, destruction | Rançongiciel, `DROP`, saturation de connexions |

### 1.2 Profils d'attaquant

| Attaquant | Voie d'accès typique |
|-----------|----------------------|
| Externe non authentifié | Port 5432 exposé, injection SQL via l'application web |
| Application compromise | Rôle applicatif trop puissant, secrets en clair |
| Utilisateur interne malveillant | Droits excessifs, absence d'audit |
| Administrateur système | Accès aux fichiers, aux sauvegardes, à la mémoire |
| Vol physique | Disque, sauvegarde, ordinateur portable |

### 1.3 Surface d'attaque (rappel du module 01, complété)

```
                      Internet / réseau
                             │
                    [1] Pare-feu, VPN
                             │
                    [2] listen_addresses, port
                             │
          ┌──────────────────┴───────────────────┐
          │           Application web             │
          │   [3] Injection SQL, secrets, IDOR    │
          └──────────────────┬───────────────────┘
                             │ TLS [4]
                    [5] pg_hba.conf (authn)
                             │
                    [6] Rôles & privilèges (authz)
                             │
              ┌──────────────┼──────────────┐
              │              │              │
      [7] Données       [8] WAL &       [9] Sauvegardes
      au repos          archives        (chiffrement, isolement)
      (chiffrement)
              │
      [10] Journaux & audit (détection)
```

Chaque numéro correspond à une section ci-dessous ou d'un module précédent.

---

## 2. Sécurité réseau

### 2.1 Ne pas exposer, en couches

1. **Pare-feu** : n'ouvrir le 5432 qu'aux adresses des serveurs applicatifs.
   ```bash
   sudo ufw allow from 10.0.1.0/24 to any port 5432 proto tcp
   sudo ufw deny 5432
   ```
2. **listen_addresses** : n'écouter que sur les interfaces nécessaires.
   ```ini
   listen_addresses = 'localhost,10.0.0.11'   # jamais '*' sans pare-feu strict
   ```
3. **Réseau privé / VPN** : idéalement, la base n'est joignable que depuis un réseau privé.
4. **pg_hba.conf** : dernière barrière logique (section 3).

Changer le port n'est **pas** une mesure de sécurité (au mieux, un peu moins de bruit dans les scans).

### 2.2 Détecter une exposition

```bash
sudo ss -tlnp | grep 5432          # sur quelles interfaces PostgreSQL écoute
```

Depuis un poste extérieur autorisé du lab : `nmap -p 5432 <ip>`. Sur Internet, des moteurs comme Shodan recensent en permanence les bases exposées.

---

## 3. Authentification

### 3.1 Hiérarchie des méthodes (rappel module 02)

À retenir : `scram-sha-256` au minimum, `cert` ou `gss` pour l'authentification forte, jamais `trust`, `password` ou `md5` en production.

### 3.2 Forcer SCRAM

```ini
password_encryption = scram-sha-256
```

Puis redéfinir les mots de passe encore en `md5`. Détection :

```sql
SELECT rolname FROM pg_authid
WHERE rolpassword IS NOT NULL AND rolpassword NOT LIKE 'SCRAM-SHA-256$%';
```

### 3.3 Politique de mots de passe

PostgreSQL n'impose pas nativement de complexité. Options :

- extension `passwordcheck` (refuse les mots de passe trivialement faibles) ;
- déléguer à un annuaire (LDAP, Kerberos) qui applique la politique de l'entreprise ;
- expiration avec `VALID UNTIL` ;
- ralentir la force brute avec `auth_delay` :
  ```ini
  shared_preload_libraries = 'auth_delay'
  auth_delay.milliseconds = 500
  ```

### 3.4 Authentification par certificat client

L'authentification la plus forte : le client prouve son identité avec un certificat signé par l'autorité de certification (CA) de confiance.

```
# pg_hba.conf
hostssl  banque  app_banque  10.0.1.0/24  cert  clientcert=verify-full
```

Avec `cert`, il n'y a pas de mot de passe : le CN (ou un SAN) du certificat doit correspondre au rôle (ou à une correspondance dans `pg_ident.conf`). `clientcert=verify-full` impose que le certificat client soit valide **et** que son identité corresponde. On génère les certificats clients au module suivant (section 5).

### 3.5 Limiter les dégâts d'un compte compromis

- `CONNECTION LIMIT` par rôle.
- `VALID UNTIL` pour les comptes temporaires.
- Comptes **nominatifs** (traçabilité), jamais partagés.
- Rôles applicatifs sans droit de connexion **directe** depuis Internet.
- Surveillance des connexions (`log_connections`, section 7).

---

## 4. Autorisation : le moindre privilège (rappel module 04)

Points de contrôle de sécurité :

- Aucune application connectée en **superutilisateur**.
- Objets possédés par un rôle `NOLOGIN`, application sans droit de **DDL**.
- `PUBLIC` neutralisé (`REVOKE … FROM PUBLIC`, `search_path` maîtrisé).
- Aucun rôle applicatif membre de `pg_read_server_files`, `pg_write_server_files`, `pg_execute_server_program`, ni `SUPERUSER`, `REPLICATION`, `BYPASSRLS`.
- RLS pour le cloisonnement par ligne ; colonnes sensibles protégées par des privilèges de colonne ou des vues.
- `SECURITY DEFINER` écrit selon les quatre règles (search_path figé, entrées validées, noms qualifiés, EXECUTE retiré à PUBLIC).

Le script `scripts/sql/audit_securite.sql` automatise la vérification de la plupart de ces points.

---

## 5. Chiffrement en transit (TLS)

### 5.1 Pourquoi

Sans TLS, tout le trafic (requêtes, résultats, et — selon la méthode d'authentification — des éléments d'authentification) circule en clair et peut être intercepté sur le réseau. SCRAM protège le mot de passe même sans TLS, mais **pas les données**.

### 5.2 Activer TLS côté serveur

```ini
ssl = on
ssl_cert_file = 'server.crt'
ssl_key_file = 'server.key'
ssl_ca_file = 'root.crt'            # pour vérifier les certificats clients
ssl_min_protocol_version = 'TLSv1.2'
ssl_ciphers = 'HIGH:!aNULL:!MD5'
```

La clé privée doit appartenir à `postgres` et être en mode `0600`, sinon le serveur refuse de démarrer.

### 5.3 Modes SSL côté client

C'est le **client** qui décide du niveau d'exigence, via `sslmode` :

| `sslmode` | Chiffré | Vérifie le certificat serveur | Vérifie le nom d'hôte | Protège contre |
|-----------|:-------:|:-----------------------------:|:---------------------:|----------------|
| `disable` | Non | — | — | rien |
| `allow` / `prefer` | Peut-être | Non | Non | écoute passive (parfois) |
| `require` | Oui | **Non** | Non | écoute passive, **pas** l'homme du milieu |
| `verify-ca` | Oui | Oui | Non | AC non fiable |
| `verify-full` | Oui | Oui | **Oui** | **homme du milieu** |

> ⚠️ **Le piège de `require`** : le trafic est chiffré, mais le client ne vérifie pas **à qui** il parle. Un attaquant en position d'homme du milieu présente son propre certificat, le client l'accepte, et l'attaquant déchiffre tout. **Toujours utiliser `verify-full`** en production ; côté serveur, on peut forcer `hostssl` dans `pg_hba.conf`, mais cela n'oblige pas le client à vérifier le certificat : la vérification est de sa responsabilité.

### 5.4 Vérifier

```sql
SELECT ssl, version, cipher, bits FROM pg_stat_ssl WHERE pid = pg_backend_pid();
SELECT datname, usename, ssl, client_addr
FROM pg_stat_ssl JOIN pg_stat_activity USING (pid);
```

### 5.5 TP express — chaîne TLS complète (lab)

```bash
$ sudo -i -u postgres
postgres$ cd ~ && mkdir -p tls && cd tls

# 1. Autorité de certification de test
postgres$ openssl req -new -x509 -days 3650 -nodes -out root.crt -keyout root.key \
            -subj "/CN=CA-Formation-DBA"

# 2. Certificat serveur signé par la CA (CN = nom d'hôte utilisé par les clients)
postgres$ openssl req -new -nodes -out server.csr -keyout server.key -subj "/CN=localhost"
postgres$ openssl x509 -req -in server.csr -CA root.crt -CAkey root.key \
            -CAcreateserial -out server.crt -days 365
postgres$ chmod 600 server.key

# 3. Certificat client pour le rôle app_banque (CN = nom du rôle)
postgres$ openssl req -new -nodes -out client.csr -keyout client.key -subj "/CN=app_banque"
postgres$ openssl x509 -req -in client.csr -CA root.crt -CAkey root.key \
            -CAcreateserial -out client.crt -days 365
postgres$ chmod 600 client.key
```

Configurer le serveur :

```bash
$ sudo tee /etc/postgresql/16/main/conf.d/40-tls.conf > /dev/null <<'EOF'
ssl = on
ssl_cert_file = '/var/lib/postgresql/tls/server.crt'
ssl_key_file  = '/var/lib/postgresql/tls/server.key'
ssl_ca_file   = '/var/lib/postgresql/tls/root.crt'
ssl_min_protocol_version = 'TLSv1.2'
EOF
$ sudo systemctl restart postgresql@16-main
```

Tester les trois niveaux depuis un compte utilisateur (copie `root.crt` et les fichiers client dans `~/.postgresql/` : `root.crt`, `postgresql.crt`, `postgresql.key`) :

```bash
# Chiffré mais vulnérable à l'homme du milieu
$ psql "host=localhost dbname=banque user=app_banque sslmode=require"

# Vérification complète du serveur
$ psql "host=localhost dbname=banque user=app_banque sslmode=verify-full sslrootcert=/chemin/root.crt"

# Authentification par certificat (après avoir ajouté la règle hostssl … cert)
$ psql "host=localhost dbname=banque user=app_banque sslmode=verify-full \
        sslcert=/chemin/client.crt sslkey=/chemin/client.key sslrootcert=/chemin/root.crt"
```

Vérifie chaque session avec `SELECT ssl, cipher FROM pg_stat_ssl WHERE pid = pg_backend_pid();`.

---

## 6. Injection SQL

C'est la vulnérabilité applicative n°1 touchant les bases de données (catégorie « Injection » de l'OWASP Top 10). Elle ne se corrige pas dans PostgreSQL mais dans le **code applicatif** ; le DBA doit la comprendre pour conseiller, auditer et limiter les dégâts.

### 6.1 Le mécanisme

Le code construit une requête en **concaténant** une entrée utilisateur :

```python
# VULNÉRABLE
requete = "SELECT * FROM bank.clients WHERE email = '" + saisie + "'"
```

Avec `saisie = x' OR '1'='1`, la requête devient :

```sql
SELECT * FROM bank.clients WHERE email = 'x' OR '1'='1'
```

La condition est toujours vraie : toute la table est renvoyée. Avec `saisie = x'; DROP TABLE bank.operations; --`, on tente une destruction. L'attaquant exploite le fait que **données et code se mélangent** dans la chaîne.

### 6.2 Types d'injection

| Type | Principe |
|------|----------|
| **In-band (union-based)** | `UNION SELECT` pour exfiltrer d'autres tables dans le résultat affiché |
| **Basée sur l'erreur** | Provoquer des messages d'erreur qui révèlent la structure ou des données |
| **Booléenne (aveugle)** | Déduire l'information vraie/faux d'après le comportement de la page |
| **Temporelle (aveugle)** | `pg_sleep()` pour déduire l'information du temps de réponse |
| **Empilée** (*stacked*) | `; DELETE …` : plusieurs instructions (bloqué par la plupart des pilotes, mais pas tous) |

### 6.3 La parade : requêtes paramétrées

La seule protection fiable sépare **le code** (la requête, fixe) et **les données** (les paramètres, jamais interprétés comme du SQL).

```python
# SÛR — psycopg (Python)
cur.execute("SELECT * FROM bank.clients WHERE email = %s", (saisie,))

# SÛR — Java JDBC
PreparedStatement ps = c.prepareStatement("SELECT * FROM bank.clients WHERE email = ?");
ps.setString(1, saisie);

# SÛR — PHP PDO
$stmt = $pdo->prepare("SELECT * FROM bank.clients WHERE email = :email");
$stmt->execute(['email' => $saisie]);
```

Le pilote envoie la requête et les paramètres **séparément** : la valeur `x' OR '1'='1` est traitée comme une chaîne littérale à comparer, jamais comme du SQL.

> ⚠️ Les `%s` de psycopg ne sont **pas** un formatage de chaîne Python : il ne faut jamais écrire `cur.execute("... = %s" % saisie)` ni `f"... = {saisie}"`. Le paramètre doit passer par le **deuxième argument** d'`execute`.

### 6.4 Cas particuliers

- **Identifiants dynamiques** (nom de table ou de colonne choisi à l'exécution) : ils ne peuvent pas être des paramètres. Il faut les valider contre une **liste blanche** ou utiliser une API d'échappement d'identifiants (`psycopg.sql.Identifier`, `quote_ident`).
- **SQL dynamique en PL/pgSQL** : utiliser `format()` avec `%I` (identifiant) et `%L` (littéral), ou `EXECUTE … USING` :
  ```sql
  EXECUTE format('SELECT * FROM %I WHERE id = $1', nom_table) USING p_id;
  ```
  Ne **jamais** concaténer avec `||` dans un `EXECUTE`.
- **Clause `IN`** : passer un tableau, `WHERE id = ANY($1)`, plutôt que de construire la liste.

### 6.5 Défense en profondeur côté base

Les requêtes paramétrées empêchent l'injection ; le reste **limite les dégâts** si une injection passe malgré tout :

- Rôle applicatif à **droits minimaux** (pas de `DROP`, pas d'accès aux tables sensibles inutiles).
- **RLS** pour cloisonner les données.
- **`statement_timeout`** contre les injections temporelles et les requêtes lourdes.
- **Vues** exposant uniquement les colonnes nécessaires.
- **Détection** : `pg_stat_statements` et les journaux révèlent des requêtes anormales (voir section 7).
- **WAF** (pare-feu applicatif) et validation des entrées côté application, en complément (jamais en remplacement).

### 6.6 TP — injection contrôlée dans le lab

> Exclusivement dans ton lab. Reproduire ceci sur un système tiers est un délit.

Simule une application vulnérable et sa version corrigée :

```bash
$ cat > /tmp/demo_injection.py <<'PY'
import psycopg2
conn = psycopg2.connect("host=127.0.0.1 dbname=banque user=app_banque password=CHANGE_MOI")
cur = conn.cursor()

def vulnerable(saisie):
    q = "SELECT id_client, nom, email FROM bank.clients WHERE email = '" + saisie + "'"
    print("  Requête envoyée :", q)
    cur.execute(q)
    return cur.fetchall()

def sur(saisie):
    cur.execute("SELECT id_client, nom, email FROM bank.clients WHERE email = %s", (saisie,))
    return cur.fetchall()

for label, fn in [("VULNÉRABLE", vulnerable), ("SÛR", sur)]:
    print(f"\n=== {label} ===")
    print(" normal :", len(fn("client42@exemple.ma")), "ligne(s)")
    try:
        print(" injection \"' OR '1'='1\" :", len(fn("x' OR '1'='1")), "ligne(s)")
    except Exception as e:
        conn.rollback(); print(" injection bloquée :", str(e).splitlines()[0])
PY
$ python3 /tmp/demo_injection.py   # adapte le mot de passe
```

Constat : la version vulnérable renvoie **100 000** lignes sur l'injection, la version sûre en renvoie **0** (aucun e-mail n'est littéralement `x' OR '1'='1`). Grâce au moindre privilège (module 04), même la version vulnérable ne peut pas faire de `DROP` : teste-le en essayant `x'; DROP TABLE bank.operations; --` et observe l'échec sur le privilège.

Efface le fichier de démonstration après le TP.

---

## 7. Journalisation de sécurité et audit

### 7.1 Journalisation native (rappel module 02)

Pour la sécurité, activer au minimum : `log_connections`, `log_disconnections`, `log_statement = 'ddl'`, un `log_line_prefix` complet (avec `%u`, `%d`, `%h`), `log_line_prefix` incluant l'IP.

Limite : `log_statement` est grossier (`none`/`ddl`/`mod`/`all`) et `all` est trop verbeux et dangereux (secrets en clair).

### 7.2 pgaudit

L'extension `pgaudit` produit un audit **structuré et ciblé** : qui a fait quoi, sur quel objet.

```ini
shared_preload_libraries = 'pg_stat_statements,pgaudit'
pgaudit.log = 'ddl, role, write'      # classes : read, write, ddl, role, function, misc
pgaudit.log_catalog = off
pgaudit.log_parameter = on            # journalise aussi les paramètres (attention aux données sensibles)
pgaudit.log_relation = on
```

Classes : `read` (SELECT), `write` (INSERT/UPDATE/DELETE), `ddl`, `role` (GRANT, CREATE ROLE…), `function`, `misc`.

Audit ciblé par objet (plutôt que tout journaliser) :

```sql
CREATE ROLE auditeur NOLOGIN;
ALTER TABLE bank.clients SET (pgaudit.roles = 'auditeur');   -- selon la configuration
```

Chaque entrée pgaudit indique la classe, la commande, le type et le nom d'objet, et — si activé — le texte et les paramètres. Ces journaux sont ensuite envoyés vers un **SIEM** (Wazuh, Elastic, Splunk) pour la corrélation et l'alerte.

### 7.3 Signaux à détecter

| Signal | Interprétation |
|--------|----------------|
| Échecs d'authentification répétés depuis une IP | Force brute |
| Connexion réussie d'un rôle depuis une IP inhabituelle | Compte compromis |
| `SELECT` massif sur `clients` par le rôle applicatif | Exfiltration / injection |
| Requêtes contenant `pg_sleep`, `UNION SELECT`, `information_schema` | Tentative d'injection |
| `CREATE ROLE`, `ALTER ROLE … SUPERUSER`, `GRANT` inattendus | Élévation de privilèges |
| Appel à `COPY … PROGRAM`, `pg_read_file` | Tentative d'accès système |
| Pic de trafic ou de connexions | Déni de service |

### 7.4 Traçabilité des modifications métier

Pour tracer **qui a changé quelle donnée** (au-delà des accès), on ajoute des colonnes d'audit (`modifie_par`, `modifie_le`) alimentées par des triggers, ou une table d'historique. C'est complémentaire de pgaudit, qui trace l'**action**, pas l'**état** avant/après.

---

## 8. Chiffrement au repos

### 8.1 Les trois niveaux

| Niveau | Protège contre | Mécanisme |
|--------|----------------|-----------|
| **Disque / volume** | Vol de disque physique, mise au rebut | LUKS (Linux), chiffrement du volume cloud, SGBD non concerné |
| **Cluster (TDE)** | Vol de fichiers, accès système partiel | Chiffrement transparent des fichiers de données |
| **Colonne / application** | DBA curieux, fuite d'un dump, moindre exposition | `pgcrypto`, chiffrement applicatif |

### 8.2 Chiffrement de volume (recommandé par défaut)

Le plus simple et le plus robuste contre le vol physique : chiffrer le système de fichiers (LUKS) ou le volume cloud. **Transparent** pour PostgreSQL, coût négligeable sur CPU moderne (AES-NI). Limite : une fois le volume monté, les données sont en clair pour tout processus qui y accède ; cela ne protège **pas** contre un accès logique ou un DBA malveillant.

### 8.3 TDE (Transparent Data Encryption)

Le chiffrement transparent au niveau du cluster **n'est pas** dans le PostgreSQL communautaire (à la date de rédaction). Il est proposé par certaines distributions (EDB, Percona, Cybertec) et discuté pour une future version. En attendant, le chiffrement de volume couvre le même besoin (vol de fichiers).

### 8.4 Chiffrement au niveau colonne avec `pgcrypto`

Pour protéger des colonnes précises même de l'administrateur de la base :

```sql
CREATE EXTENSION pgcrypto;

-- Hachage d'un mot de passe applicatif (jamais réversible)
INSERT INTO utilisateurs (login, mdp_hash)
VALUES ('sara', crypt('MotDePasse!', gen_salt('bf', 12)));   -- bcrypt
SELECT (mdp_hash = crypt('MotDePasse!', mdp_hash)) AS ok FROM utilisateurs WHERE login = 'sara';

-- Chiffrement réversible d'une donnée sensible (ex. numéro de carte)
-- La clé NE DOIT PAS être stockée dans la base ni écrite en clair dans les requêtes.
UPDATE bank.clients
   SET cin_chiffre = pgp_sym_encrypt(cin, :cle_passee_par_parametre)
 WHERE id_client = 1;
SELECT pgp_sym_decrypt(cin_chiffre, :cle) FROM bank.clients WHERE id_client = 1;
```

> ⚠️ **Le problème central est la gestion des clés.** Si la clé est dans la base, dans le code, ou passée en clair dans une requête (donc dans les journaux et `pg_stat_statements`), le chiffrement ne protège plus de grand-chose. Idéalement, la clé vit dans un **coffre** (HashiCorp Vault, KMS cloud, HSM) et n'est jamais persistée côté base. Le chiffrement au niveau colonne casse aussi l'indexation et les recherches sur ces colonnes : à réserver aux données rarement recherchées.

### 8.5 Masquage et pseudonymisation

Pour fournir des données réalistes à un environnement de test ou de développement sans exposer les vraies données personnelles :

- extension **`anon`** (PostgreSQL Anonymizer) : masquage dynamique, pseudonymisation, données factices ;
- ou un `pg_dump` filtré transformant les colonnes sensibles.

C'est une exigence de conformité : les données de production ne doivent pas se retrouver telles quelles en développement.

---

## 9. Gestion des vulnérabilités et durcissement système

### 9.1 CVE et mises à jour

- Suivre les annonces de sécurité PostgreSQL (chaque version mineure trimestrielle corrige des bugs et parfois des CVE).
- **Appliquer les versions mineures rapidement** : elles n'exigent qu'un remplacement de binaires et un redémarrage (module 02).
- Ne pas faire tourner de version **en fin de support** (5 ans après la sortie majeure) : plus aucun correctif de sécurité.
- Auditer aussi les **extensions** tierces, qui exécutent du code natif dans le processus serveur.

Vérifier sa version et son support :

```sql
SELECT version();
SELECT current_setting('server_version_num');   -- ex. 160004 = 16.4
```

### 9.2 Durcissement du système hôte

Le SGBD n'est jamais plus sûr que la machine qui l'héberge :

- serveur **dédié** à la base (aucun autre service exposé) ;
- compte système `postgres` sans shell interactif inutile, PGDATA en `0700` ;
- pas de secrets en clair dans les variables d'environnement ou l'historique shell ;
- `vm.overcommit_memory = 2` (éviter que l'OOM killer tue le postmaster) ;
- mises à jour de l'OS, SELinux/AppArmor actifs ;
- sauvegardes chiffrées et isolées (module 06) ;
- accès SSH restreint et journalisé.

### 9.3 Benchmark CIS

Le **CIS Benchmark for PostgreSQL** fournit une liste de contrôle détaillée et reconnue. La checklist de l'annexe C en reprend les points essentiels, adaptés à cette formation.

---

## 10. Conformité

### 10.1 Cadre marocain et européen

| Texte | Portée |
|-------|--------|
| **Loi 09-08** (Maroc) | Protection des données à caractère personnel ; autorité : la CNDP |
| **RGPD** (UE) | S'applique dès qu'on traite des données de résidents de l'UE |
| **PCI-DSS** | Obligatoire pour les données de cartes bancaires |
| **Loi 05-20** (Maroc) | Cybersécurité |

### 10.2 Traduction technique des principes

| Principe | Mise en œuvre PostgreSQL |
|----------|---------------------------|
| Minimisation | Ne stocker que le nécessaire ; privilèges de colonne |
| Limitation d'accès | Rôles, RLS, moindre privilège |
| Sécurité | TLS, chiffrement, durcissement, audit |
| Traçabilité | pgaudit, journaux, table d'historique |
| Droit à l'effacement | Suppression **et** purge des sauvegardes après rétention (module 06 : une donnée « supprimée » survit dans le WAL et les sauvegardes) |
| Notification de violation | Détection (SIEM) + procédure d'incident |
| Durée de conservation | Politique de rétention, partitionnement pour purger par lots (module 03) |

> 🔐 Rappel technique de conformité : une donnée personnelle supprimée logiquement (`DELETE`) reste physiquement présente dans les anciennes versions de lignes jusqu'au VACUUM (module 05), dans le WAL, dans les archives et dans toutes les sauvegardes jusqu'à leur expiration. L'effacement « complet » est un processus, pas une commande.

---

## TP 9 — Audit de sécurité complet

### Étape 1 : lancer l'audit automatisé

```bash
$ sudo -u postgres psql -d banque -f scripts/sql/audit_securite.sql
```

Le script vérifie : superutilisateurs, rôles à attributs dangereux, comptes sans mot de passe, hachages md5, privilèges de `PUBLIC`, membres des rôles serveur sensibles, présence de TLS, méthodes d'authentification faibles, extensions installées, tables sans propriétaire dédié. Analyse chaque avertissement.

### Étape 2 : corriger

Pour chaque point signalé, applique la correction et documente-la. Points typiques sur une installation fraîche : `PUBLIC` a des droits sur `public`, `md5` peut subsister, TLS n'est pas activé (fait à la section 5), audit absent.

### Étape 3 : mettre en place pgaudit

Installe et configure `pgaudit` (section 7.2), redémarre, puis génère des actions et retrouve-les dans le journal :

```sql
banque=# CREATE TABLE bank.test_audit (id int);   -- ddl
banque=# CREATE ROLE audit_temp NOLOGIN;          -- role
banque=# INSERT INTO bank.test_audit VALUES (1);  -- write
banque=# DROP TABLE bank.test_audit;
banque=# DROP ROLE audit_temp;
```

```bash
$ sudo grep AUDIT /var/log/postgresql/postgresql-16-main.log | tail
```

### Étape 4 : simuler une attaque et la détecter

Depuis le rôle `app_banque`, exécute une requête ressemblant à une injection réussie (exfiltration) :

```sql
-- avec app_banque
banque=> SELECT count(*) FROM bank.comptes;      -- lecture massive inhabituelle
```

Puis, en tant qu'analyste sécurité, retrouve cette activité dans `pg_stat_statements` et dans les journaux pgaudit. Rédige la règle de détection que tu configurerais dans un SIEM (par exemple : « rôle `app_banque` exécutant un agrégat sans clause `WHERE` sur `comptes` »).

### Étape 5 : rapport

Rédige un rapport d'audit d'une page : constats classés par criticité (critique / élevé / moyen / faible), recommandations, et plan de remédiation priorisé. C'est le livrable type d'un audit de sécurité de base de données.

---

## Exercices

1. Un développeur affirme : « On utilise `sslmode=require`, donc les connexions sont sécurisées. » Explique précisément ce contre quoi il n'est **pas** protégé et corrige la configuration.
2. Analyse ce code et indique s'il est vulnérable ; si oui, corrige-le et explique l'attaque possible :
   ```python
   filtre = request.args.get('tri', 'nom')
   cur.execute(f"SELECT * FROM bank.clients ORDER BY {filtre}")
   ```
3. Conçois une stratégie de chiffrement pour la colonne `cin` de `bank.clients` : niveau choisi, gestion de la clé, impact sur les recherches, procédure de rotation de clé.
4. Écris cinq règles de détection SIEM à partir des journaux PostgreSQL, avec pour chacune le signal, la source (log natif ou pgaudit) et le niveau d'alerte.
5. Réalise l'audit de sécurité de ton lab avec `audit_securite.sql`, corrige tous les points critiques et élevés, puis relance l'audit pour prouver la remédiation.

---

## Quiz

1. Que garantit SCRAM même en l'absence de TLS, et que ne garantit-il pas ?
2. Pourquoi `sslmode=require` est-il insuffisant, et que faut-il utiliser ?
3. Quelle est la seule protection fiable contre l'injection SQL ?
4. Pourquoi le moindre privilège limite-t-il les dégâts d'une injection ?
5. Comment gère-t-on du SQL dynamique sûr en PL/pgSQL ?
6. Quelle extension fournit un audit structuré et quelles sont ses classes principales ?
7. Quels sont les trois niveaux de chiffrement au repos et contre quoi protègent-ils ?
8. Quel est le problème central du chiffrement au niveau colonne ?
9. Pourquoi appliquer rapidement les versions mineures de PostgreSQL ?
10. Pourquoi une donnée personnelle « supprimée » n'est-elle pas immédiatement effacée ?

*Corrigés : [annexe D](annexes/D-corriges.md#module-09).*

---

## À retenir

- Défense en couches : pare-feu → `listen_addresses` → TLS `verify-full` → SCRAM/certificat → moindre privilège → chiffrement → audit.
- L'injection SQL se corrige par des **requêtes paramétrées** ; le moindre privilège et RLS limitent les dégâts.
- `verify-full` obligatoire ; `require` ne protège pas de l'homme du milieu.
- Chiffrement de volume par défaut ; chiffrement colonne pour le plus sensible, avec gestion des clés hors base.
- pgaudit + SIEM pour détecter ; versions à jour ; CIS Benchmark pour durcir ; conformité loi 09-08 / RGPD.
