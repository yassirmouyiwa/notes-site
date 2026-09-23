# Module 04 — Utilisateurs, rôles et privilèges

## Objectifs

- Créer et gérer des rôles, leurs attributs et leurs appartenances.
- Accorder et retirer des privilèges à chaque niveau (base, schéma, objet, colonne).
- Neutraliser les privilèges par défaut accordés à `PUBLIC`.
- Utiliser les privilèges par défaut (`ALTER DEFAULT PRIVILEGES`) et les rôles prédéfinis.
- Mettre en œuvre la sécurité au niveau des lignes (RLS).
- Écrire des fonctions `SECURITY DEFINER` sûres.
- Concevoir un modèle de droits complet fondé sur le moindre privilège.

---

## 1. Les rôles

Dans PostgreSQL, **utilisateurs et groupes sont une seule notion : le rôle**. Un « utilisateur » est simplement un rôle qui a l'attribut `LOGIN`. Un « groupe » est un rôle dont d'autres rôles sont membres.

Les rôles sont **globaux au cluster** : ils existent pour toutes les bases.

```sql
CREATE ROLE alice LOGIN;                 -- un utilisateur
CREATE USER bob;                         -- équivalent à CREATE ROLE bob LOGIN
CREATE ROLE analystes NOLOGIN;           -- un groupe
GRANT analystes TO alice;                -- alice devient membre du groupe
```

### 1.1 Attributs d'un rôle

| Attribut | Effet |
|----------|-------|
| `LOGIN` / `NOLOGIN` | Peut ouvrir une session |
| `SUPERUSER` | **Contourne toutes les vérifications de droits.** Peut lire les fichiers du serveur, exécuter des programmes système, charger du code natif |
| `CREATEDB` | Peut créer des bases |
| `CREATEROLE` | Peut créer, modifier et supprimer des rôles (restreint depuis PG 16, voir plus bas) |
| `REPLICATION` | Peut ouvrir des connexions de réplication et faire des sauvegardes physiques |
| `BYPASSRLS` | Ignore les politiques de sécurité au niveau des lignes |
| `INHERIT` / `NOINHERIT` | Hérite automatiquement des privilèges des rôles dont il est membre |
| `CONNECTION LIMIT n` | Nombre maximal de sessions simultanées |
| `PASSWORD '...'` | Mot de passe (haché selon `password_encryption`) |
| `VALID UNTIL 'date'` | Date d'expiration du **mot de passe** (pas du rôle) |

```sql
CREATE ROLE app_banque LOGIN CONNECTION LIMIT 50;
ALTER ROLE app_banque VALID UNTIL '2027-01-01';
ALTER ROLE alice NOLOGIN;              -- désactiver un compte sans le supprimer
```

### 1.2 Gérer les mots de passe proprement

```sql
postgres=# \password alice
```

La méta-commande `\password` calcule le hachage SCRAM **côté client** et n'envoie que le hachage : le mot de passe en clair n'apparaît ni dans l'historique psql, ni dans les journaux du serveur, ni dans `pg_stat_activity`. C'est la méthode à utiliser.

À l'inverse, `CREATE ROLE alice PASSWORD 'Secret'` laisse le mot de passe dans `~/.psql_history` et potentiellement dans les journaux.

Vérifier l'algorithme de hachage utilisé :

```sql
SHOW password_encryption;                        -- doit être scram-sha-256
SELECT rolname, left(rolpassword, 14) FROM pg_authid WHERE rolpassword IS NOT NULL;
```

Les hachages commencent par `SCRAM-SHA-256$` ou par `md5` (à migrer : il suffit de redéfinir le mot de passe une fois `password_encryption = scram-sha-256`).

### 1.3 Héritage, `SET ROLE` et options d'appartenance

Un membre d'un rôle peut :

- **hériter** de ses privilèges automatiquement (si `INHERIT`) ;
- **endosser** ce rôle avec `SET ROLE nom_du_role` (pour créer des objets qui lui appartiendront, par exemple) ;
- **administrer** l'appartenance (ajouter d'autres membres) s'il a reçu `WITH ADMIN OPTION`.

Depuis PostgreSQL 16, ces trois capacités sont réglables **individuellement** pour chaque appartenance :

```sql
GRANT banque_owner TO dba_alice WITH INHERIT FALSE, SET TRUE;
-- dba_alice n'a pas les droits du propriétaire en permanence,
-- mais peut faire SET ROLE banque_owner quand elle en a besoin.
```

