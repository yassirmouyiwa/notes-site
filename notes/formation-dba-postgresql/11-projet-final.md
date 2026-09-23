# Module 11 — Projet final de synthèse

## But

Concevoir, déployer, sécuriser, superviser et documenter une instance PostgreSQL de production complète, puis démontrer sa résilience. Ce projet mobilise **tous** les modules précédents. Il est calibré pour être présenté comme un mini-projet de fin de module, avec une soutenance de 15 minutes.

---

## 1. Contexte : « CliniqueNord »

Tu es le DBA d'un réseau de cliniques à Tétouan et Tanger. Le système gère des **données de santé** (parmi les plus sensibles au sens de la loi 09-08 et du RGPD) : patients, praticiens, rendez-vous, consultations, prescriptions, factures.

Contraintes imposées :

- **Confidentialité** : les données de santé exigent le plus haut niveau de protection.
- **Disponibilité** : la prise de rendez-vous fonctionne de 7 h à 22 h, 7 j/7 ; RTO ≤ 15 min, RPO ≤ 1 min.
- **Traçabilité** : tout accès aux dossiers médicaux doit être auditable (exigence légale).
- **Cloisonnement** : une secrétaire d'agence ne voit que les patients de son agence ; un médecin ne voit que ses patients ; un patient (portail) ne voit que son propre dossier.
- **Conformité** : durée de conservation, droit d'accès et d'effacement.

