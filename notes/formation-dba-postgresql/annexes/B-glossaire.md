# Annexe B — Glossaire

Définitions des termes techniques employés dans la formation. Classées par ordre alphabétique.

---

**ACID** — Quatre propriétés garantissant la fiabilité des transactions : Atomicité (tout ou rien), Cohérence (les contraintes restent respectées), Isolation (les transactions concurrentes ne se perturbent pas indûment), Durabilité (une transaction validée survit à une panne).

**ANALYZE** — Commande qui met à jour les statistiques sur la distribution des données d'une table, utilisées par le planificateur pour choisir les plans d'exécution.

**Archivage WAL** — Copie des segments WAL vers un stockage externe au fil de leur production (`archive_command`), permettant la restauration à un instant précis (PITR).

**Autovacuum** — Processus d'arrière-plan qui déclenche automatiquement VACUUM et ANALYZE selon l'activité des tables.

**Backend** — Processus serveur dédié à une connexion client. PostgreSQL crée un processus par connexion (modèle *process-per-connection*).

**BRIN** (*Block Range Index*) — Type d'index compact stockant des résumés (min/max) par plage de blocs. Efficace uniquement quand les données sont physiquement ordonnées selon la colonne indexée.

**Bloat** (gonflement) — Espace occupé par des versions de lignes mortes non encore récupérées, ou par des index fragmentés. Corrigé par VACUUM (espace réutilisable) ou VACUUM FULL / REINDEX (restitution au système).

**B-tree** — Type d'index par défaut, équilibré, adapté aux comparaisons d'égalité et d'intervalle et au tri.

**Cache hit ratio** — Proportion de lectures servies depuis le cache mémoire (`shared_buffers`) plutôt que depuis le disque.

**Checkpoint** (point de reprise) — Opération qui écrit sur disque toutes les pages modifiées en mémoire et marque un point à partir duquel la reprise après panne peut commencer.

**CIA** — Confidentialité, Intégrité, Disponibilité (*Availability*) : les trois propriétés fondamentales de la sécurité de l'information.

**Cluster (PostgreSQL)** — Un ensemble de bases de données géré par une même instance du serveur, partageant un même PGDATA, un port et des rôles. À ne pas confondre avec un cluster de haute disponibilité.

**CTE** (*Common Table Expression*) — Sous-requête nommée introduite par `WITH`, améliorant la lisibilité et permettant la récursivité.

**DDL / DML** — *Data Definition Language* (CREATE, ALTER, DROP) / *Data Manipulation Language* (SELECT, INSERT, UPDATE, DELETE).

**Failover** (bascule) — Promotion d'une réplique en primaire à la suite de la défaillance du primaire d'origine.

**FILLFACTOR** — Pourcentage de remplissage d'une page laissé à l'écriture initiale, réservant de la place aux mises à jour HOT sur la même page.

**HOT** (*Heap-Only Tuple*) — Optimisation évitant de mettre à jour les index quand la nouvelle version d'une ligne tient dans la même page et ne modifie aucune colonne indexée.

**HBA** (*Host-Based Authentication*) — Mécanisme de contrôle d'accès de PostgreSQL, configuré dans `pg_hba.conf`.

**Index couvrant** — Index contenant (via `INCLUDE`) toutes les colonnes nécessaires à une requête, permettant un parcours d'index seul (*index-only scan*) sans accès à la table.

**Injection SQL** — Vulnérabilité applicative où une entrée non maîtrisée modifie la structure d'une requête. Contrée par les requêtes paramétrées.

**Instance** — Le serveur PostgreSQL en cours d'exécution (le postmaster et ses processus), gérant un cluster.

**Isolation (niveaux)** — Degré de protection entre transactions concurrentes : *Read Committed* (défaut), *Repeatable Read*, *Serializable*.

**LSN** (*Log Sequence Number*) — Position d'un enregistrement dans le flux WAL, servant de référence pour la réplication et la reprise.

**MVCC** (*Multi-Version Concurrency Control*) — Mécanisme où chaque écriture crée une nouvelle version de ligne, permettant aux lecteurs de ne pas bloquer les écrivains et inversement.