C'est l'équivalent de `sudo` : on travaille avec peu de droits et on les élève explicitement.

```sql
SELECT current_user, session_user;   -- rôle courant / rôle de connexion
SET ROLE banque_owner;
RESET ROLE;
```

### 1.4 `CREATEROLE` depuis PostgreSQL 16

Avant PG 16, un rôle `CREATEROLE` pouvait s'accorder presque n'importe quel rôle, ce qui en faisait un quasi-superutilisateur. Depuis PG 16, il ne peut gérer que les rôles sur lesquels il a `ADMIN OPTION` (en pratique, ceux qu'il a créés). C'est désormais un vrai rôle de **délégation de l'administration des comptes**.

### 1.5 Consulter les rôles

```sql
\du+
SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolcanlogin,
       rolreplication, rolbypassrls, rolconnlimit, rolvaliduntil
FROM pg_roles ORDER BY rolname;

-- Appartenances
SELECT r.rolname AS membre, g.rolname AS groupe,
       m.admin_option, m.inherit_option, m.set_option     -- colonnes PG 16+
FROM pg_auth_members m
JOIN pg_roles r ON r.oid = m.member
JOIN pg_roles g ON g.oid = m.roleid
ORDER BY 1, 2;
```

---

## 2. Propriété des objets

Chaque objet (base, schéma, table, fonction…) a un **propriétaire**, par défaut le rôle qui l'a créé. Le propriétaire :

- a **tous les privilèges** sur l'objet (qu'il peut se retirer, puis se redonner) ;
- est le seul (avec les superutilisateurs) à pouvoir le **modifier** (`ALTER`) ou le **supprimer** (`DROP`) ;
- peut accorder des privilèges à d'autres.

```sql
ALTER TABLE bank.clients OWNER TO banque_owner;
ALTER SCHEMA bank OWNER TO banque_owner;
```

**Bonne pratique** : les objets applicatifs appartiennent à un rôle **`NOLOGIN`** dédié (`banque_owner`). Personne ne se connecte directement avec ce rôle ; les migrations de schéma se font via `SET ROLE`. Ainsi, l'application qui tourne au quotidien **ne peut pas** faire de `DROP TABLE`.

Supprimer un rôle qui possède des objets :

```sql
REASSIGN OWNED BY ancien_employe TO banque_owner;   -- dans CHAQUE base concernée
DROP OWNED BY ancien_employe;                       -- retire aussi ses privilèges, dans chaque base
DROP ROLE ancien_employe;
```

---

## 3. Les privilèges

### 3.1 Privilèges par type d'objet

