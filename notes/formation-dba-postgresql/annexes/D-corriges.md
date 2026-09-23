# Annexe D — Corrigés

Corrigés des quiz (10 questions) et exercices (5) des modules 01 à 10. Les réponses aux exercices ouverts donnent une correction type ; d'autres formulations valables existent. Confronte toujours à ton propre lab.

> Le module 11 (projet final) n'a pas de quiz : il est évalué par la grille `/100` du module.

---

## Module 01 {#module-01}

### Quiz

1. **Instance vs base.** Une *instance* est le serveur en cours d'exécution (le postmaster et ses processus) qui gère un *cluster* ; une *base de données* est un conteneur logique d'objets à l'intérieur de ce cluster. Une instance sert plusieurs bases.
2. **Qui crée les backends ?** Le **postmaster** : à chaque connexion acceptée, il fait un `fork` d'un processus backend dédié.
3. **Taille de page.** **8 Ko** par défaut (fixée à la compilation).
4. **Répertoire du WAL.** `pg_wal/` (sous `PGDATA`).
5. **Ordre d'un COMMIT.** L'enregistrement de validation est écrit dans le tampon WAL, puis **forcé sur disque** (`fsync`, selon `synchronous_commit`) ; une fois le WAL durable, le `COMMIT` est confirmé au client. Les pages de données modifiées, elles, sont écrites plus tard (checkpoint / bgwriter).
6. **Rôle du checkpoint.** Écrire sur disque toutes les pages modifiées (*dirty*) et marquer un point de reprise à partir duquel le rejeu WAL peut commencer après une panne. Il borne la durée de reprise et permet le recyclage des anciens WAL.
7. **Pourquoi protéger le WAL.** Parce qu'il contient les modifications validées **avant** qu'elles ne soient dans les fichiers de données : le perdre, c'est perdre des transactions validées et compromettre la reprise. C'est le garant de la durabilité (D d'ACID).
8. **Rôles : base ou cluster ?** **Globaux au cluster** : un rôle existe pour toutes les bases de l'instance.
9. **Pourquoi un pooler.** Chaque connexion = un processus + de la mémoire ; au-delà de quelques centaines, le coût devient prohibitif. Un pooler (PgBouncer) mutualise un petit nombre de connexions serveur entre de nombreux clients.
10. **pg_authid.** Le catalogue des rôles **avec les hachages de mots de passe** ; lisible uniquement par les superutilisateurs (contrairement à la vue `pg_roles`, qui masque le mot de passe).

### Exercices

1. **`shared_buffers` à 90 %.** Mauvaise idée : PostgreSQL s'appuie aussi sur le cache du système d'exploitation (double mise en cache), et laisse de la RAM au `work_mem` par connexion, à la maintenance et aux autres processus. Un `shared_buffers` trop grand affame le reste, augmente le coût des checkpoints et dégrade souvent les performances. Ordre de grandeur usuel : **25 % de la RAM**, à ajuster par la mesure.
2. **Mémoire max théorique.** `work_mem` s'alloue **par opération de tri/hachage**, pas par connexion : 300 × 64 Mo × 4 ≈ **75 Go** dans le pire cas, sans compter `shared_buffers` ni la maintenance. Conclusion : `work_mem` élevé × beaucoup de connexions peut faire exploser la RAM et déclencher l'OOM killer ; il faut le dimensionner prudemment (ou le régler par rôle) et limiter les connexions (pooler).
3. **COMMIT rapide.** Le `COMMIT` ne force sur disque que le **WAL** (écriture séquentielle, peu volumineuse) ; les pages de données modifiées (écritures aléatoires, plus lourdes) sont différées au checkpoint. On paie donc, à la validation, une petite écriture séquentielle plutôt que de nombreuses écritures aléatoires.
4. **Suppression dans `pg_wal/`.** Selon ce qui est supprimé : perte de transactions non encore appliquées aux fichiers de données, **impossibilité de reprise après panne**, rupture de la réplication et de l'archivage, voire cluster qui refuse de démarrer ou corruption logique. On ne supprime **jamais** un WAL à la main : on corrige la cause (archivage, slot) et on laisse PostgreSQL recycler.
5. **Deux clusters.** **Deux instances** distinctes (deux postmasters, deux PGDATA, deux ports). Un rôle créé sur le cluster 15 **n'existe pas** sur le cluster 16 : les rôles sont globaux à *un* cluster, pas partagés entre clusters.

---

## Module 02 {#module-02}

### Quiz

1. **Checksums.** `initdb --data-checksums` (option `-k`). Recommandé : détecte les corruptions silencieuses.
2. **Danger d'`initdb` sans options d'auth.** Le cluster peut être créé avec `trust` par défaut sur les accès locaux : quiconque a un accès local peut se connecter en superutilisateur sans mot de passe. Il faut fixer `--auth-host=scram-sha-256 --auth-local=scram-sha-256` (ou durcir `pg_hba.conf` immédiatement).
3. **`host` vs `hostssl`.** `host` accepte la connexion TCP chiffrée **ou non** ; `hostssl` n'accepte que les connexions **chiffrées par TLS**.
4. **Première ligne correspondante qui échoue.** L'authentification est **refusée** : PostgreSQL n'essaie pas les lignes suivantes. La première règle qui correspond (type, base, user, adresse) décide, même si son authentification échoue.
5. **Méthode mot de passe.** `scram-sha-256`.
6. **Redémarrage requis ?** Colonne `context` de `pg_settings` : `postmaster` = redémarrage ; `sighup` = rechargement ; `user`/`superuser` = à chaud. `SELECT name, context FROM pg_settings WHERE name = '...';`
7. **Erreur de syntaxe pg_hba.** `pg_hba_file_rules` (colonne `error`), à consulter **avant** `pg_reload_conf()`.
8. **`fast` vs `immediate`.** `fast` : refuse les nouvelles connexions, annule les transactions en cours et ferme proprement (checkpoint) — pas de rejeu au redémarrage. `immediate` : arrêt brutal sans checkpoint, comme un crash — reprise par rejeu WAL au démarrage suivant. On préfère `fast`.
9. **Où écrit `ALTER SYSTEM`.** Dans `postgresql.auto.conf` (dans PGDATA), lu **après** `postgresql.conf` (il a donc priorité).
10. **Changer le port ≠ sécurité.** C'est de l'obscurité : un scan de ports trouve le service en quelques secondes. La sécurité vient de l'authentification, du chiffrement et du contrôle d'accès, pas du numéro de port.

### Exercices

1. **Lignes pg_hba.**
   ```
   hostssl boutique  app_web     10.10.0.0/24   scram-sha-256
   hostssl entrepot  +analystes  172.16.0.0/16  scram-sha-256
   host    all       all         0.0.0.0/0      reject
   host    all       all         ::/0           reject
   ```
2. **Ordre inversé.** La première ligne `0.0.0.0/0 scram-sha-256` correspond **déjà** à 10.0.0.5 : l'application se voit demander un mot de passe SCRAM et la règle `cert` en dessous n'est **jamais atteinte**. Il faut placer la règle spécifique (`cert`) **avant** la règle générale.
3. **Redémarrage.** Nécessitent un redémarrage : `max_connections`, `shared_preload_libraries`, `wal_level` (`context = postmaster`). Rechargeables : `work_mem`, `log_min_duration_statement`, `archive_command` (`context = sighup`/`user`). Vérification : `SELECT name, context FROM pg_settings WHERE name IN (...);`
4. **Config 64 Go / PgBouncer.** Ordres de grandeur : `shared_buffers = 16GB` (~25 %), `effective_cache_size = 48GB` (~75 %), `work_mem = 32–64MB` (prudent car multiplié), `maintenance_work_mem = 2GB`, `max_connections = 200` (PgBouncer devant, donc peu de connexions serveur), `wal_buffers = 64MB`, `checkpoint_completion_target = 0.9`, SSD → `random_page_cost = 1.1`. À affiner par la mesure.
5. **Pourquoi éviter `log_statement = 'all'`.** (1) Volume : journalise chaque requête, coût I/O et disque énormes sous charge. (2) Sécurité : capture des données sensibles et des littéraux (dont, selon les cas, des secrets) en clair dans les journaux. On préfère `log_min_duration_statement` pour ne cibler que les requêtes lentes.

---

## Module 03 {#module-03}

### Quiz

1. **Schéma = répertoire ?** Non. Un schéma est un espace de noms **logique** ; il ne correspond pas à un répertoire. Les fichiers sont organisés par *tablespace* et par OID, pas par schéma.
2. **Taille max d'un segment.** **1 Go** : au-delà, la table est découpée en fichiers `oid`, `oid.1`, `oid.2`…
3. **`_fsm` et `_vm`.** `_fsm` (*Free Space Map*) : espace libre par page, pour placer les nouvelles lignes. `_vm` (*Visibility Map*) : pages dont toutes les lignes sont visibles par tous (accélère VACUUM et les *index-only scans*).
4. **`ctid`.** L'adresse physique d'une version de ligne : `(numéro_de_page, numéro_d_emplacement)`. Il change lorsqu'une ligne est mise à jour ou déplacée : ce n'est pas un identifiant stable.
5. **`xmin` / `xmax`.** `xmin` = XID de la transaction qui a **créé** la version de ligne ; `xmax` = XID de celle qui l'a **supprimée/remplacée** (0 si vivante). Base de la visibilité MVCC.
6. **Seuil TOAST.** Environ **2 Ko** (un quart de page) : au-delà, PostgreSQL compresse puis déporte la valeur dans la table TOAST associée.
7. **Mise à jour HOT.** *Heap-Only Tuple* : la nouvelle version tient dans la **même page** et **aucune colonne indexée** n'est modifiée. On évite alors de mettre à jour les index. Condition favorisée par un `fillfactor` < 100.
8. **`UNLOGGED` après crash.** La table est **vidée** (tronquée) : les tables non journalisées n'écrivent pas de WAL et ne survivent pas à un arrêt brutal. Rapides mais non durables.
9. **Taille totale.** `pg_total_relation_size('schema.table')` (table + index + TOAST). `pg_relation_size` ne donne que la table seule.
10. **Élagage de partitions** (*partition pruning*). Le planificateur écarte, dès la planification (ou à l'exécution), les partitions qui ne peuvent pas contenir de lignes correspondant à la clause `WHERE`, ne parcourant que les partitions utiles.

### Exercices

1. **`logs_web` 50 M/mois, 12 mois.** Partitionnement **par intervalle sur la date, une partition par mois**. Procédure mensuelle : créer la partition du mois **à venir** (à l'avance), puis `DETACH`/`DROP` de la partition du 13ᵉ mois (purge instantanée, sans `DELETE` massif). Justification : purge par `DROP` (rapide, pas de bloat), élagage à la lecture, maintenance et VACUUM par partition. Automatiser (cron ou `pg_partman`).
2. **PK et clé de partition.** Sur une table partitionnée, tout index **unique** (donc la clé primaire) doit **inclure la colonne de partitionnement**, car l'unicité n'est garantie que **par partition** : PostgreSQL ne peut pas imposer une unicité globale sans la clé de partition. Conséquence : `id_operation` seul n'est unique que dans sa partition ; la PK devient `(id_operation, date_op)`. Pour une unicité vraiment globale, il faut une autre approche (identifiant naturellement unique, ou contrainte applicative).
3. **`sessions_web` 500 UPDATE/s.** Baisser le `fillfactor` (par ex. `70`) pour laisser de la place aux mises à jour **HOT** sur la même page (colonne mise à jour non indexée → HOT possible). Mesurer via `pg_stat_user_tables` : suivre `n_tup_hot_upd` vs `n_tup_upd` (part de HOT) et l'évolution du bloat / des dead tuples.
4. **`double precision` pour des montants.** À proscrire : le binaire flottant ne représente pas exactement les décimales. Utiliser `numeric`.
   ```sql
   SELECT 0.1::float8 + 0.2::float8;      -- 0.30000000000000004
   SELECT 0.1::numeric + 0.2::numeric;    -- 0.3
   ```
   Sur des millions d'opérations, les erreurs s'accumulent : soldes faux. `numeric(15,2)` pour de l'argent.
5. **ID séquentiel dans l'URL** (IDOR / énumération). Un identifiant prévisible permet d'énumérer et, si l'autorisation est mal vérifiée, d'accéder aux ressources d'autrui. Côté base : exposer un identifiant **non devinable** (`uuid` via `gen_random_uuid()`, ou identifiant opaque) à la place de la séquence. Mais cela ne remplace **pas** le contrôle d'accès applicatif (et RLS côté base).

---

## Module 04 {#module-04}

### Quiz

1. **Utilisateur vs groupe.** Aucun mécanisme distinct : ce sont des **rôles**. Un rôle avec `LOGIN` sert d'utilisateur, un rôle `NOLOGIN` sert de groupe. `GRANT groupe TO utilisateur` établit l'appartenance.
2. **Rôles propres à une base ?** Non, **globaux au cluster**.
3. **Trois privilèges pour lire une table.** `CONNECT` sur la base, `USAGE` sur le schéma, `SELECT` sur la table.
4. **PUBLIC sur une nouvelle fonction.** `EXECUTE` est accordé à `PUBLIC` par défaut. Bonne pratique : `REVOKE EXECUTE ON FUNCTION ... FROM PUBLIC`.
5. **`ALTER DEFAULT PRIVILEGES`.** Définit les privilèges appliqués **aux objets créés à l'avenir**. Piège de `FOR ROLE` : les privilèges par défaut ne s'appliquent qu'aux objets créés **par le rôle indiqué** ; si les tables sont créées par un autre rôle que celui visé, la règle ne s'applique pas.
6. **`\password`.** Il hache le mot de passe **côté client** et n'envoie que le hachage : le mot de passe en clair n'apparaît ni dans les journaux, ni dans `pg_stat_statements`, ni dans l'historique. `CREATE/ALTER ROLE ... PASSWORD 'enclair'` fuiterait.
7. **RLS activée sans politique.** Par défaut, **aucune ligne** n'est visible pour les rôles soumis à RLS (politique implicite « refuser tout »). Il faut créer explicitement des politiques.
8. **Rôles jamais soumis à RLS.** Le **propriétaire de la table** (sauf `FORCE ROW LEVEL SECURITY`), les **superutilisateurs**, et les rôles ayant l'attribut **`BYPASSRLS`**.
9. **Quatre règles d'une `SECURITY DEFINER` sûre.** (1) Figer `search_path` (`SET search_path = ...`) ; (2) qualifier les objets par leur schéma ; (3) valider/assainir les entrées ; (4) retirer `EXECUTE` à `PUBLIC` et ne l'accorder qu'aux rôles voulus.
10. **`pg_execute_server_program`.** Il permet d'exécuter des **commandes du système d'exploitation** via `COPY ... PROGRAM`, avec les droits de l'utilisateur système `postgres` : un membre peut compromettre le serveur hôte. À n'accorder à personne côté application.

### Exercices

1. **Stagiaire lecture 3 mois, sauf 2 colonnes.**
   ```sql
   CREATE ROLE stagiaire LOGIN PASSWORD '...' VALID UNTIL '2026-12-23';
   GRANT CONNECT ON DATABASE banque TO stagiaire;
   GRANT USAGE ON SCHEMA bank TO stagiaire;
   GRANT SELECT ON ALL TABLES IN SCHEMA bank TO stagiaire;
   REVOKE SELECT ON bank.clients FROM stagiaire;          -- retirer l'accès global à clients
   GRANT SELECT (id_client, nom, prenom, email, id_agence) ON bank.clients TO stagiaire; -- colonnes autorisées seulement
   ```
   (Adapter la liste de colonnes ; `cin` et `date_naissance` en sont volontairement absents.) `VALID UNTIL` gère l'expiration.
2. **`GRANT ... ALL TABLES` insuffisant.** Il ne concerne que les tables **existant à l'instant du GRANT**. Démonstration : après le GRANT, créer une nouvelle table dans `bank`, s'y connecter en `r_lecture` → **permission refusée**. Solution : `ALTER DEFAULT PRIVILEGES IN SCHEMA bank GRANT SELECT ON TABLES TO r_lecture;` (pour les futurs objets créés par le bon rôle).
3. **Politique RLS conseiller.**
   ```sql
   ALTER TABLE bank.clients ENABLE ROW LEVEL SECURITY;
   CREATE POLICY conseiller_sel ON bank.clients FOR SELECT TO r_conseiller
     USING (id_agence = current_setting('app.agence')::int);
   CREATE POLICY conseiller_upd ON bank.clients FOR UPDATE TO r_conseiller
     USING     (id_agence = current_setting('app.agence')::int)   -- lignes modifiables
     WITH CHECK (id_agence = current_setting('app.agence')::int);  -- empêche de changer d'agence
   ```
   De plus, restreindre les **colonnes** modifiables au niveau privilèges : `GRANT UPDATE (telephone, email) ON bank.clients TO r_conseiller;`. Le `WITH CHECK` sur `id_agence` interdit de déplacer un client ; le `GRANT` de colonnes interdit de toucher au reste.
4. **Fonction `debloquer_compte` à corriger.** Failles : `SECURITY DEFINER` appartenant à **postgres** (superutilisateur) ; `search_path` non figé (détournement possible via une table `comptes` malveillante dans un schéma en tête de `search_path`) ; table non qualifiée ; `EXECUTE` ouvert à `PUBLIC` ; aucune validation. Correction :
   ```sql
   CREATE OR REPLACE FUNCTION bank.debloquer_compte(p_id bigint) RETURNS void
   LANGUAGE sql SECURITY DEFINER SET search_path = bank, pg_temp AS
   $$ UPDATE bank.comptes SET statut = 'ACTIF' WHERE id_compte = p_id $$;
   ALTER FUNCTION bank.debloquer_compte(bigint) OWNER TO banque_owner;  -- pas postgres
   REVOKE EXECUTE ON FUNCTION bank.debloquer_compte(bigint) FROM PUBLIC;
   GRANT  EXECUTE ON FUNCTION bank.debloquer_compte(bigint) TO r_support;
   ```
5. **Départ d'un employé, objets dans deux bases.** Ne pas `DROP ROLE` directement (échoue s'il possède des objets ou a des privilèges). Procédure, **dans chaque base** où il possède des objets :
   ```sql
   REASSIGN OWNED BY employe TO banque_owner;   -- transfère la propriété
   DROP OWNED BY employe;                        -- retire les privilèges restants dans cette base
   ```
   Puis, une fois fait dans **toutes** les bases : `DROP ROLE employe;`. Vérifier au préalable ce qu'il possède ; décider si `REASSIGN` (garder) ou `DROP OWNED` (supprimer) selon les objets.

---

## Module 05 {#module-05}

### Quiz

1. **`xmin`/`xmax`.** `xmin` : XID créateur de la version de ligne ; `xmax` : XID qui l'a invalidée (0 si toujours vivante). Servent à déterminer la visibilité pour chaque transaction.
2. **SELECT ne bloque pas UPDATE.** Grâce au **MVCC** : un `UPDATE` crée une **nouvelle version** de la ligne sans détruire l'ancienne ; les lecteurs continuent de voir la version cohérente avec leur instantané. Lecteurs et écrivains ne se bloquent pas.
3. **Isolation par défaut.** *Read Committed*.
4. **Erreur à rejouer en Serializable.** L'erreur de sérialisation `serialization_failure` (SQLSTATE **40001**) : l'application doit intercepter et **rejouer** la transaction.
5. **Verrou de `VACUUM FULL`.** Un `ACCESS EXCLUSIVE` sur toute la table : **tout accès est bloqué** pendant l'opération (elle réécrit la table). D'où l'usage de `pg_repack` ou d'une fenêtre de maintenance.
6. **Résolution d'un deadlock.** PostgreSQL détecte le cycle d'attente et **annule l'une des transactions** (`deadlock_detected`, 40P01) pour rompre la boucle ; l'application doit la rejouer.
7. **`pg_cancel_backend` vs `pg_terminate_backend`.** Le premier **annule la requête** en cours (la session survit) ; le second **ferme la session** entière (rollback de la transaction en cours). On tente `cancel` avant `terminate`.
8. **Trois causes bloquant VACUUM.** Une transaction ancienne toujours ouverte (`idle in transaction`), une transaction préparée oubliée (*prepared xact*), un slot de réplication en retard ou `hot_standby_feedback` d'une réplique — tous maintiennent un `xmin` horizon empêchant de nettoyer les versions plus récentes.
9. **Wraparound.** Les XID sont sur 32 bits (espace circulaire) ; s'ils bouclent, d'anciennes transactions paraîtraient futures et des données deviendraient invisibles. PostgreSQL **gèle** (*freeze*) les vieux tuples via VACUUM ; en cas d'imminence, il force le VACUUM et, en dernier recours, **bloque les écritures** pour se protéger.
10. **`fsync=off` vs `synchronous_commit=off`.** `synchronous_commit = off` : risque de perdre les **quelques dernières** transactions validées en cas de crash, mais la base reste **cohérente**. `fsync = off` : risque de **corruption** de toute la base en cas de crash. Le second est bien plus dangereux.

### Exercices

1. **`virement` sans deadlock.** Verrouiller les deux comptes **toujours dans le même ordre** (par identifiant croissant), pour que deux virements croisés ne s'attendent jamais mutuellement :
   ```sql
   -- verrouiller d'abord le plus petit id, puis le plus grand
   PERFORM 1 FROM bank.comptes WHERE id_compte IN (p_src, p_dst)
     ORDER BY id_compte FOR UPDATE;
   ```
   Ainsi 1→2 et 2→1 verrouillent tous deux 1 puis 2 : plus de cycle.
2. **10 000 requêtes / 500 places.** (a) `UPDATE places SET statut='vendue' WHERE id=$1 AND statut='libre'` et vérifier le nombre de lignes affectées (verrouillage optimiste au niveau ligne, sans survente). (b) Compteur avec `SELECT ... FOR UPDATE` sur une ligne de stock, ou file d'attente (une insertion par réservation, contrôlée). Comparaison : (a) simple, très concurrent, chaque place indépendante ; (b) sérialise davantage (point de contention sur le compteur) mais gère un stock agrégé. On préfère (a) quand chaque place est identifiable.
3. **Transaction Repeatable Read de 6 h.** Elle maintient un `xmin` horizon très ancien → **VACUUM ne peut plus nettoyer**, bloat massif, risque de wraparound. Alternatives : découper en lots (plusieurs transactions), utiliser une **réplique** dédiée au reporting, ou un `pg_dump`/instantané. Ne jamais tenir une transaction ouverte des heures.
4. **`evenements` insertions seules, autovacuum jamais déclenché.** Sans mises à jour/suppressions, l'autovacuum basé sur les dead tuples ne se déclenche pas → pas de **freeze** → risque de **wraparound**. Avant PG 13, régler `autovacuum_freeze_max_age` et/ou planifier un `VACUUM (FREEZE)` régulier ; PG 13+ introduit un autovacuum déclenché par l'âge d'insertion (`autovacuum_vacuum_insert_threshold`).
5. **`synchronous_commit = off` pour une banque.** Refus : cela accepte de **perdre des transactions validées** (virements confirmés au client) en cas de crash — inacceptable pour de l'argent. La base resterait cohérente mais des opérations confirmées disparaîtraient. Alternative : le garder `on` globalement, et ne le relâcher éventuellement que pour des traitements non critiques (par transaction, `SET LOCAL synchronous_commit = off`).

---

## Module 06 {#module-06}

### Quiz

1. **RPO / RTO.** RPO = perte de données maximale tolérée (en temps) ; RTO = durée d'indisponibilité maximale tolérée pour rétablir le service.
2. **Réplication ≠ sauvegarde.** Une réplique reproduit **immédiatement** les erreurs : un `DROP TABLE` ou un `DELETE` fautif est répliqué aussitôt. La sauvegarde permet de revenir **en arrière** ; pas la réplication.
3. **Format `pg_dump` parallèle.** Le format **répertoire** (`-Fd`), avec `-j` (jobs parallèles). Le format custom (`-Fc`) permet le parallélisme à la **restauration** mais pas à la sauvegarde.
4. **Ce que `pg_dump` ne sauvegarde pas.** Les objets **globaux** (rôles, tablespaces, paramètres de connexion) : ils sont propres au cluster, pas à une base. On les récupère avec `pg_dumpall --globals-only`.
5. **Code retour d'`archive_command`.** Elle doit renvoyer **0 uniquement en cas de succès réel** (fichier bien copié et durable). Un faux succès fait recycler un WAL non archivé → trou irréparable dans la chaîne PITR.
6. **Fichier de déclenchement (PG 12+).** `recovery.signal` (dans PGDATA) déclenche une restauration ; `standby.signal` déclenche le mode réplique. Les anciens `recovery.conf` n'existent plus.
7. **`recovery_target_action = 'pause'`.** Une fois la cible atteinte, la reprise **se met en pause** (sans promouvoir) : on peut inspecter l'état, puis promouvoir (`pg_wal_replay_resume` / promotion) ou ajuster la cible.
8. **`pg_verifybackup` et sa limite.** Il vérifie l'**intégrité** d'une sauvegarde de base (`pg_basebackup` avec manifeste) : fichiers présents, sommes de contrôle correctes. Limite : il ne vérifie **pas** que la base est **restaurable et cohérente fonctionnellement** — seul un vrai test de restauration le prouve.
9. **Chiffrement asymétrique pour les sauvegardes.** La **clé publique** (sur le serveur) suffit à chiffrer ; la **clé privée** (gardée ailleurs, hors ligne) est seule capable de déchiffrer. Ainsi, un serveur compromis ne permet pas de déchiffrer les sauvegardes existantes.
10. **Timeline.** Un identifiant d'« histoire » du cluster : après chaque restauration/promotion, PostgreSQL crée une **nouvelle timeline** pour éviter de confondre des WAL divergents. Un fichier `.history` en trace la généalogie.

### Exercices

1. **RPO 15 min / RTO 2 h / 500 Go.** Sauvegarde **physique** (pgBackRest ou `pg_basebackup`) hebdomadaire complète + différentielles quotidiennes, **archivage WAL en continu** (RPO piloté par la fréquence d'archivage → bien < 15 min). Rétention (ex. 4 semaines), stockage **hors site** et immuable, **chiffrement**. RTO 2 h atteignable avec restauration physique + rejeu WAL. **Tests de restauration** mensuels datés. Éventuellement une réplique pour réduire le RTO.
2. **`pg_dump` par base insuffisant.** Il ne contient pas les **rôles**, **tablespaces** ni paramètres globaux : à la restauration, les propriétaires et privilèges manqueraient. Ajouter `pg_dumpall --globals-only`.
3. **`DELETE` à heure inconnue.** Croiser les sources : journaux applicatifs et **journaux PostgreSQL** (si `log_statement`/pgaudit actifs) pour approcher l'heure ; `pg_waldump` pour repérer l'enregistrement du `DELETE` et son horodatage/LSN. Puis restaurer avec `recovery_target_action = 'pause'` sur une cible **juste avant**, inspecter, ajuster par dichotomie, et promouvoir une fois le bon instant trouvé.
4. **Archivage en échec depuis 3 jours.** Conséquences : (1) **`pg_wal` grossit** (WAL retenu) jusqu'à saturer le disque ; (2) **trou dans la chaîne PITR** → impossible de restaurer sur cette période. Prévention : **superviser** `pg_stat_archiver` (`last_failed_time`), alerter dès le premier échec, tester l'archivage.
5. **Runbook PITR.** Voir le runbook détaillé du module 06. Structure attendue : préconditions (sauvegarde de base + WAL disponibles), arrêt de l'instance cible, restauration de la sauvegarde de base dans un PGDATA propre, configuration `restore_command` + `recovery_target_time` + `recovery_target_action='pause'`, création de `recovery.signal`, démarrage, vérification de l'état atteint, promotion, contrôles post-restauration, communication.

---

## Module 07 {#module-07}

### Quiz

1. **Baisser `random_page_cost` sur SSD.** Le coût par défaut (4.0) suppose des disques rotatifs où l'accès aléatoire est bien plus lent que le séquentiel. Sur SSD, l'écart est faible : `random_page_cost = 1.1` reflète mieux la réalité et encourage l'usage des **index**.
2. **À regarder en premier dans un plan lent.** L'écart entre **lignes estimées et lignes réelles** (`rows` vs `actual rows`) : une mauvaise estimation trahit des statistiques obsolètes ou un mauvais choix de plan. Puis les nœuds les plus coûteux (parcours séquentiels sur grosses tables, tris sur disque).
3. **`EXPLAIN` vs `EXPLAIN ANALYZE`.** `EXPLAIN` donne le plan **estimé** sans exécuter ; `EXPLAIN ANALYZE` **exécute réellement** et donne les temps/lignes réels. Risque : sur un `INSERT/UPDATE/DELETE`, `ANALYZE` **modifie les données** — l'entourer d'une transaction annulée (`BEGIN; ... ROLLBACK;`).
4. **`loops=3`.** Le nœud a été exécuté **3 fois** (par ex. le côté interne d'une boucle imbriquée) ; le temps et les lignes affichés sont **par itération** : multiplier par `loops` pour le total.
5. **Index BRIN pertinent.** Quand les données sont **physiquement ordonnées** selon la colonne (corrélation forte entre l'ordre de stockage et la valeur), typiquement une colonne temporelle sur une table append-only. Sinon, BRIN est inefficace.
6. **Ordre des colonnes d'un index multicolonne.** L'index sert surtout les requêtes filtrant sur un **préfixe** des colonnes, dans l'ordre. Placer d'abord les colonnes utilisées en **égalité**, puis celle utilisée en intervalle/tri. Un mauvais ordre rend l'index inutilisable pour la requête.
7. **`CREATE INDEX CONCURRENTLY`.** Il construit l'index **sans verrou exclusif prolongé** (pas de blocage des écritures). En cas d'échec, il laisse un index **`INVALID`** qu'il faut supprimer (`DROP INDEX`) puis recréer.
8. **Trier par `total_exec_time`.** Parce qu'une requête un peu lente mais **très fréquente** pèse plus sur le système qu'une requête très lente mais rare. `total_exec_time = mean × calls` capture la charge réelle.
9. **Manque de `work_mem`.** La mention d'un tri/hachage **sur disque** dans le plan (`Sort Method: external merge Disk: ...`, ou `Batches > 1` sur un hachage) : l'opération a débordé de la mémoire allouée.
10. **Mode PgBouncer le plus utilisé.** Le mode **transaction** : une connexion serveur est assignée le temps d'une transaction. Contrainte principale : incompatible avec les fonctionnalités liées à la **session** (prepared statements côté session, `SET` de session, curseurs `WITH HOLD`, `LISTEN/NOTIFY`) sans précautions.

### Exercices

1. **Index pour chaque requête sur `operations`.**
   (a) `WHERE type_op='RETRAIT'` : peu sélectif (une valeur parmi peu) → souvent **aucun index** utile (parcours séquentiel probablement choisi) ; un index partiel n'a de sens que si `RETRAIT` est rare.
   (b) `WHERE id_compte=$1 AND type_op='PAIEMENT_CB' AND date_op > ...` : index composite **`(id_compte, type_op, date_op)`** (égalités puis intervalle en dernier) ; idéal pour ce filtre.
   (c) `WHERE libelle ILIKE '%loyer%'` : motif entouré de `%` → un B-tree est inutilisable. Utiliser un index **trigram** (`pg_trgm`, GIN) sur `libelle`.
   (d) `WHERE date_op::date = '2024-05-01'` : le `::date` sur la colonne empêche l'index ; réécrire en **intervalle** `date_op >= '2024-05-01' AND date_op < '2024-05-02'` et indexer `date_op` (ou créer un index sur l'**expression** `(date_op::date)`).
2. **`Nested Loop (rows=1) (actual rows=250000)`.** Grosse **sous-estimation** : le planificateur croyait 1 ligne et a choisi une boucle imbriquée, catastrophique à 250 000 itérations. Cause probable : statistiques obsolètes ou corrélation entre colonnes non capturée. Corriger : `ANALYZE`, éventuellement `CREATE STATISTICS` (dépendances multi-colonnes), vérifier les estimations ; le planificateur choisira alors un *hash join*.
3. **14 index, 3 requêtes, insertions lentes.** Chaque insertion doit mettre à jour **tous** les index → surcoût. Démarche : mesurer l'usage réel (`pg_stat_user_indexes.idx_scan`), identifier les index **jamais utilisés** et les **redondants** (préfixes couverts par un autre), les supprimer, ne conserver que ceux servant les 3 requêtes. Vérifier ensuite le gain en écriture.
4. **Pagination `OFFSET` lente.** `OFFSET 5000*n` lit et jette toutes les lignes précédentes. Réécrire en **pagination par curseur** (*keyset*) :
   ```sql
   SELECT ... FROM t WHERE (date_op, id) < ($dernier_date, $dernier_id)
   ORDER BY date_op DESC, id DESC LIMIT 50;
   ```
   Le temps devient constant, indépendant de la profondeur de page (avec un index sur `(date_op, id)`).
5. **`work_mem = 1GB`, `max_connections = 400`.** `work_mem` est **par opération** : 400 connexions × plusieurs tris × 1 Go ⇒ des **téraoctets** théoriques, OOM garanti. Alternative : `work_mem` modéré global (ex. 32–64 Mo), **relevé ponctuellement par requête/rôle** pour les gros traitements (`SET LOCAL work_mem`), et pooler pour limiter la concurrence.

---

## Module 08 {#module-08}

### Quiz

1. **Physique vs logique.** Physique (*streaming*) : réplication **binaire** au niveau des blocs via le WAL ; la réplique est une copie exacte, même version. Logique : réplication au niveau **lignes/tables** via un flux décodé ; autorise versions/schémas différents et réplication sélective.
2. **Fichier « je suis une réplique ».** `standby.signal` (dans PGDATA).
3. **Slot de réplication : rôle et danger.** Il garantit que le primaire **conserve** les WAL tant que la réplique ne les a pas consommés (pas de perte par recyclage). Danger : si la réplique disparaît sans que le slot soit supprimé, le primaire **accumule les WAL indéfiniment** → saturation disque.
4. **Paramètre limitant le WAL d'un slot.** `max_slot_wal_keep_size`.
5. **Seule réplique synchrone tombée.** Si `synchronous_standby_names` l'exige et qu'aucune autre réplique synchrone n'est disponible, les `COMMIT` du primaire **attendent** (se bloquent) faute de confirmation. D'où l'importance d'avoir ≥ 2 candidates synchrones ou une politique adaptée.
6. **`pg_rewind` et sa condition.** Il resynchronise un ancien primaire avec le nouveau après une bascule, sans recopier toute la base, en ne corrigeant que les blocs divergents. Condition : les **checksums de données** ou `wal_log_hints = on` doivent avoir été activés sur le cluster.
7. **Split-brain et Patroni.** Split-brain : deux nœuds se croient primaires simultanément → divergence des données. Patroni l'évite par un **verrou de leader** dans un magasin de consensus distribué (etcd/Consul/ZooKeeper) : un seul nœud peut détenir le bail de leader ; les autres restent répliques (fencing).
8. **DDL en réplication logique ?** **Non** : la réplication logique ne propage pas les changements de schéma (CREATE/ALTER TABLE). Il faut appliquer le DDL **manuellement** des deux côtés, dans le bon ordre.
9. **Réplique différée.** Une réplique volontairement en **retard** (`recovery_min_apply_delay`) protège contre les erreurs humaines : si un `DROP`/`DELETE` fautif survient, on dispose d'une fenêtre pour récupérer les données avant qu'elles ne soient appliquées sur la réplique différée.
10. **Rôle `REPLICATION` sensible.** Il permet d'ouvrir un flux de réplication et donc de **lire l'intégralité des données** du cluster (copie complète via `pg_basebackup`), en contournant les privilèges au niveau objet. À réserver à un compte dédié, sur un réseau restreint, avec TLS/certificat.

### Exercices

1. **Zéro perte, bascule < 30 s, 300 km.** Réplication **synchrone** (`remote_apply` ou `on`) pour le RPO nul, mais 300 km imposent une **latence** aller-retour ajoutée à **chaque commit** (plusieurs ms) : débit d'écriture réduit. Compromis : synchrone `remote_write` (moins strict) ou réplique synchrone proche + réplique asynchrone distante. Automatiser la bascule (Patroni) pour le RTO < 30 s. Discuter : le RPO nul à 300 km **coûte** en latence ; l'exigence doit être pondérée par l'impact sur les performances.
2. **`pg_wal` 180 Go, disque plein.** Causes liées à la réplication/archivage : (1) **slot inactif** retenant les WAL (`pg_replication_slots.active = false`, `restart_lsn` ancien) ; (2) **archivage en échec** (`pg_stat_archiver.last_failed_time`) empêchant le recyclage ; (3) réplique décrochée. Diagnostic : interroger ces deux vues. Résolution : réparer l'archivage / supprimer le slot fantôme ; prévention : `max_slot_wal_keep_size`, supervision.
3. **Split-brain par script naïf.** Schéma temporel : le primaire A subit une **coupure réseau** (mais tourne toujours) ; le script de surveillance ne voit plus A, **promeut** la réplique B → deux primaires. Le réseau revient : A et B ont divergé (écritures des deux côtés) → conflit irréconciliable. La leçon : une bascule sûre exige un **quorum** et un **fencing** (isoler A avant de promouvoir B), ce qu'un simple ping ne fournit pas.
4. **`hot_standby_feedback = on` et bloat.** La réplique informe le primaire des transactions **encore en cours** côté réplique pour éviter les conflits de rejeu ; le primaire **retarde alors le nettoyage** (VACUUM) des versions dont la réplique a besoin → accumulation de dead tuples (bloat) sur le primaire tant que de longues requêtes tournent sur la réplique.
5. **Migration 16 → 17 par réplication logique.** Préparer le 17 (même schéma, extensions compatibles), créer une **publication** sur le 16 et une **souscription** sur le 17, laisser rattraper le retard, **synchroniser les séquences** (non répliquées automatiquement), appliquer le DDL manuellement si besoin, vérifier la cohérence (comptages, sommes), puis basculer l'application pendant une courte fenêtre. Retour arrière : garder le 16 opérationnel et pouvoir y revenir tant que la bascule n'est pas validée ; réplication inverse éventuelle.

---

## Module 09 {#module-09}

### Quiz

1. **SCRAM sans TLS.** Il protège le **mot de passe** contre l'interception et le rejeu (défi-réponse, pas de secret transmis en clair). Il ne chiffre **pas** les données de la session : requêtes et résultats circulent en clair sans TLS.
2. **`sslmode=require` insuffisant.** Il chiffre mais **ne vérifie pas l'identité du serveur** → vulnérable à l'**homme du milieu** (l'attaquant présente son propre certificat). Utiliser **`verify-full`** (vérifie la CA **et** le nom d'hôte).
3. **Seule protection fiable contre l'injection.** Les **requêtes paramétrées** (préparées) : code et données sont envoyés séparément, la valeur n'est jamais interprétée comme du SQL.
4. **Moindre privilège limite l'injection.** Même si une injection réussit, le rôle applicatif restreint ne peut pas faire de `DROP`, lire des tables non autorisées, ni escalader : les dégâts sont bornés aux droits (minimes) du rôle.
5. **SQL dynamique sûr en PL/pgSQL.** Avec `format()` et les spécificateurs **`%I`** (identifiant) / **`%L`** (littéral), ou `EXECUTE ... USING` pour les valeurs. Jamais de concaténation `||` d'entrées dans l'`EXECUTE`.
6. **Extension d'audit structuré.** **pgaudit** ; classes principales : `read`, `write`, `ddl`, `role`, `function`, `misc`.
7. **Trois niveaux de chiffrement au repos.** (1) **Disque/volume** (LUKS) : contre le vol physique ; (2) **cluster/TDE** (fichiers) : contre le vol de fichiers ; (3) **colonne/application** (pgcrypto) : contre un accès logique / une fuite de dump / le DBA curieux.
8. **Problème central du chiffrement colonne.** La **gestion des clés** : si la clé est stockée dans la base, dans le code, ou passée en clair dans les requêtes (journaux, `pg_stat_statements`), la protection s'effondre. La clé doit vivre **hors de la base** (coffre/HSM). (Effet secondaire : perte de l'indexation/recherche sur la colonne.)
9. **Appliquer vite les versions mineures.** Elles corrigent des **bugs et des CVE** ; la mise à jour est simple (remplacement de binaires + redémarrage, sans conversion). Tarder, c'est rester exposé à des failles connues.
10. **Donnée « supprimée » pas effacée.** Un `DELETE` ne fait que marquer la ligne ; l'ancienne version survit jusqu'au VACUUM, **et** la donnée persiste dans le **WAL**, les **archives** et toutes les **sauvegardes** jusqu'à expiration de leur rétention. L'effacement complet est un processus.

### Exercices

1. **« `require` suffit ».** Il n'est **pas** protégé contre l'homme du milieu : un attaquant interceptant la connexion présente son propre certificat, le client l'accepte (aucune vérification), et tout est déchiffré. Correction : côté client `sslmode=verify-full` avec `sslrootcert` pointant sur la CA de confiance ; côté serveur, `hostssl` et de préférence authentification par certificat client.
2. **Code `ORDER BY {filtre}`.** **Vulnérable** : `filtre` (identifiant de colonne) est injecté par f-string dans le SQL → injection possible (`1; DROP ...`, sous-requêtes, exfiltration). Un identifiant ne peut pas être un paramètre lié : le valider par **liste blanche** de colonnes autorisées.
   ```python
   colonnes_ok = {'nom', 'prenom', 'date_creation'}
   if filtre not in colonnes_ok:
       filtre = 'nom'
   cur.execute(f"SELECT * FROM bank.clients ORDER BY {filtre}")  # sûr car filtre ∈ liste blanche
   ```
   (Ou utiliser `psycopg.sql.Identifier`.)
3. **Chiffrement de `cin`.** Niveau **colonne** (pgcrypto, `pgp_sym_encrypt`) car donnée très sensible et rarement recherchée. **Clé** hors base (Vault/KMS), passée en paramètre à la requête, jamais journalisée ; ne pas la stocker dans la table. **Impact recherche** : plus d'index ni de recherche par `cin` en clair → prévoir un identifiant/hachage déterministe séparé si une recherche exacte est nécessaire. **Rotation** : déchiffrer avec l'ancienne clé et rechiffrer avec la nouvelle par lots, versionner la clé (colonne `cle_version`).
4. **Cinq règles de détection SIEM (exemples).**
   | Signal | Source | Niveau |
   |--------|--------|--------|
   | Échecs d'authentification répétés depuis une IP | log natif (`log_connections`) | élevé |
   | Connexion d'un rôle applicatif depuis une IP inhabituelle | log natif | élevé |
   | `SELECT` massif / agrégat sans `WHERE` sur `clients` par le rôle app | pgaudit (`read`) | critique |
   | `CREATE ROLE` / `ALTER ROLE ... SUPERUSER` / `GRANT` inattendu | pgaudit (`role`) | critique |
   | Requête contenant `pg_sleep`, `UNION SELECT`, `information_schema` | log natif / pgaudit | élevé |
5. **Audit du lab.** Démarche attendue : exécuter `audit_securite.sql`, lister les constats (PUBLIC sur `public`, éventuels md5, TLS absent, audit absent), **corriger** (REVOKE PUBLIC, passage SCRAM, activation TLS `verify-full`, mise en place pgaudit), puis **relancer** le script et montrer que les points critiques/élevés ont disparu. Documenter avant/après.

---

## Module 10 {#module-10}

### Quiz

1. **Quatre familles de métriques.** Disponibilité, saturation, performance, santé interne.
2. **Rôle pour la supervision.** `pg_monitor` (jamais un superutilisateur).
3. **`pg_isready`.** Il teste si l'instance **accepte les connexions** et renvoie un **code de sortie** (0 = prêt, 1 = refuse, 2 = pas de réponse, 3 = pas de tentative). Il n'exécute aucune requête.
4. **Mineure vs majeure.** Mineure (16.3→16.4) : mêmes formats internes, simple remplacement de binaires + redémarrage. Majeure (16→17) : format potentiellement différent, **migration** nécessaire (dump/restore, `pg_upgrade` ou réplication logique).
5. **ANALYZE après `pg_upgrade`.** Parce que les **statistiques du planificateur ne sont pas transférées** : sans elles, les premiers plans sont mauvais. Lancer `vacuumdb --all --analyze-in-stages`.
6. **`--link` de `pg_upgrade`.** Il crée des **liens durs** au lieu de copier les fichiers → migration très rapide, peu de disque. Inconvénient : l'**ancien cluster n'est plus réutilisable** ensuite (pas de retour arrière simple sans sauvegarde).
7. **Rapport HTML des journaux.** **pgBadger** ; il a besoin en amont d'un `log_line_prefix` complet et de `log_min_duration_statement` (et de journaux au bon format).
8. **`pg_wal` remplit le disque.** Ne **jamais supprimer un WAL à la main** : on corrige la cause (slot inactif, archivage en échec) et on laisse PostgreSQL recycler.
9. **cron vs pg_cron.** `cron` planifie des tâches **côté système** (scripts shell : sauvegardes, maintenance externe). `pg_cron` est une **extension** qui planifie des tâches **en base** (SQL), pratique en environnement managé.
10. **Runbook.** Procédure écrite, testée et exécutable sous stress par l'astreinte pour un incident donné (symptômes, diagnostic, actions, vérifications, escalade). Indispensable pour réagir vite et sans improvisation lors d'une crise.

### Exercices

1. **Dix métriques (exemple).**
   | Métrique | Source | WARN | CRIT | Action |
   |----------|--------|------|------|--------|
   | Instance joignable | `pg_isready` | — | échec | escalade immédiate |
   | % connexions | `pg_stat_activity` | 70 % | 85 % | pooler, tuer sessions inutiles |
   | Disque données | OS | 80 % | 90 % | libérer / étendre |
   | Retard réplication | `pg_stat_replication` | 100 Mo | 1 Go | vérifier réseau/réplique |
   | Âge XID | `pg_database` | 300 M | 800 M | VACUUM freeze |
   | Idle in transaction | `pg_stat_activity` | 5 min | 15 min | terminer sessions |
   | Attente de verrou | `pg_stat_activity` | 30 s | 5 min | identifier bloqueur |
   | Échec archivage | `pg_stat_archiver` | — | tout échec | réparer archivage |
   | Cache hit | `pg_stat_database` | 95 % | 90 % | investiguer |
   | Dead tuples grosse table | `pg_stat_user_tables` | 20 % | 40 % | ajuster autovacuum |
2. **Sessions actives > 5 min.**
   ```sql
   SELECT pid, usename, now() - query_start AS duree,
          wait_event_type, wait_event, query
   FROM pg_stat_activity
   WHERE state = 'active' AND now() - query_start > interval '5 min'
   ORDER BY duree DESC;
   ```
3. **`pg_upgrade --link` sans sauvegarde, échec à mi-parcours.** Situation dangereuse : avec `--link`, l'ancien cluster partage les fichiers et peut être **inutilisable**, sans sauvegarde pour revenir en arrière → risque de perte. Leçon : **toujours sauvegarder avant**, tester la migration sur une copie, et n'utiliser `--link` qu'avec une sauvegarde valide et un plan de retour arrière.
4. **16 → 18, 2 To, RTO 15 min.** Le dump/restore (trop long) et `pg_upgrade --link` (fenêtre courte mais retour arrière difficile) sont risqués pour ce RTO sur 2 To. Méthode conseillée : **réplication logique** vers une instance 18 préparée en parallèle (bascule quasi nulle, retour arrière possible), ou à défaut `pg_upgrade --link` bien répété et chronométré avec sauvegarde. Justification : la réplication logique découple la migration de la fenêtre d'indisponibilité.
5. **Runbook « too many clients ».** Symptôme : erreurs `FATAL: sorry, too many clients already`. Diagnostic : `SELECT count(*) FROM pg_stat_activity;` vs `max_connections` ; repérer les sessions `idle`/`idle in transaction` et leur origine (fuite applicative, absence de pooler, pic). Action immédiate : se connecter via les connexions réservées (`superuser_reserved_connections`), terminer les sessions inutiles (`pg_terminate_backend`), au besoin relever temporairement `max_connections`. Correction durable : **PgBouncer** en mode transaction, corriger la fuite de connexions applicative, superviser le ratio de connexions. Vérification : le compte de connexions redescend, l'application se reconnecte. Prévention : pooler, alerte à 70/85 %.

---

*Fin des corrigés. Pour approfondir : [annexe F — ressources](F-ressources.md).*
