# Annexe F — Ressources pour aller plus loin

Sélection de ressources fiables pour approfondir. Privilégie toujours la **documentation officielle**, qui fait autorité et suit la version.

---

## Documentation officielle

- **Documentation PostgreSQL** — `https://www.postgresql.org/docs/` — la référence absolue, par version. Chapitres particulièrement utiles après cette formation : *Server Administration*, *Client Authentication*, *Backup and Restore*, *High Availability*, *Monitoring*, *Performance Tips*.
- **Notes de version** (*Release Notes*) — `https://www.postgresql.org/docs/release/` — à lire avant toute montée de version majeure (changements incompatibles).
- **Wiki PostgreSQL** — `https://wiki.postgresql.org/` — pages pratiques (*Don't Do This*, *Slow Query Questions*, *Number Of Database Connections*).

## Compréhension interne (architecture)

- **The Internals of PostgreSQL** (Hironobu Suzuki) — `https://www.interdb.jp/pg/` — explication visuelle et progressive du fonctionnement interne (MVCC, WAL, VACUUM, processus). Gratuit, excellent pour consolider les modules 01, 03, 05.
- **PostgreSQL 14 Internals** (Egor Rogov, Postgres Pro) — livre PDF **gratuit** — plongée approfondie dans MVCC, l'indexation, le planificateur, le WAL. Le complément idéal pour qui veut aller au fond.

## Ressources francophones

- **Dalibo** — `https://www.dalibo.com/formations` — supports de formation en **français**, très complets et régulièrement mis à jour (souvent sous licence libre). Blog technique de qualité.
- **PostgreSQL.fr** — `https://docs.postgresql.fr/` — documentation officielle **traduite en français**.

## Performance et indexation

- **Use The Index, Luke!** (Markus Winand) — `https://use-the-index-luke.com/` — tout sur l'indexation SQL et l'optimisation des requêtes, applicable à PostgreSQL. Pédagogique.
- **explain.dalibo.com** — `https://explain.dalibo.com/` — visualiseur de plans `EXPLAIN` : colle ton plan, il met en évidence les nœuds coûteux. Indispensable pour le module 07.
- **PGMustard** / **pgMustard glossary** — ressources sur la lecture des plans d'exécution.

## Sauvegarde et haute disponibilité

- **pgBackRest** — `https://pgbackrest.org/` — l'outil de référence pour la sauvegarde physique, le PITR et la restauration parallèle. Documentation exemplaire.
- **Patroni** — `https://patroni.readthedocs.io/` — gestion automatisée du basculement (failover) avec consensus distribué. Pour le module 08 en production.
- **repmgr** — `https://www.repmgr.org/` — alternative de gestion de réplication et de bascule.
- **CloudNativePG** — `https://cloudnative-pg.io/` — opérateur Kubernetes pour PostgreSQL (déploiement déclaratif, HA).

## Sécurité (ton domaine)

- **CIS Benchmark for PostgreSQL** — `https://www.cisecurity.org/benchmark/postgresql` — référentiel de durcissement détaillé et reconnu ; base de l'annexe C.
- **pgaudit** — `https://www.pgaudit.org/` — extension d'audit ; documentation de configuration.
- **PostgreSQL Anonymizer** (`anon`) — `https://postgresql-anonymizer.readthedocs.io/` — masquage et pseudonymisation des données (conformité).
- **OWASP** — `https://owasp.org/` — *Top 10*, *SQL Injection Prevention Cheat Sheet*, *Database Security Cheat Sheet* : la référence applicative sur l'injection et la défense en profondeur.
- **STIG PostgreSQL** (DISA) — guides de durcissement complémentaires au CIS.
- **CNDP** (Maroc) — `https://www.cndp.ma/` — autorité de la loi 09-08 sur la protection des données personnelles.

## Supervision

- **postgres_exporter** — `https://github.com/prometheus-community/postgres-exporter` — export des métriques vers Prometheus.
- **pgBadger** — `https://github.com/darold/pgbadger` — analyse des journaux en rapport HTML.
- **check_postgres** — `https://bucardo.org/check_postgres/` — contrôles pour Nagios/Icinga.
- **pgwatch** — supervision clé en main avec tableaux de bord.

## Extensions utiles à connaître

- **pg_stat_statements** (module contrib) — statistiques par requête ; incontournable.
- **pgcrypto** (module contrib) — fonctions de chiffrement/hachage.
- **pg_partman** — `https://github.com/pgpartman/pg_partman` — gestion automatisée des partitions.
- **pg_cron** — `https://github.com/citusdata/pg_cron` — planification de tâches en base.
- **PostGIS** — `https://postgis.net/` — données géospatiales (si besoin métier).
- **TimescaleDB** — séries temporelles à grande échelle.

## Communauté et veille

- **Listes de diffusion PostgreSQL** — `https://www.postgresql.org/list/` — notamment *pgsql-general* et *pgsql-admin*.
- **Planet PostgreSQL** — `https://planet.postgresql.org/` — agrégateur des blogs de la communauté ; bonne veille technique.
- **Annonces de sécurité** — `https://www.postgresql.org/support/security/` — CVE et correctifs ; à suivre pour la gestion des vulnérabilités (module 09).
- **pgexercises.com** — `https://pgexercises.com/` — exercices SQL interactifs pour entretenir la pratique.

---

## Suggestion de parcours après la formation

1. Consolider l'**interne** avec Suzuki puis Rogov (MVCC, WAL, planificateur).
2. Approfondir la **performance** avec *Use The Index, Luke!* et explain.dalibo.com sur tes propres requêtes.
3. Monter une **HA réelle** avec Patroni + pgBackRest dans ton lab.
4. Sur ta spécialité, dérouler le **CIS Benchmark** et l'**OWASP** de bout en bout sur ton instance, puis mettre en place pgaudit + un SIEM (Wazuh/Elastic).
5. Contribuer ou suivre la communauté (Planet PostgreSQL, listes) pour rester à jour.