| Objet | Privilèges |
|-------|------------|
| Base | `CONNECT`, `CREATE` (schémas), `TEMPORARY` |
| Schéma | `USAGE` (accéder aux objets qu'il contient), `CREATE` (y créer des objets) |
| Table / vue | `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `REFERENCES`, `TRIGGER`, `MAINTAIN` (PG 17+ : VACUUM, ANALYZE, REINDEX…) |
| Colonne | `SELECT`, `INSERT`, `UPDATE`, `REFERENCES` |
| Séquence | `USAGE` (`nextval`, `currval`), `SELECT` (`currval`), `UPDATE` (`setval`) |
| Fonction / procédure | `EXECUTE` |
| Tablespace | `CREATE` |
| Type, domaine, langage | `USAGE` |

### 3.2 La chaîne d'accès : les trois portes

Pour lire `bank.clients`, un rôle doit franchir **trois niveaux** :

1. `CONNECT` sur la base `banque` (et une ligne adaptée dans `pg_hba.conf`) ;
2. `USAGE` sur le schéma `bank` ;
3. `SELECT` sur la table `bank.clients`.

Oublier l'un de ces niveaux est l'erreur la plus fréquente : « j'ai donné `SELECT` sur la table mais ça ne marche pas » signifie presque toujours qu'il manque `USAGE` sur le schéma.

### 3.3 GRANT et REVOKE

```sql
GRANT CONNECT ON DATABASE banque TO r_lecture;
GRANT USAGE ON SCHEMA bank TO r_lecture;
GRANT SELECT ON ALL TABLES IN SCHEMA bank TO r_lecture;     -- tables EXISTANTES seulement

GRANT SELECT, INSERT, UPDATE, DELETE ON bank.operations TO r_ecriture;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA bank TO r_ecriture;

-- Privilège sur des colonnes
GRANT SELECT (id_client, nom, prenom, id_agence) ON bank.clients TO r_support;
GRANT UPDATE (telephone, email) ON bank.clients TO r_support;

-- Permettre au bénéficiaire de redistribuer le privilège
GRANT SELECT ON bank.agences TO chef_equipe WITH GRANT OPTION;

REVOKE DELETE ON bank.operations FROM r_ecriture;
REVOKE ALL ON bank.clients FROM PUBLIC;
```

> ⚠️ `GRANT … ON ALL TABLES IN SCHEMA` ne concerne que les tables **existant au moment de la commande**. Les tables créées ensuite ne sont pas couvertes : c'est le rôle de `ALTER DEFAULT PRIVILEGES` (section 4).

### 3.4 Consulter les privilèges

```sql
\dp bank.*          -- privilèges des tables
\dn+                -- privilèges des schémas
\l                  -- privilèges des bases
\ddp                -- privilèges par défaut
```

Lecture d'une ACL (liste de contrôle d'accès) affichée par `\dp` :

```
r_lecture=r/banque_owner
│         │ └── accordé par banque_owner
│         └──── privilèges : r=SELECT
└──────────────── bénéficiaire (vide = PUBLIC)
```

Codes : `r` SELECT, `a` INSERT, `w` UPDATE, `d` DELETE, `D` TRUNCATE, `x` REFERENCES, `t` TRIGGER, `m` MAINTAIN, `X` EXECUTE, `U` USAGE, `C` CREATE, `c` CONNECT, `T` TEMPORARY, `*` = avec GRANT OPTION.

Fonctions de test :

```sql
SELECT has_table_privilege('alice', 'bank.clients', 'SELECT');
SELECT has_schema_privilege('alice', 'bank', 'USAGE');
SELECT has_database_privilege('alice', 'banque', 'CONNECT');
SELECT has_column_privilege('alice', 'bank.clients', 'cin', 'SELECT');
SELECT has_function_privilege('public', 'bank.virement(bigint,bigint,numeric)', 'EXECUTE');
```

---

## 4. PUBLIC et les privilèges accordés par défaut

### 4.1 Le pseudo-rôle PUBLIC

`PUBLIC` désigne **tous les rôles, présents et futurs**. PostgreSQL accorde automatiquement à `PUBLIC` :

| Objet | Privilèges accordés à PUBLIC à la création |
|-------|--------------------------------------------|
| Base | `CONNECT`, `TEMPORARY` |
| Fonction / procédure | **`EXECUTE`** |
| Langage, type, domaine | `USAGE` |
| Schéma `public` | `USAGE` (et `CREATE` **avant** PG 15) |

Conséquences :

- Tout rôle `LOGIN` peut se connecter à **toutes les bases** (si `pg_hba.conf` le permet) et y lister le catalogue.
- Toute nouvelle fonction est exécutable par tous.
- Avant PG 15, tout utilisateur pouvait créer des objets dans `public` (piège du `search_path`).

### 4.2 Durcissement de base

À appliquer dans chaque base applicative :

```sql
REVOKE ALL ON DATABASE banque FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
-- puis accorder explicitement CONNECT aux rôles qui en ont besoin
```

Et pour éviter que les nouvelles fonctions soient exécutables par tous :

```sql
ALTER DEFAULT PRIVILEGES FOR ROLE banque_owner REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
```

### 4.3 ALTER DEFAULT PRIVILEGES

Définit les privilèges qui seront **automatiquement** accordés sur les objets **futurs** créés par un rôle donné.

```sql
ALTER DEFAULT PRIVILEGES FOR ROLE banque_owner IN SCHEMA bank
    GRANT SELECT ON TABLES TO r_lecture;

ALTER DEFAULT PRIVILEGES FOR ROLE banque_owner IN SCHEMA bank
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO r_ecriture;

ALTER DEFAULT PRIVILEGES FOR ROLE banque_owner IN SCHEMA bank
    GRANT USAGE ON SEQUENCES TO r_ecriture;
```

> ⚠️ Le `FOR ROLE` est essentiel : ces règles ne s'appliquent qu'aux objets créés **par ce rôle**. Si un DBA crée une table en étant connecté en `postgres` au lieu de faire `SET ROLE banque_owner`, les privilèges par défaut ne s'appliquent pas et la table appartient à `postgres`.

---

## 5. Les rôles prédéfinis

PostgreSQL fournit des rôles `NOLOGIN` prêts à l'emploi, qui évitent de donner `SUPERUSER` pour des tâches précises.

| Rôle | Capacité | Depuis |
|------|----------|--------|
| `pg_read_all_data` | `SELECT` sur toutes les tables, vues et séquences de toutes les bases | 14 |
| `pg_write_all_data` | `INSERT`, `UPDATE`, `DELETE` partout | 14 |
| `pg_monitor` | Lire toutes les vues de supervision (regroupe `pg_read_all_settings`, `pg_read_all_stats`, `pg_stat_scan_tables`) | 10 |
| `pg_signal_backend` | Annuler / terminer les sessions des autres rôles (sauf superutilisateurs) | 9.6 |
| `pg_checkpoint` | Lancer `CHECKPOINT` | 15 |
| `pg_maintain` | `VACUUM`, `ANALYZE`, `REINDEX`, `CLUSTER`, `REFRESH MATERIALIZED VIEW` partout | 17 |
| `pg_use_reserved_connections` | Utiliser les connexions réservées (`reserved_connections`) | 16 |
| `pg_create_subscription` | Créer des souscriptions de réplication logique | 16 |
| `pg_database_owner` | Membre implicite : le propriétaire de la base courante | 14 |
| `pg_read_server_files` | ⚠️ Lire **n'importe quel fichier** accessible au compte système `postgres` | 11 |
| `pg_write_server_files` | ⚠️ Écrire des fichiers sur le serveur | 11 |
| `pg_execute_server_program` | ⚠️ **Exécuter des programmes** sur le serveur (`COPY … PROGRAM`) | 11 |

> 🔐 **Angle sécurité**
> Les trois derniers rôles équivalent pratiquement à un accès au compte système `postgres` : lecture de `pg_hba.conf`, des clés TLS, des fichiers de données (et donc des hachages de mots de passe), voire exécution de commandes. Les accorder revient presque à accorder `SUPERUSER`. Un audit doit vérifier qu'**aucun** rôle applicatif n'en est membre.

Exemple : un compte de supervision sans superutilisateur :

```sql
CREATE ROLE supervision LOGIN CONNECTION LIMIT 5;
GRANT pg_monitor TO supervision;
```

---

## 6. Sécurité au niveau des lignes (RLS)

### 6.1 Principe

Les privilèges classiques portent sur des **tables entières** ou des **colonnes**. La **Row Level Security** filtre les **lignes** qu'un rôle peut voir ou modifier, selon une condition.

Cas d'usage : un conseiller bancaire ne voit que les clients de son agence ; une application multi-clients (*multi-tenant*) isole les données de chaque client.

### 6.2 Mise en œuvre

```sql
-- 1. Activer RLS sur la table
ALTER TABLE bank.clients ENABLE ROW LEVEL SECURITY;

-- 2. Définir des politiques
CREATE POLICY p_conseiller_agence ON bank.clients
    FOR SELECT
    TO r_conseiller
    USING (id_agence = (SELECT id_agence FROM bank.conseillers WHERE login = current_user));
```

| Clause | Rôle |
|--------|------|
| `FOR SELECT \| INSERT \| UPDATE \| DELETE \| ALL` | Commandes concernées |
| `TO rôle` | Rôles concernés (défaut : `PUBLIC`) |
| `USING (condition)` | Lignes **existantes** visibles / modifiables |
| `WITH CHECK (condition)` | Lignes **nouvelles ou modifiées** acceptées (INSERT, UPDATE) |
| `AS PERMISSIVE` (défaut) / `AS RESTRICTIVE` | Les politiques permissives sont combinées par **OU**, les restrictives par **ET** |

### 6.3 Règles à connaître

- Si RLS est activé et qu'**aucune politique** ne s'applique à un rôle, il ne voit **aucune ligne** (refus par défaut).
- Le **propriétaire** de la table n'est **pas** soumis aux politiques, sauf avec `ALTER TABLE … FORCE ROW LEVEL SECURITY`.
- Les **superutilisateurs** et les rôles `BYPASSRLS` ignorent toujours RLS.
- `pg_dump` échoue par défaut sur une table protégée par RLS si le rôle n'a pas `BYPASSRLS`, pour éviter une sauvegarde silencieusement incomplète.
- Les contraintes d'unicité et les clés étrangères sont vérifiées **sur toutes les lignes** : un utilisateur peut déduire l'existence d'une ligne invisible via une erreur de doublon (canal auxiliaire).

### 6.4 Multi-tenant avec une variable de session

```sql
CREATE POLICY p_tenant ON commandes
    USING (tenant_id = current_setting('app.tenant_id')::int)
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::int);

