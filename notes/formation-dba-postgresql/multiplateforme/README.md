# Volet multiplateforme — Fedora / RHEL et Windows

La formation (modules 00 à 11, à la racine) est écrite pour **Debian/Ubuntu**. Ce dossier permet de la suivre **aussi sur Fedora/RHEL et sur Windows**, sans rien perdre.

## Pourquoi seulement quelques fichiers, et pas 12 modules × 3

Parce que **l'immense majorité de la formation est indépendante du système** : tout le SQL, les rôles, la sécurité applicative, MVCC, la sauvegarde logique, la supervision par les vues `pg_stat_*`, `psql` et ses méta-commandes sont **identiques partout**. Ce qui change tient à l'installation, aux **chemins de fichiers**, à la **gestion du service** et à quelques outils. Ces différences sont rassemblées ici plutôt que dupliquées douze fois.

## Ordre de lecture

1. **`equivalences-plateformes.md`** — la **table de traduction centrale** : pour chaque chemin ou commande Debian cité dans un module, l'équivalent Fedora et Windows. Garde-la ouverte pendant toute la formation.
2. Selon ton système :
   - **Fedora/RHEL** : `lab-fedora.md` (mise en place, équivalent du module 00) puis `config-fedora.md` (spécificités du module 02).
   - **Windows** : `lab-windows.md` (mise en place, équivalent du module 00) puis `config-windows.md` (spécificités du module 02).
3. Puis **suis les modules 01 à 11 à la racine**, en traduisant chemins et commandes avec la table.

## Scripts

| Script | Debian/Ubuntu & Fedora | Windows |
|--------|------------------------|---------|
| Contrôle de santé | `scripts/bash/verifier_sante.sh` | `scripts/powershell/verifier_sante.ps1` |
| Sauvegarde logique chiffrée | `scripts/bash/sauvegarde_logique.sh` | `scripts/powershell/sauvegarde_logique.ps1` |
| Requêtes de supervision | `scripts/sql/requetes_supervision.sql` — **portable, identique partout** | idem |
| Audit de sécurité | `scripts/sql/audit_securite.sql` — **portable, identique partout** | idem |

Les deux scripts **bash** tournent tels quels sur **Fedora** (Linux) ; seuls les chemins de journaux et l'hôte par défaut peuvent différer (voir la table). Sur **Windows**, utilise les versions **PowerShell** fournies. Les scripts **SQL** et les fichiers de **configuration** (`scripts/config/`) sont valables partout ; seuls les chemins cités en commentaire changent.

> Les deux `.ps1` ont été rédigés avec soin mais **n'ont pas pu être exécutés** dans l'environnement de préparation (pas de Windows disponible) : teste-les sur ton poste avant tout usage réel. Les scripts bash et SQL, eux, ont été testés sur PostgreSQL 16.

## L'option la plus simple pour apprendre : Docker

`scripts/lab/docker-compose.yml` fournit exactement le même environnement sur les trois systèmes (Docker Desktop sur Windows, moteur natif sur Fedora). Idéal pour l'apprentissage ; en production, tu retrouveras les spécificités de ton OS — d'où l'utilité de la table d'équivalence.
