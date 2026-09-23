# Annexe C — Checklist de durcissement

Liste de contrôle de sécurité, inspirée du **CIS Benchmark for PostgreSQL** et adaptée à cette formation. À parcourir avant toute mise en production, puis périodiquement en audit. Le script `scripts/sql/audit_securite.sql` automatise une partie de ces vérifications.

Cocher chaque point : `[ ]` à faire · `[x]` fait · `s/o` sans objet.

---

## 1. Installation et système hôte

- [ ] PostgreSQL installé depuis une source de confiance (dépôt officiel PGDG).
- [ ] Version **supportée** (pas en fin de vie) et à jour des versions mineures.
- [ ] Serveur **dédié** à la base : aucun autre service exposé sur la même machine.
- [ ] Système d'exploitation à jour, SELinux ou AppArmor actif.
- [ ] Compte système `postgres` sans shell interactif inutile ; pas de connexion directe.
- [ ] `PGDATA` en permissions `0700`, propriété `postgres`.
- [ ] `vm.overcommit_memory = 2` pour protéger le postmaster de l'OOM killer.
- [ ] Horloge synchronisée (NTP) — indispensable pour la corrélation des journaux.

## 2. Réseau

- [ ] Pare-feu n'autorisant le port 5432 qu'aux adresses des serveurs applicatifs.
- [ ] `listen_addresses` limité aux interfaces nécessaires (jamais `*` sans pare-feu strict).
- [ ] Base non joignable depuis Internet (réseau privé / VPN).
- [ ] Endpoint de supervision (exporter) sur un réseau d'administration séparé.

## 3. Authentification (`pg_hba.conf`)

- [ ] Aucune règle `trust` (hors socket local jetable de dépannage).
- [ ] Aucune règle `password` (mot de passe en clair).
- [ ] Aucune règle `md5` : tout en `scram-sha-256` (ou `cert`, `ldap`, `gss`).
- [ ] `hostssl` (et non `host`) pour tous les accès réseau.
- [ ] Règles ordonnées du plus spécifique au plus général.
- [ ] Adresses restreintes au plus juste (`/32` quand c'est possible).
- [ ] Ligne finale `reject` explicite pour tout le reste.
- [ ] `password_encryption = scram-sha-256`.
- [ ] Authentification par **certificat** pour les rôles applicatifs sensibles (idéal).

## 4. Rôles et privilèges

- [ ] Un seul (ou très peu de) superutilisateur(s), nominatif(s), jamais utilisé(s) par une application.
- [ ] Aucune application connectée en superutilisateur ni propriétaire des objets.
- [ ] Objets possédés par un rôle `NOLOGIN` dédié.
- [ ] Rôles de connexion **nominatifs** (traçabilité), hérités de rôles de groupe.
- [ ] Moindre privilège : chaque rôle n'a que les droits nécessaires (jusqu'au niveau colonne si besoin).
- [ ] `REVOKE` des privilèges de `PUBLIC` sur le schéma `public` et les objets sensibles.
- [ ] Aucun rôle applicatif membre de `pg_read_server_files`, `pg_write_server_files`, `pg_execute_server_program`.
- [ ] Aucun rôle applicatif avec `SUPERUSER`, `REPLICATION`, `CREATEROLE`, `CREATEDB` ou `BYPASSRLS` non justifié.
- [ ] `CONNECTION LIMIT` et `VALID UNTIL` pour les comptes temporaires.
- [ ] `search_path` maîtrisé (pas de schéma modifiable par tous en tête).

## 5. Cloisonnement des données

- [ ] RLS activée et testée sur les tables multi-locataires / sensibles.
- [ ] Vues exposant uniquement les colonnes nécessaires aux rôles applicatifs.
- [ ] Fonctions `SECURITY DEFINER` conformes aux quatre règles (search_path figé, entrées validées, noms qualifiés, `EXECUTE` retiré à `PUBLIC`).

## 6. Chiffrement

- [ ] **TLS activé** (`ssl = on`), certificat serveur signé par une CA de confiance.
- [ ] Clé privée serveur en `0600`, propriété `postgres`.
- [ ] `ssl_min_protocol_version = 'TLSv1.2'` (ou supérieur).
- [ ] Clients configurés en `sslmode=verify-full` (pas `require`).
- [ ] Chiffrement du volume de données (LUKS / volume cloud) contre le vol physique.
- [ ] Colonnes très sensibles chiffrées (pgcrypto) **avec gestion des clés hors base**.
- [ ] Mots de passe applicatifs **hachés** (bcrypt), jamais chiffrés de façon réversible.

## 7. Audit et journalisation

- [ ] `log_connections` et `log_disconnections` activés.
- [ ] `log_statement = 'ddl'` (au minimum) ; `log_line_prefix` complet (avec `%u`, `%d`, `%h`).
- [ ] `log_min_duration_statement` réglé pour repérer les requêtes lentes.
- [ ] `log_file_mode = 0600` ; rotation configurée.
- [ ] **pgaudit** installé et configuré (classes `ddl, role, write`, plus `read` sur les données sensibles).
- [ ] Journaux exportés vers un **SIEM** avec règles de détection et alertes.
- [ ] Traçabilité métier (colonnes ou table d'historique) pour les données réglementées.

## 8. Sauvegarde et disponibilité

- [ ] Stratégie de sauvegarde documentée respectant le RPO/RTO cibles.
- [ ] Sauvegardes **chiffrées** et **vérifiées** (`pg_verifybackup`).
- [ ] Sauvegardes stockées **hors du serveur** de production (isolement, immuabilité contre les rançongiciels).
- [ ] **Test de restauration** régulier et daté (une sauvegarde non testée n'existe pas).
- [ ] PITR opérationnel (archivage WAL) et runbook rédigé.
- [ ] Réplication en place si la disponibilité l'exige ; bascule testée.
- [ ] `max_slot_wal_keep_size` défini pour éviter la saturation par un slot abandonné.

## 9. Limitation des dégâts

- [ ] `statement_timeout` par rôle applicatif.
- [ ] `idle_in_transaction_session_timeout` défini.
- [ ] `lock_timeout` défini.
- [ ] `superuser_reserved_connections` réservé à l'administration.
- [ ] Pooler de connexions (PgBouncer) devant l'application.

## 10. Conformité et gouvernance

- [ ] Registre des traitements de données personnelles (loi 09-08 / RGPD).
- [ ] Durées de conservation définies et appliquées (purge, partitionnement).
- [ ] Procédure d'effacement couvrant aussi WAL, archives et sauvegardes après rétention.
- [ ] Données de production **jamais** utilisées telles quelles en développement (masquage / pseudonymisation).
- [ ] Procédure d'incident et de notification de violation.
- [ ] Accès et actions des administrateurs journalisés.

## 11. Vérification finale

- [ ] `scripts/sql/audit_securite.sql` exécuté, tous les points critiques et élevés traités.
- [ ] `SELECT * FROM pg_hba_file_rules WHERE error IS NOT NULL;` → aucune erreur.
- [ ] `SELECT * FROM pg_file_settings WHERE error IS NOT NULL;` → aucune erreur.
- [ ] Test d'intrusion basique réalisé dans le lab (exposition, méthodes d'auth, injection).
- [ ] Documentation d'architecture et runbooks à jour.

---

> Le durcissement n'est pas un état mais un **processus** : à re-vérifier à chaque montée de version, changement d'architecture ou nouvel usage.