-- L'application, à chaque transaction :
BEGIN;
SET LOCAL app.tenant_id = '42';
SELECT * FROM commandes;   -- uniquement le tenant 42
COMMIT;
```

> ⚠️ Cette technique suppose que l'application est de confiance : un utilisateur qui peut exécuter du SQL arbitraire peut changer `app.tenant_id`. RLS protège contre les **erreurs** de l'application (requête oubliant le filtre), pas contre une **injection SQL** avec un rôle qui peut modifier la variable.

---

## 7. Fonctions SECURITY DEFINER

### 7.1 Principe

Par défaut, une fonction s'exécute avec les droits de **l'appelant** (`SECURITY INVOKER`). Avec `SECURITY DEFINER`, elle s'exécute avec les droits de son **propriétaire**, comme un programme `setuid` sous Linux.

Usage : donner accès à une **opération contrôlée** sans donner accès aux tables. L'application peut appeler `bank.virement()` sans avoir le droit de faire `UPDATE` directement sur `bank.comptes`.

### 7.2 Le piège du `search_path`

Si la fonction utilise des noms non qualifiés et que l'appelant contrôle son `search_path`, il peut placer devant un schéma à lui contenant une fonction ou un opérateur homonyme (par exemple une fausse fonction `now()` ou un opérateur `=`), qui sera exécuté **avec les droits du propriétaire**. C'est une élévation de privilèges.

### 7.3 Modèle sûr

```sql
CREATE FUNCTION bank.virement(p_source bigint, p_dest bigint, p_montant numeric)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp          -- 1. search_path figé, pg_temp EN DERNIER
AS $$
BEGIN
    IF p_montant <= 0 THEN                      -- 2. validation des entrées
        RAISE EXCEPTION 'Montant invalide : %', p_montant;
    END IF;

    UPDATE bank.comptes                         -- 3. noms entièrement qualifiés
       SET solde = solde - p_montant
     WHERE id_compte = p_source AND statut = 'ACTIF' AND solde >= p_montant;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Compte source % inexistant, inactif ou solde insuffisant', p_source;
    END IF;

    UPDATE bank.comptes
       SET solde = solde + p_montant
     WHERE id_compte = p_dest AND statut = 'ACTIF';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Compte destination % inexistant ou inactif', p_dest;
    END IF;

    INSERT INTO bank.operations (id_compte, type_op, montant, date_op, libelle)
    VALUES (p_source, 'VIREMENT_OUT', p_montant, now(), 'Virement vers ' || p_dest),
           (p_dest,   'VIREMENT_IN',  p_montant, now(), 'Virement de '   || p_source);
