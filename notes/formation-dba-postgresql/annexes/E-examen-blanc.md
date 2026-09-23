# Annexe E — Examen blanc

Examen de synthèse couvrant l'ensemble de la formation. À traiter en conditions réelles (2 h, sans consulter les corrigés), puis à s'auto-évaluer avec le barème.

- **Partie I** — Questions de cours (20 pts)
- **Partie II** — Analyse et diagnostic (30 pts)
- **Partie III** — Mise en situation pratique (30 pts)
- **Partie IV** — Sécurité (20 pts)

**Total : 100 points.** Le corrigé suit l'énoncé.

---

## Énoncé

### Partie I — Questions de cours (20 pts, 2 pts chacune)

1. Expliquez la différence entre une instance, un cluster et une base de données.
2. Décrivez, dans l'ordre, ce qui se passe lors d'un `COMMIT`. Qu'est-ce qui garantit la durabilité ?
3. Qu'est-ce que le MVCC ? Pourquoi un lecteur ne bloque-t-il jamais un écrivain ?
4. Quels sont les trois privilèges nécessaires et suffisants pour qu'un rôle lise une table dans un schéma non-`public` ?
5. Différence entre RPO et RTO. Donnez un exemple chiffré pour chacun.
6. Pourquoi la réplication physique n'est-elle pas une sauvegarde ?
7. Qu'est-ce que le wraparound des XID et comment PostgreSQL le prévient-il ?
8. Citez trois éléments à vérifier en premier dans un plan `EXPLAIN ANALYZE` lent.
9. Pourquoi `sslmode=require` ne suffit-il pas ? Que faut-il utiliser ?
10. Quelle est la seule protection fiable contre l'injection SQL, et pourquoi ?

### Partie II — Analyse et diagnostic (30 pts)

**Exercice A (10 pts).** Le disque du serveur est plein à 98 %. `du -sh` sur `pg_wal/` renvoie 210 Go.
1. Citez les trois causes les plus probables. (6 pts)
2. Pour chacune, indiquez la requête ou la commande de diagnostic. (3 pts)
3. Quelle action est **strictement interdite** ? (1 pt)

**Exercice B (10 pts).** Une requête analytique met 45 secondes. Son plan contient :
```
Seq Scan on operations (cost=... rows=2000000) (actual time=... rows=312 loops=1)
  Filter: (date_op::date = '2024-05-01'::date)
  Rows Removed by Filter: 1999688
```
1. Pourquoi l'index sur `date_op` n'est-il pas utilisé ? (3 pts)
2. Réécrivez la clause `WHERE` pour permettre son usage. (4 pts)
3. Proposez une solution alternative si l'on ne peut pas modifier la requête. (3 pts)

**Exercice C (10 pts).** Sur le primaire, `pg_stat_replication` est **vide**, alors qu'une réplique est censée être connectée.
1. Citez quatre causes possibles. (4 pts)
2. Quelles vues/commandes consultez-vous, côté primaire **et** côté réplique ? (4 pts)
3. Comment prévenir ce type d'incident ? (2 pts)

### Partie III — Mise en situation pratique (30 pts)

Vous déployez la base `boutique` (e-commerce) pour une PME marocaine. Contraintes : RPO ≤ 5 min, RTO ≤ 1 h, données clients soumises à la loi 09-08, pic de charge le soir.

1. **Sauvegarde (8 pts).** Proposez une stratégie complète : type, outil, fréquence, rétention, emplacement, chiffrement, tests. Justifiez au regard du RPO/RTO.
2. **Rôles (8 pts).** Définissez la hiérarchie de rôles (propriétaire, application, lecture, administration) et le principe appliqué. Écrivez les commandes pour le rôle applicatif et son moindre privilège.
3. **Performance (7 pts).** La page « mes commandes » (`WHERE id_client=$1 ORDER BY date_commande DESC LIMIT 20`) est lente. Proposez l'index et expliquez pourquoi il convient.
4. **Supervision (7 pts).** Listez cinq métriques à surveiller avec leurs seuils, et le rôle utilisé par la sonde.

### Partie IV — Sécurité (20 pts)

1. **(6 pts)** Écrivez trois lignes `pg_hba.conf` pour : l'application depuis 10.0.1.0/24 vers `boutique` avec TLS obligatoire ; les DBA (rôle `dba`) depuis 10.0.9.0/24 avec TLS ; refus du reste.
2. **(6 pts)** Ce code Python est-il vulnérable ? Corrigez-le.
   ```python
   login = request.form['login']
   cur.execute("SELECT * FROM clients WHERE login = '%s'" % login)
   ```
