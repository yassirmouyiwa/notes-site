---
title: Parcours DevSecOps — sommaire
date: 2026-09-20
tags: devsecops, parcours, embarque
description: Parcours d'auto-formation en 15 modules pour passer de la cybersécurité et des systèmes embarqués au DevSecOps : pipeline, supply chain, conformité.
---

# Parcours DevSecOps — de la cybersécurité / systèmes embarqués vers le DevSecOps

Parcours d'auto-formation pas à pas, écrit pour **quelqu'un qui a déjà des bases en
cybersécurité et en systèmes embarqués** (ENSA Tétouan) et qui veut ajouter la partie
« industrialisation » : CI/CD, automatisation des contrôles de sécurité, supply chain,
conformité (CRA, IEC 62443).

L'objectif n'est pas de devenir développeur web : c'est d'être capable de **construire une
chaîne de build/déploiement dans laquelle la sécurité est automatisée**, y compris pour du
firmware.

---

## Comment utiliser ce dossier

1. Un module = un fichier `.md` = **1 semaine** (environ 6–10 h).
2. Chaque module a la même structure :
   - **Objectifs** — ce que tu dois savoir faire à la fin
   - **Théorie utile** — le minimum, pas un cours magistral
   - **Outils** — ce qu'on installe et pourquoi
   - **Lab** — manipulation concrète, commandes réelles
   - **Critères de validation** — tu passes au module suivant quand c'est coché
   - **Pièges / erreurs classiques**
   - **Pour aller plus loin**
3. **Ne lis pas sans faire le lab.** Le DevSecOps se mesure en pipelines qui tournent, pas en
   fiches de lecture.
4. Les livrables des labs vont dans `labs/` (un sous-dossier par module).

## Machine de travail (état au 2026-09-20)

| Élément | État | Conséquence |
|---|---|---|
| Fedora 44 | OK | `dnf` pour tout installer |
| `podman` | installé | on utilise **podman** partout, pas docker (`alias docker=podman` marche à 95 %) |
| `python3` | installé, **pip absent en système** | toujours créer un venv : `python3 -m venv .venv && .venv/bin/pip install ...` |
| `gcc`, `make`, `cmake`, `qemu` | **absents** | à installer au module 04 (`sudo dnf install ...`) |
| `git` + `gh` | installés et configurés | les labs CI se font sur GitHub Actions |
| `sudo` | **ne marche pas via Claude Code** (pas de TTY) | ouvre un vrai terminal pour les installs root |

## Plan du parcours

### Socle (semaines 1–3)
| # | Module | Cœur du sujet |
|---|---|---|
| 00 | [Prérequis et mise en place](00-prerequis.md) | Linux, Git, conteneurs, ce qu'il faut savoir avant |
| 01 | [Fondamentaux DevSecOps](01-fondamentaux-devsecops.md) | Culture, shift-left, cycle de vie, modèle de menace du pipeline |
| 02 | [Git et sécurité du code](02-git-securite-du-code.md) | Hygiène Git, secrets, signature, protection de branche |

### Automatisation (semaines 4–8)
| # | Module | Cœur du sujet |
|---|---|---|
| 03 | [CI/CD : bases](03-cicd-bases.md) | GitHub Actions, runners, artefacts, gates |
| 04 | [SAST — analyse statique](04-sast-analyse-statique.md) | Semgrep, CodeQL, clang-tidy, MISRA, flags de durcissement C |
| 05 | [SCA, CVE et SBOM](05-sca-dependances-sbom.md) | Syft/Grype, CycloneDX, CVE check Yocto/Buildroot |
| 06 | [Gestion des secrets](06-gestion-des-secrets.md) | SOPS/age, Vault, OIDC, clés dans le firmware, TPM/SE |
| 07 | [Sécurité des conteneurs](07-conteneurs-securite.md) | Durcissement d'image, Trivy, signature Cosign |
| 08 | [DAST et fuzzing](08-dast-et-fuzzing.md) | ZAP, nuclei, AFL++/libFuzzer, fuzzing de protocole embarqué |

### Infrastructure et embarqué (semaines 9–11)
| # | Module | Cœur du sujet |
|---|---|---|
| 09 | [IaC et durcissement système](09-iac-et-durcissement.md) | Ansible/Terraform, Checkov, CIS, durcissement noyau |
| 10 | [Supply chain du firmware](10-embarque-supply-chain.md) | **Le module clé pour toi** : Yocto/Buildroot, secure boot, OTA signé, builds reproductibles |
| 11 | [Runtime, détection et réponse](11-runtime-monitoring.md) | Logs, Wazuh/Falco, auditd, incident response |

### Cadre et synthèse (semaines 12–14)
| # | Module | Cœur du sujet |
|---|---|---|
| 12 | [Normes et conformité](12-normes-et-conformite.md) | CRA européen, IEC 62443, ISO 21434, SSDF, SLSA, OWASP SAMM |
| 13 | [Projet final](13-projet-final.md) | Pipeline complet sur un projet embarqué |
| 14 | [Ressources, certifs, veille](14-ressources-certifications.md) | Quoi lire, quoi passer, comment rester à jour |
| 99 | [Checklists](99-checklists.md) | Aide-mémoire à garder ouvert |

## Suivi de progression

- [ ] 00 Prérequis
- [ ] 01 Fondamentaux
- [ ] 02 Git et code
- [ ] 03 CI/CD
- [ ] 04 SAST
- [ ] 05 SCA / SBOM
- [ ] 06 Secrets
- [ ] 07 Conteneurs
- [ ] 08 DAST / fuzzing
- [ ] 09 IaC / durcissement
- [ ] 10 Supply chain firmware
- [ ] 11 Runtime
- [ ] 12 Normes
- [ ] 13 Projet final
- [ ] 14 Suite

## Ce que tu sauras faire à la fin

- Écrire un pipeline GitHub Actions qui **casse le build** sur secret commité, CVE critique,
  vulnérabilité SAST ou image non signée.
- Produire un **SBOM** CycloneDX pour une image firmware et le confronter à la base CVE.
- Mettre en place une chaîne **secure boot + mise à jour OTA signée** et la tester en CI.
- Justifier tes choix face aux exigences du **Cyber Resilience Act** et de l'**IEC 62443-4-1**.