END;
$$;

ALTER FUNCTION bank.virement(bigint, bigint, numeric) OWNER TO banque_owner;
REVOKE EXECUTE ON FUNCTION bank.virement(bigint, bigint, numeric) FROM PUBLIC;  -- 4.
GRANT  EXECUTE ON FUNCTION bank.virement(bigint, bigint, numeric) TO r_app;
```

Les quatre règles :

1. **Figer le `search_path`** dans la définition de la fonction, avec `pg_temp` en dernier (sinon le schéma temporaire de l'appelant est cherché en premier).
2. **Valider les entrées**.
3. **Qualifier tous les noms** (`bank.comptes`, et au besoin `pg_catalog.now()`).
4. **Retirer `EXECUTE` à `PUBLIC`** et l'accorder uniquement aux rôles prévus.

Et bien sûr : le propriétaire ne doit **pas** être un superutilisateur, sauf nécessité absolue.

### 7.4 Vues et `security_invoker`

Une vue s'exécute par défaut avec les droits de son **propriétaire** (comme `SECURITY DEFINER`), ce qui permet d'exposer un sous-ensemble de colonnes. Depuis PG 15, `WITH (security_invoker = true)` fait appliquer les droits et les politiques RLS de **l'appelant**.

```sql
CREATE VIEW bank.v_clients_publics AS
    SELECT id_client, nom, prenom, id_agence FROM bank.clients;