> Alternative : si tu préfères, réutilise la base `banque` des TP et réinterprète les exigences (secret bancaire, secrétaire = conseiller d'agence, etc.). La grille de notation s'applique de la même façon.

---

## 2. Travail demandé

### Lot 1 — Modélisation et déploiement (module 03)

- Schéma relationnel : au moins `agences`, `praticiens`, `patients`, `rendez_vous`, `consultations`, `prescriptions`, `factures`. Types adaptés (contraintes, clés étrangères, `CHECK`, énumérations ou domaines pour les statuts).
- Au moins une table volumineuse **partitionnée** de façon justifiée (par exemple `consultations` par mois, ou `journal_acces` par mois).
- Jeu de données de test réaliste (plusieurs agences, milliers de patients, dizaines de milliers de rendez-vous), avec des données **fictives** (jamais de vraies données personnelles).
- Installation reproductible (script d'initialisation, ou Ansible/compose en bonus).

### Lot 2 — Rôles, privilèges et cloisonnement (modules 04 et 09)

- Propriétaire `NOLOGIN` des objets ; aucun accès applicatif en superutilisateur.
- Rôles de groupe : `r_medecin`, `r_secretaire`, `r_facturation`, `r_lecture_audit`, `r_portail_patient`.
- Rôles de connexion nominatifs, hérités des groupes.
- Moindre privilège appliqué colonne par colonne pour les données sensibles.
- **RLS** mettant en œuvre les trois règles de cloisonnement (agence, médecin, patient).
- Fonctions `SECURITY DEFINER` conformes aux quatre règles pour les opérations transverses (par exemple, prise de rendez-vous).

### Lot 3 — Sécurité (module 09)

- **TLS** activé, connexions en `verify-full`, idéalement authentification par **certificat** pour le rôle applicatif.
- `pg_hba.conf` durci (aucun `trust`, `scram-sha-256`, `hostssl`).
- Chiffrement d'au moins une donnée très sensible au niveau colonne (avec discussion de la gestion de clé) **ou** chiffrement de volume documenté.
- **pgaudit** configuré pour tracer les accès aux dossiers médicaux (classe `read` sur les tables sensibles, `role`, `ddl`).
- Neutralisation de `PUBLIC`, `search_path` maîtrisé.

### Lot 4 — Sauvegarde et PITR (module 06)

- Stratégie documentée respectant le RPO/RTO (sauvegarde de base + archivage WAL).
- Sauvegardes **chiffrées** et vérifiées (`pg_verifybackup`).
- **Démonstration** d'une restauration PITR jusqu'à un instant précis (avant un incident simulé).

### Lot 5 — Haute disponibilité (module 08)

- Une **réplique physique** en flux avec slot.
- Réplication synchrone justifiée (ou asynchrone, avec argumentation par rapport au RPO).
- **Démonstration** d'une bascule (promotion de la réplique) et estimation du RTO atteint.

### Lot 6 — Performance (module 07)

- Index justifiés par des plans `EXPLAIN ANALYZE` (avant/après) sur les requêtes principales.
- `pg_stat_statements` activé ; identification et optimisation des trois requêtes les plus coûteuses.
- Configuration mémoire adaptée (documentée).

### Lot 7 — Supervision et exploitation (module 10)

- Requêtes ou tableau de bord de supervision ; compte `pg_monitor`.
- Script de contrôle de santé.
- Automatisation : sauvegarde planifiée, au moins une tâche de maintenance.
- Au moins **deux runbooks** (par exemple : perte du primaire, disque plein WAL).

### Lot 8 — Documentation et soutenance

- **Dossier d'architecture** (5 à 10 pages) : schéma, choix techniques justifiés, matrice des rôles et privilèges, modèle de menaces, stratégie de sauvegarde et de HA.
- **Journal de bord** des tests de résilience (PITR, failover) avec résultats mesurés (RTO/RPO obtenus).
- Soutenance de 15 min avec démonstration en direct d'au moins un scénario de résilience.

---

## 3. Scénarios de résilience à démontrer

Au moins **deux** des scénarios suivants, exécutés et mesurés :

1. **Suppression accidentelle** : un `DELETE` sans `WHERE` sur `patients` à un instant T ; restauration PITR à T−1 s ; mesurer le RTO.
2. **Perte du primaire** : arrêt brutal ; promotion de la réplique ; bascule de l'application ; mesurer le RTO et vérifier le RPO.
3. **Tentative d'intrusion** : injection SQL simulée depuis le rôle applicatif ; montrer qu'elle est bloquée (requêtes paramétrées) ou limitée (moindre privilège), et **détectée** (pgaudit + requête de détection).
4. **Saturation** : montée en connexions ; montrer l'effet d'un pooler ou des connexions réservées.

---

## 4. Grille de notation (/100)

| Critère | Points |
|---------|-------:|
| **Modélisation et déploiement** (schéma, types, partitionnement, jeu de données) | 12 |
| **Rôles et privilèges** (moindre privilège, propriété, héritage) | 12 |
| **Cloisonnement RLS** (trois règles correctes et testées) | 10 |
| **Sécurité réseau et TLS** (verify-full, pg_hba durci) | 10 |
| **Chiffrement et audit** (colonne/volume, pgaudit exploitable) | 10 |
| **Sauvegarde et PITR** (stratégie + démonstration mesurée) | 12 |
| **Haute disponibilité** (réplique + bascule démontrée) | 10 |
| **Performance** (plans avant/après, requêtes optimisées) | 8 |
| **Supervision et automatisation** (santé, cron, runbooks) | 8 |
| **Documentation et soutenance** (clarté, justification, démonstration) | 8 |
| **Bonus** : IaC (Ansible/Patroni/compose), pgBackRest, exporter Prometheus + Grafana, CI | +5 |

**Barème indicatif** : ≥ 85 excellent (prêt pour un stage DBA) ; 70–84 solide ; 55–69 acceptable avec lacunes ; < 55 à retravailler.

---

## 5. Livrables

```
projet-cliniquenord/
├── README.md                    # comment déployer et tester, prérequis
├── docs/
│   ├── architecture.md          # dossier d'architecture
│   ├── modele-menaces.md        # analyse de risques
│   ├── matrice-privileges.md    # qui a accès à quoi
│   └── journal-resilience.md    # tests PITR/failover, RTO/RPO mesurés
├── sql/
│   ├── 01_schema.sql
│   ├── 02_donnees_test.sql
│   ├── 03_roles_privileges.sql
│   ├── 04_rls.sql
│   ├── 05_fonctions.sql
│   └── 06_index.sql
├── securite/
│   ├── pg_hba.conf
│   ├── postgresql_securite.conf
│   ├── pgaudit.conf
│   └── tls/                      # procédure de génération (pas les clés privées !)
├── exploitation/
│   ├── sauvegarde.sh
│   ├── verifier_sante.sh
│   ├── supervision.sql
│   └── runbooks/
│       ├── perte-primaire.md
│       └── disque-plein-wal.md
└── runbooks-demo/               # captures ou journaux des démonstrations
```

> 🔐 Ne **jamais** committer de clé privée, de mot de passe ou de vraies données. Fournir des exemples (`.example`) et un `.gitignore`. C'est un critère d'évaluation.

---

## 6. Conseils

- Avance **module par module** : chaque lot correspond à un module déjà étudié ; reprends les TP.
- **Documente au fil de l'eau**, pas à la fin.
- **Mesure** tes RTO/RPO réels : c'est ce qui distingue une architecture affirmée d'une architecture prouvée.
- Sur la sécurité (ton domaine), pousse le modèle de menaces et la détection : c'est là que tu peux te démarquer.
- Fais une **répétition** de la démonstration de résilience : une bascule ratée en direct s'anticipe en la testant trois fois avant.

Bon projet.