3. **(4 pts)** Un audit révèle que `PUBLIC` a `CREATE` sur le schéma `public` et que trois comptes utilisent `md5`. Quelles commandes appliquez-vous ?
4. **(4 pts)** Citez quatre points de la checklist de durcissement que vous vérifieriez en priorité avant la mise en production, et expliquez brièvement pourquoi.

---
---

## Corrigé

### Partie I

1. **Instance / cluster / base.** L'*instance* est le serveur en cours d'exécution (postmaster + processus). Le *cluster* est l'ensemble des bases gérées par cette instance (un PGDATA, un port, des rôles partagés). Une *base* est un conteneur logique d'objets dans le cluster. Une instance ↔ un cluster ↔ plusieurs bases.
2. **COMMIT.** L'enregistrement de validation est écrit dans le WAL puis **forcé sur disque** (`fsync`, selon `synchronous_commit`) ; une fois le WAL durable, le client reçoit la confirmation. Les pages de données sont écrites plus tard (checkpoint). La durabilité est garantie par le **WAL** (écriture avant les données).
3. **MVCC.** Chaque écriture crée une **nouvelle version** de ligne (`xmin`/`xmax`) au lieu d'écraser l'ancienne. Un lecteur voit la version cohérente avec son instantané ; il n'a pas besoin d'attendre l'écrivain, qui travaille sur une autre version. D'où l'absence de blocage lecteur/écrivain.
4. **Trois privilèges.** `CONNECT` sur la base, `USAGE` sur le schéma, `SELECT` sur la table.
5. **RPO / RTO.** RPO = perte de données max tolérée (ex. « au plus 5 min de transactions »). RTO = durée d'indisponibilité max tolérée (ex. « service rétabli en moins d'1 h »).
6. **Réplication ≠ sauvegarde.** Elle reproduit **immédiatement** les erreurs (un `DROP`/`DELETE` fautif est répliqué aussitôt). Elle ne permet pas de revenir en arrière.
7. **Wraparound.** Épuisement de l'espace circulaire des XID 32 bits ; d'anciennes transactions paraîtraient futures et des lignes deviendraient invisibles. Prévention : VACUUM de **gel** (*freeze*) des vieux tuples ; en cas d'imminence, PostgreSQL force le VACUUM puis **bloque les écritures**.
8. **Plan lent : à vérifier.** L'écart estimation/réel (`rows` vs `actual rows`) ; les parcours séquentiels sur grosses tables ; les tris/hachages **sur disque** (manque de `work_mem`) ; le nombre de `loops`.
9. **`require` insuffisant.** Il chiffre mais ne vérifie pas l'identité du serveur → homme du milieu possible. Utiliser **`verify-full`**.
10. **Injection SQL.** Les **requêtes paramétrées** : le pilote envoie séparément le code (fixe) et les données (jamais interprétées comme du SQL), rendant l'injection impossible.

### Partie II

**Exercice A.**
1. Causes probables : (a) un **slot de réplication inactif** retenant les WAL ; (b) l'**archivage en échec** (WAL non recyclés) ; (c) une **réplique décrochée** / réseau ; (accessoirement un pic de production de WAL ou `wal_keep_size` trop grand).
2. Diagnostic : `SELECT slot_name, active, pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) FROM pg_replication_slots;` (slots) ; `SELECT * FROM pg_stat_archiver;` (archivage : `last_failed_time`) ; `SELECT * FROM pg_stat_replication;` (réplique).
3. **Interdit** : supprimer des fichiers dans `pg_wal/` à la main.

**Exercice B.**
1. `date_op::date = ...` applique une **fonction/transformation à la colonne** : l'index sur `date_op` (timestamp) ne peut pas être utilisé, d'où le `Seq Scan`.
2. Réécriture par **intervalle** :
   ```sql
   WHERE date_op >= '2024-05-01' AND date_op < '2024-05-02'
   ```
3. Alternative sans toucher à la requête : créer un **index sur l'expression** `CREATE INDEX ON bank.operations ((date_op::date));` (l'index correspond alors exactement au filtre).