GRANT SELECT ON bank.v_clients_publics TO r_support;
```

Pour une vue utilisée comme filtre de sécurité, ajouter `WITH (security_barrier)` empêche qu'une fonction malveillante fournie dans la requête s'exécute sur des lignes normalement filtrées.

---

## 8. Concevoir un modèle de droits

### 8.1 Principes

1. **Moindre privilège** : chaque rôle a exactement ce dont il a besoin, rien de plus.
2. **Séparation des rôles** : propriétaire des objets ≠ application ≠ lecture ≠ administration.
3. **Droits sur des groupes, pas sur des personnes** : on accorde aux rôles `NOLOGIN`, on rend les personnes membres.
4. **Aucune application en superutilisateur.** Jamais.
5. **Comptes nominatifs** pour les humains (traçabilité), pas de compte partagé.
6. **Revue périodique** des droits et suppression des comptes inutilisés.

### 8.2 Modèle type

```
                  ┌───────────────────┐
                  │  banque_owner     │  NOLOGIN — possède schéma et objets
                  └─────────▲─────────┘
                            │ SET ROLE (migrations)
                  ┌─────────┴─────────┐
                  │ dba_alice (LOGIN) │  INHERIT FALSE, SET TRUE
                  └───────────────────┘

┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ r_lecture    │   │ r_ecriture   │   │ r_app        │   │ r_conseiller │  NOLOGIN
│ SELECT       │   │ SELECT, DML  │   │ EXECUTE      │   │ SELECT + RLS │
└──────▲───────┘   └──────▲───────┘   │ fonctions    │   └──────▲───────┘
       │                  │           └──────▲───────┘          │
  analyste_youssef   batch_import        app_banque        conseiller_tetouan
     (LOGIN)            (LOGIN)            (LOGIN)              (LOGIN)
```

---

## TP 4 — Construire le modèle de droits de la base `banque`

### Étape 0 : état initial

```sql
banque=# \dn+
banque=# \dp bank.*
banque=# \l banque
```

Note que tout appartient à `postgres` et que `PUBLIC` a `CONNECT` et `TEMPORARY` sur la base.

### Étape 1 : rôle propriétaire et transfert de propriété

```sql
banque=# CREATE ROLE banque_owner NOLOGIN;
banque=# ALTER SCHEMA bank OWNER TO banque_owner;
banque=# ALTER TABLE bank.agences    OWNER TO banque_owner;
banque=# ALTER TABLE bank.clients    OWNER TO banque_owner;
banque=# ALTER TABLE bank.comptes    OWNER TO banque_owner;
banque=# ALTER TABLE bank.operations OWNER TO banque_owner;
banque=# ALTER TABLE bank.gardes     OWNER TO banque_owner;
banque=# \dp bank.*
```

Les séquences des colonnes d'identité changent de propriétaire avec leur table.

### Étape 2 : fermer les accès par défaut

```sql
banque=# REVOKE ALL ON DATABASE banque FROM PUBLIC;
banque=# REVOKE ALL ON SCHEMA public FROM PUBLIC;
banque=# ALTER DEFAULT PRIVILEGES FOR ROLE banque_owner REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
```

### Étape 3 : rôles de groupe

```sql
banque=# CREATE ROLE r_lecture    NOLOGIN;
banque=# CREATE ROLE r_ecriture   NOLOGIN;
banque=# CREATE ROLE r_app        NOLOGIN;
banque=# CREATE ROLE r_support    NOLOGIN;
banque=# CREATE ROLE r_conseiller NOLOGIN;

banque=# GRANT CONNECT ON DATABASE banque TO r_lecture, r_ecriture, r_app, r_support, r_conseiller;
banque=# GRANT USAGE ON SCHEMA bank TO r_lecture, r_ecriture, r_app, r_support, r_conseiller;

-- Lecture seule
banque=# GRANT SELECT ON ALL TABLES IN SCHEMA bank TO r_lecture;
banque=# ALTER DEFAULT PRIVILEGES FOR ROLE banque_owner IN SCHEMA bank GRANT SELECT ON TABLES TO r_lecture;

-- Écriture (traitements par lots)
banque=# GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA bank TO r_ecriture;
banque=# GRANT USAGE ON ALL SEQUENCES IN SCHEMA bank TO r_ecriture;
banque=# ALTER DEFAULT PRIVILEGES FOR ROLE banque_owner IN SCHEMA bank
         GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO r_ecriture;
banque=# ALTER DEFAULT PRIVILEGES FOR ROLE banque_owner IN SCHEMA bank
         GRANT USAGE ON SEQUENCES TO r_ecriture;

-- Support : colonnes non sensibles uniquement, modification du contact
banque=# GRANT SELECT (id_client, nom, prenom, email, telephone, id_agence) ON bank.clients TO r_support;
banque=# GRANT UPDATE (email, telephone) ON bank.clients TO r_support;