**Moindre privilège** — Principe de sécurité : n'accorder que les droits strictement nécessaires à chaque rôle.

**Partitionnement** — Découpage d'une grande table logique en sous-tables physiques (partitions) selon une clé (par intervalle, liste ou hachage).

**PGDATA** — Répertoire contenant l'ensemble des fichiers de données d'un cluster.

**pgaudit** — Extension produisant un journal d'audit structuré des opérations (lecture, écriture, DDL, rôle…).

**PITR** (*Point-In-Time Recovery*) — Restauration d'une base à un instant précis, à partir d'une sauvegarde de base et du rejeu des WAL archivés.

**Planificateur** (*planner/optimizer*) — Composant qui, à partir des statistiques, choisit le plan d'exécution estimé le moins coûteux pour une requête.

**Pooler** (gestionnaire de connexions) — Intermédiaire (PgBouncer, Pgpool-II) mutualisant un petit nombre de connexions serveur entre de nombreux clients.

**Postmaster** — Le processus principal de l'instance, qui accepte les connexions et gère les processus enfants.

**Réplication logique** — Réplication au niveau des lignes/tables via un flux de modifications décodées, autorisant des versions ou schémas différents entre source et cible.

**Réplication physique** (*streaming*) — Réplication au niveau des blocs via le flux WAL ; la réplique est une copie binaire du primaire.

**RLS** (*Row-Level Security*) — Sécurité au niveau des lignes : des politiques filtrent automatiquement les lignes visibles ou modifiables selon le rôle.

**RPO** (*Recovery Point Objective*) — Perte de données maximale tolérée, exprimée en temps (ex. « au plus 1 minute »).

**RTO** (*Recovery Time Objective*) — Durée d'indisponibilité maximale tolérée pour rétablir le service.

**Rôle** — Entité de sécurité PostgreSQL, pouvant représenter un utilisateur (avec `LOGIN`) ou un groupe (`NOLOGIN`). Un seul concept unifie utilisateurs et groupes.

**SCRAM-SHA-256** — Méthode d'authentification par mot de passe haché résistante à l'interception, recommandée par défaut.

**SECURITY DEFINER** — Fonction s'exécutant avec les privilèges de son propriétaire plutôt que de l'appelant ; puissante mais à sécuriser (search_path figé, entrées validées).

**Slot de réplication** — Mécanisme garantissant que le primaire conserve les WAL nécessaires à une réplique tant qu'elle ne les a pas consommés.

**Split-brain** — Situation dangereuse où deux nœuds se croient simultanément primaires ; évitée par un mécanisme de quorum/fencing.

**Statistiques** — Données sur la distribution des valeurs des colonnes, collectées par ANALYZE et utilisées par le planificateur.

**TDE** (*Transparent Data Encryption*) — Chiffrement transparent des fichiers de données au niveau du cluster (non disponible dans le PostgreSQL communautaire à ce jour).

**TOAST** (*The Oversized-Attribute Storage Technique*) — Mécanisme de stockage déporté et compressé des valeurs volumineuses (grands textes, binaires).

**Transaction** — Unité de travail atomique délimitée par `BEGIN` et `COMMIT`/`ROLLBACK`.

**Tuple** — Synonyme de ligne (version d'un enregistrement) dans la terminologie PostgreSQL.

**VACUUM** — Opération récupérant l'espace des versions de lignes mortes et prévenant le bouclage des identifiants de transaction (*wraparound*).

**Vue matérialisée** — Résultat d'une requête stocké physiquement, rafraîchi à la demande (`REFRESH`), utile pour des agrégats coûteux.

**WAL** (*Write-Ahead Log*) — Journal des modifications écrit **avant** leur application aux fichiers de données, garantissant la durabilité et permettant reprise, archivage et réplication.

**Wraparound** (bouclage des XID) — Épuisement de l'espace circulaire des identifiants de transaction ; prévenu par le VACUUM de gel (*freeze*). En cas d'imminence, PostgreSQL peut bloquer les écritures pour se protéger.

**XID** (*Transaction ID*) — Identifiant numérique attribué à chaque transaction, servant à la visibilité MVCC.
