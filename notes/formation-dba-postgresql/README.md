# Formation intensive — Administration de Bases de Données avec PostgreSQL

> Parcours complet du métier de DBA, de l'architecture interne jusqu'à la mise en production sécurisée.
> Public : étudiants ingénieurs (profil cybersécurité & systèmes embarqués).
> SGBD de référence : **PostgreSQL 16 ou plus récent**. Les modules sont écrits pour **Ubuntu/Debian**, mais un [volet multiplateforme](multiplateforme/README.md) permet de tout suivre sur **Fedora/RHEL** et **Windows**.

---

## Objectifs de la formation

À la fin du parcours, tu seras capable de :

1. Expliquer l'architecture interne d'un SGBD (processus, mémoire, fichiers, journal WAL).
2. Installer, configurer et dimensionner une instance PostgreSQL de production.
3. Gérer le stockage physique et logique (tablespaces, TOAST, partitionnement).
4. Concevoir un modèle de droits fondé sur le **moindre privilège** (rôles, RLS, privilèges par défaut).
5. Maîtriser les transactions, le MVCC, les verrous, le VACUUM et les niveaux d'isolation.
6. Mettre en place une stratégie de sauvegarde **testée** avec restauration à un instant donné (PITR).
7. Diagnostiquer et optimiser les performances (plans d'exécution, index, statistiques, paramètres).
8. Déployer une architecture haute disponibilité (réplication physique et logique, bascule).
9. **Sécuriser** une base de bout en bout : réseau, TLS, authentification, autorisation, injection SQL, chiffrement, audit, durcissement.
10. Superviser, automatiser et mettre à jour une plateforme PostgreSQL, et réagir aux incidents.

---

## Sommaire

| # | Fichier | Contenu | Durée indicative |
|---|---------|---------|------------------|
| 00 | [Mise en place du laboratoire](00-mise-en-place-du-lab.md) | VM, installation, jeu de données | 2 h |
| 01 | [Architecture et fondamentaux](01-architecture-et-fondamentaux.md) | Instance, processus, mémoire, WAL, cycle d'une requête | 6 h |
| 02 | [Installation et configuration](02-installation-et-configuration.md) | initdb, clusters, postgresql.conf, pg_hba.conf, journaux | 6 h |
| 03 | [Stockage physique et logique](03-stockage-physique-et-logique.md) | Fichiers, pages, TOAST, tablespaces, partitionnement | 7 h |
| 04 | [Utilisateurs, rôles et privilèges](04-utilisateurs-roles-privileges.md) | Rôles, GRANT, privilèges par défaut, RLS, SECURITY DEFINER | 8 h |
| 05 | [Transactions, concurrence et MVCC](05-transactions-concurrence-mvcc.md) | ACID, isolation, verrous, deadlocks, VACUUM, wraparound | 9 h |
| 06 | [Sauvegarde et restauration](06-sauvegarde-et-restauration.md) | pg_dump, pg_basebackup, archivage WAL, PITR, pgBackRest | 9 h |
| 07 | [Performance et optimisation](07-performance-et-optimisation.md) | EXPLAIN, index, statistiques, tuning, pg_stat_statements | 10 h |
| 08 | [Haute disponibilité et réplication](08-haute-disponibilite-replication.md) | Réplication physique/logique, slots, bascule, Patroni | 9 h |
| 09 | [Sécurité des bases de données](09-securite-des-bases-de-donnees.md) | Menaces, TLS, authentification, injection SQL, chiffrement, audit | 12 h |
| 10 | [Supervision et automatisation](10-supervision-et-automatisation.md) | Métriques, alertes, maintenance, montées de version, incidents | 8 h |
| 11 | [Projet final](11-projet-final.md) | Déploiement complet et sécurisé d'une plateforme | 15 h |

**Total indicatif : environ 100 heures** (cours + TP + projet).

### Annexes

| Fichier | Contenu |
|---------|---------|
| [A — Aide-mémoire](annexes/A-aide-memoire.md) | Commandes psql, SQL d'administration, outils en ligne de commande |
| [B — Glossaire](annexes/B-glossaire.md) | Définitions de tous les termes techniques |
| [C — Checklist de durcissement](annexes/C-checklist-durcissement.md) | Liste de contrôle sécurité prête à l'emploi |
| [D — Corrigés](annexes/D-corriges.md) | Corrigés de tous les quiz et exercices |
| [E — Examen blanc](annexes/E-examen-blanc.md) | Examen de synthèse avec corrigé |
| [F — Ressources](annexes/F-ressources.md) | Documentation, livres, outils pour aller plus loin |

### Scripts fournis

| Chemin | Rôle |
|--------|------|
| `scripts/sql/01_jeu_de_donnees_banque.sql` | Crée la base `banque` utilisée dans tous les TP (≈ 2 millions d'opérations) |
| `scripts/sql/requetes_supervision.sql` | Requêtes de supervision prêtes à l'emploi |
| `scripts/sql/audit_securite.sql` | Audit de sécurité automatisé d'une instance |
| `scripts/bash/sauvegarde_logique.sh` | Sauvegarde pg_dump chiffrée avec rotation et vérification |
| `scripts/bash/verifier_sante.sh` | Contrôle de santé au format Nagios/Icinga (codes de sortie 0/1/2) |
| `scripts/config/postgresql_durci.conf` | Extrait de configuration durcie commentée |
| `scripts/config/pg_hba_exemple.conf` | Exemple de pg_hba.conf de production commenté |
| `scripts/lab/docker-compose.yml` | Alternative Docker pour démarrer rapidement |
| `scripts/powershell/verifier_sante.ps1` | Contrôle de santé, version **Windows** (PowerShell) |
| `scripts/powershell/sauvegarde_logique.ps1` | Sauvegarde chiffrée, version **Windows** (PowerShell) |

### Multiplateforme — Fedora / RHEL et Windows

Les modules sont rédigés pour Ubuntu/Debian. Pour les suivre sur un autre système, commence par le [volet multiplateforme](multiplateforme/README.md) :

| Fichier | Contenu |
|---------|---------|
| [Équivalences entre plateformes](multiplateforme/equivalences-plateformes.md) | **Table centrale** : chaque chemin/commande Debian et son équivalent Fedora & Windows |
| [Lab Fedora](multiplateforme/lab-fedora.md) · [Config Fedora](multiplateforme/config-fedora.md) | Mise en place et spécificités du module 02 sur Fedora/RHEL |
| [Lab Windows](multiplateforme/lab-windows.md) · [Config Windows](multiplateforme/config-windows.md) | Mise en place et spécificités du module 02 sur Windows |

Le SQL, les concepts et `psql` sont identiques partout : seuls changent l'installation, les chemins et la gestion du service.

---

## Organisation de chaque module

Chaque module suit la même structure :

1. **Objectifs** — ce que tu dois savoir faire à la fin.
2. **Cours** — les notions, expliquées dans l'ordre logique.
3. **Encadrés « 🔐 Angle sécurité »** — l'impact des notions sur la sécurité, fil rouge de la formation.
4. **TP** — manipulations guidées, avec résultats attendus.
5. **Exercices** — à faire seul, corrigés en annexe D.
6. **Quiz** — auto-évaluation, corrigée en annexe D.
7. **À retenir** — synthèse en quelques lignes.

---

## Conventions

| Notation | Signification |
|----------|---------------|
| `$ commande` | Commande shell exécutée par ton utilisateur Linux |
| `# commande` ou `sudo commande` | Commande nécessitant les droits root |
| `postgres$ commande` | Commande exécutée en tant qu'utilisateur Linux `postgres` (`sudo -i -u postgres`) |
| `banque=#` | Invite psql, connecté en superutilisateur à la base `banque` |
| `banque=>` | Invite psql, connecté avec un rôle non superutilisateur |
| `16` dans les chemins | Numéro de version majeure : **remplace-le par ta version** (17, 18…) |
| **Session A / Session B** | Deux terminaux psql ouverts en parallèle (utilise `tmux`) |

---

## Planning intensif suggéré (4 semaines)

| Semaine | Contenu |
|---------|---------|
| 1 | Modules 00, 01, 02, 03 — bases solides, lab opérationnel |
| 2 | Modules 04, 05, 06 — droits, concurrence, sauvegarde (cœur du métier) |
| 3 | Modules 07, 08, 09 — performance, HA, sécurité |
| 4 | Module 10, examen blanc, projet final |

Conseil : **ne saute pas les TP**. Le métier de DBA s'apprend en cassant des choses dans un lab, puis en les réparant. Prends un snapshot de ta VM avant chaque module.

---

## Prérequis

- SQL de base : `SELECT`, jointures, `GROUP BY`, `INSERT/UPDATE/DELETE`, contraintes.
- Système : à l'aise en ligne de commande. Sous Ubuntu/Debian ou Fedora : navigation, droits de fichiers, `systemctl`, `sudo`. Sous Windows : PowerShell, services, variables d'environnement (voir le [volet multiplateforme](multiplateforme/README.md)).
- Réseau : adresses IP, ports, notion de TLS et de certificats.

---

## Avertissement

Les manipulations de sécurité (injection SQL, capture réseau, tests d'authentification) sont destinées **exclusivement à ton laboratoire** ou à des systèmes pour lesquels tu disposes d'une **autorisation écrite**. Tester un système tiers sans autorisation est illégal (au Maroc, articles 607-3 et suivants du Code pénal relatifs aux atteintes aux systèmes de traitement automatisé des données).