-- Application : lecture des comptes + fonction de virement uniquement
banque=# GRANT SELECT ON bank.comptes, bank.agences TO r_app;
```

### Étape 4 : utilisateurs

```sql
banque=# CREATE ROLE analyste_youssef LOGIN IN ROLE r_lecture;
banque=# CREATE ROLE agent_salma      LOGIN IN ROLE r_support;
banque=# CREATE ROLE app_banque       LOGIN IN ROLE r_app CONNECTION LIMIT 20;
banque=# CREATE ROLE dba_alice        LOGIN;
banque=# GRANT CONNECT ON DATABASE banque TO dba_alice;   -- PUBLIC n'a plus CONNECT
banque=# GRANT banque_owner TO dba_alice WITH INHERIT FALSE, SET TRUE;
banque=# \password analyste_youssef
banque=# \password agent_salma
banque=# \password app_banque
banque=# \password dba_alice
```

(Sur PostgreSQL 15 ou antérieur, remplace la ligne `GRANT … WITH INHERIT FALSE, SET TRUE` par `GRANT banque_owner TO dba_alice;` et crée `dba_alice` avec `NOINHERIT`.)

### Étape 5 : fonction de virement

Crée la fonction `bank.virement` de la section 7.3, en l'exécutant **en tant que** `banque_owner` pour qu'elle lui appartienne et que les privilèges par défaut s'appliquent :

```sql
banque=# SET ROLE banque_owner;
banque=> -- coller ici le CREATE FUNCTION de la section 7.3 (sans la ligne ALTER FUNCTION … OWNER)
banque=> RESET ROLE;
banque=# GRANT EXECUTE ON FUNCTION bank.virement(bigint, bigint, numeric) TO r_app;
banque=# \df+ bank.virement
```

### Étape 6 : tests de chaque rôle

Connecte-toi successivement avec chaque rôle (`psql -h 127.0.0.1 -U <rôle> -d banque`) et vérifie :

| Rôle | Commande | Résultat attendu |
|------|----------|------------------|
| `analyste_youssef` | `SELECT count(*) FROM bank.operations;` | OK |
| `analyste_youssef` | `DELETE FROM bank.operations WHERE id_operation = 1;` | `permission denied` |
| `agent_salma` | `SELECT nom, telephone FROM bank.clients LIMIT 5;` | OK |
| `agent_salma` | `SELECT cin FROM bank.clients LIMIT 5;` | `permission denied` |
| `agent_salma` | `SELECT * FROM bank.clients LIMIT 5;` | `permission denied` (le `*` inclut `cin`) |
| `agent_salma` | `UPDATE bank.clients SET telephone = '0600000000' WHERE id_client = 1;` | OK |
| `app_banque` | `SELECT id_compte, solde FROM bank.comptes WHERE id_compte IN (1, 2);` | OK |
| `app_banque` | `UPDATE bank.comptes SET solde = 1000000 WHERE id_compte = 1;` | `permission denied` |
| `app_banque` | `SELECT bank.virement(1, 2, 100);` | OK (si le compte 1 a un solde suffisant et est actif) |
| `app_banque` | `SELECT bank.virement(1, 2, -50);` | Exception « Montant invalide » |
| `app_banque` | `DROP TABLE bank.operations;` | `must be owner` |
| `dba_alice` | `CREATE TABLE bank.t (id int);` | `permission denied` (pas d'héritage) |
| `dba_alice` | `SET ROLE banque_owner; CREATE TABLE bank.t (id int); RESET ROLE;` | OK |
| `analyste_youssef` | `SELECT * FROM bank.t;` | OK grâce aux privilèges par défaut |

Termine en supprimant `bank.t` (en tant que `banque_owner`).

### Étape 7 : RLS pour les conseillers

```sql
banque=# SET ROLE banque_owner;
banque=> CREATE TABLE bank.conseillers (
            login      text PRIMARY KEY,
            id_agence  smallint NOT NULL REFERENCES bank.agences
         );
banque=> RESET ROLE;
banque=# INSERT INTO bank.conseillers VALUES ('conseiller_tetouan', 1), ('conseiller_rabat', 3);
banque=# GRANT SELECT ON bank.conseillers TO r_conseiller;
banque=# GRANT SELECT ON bank.clients TO r_conseiller;

banque=# ALTER TABLE bank.clients ENABLE ROW LEVEL SECURITY;
banque=# CREATE POLICY p_conseiller_agence ON bank.clients
            FOR SELECT TO r_conseiller
            USING (id_agence = (SELECT c.id_agence FROM bank.conseillers c WHERE c.login = current_user));