**Exercice C.**
1. Causes : slot/replication non configuré ; **`standby.signal` absent** ou mauvaise `primary_conninfo` ; authentification de réplication refusée (`pg_hba` sans ligne `replication`) ; réseau/pare-feu bloquant ; réplique arrêtée ou en échec de rejeu.
2. Côté primaire : `pg_stat_replication`, `pg_replication_slots`, journaux. Côté réplique : `SELECT pg_is_in_recovery();`, `pg_stat_wal_receiver`, et le **journal de démarrage** de la réplique (erreurs de connexion/auth).
3. Prévention : superviser `pg_stat_replication` et le retard, alerter si vide/décroché, tester la reconnexion, sécuriser via slot + certificat.

### Partie III

1. **Sauvegarde.** Sauvegarde **physique** (pgBackRest) : complète hebdomadaire + différentielle quotidienne + **archivage WAL continu** (RPO ≤ 5 min facilement tenu). Rétention 2–4 semaines, stockage **hors serveur**, **chiffré**, **tests de restauration** mensuels datés. RTO ≤ 1 h atteignable par restauration physique + rejeu ; une réplique peut le réduire. Justification : le WAL continu donne le RPO fin, la sauvegarde physique donne un RTO maîtrisé.
2. **Rôles.** Principe : **moindre privilège** + séparation propriétaire/usage.
   ```sql
   CREATE ROLE boutique_owner NOLOGIN;
   CREATE ROLE r_app NOLOGIN;
   CREATE ROLE app_boutique LOGIN PASSWORD '...' CONNECTION LIMIT 50;
   GRANT r_app TO app_boutique;
   GRANT CONNECT ON DATABASE boutique TO r_app;
   GRANT USAGE ON SCHEMA shop TO r_app;
   GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA shop TO r_app;
   ALTER DEFAULT PRIVILEGES FOR ROLE boutique_owner IN SCHEMA shop
     GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO r_app;
   -- l'application n'est PAS propriétaire, pas de DDL, pas de superuser
   ```
   Plus : `r_lecture` (SELECT seul) pour le reporting, DBA nominatifs.
3. **Performance.** Index composite **`(id_client, date_commande DESC)`** : il satisfait le filtre `id_client=$1` **et** fournit l'ordre `date_commande DESC` déjà trié, servant directement `LIMIT 20` sans tri ni parcours complet.
4. **Supervision (exemples).** % connexions (WARN 70 / CRIT 85), retard réplication (100 Mo / 1 Go), disque données (80 % / 90 %), âge XID (300 M / 800 M), échec archivage (tout échec = CRIT). Sonde : rôle **`pg_monitor`**.

### Partie IV

1. **pg_hba.**
   ```
   hostssl boutique  app_boutique  10.0.1.0/24   scram-sha-256
   hostssl all       +dba          10.0.9.0/24   scram-sha-256
   host    all       all           0.0.0.0/0     reject
   ```
2. **Vulnérable** (formatage `%` = concaténation). Correction par requête paramétrée :
   ```python
   cur.execute("SELECT * FROM clients WHERE login = %s", (login,))
   ```
   (Le `%s` de psycopg est un marqueur de paramètre, pas un formatage Python ; la valeur passe en 2ᵉ argument.)
3. **Corrections.**
   ```sql
   REVOKE CREATE ON SCHEMA public FROM PUBLIC;
   -- pour chaque compte md5 : forcer SCRAM
   SET password_encryption = 'scram-sha-256';
   \password compte1
   \password compte2
   \password compte3
   ```
   (Vérifier `password_encryption = scram-sha-256` dans la configuration pour l'avenir.)
4. **Quatre points prioritaires (exemples).** (a) Aucune règle `trust`/`md5` dans `pg_hba` — sinon accès non authentifié ou faible. (b) TLS actif et clients en `verify-full` — sinon interception/MITM. (c) Application non superutilisateur et moindre privilège — sinon compromission totale en cas d'injection. (d) Sauvegardes chiffrées **et testées** — sinon fausse sécurité / RTO non tenu. (Autres valables : REVOKE PUBLIC, pgaudit, chiffrement de volume, versions à jour.)

---

### Barème indicatif

| Total | Appréciation |
|-------|--------------|
| 85–100 | Excellent — niveau prêt pour un stage/mission DBA junior |
| 70–84 | Solide — bases maîtrisées, quelques approfondissements à faire |
| 55–69 | Acceptable — revoir les modules faibles |
| < 55 | À retravailler — reprendre les TP module par module |