banque=# CREATE ROLE conseiller_tetouan LOGIN IN ROLE r_conseiller;
banque=# CREATE ROLE conseiller_rabat   LOGIN IN ROLE r_conseiller;
banque=# \password conseiller_tetouan
banque=# \password conseiller_rabat
```

Teste :

```sql
-- connecté en conseiller_tetouan
banque=> SELECT id_agence, count(*) FROM bank.clients GROUP BY id_agence;
```

Un seul groupe (agence 1) doit apparaître. Même test avec `conseiller_rabat` (agence 3).

> ⚠️ **Effet de bord à constater** : RLS étant activé sur `bank.clients`, les rôles qui n'ont **aucune** politique ne voient plus aucune ligne. Connecte-toi en `analyste_youssef` et exécute `SELECT count(*) FROM bank.clients;` : le résultat est 0. Corrige en ajoutant une politique pour les autres rôles :

```sql
banque=# CREATE POLICY p_acces_complet ON bank.clients
            FOR SELECT TO r_lecture, r_support, r_ecriture
            USING (true);
banque=# CREATE POLICY p_modif_support ON bank.clients
            FOR UPDATE TO r_support
            USING (true) WITH CHECK (true);
banque=# CREATE POLICY p_ecriture ON bank.clients
            FOR ALL TO r_ecriture
            USING (true) WITH CHECK (true);
```

Vérifie à nouveau les tests de l'étape 6 pour `analyste_youssef` et `agent_salma`.

### Étape 8 : bilan

```sql
banque=# \dp bank.*
banque=# \ddp
banque=# SELECT * FROM pg_policies WHERE schemaname = 'bank';
```

Garde ce modèle : il sert dans les modules suivants.

---

## Exercices

1. Un stagiaire doit pouvoir lire toutes les tables de `bank` sauf les colonnes `cin` et `date_naissance` de `clients`, pendant trois mois. Écris toutes les commandes nécessaires.
2. Pourquoi `GRANT SELECT ON ALL TABLES IN SCHEMA bank TO r_lecture` ne suffit-il pas dans le temps ? Démontre-le par un test.
3. Écris une politique RLS qui permet à `r_conseiller` de modifier uniquement le téléphone et l'e-mail des clients de son agence, sans pouvoir déplacer un client vers une autre agence.
4. On te fournit la fonction suivante. Identifie toutes ses failles et corrige-la :
   ```sql
   CREATE FUNCTION debloquer_compte(id bigint) RETURNS void
   LANGUAGE sql SECURITY DEFINER AS
   $$ UPDATE comptes SET statut = 'ACTIF' WHERE id_compte = id $$;
   -- propriétaire : postgres
   ```
5. Un employé quitte l'entreprise. Il possède des objets dans deux bases. Donne la procédure complète et sûre pour supprimer son rôle.

---

## Quiz

1. Quelle est la différence entre un utilisateur et un groupe dans PostgreSQL ?
2. Les rôles sont-ils propres à une base ?
3. Quels sont les trois privilèges nécessaires pour lire une table ?
4. Quels privilèges `PUBLIC` reçoit-il automatiquement sur une nouvelle fonction ?
5. Que fait `ALTER DEFAULT PRIVILEGES` et quel est le piège de la clause `FOR ROLE` ?
6. Pourquoi faut-il changer les mots de passe avec `\password` ?
7. Que se passe-t-il pour un rôle quand RLS est activé sur une table sans aucune politique le concernant ?
8. Quels rôles ne sont jamais soumis à RLS ?
9. Quelles sont les quatre règles d'une fonction `SECURITY DEFINER` sûre ?
10. Pourquoi le rôle `pg_execute_server_program` est-il dangereux ?

*Corrigés : [annexe D](annexes/D-corriges.md#module-04).*

---

## À retenir

- Rôle = utilisateur ou groupe ; global au cluster ; privilèges accordés aux groupes, personnes membres des groupes.
- Trois portes : `CONNECT` (base) → `USAGE` (schéma) → privilège sur l'objet.
- Neutraliser `PUBLIC` ; utiliser `ALTER DEFAULT PRIVILEGES FOR ROLE <propriétaire>`.
- Objets possédés par un rôle `NOLOGIN` ; application sans droit de DDL ; jamais de superutilisateur applicatif.
- RLS pour filtrer les lignes ; attention au propriétaire (`FORCE`) et au refus par défaut.
- `SECURITY DEFINER` : `search_path` figé, entrées validées, noms qualifiés, `EXECUTE` retiré à `PUBLIC`.
