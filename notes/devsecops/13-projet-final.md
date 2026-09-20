---
title: DevSecOps 13 · Projet final
date: 2026-09-20
tags: devsecops, projet, embarque
description: Assembler les 12 modules en une chaîne complète pour un capteur connecté : 11 gates, firmware signé, OTA, documentation, auto-évaluation.
---

# Module 13 — Projet final : pipeline DevSecOps complet pour un produit embarqué

> Durée : 15–25 h. Objectif : assembler les 12 modules en une seule chaîne qui tourne, et en
> faire une pièce de portfolio défendable en entretien.

## Le sujet

Tu construis la chaîne de livraison d'un **capteur environnemental connecté** :

```
[Carte STM32 ou ESP32 ou Raspberry Pi]
   ├── firmware C (acquisition, parseur de trames, pile de communication)
   ├── liaison chiffrée vers une passerelle
   └── mise à jour OTA signée
[Passerelle / backend]
   ├── API de collecte (Python/Go) en conteneur
   ├── stockage
   └── serveur de distribution des mises à jour
```

Si tu n'as pas de matériel : QEMU (`qemu-system-arm -M virt`) ou **Renode** suffisent pour tout
sauf le module 10 lab 5.

## Livrables

### 1. Dépôt `capteur-connecte`

```
capteur-connecte/
├── firmware/
│   ├── src/               # code C
│   ├── include/
│   └── tests/
│       ├── unitaires/
│       └── fuzz/          # harnais libFuzzer
├── backend/
│   ├── src/
│   ├── Containerfile      # multi-stage, distroless, non-root
│   └── requirements.txt   # avec hashes
├── build/
│   └── Containerfile.build  # toolchain épinglée par sha256
├── deploy/
│   ├── ansible/           # durcissement de la passerelle
│   └── terraform/         # infra du backend (optionnel)
├── secrets/               # chiffré SOPS
├── tools/
│   ├── gate-cve.py
│   ├── verifier-durcissement.py
│   └── verifier-reproductibilite.sh
├── docs/
│   ├── threat-model.md
│   ├── matrice-conformite.md
│   ├── plan-ir.md
│   ├── architecture.md
│   └── decisions/         # ADR : pourquoi tel choix
├── .github/workflows/
│   ├── ci.yml             # sur PR : rapide (< 10 min)
│   ├── release.yml        # sur tag : build signé + attestation
│   ├── nocturne.yml       # DAST, fuzzing long, rescan CVE
│   └── hil.yml            # tests sur matériel
├── .semgrep/
├── .gitleaks.toml
├── .pre-commit-config.yaml
├── SECURITY.md
└── README.md
```

### 2. Le pipeline, par étage

**Sur chaque PR (objectif : < 10 minutes)**

| Job | Outil | Gate |
|---|---|---|
| secrets | gitleaks | bloquant |
| lint workflows | actionlint + zizmor | bloquant |
| SAST | semgrep (règles maison incluses) | bloquant sur ERROR |
| SAST C | gcc -fanalyzer, cppcheck, clang-tidy | bloquant |
| build durci | flags de durcissement + checksec | bloquant |
| tests unitaires | + ASan/UBSan | bloquant |
| fuzz court | libFuzzer 60 s sur corpus en cache | bloquant si nouveau crash |
| SCA | grype sur SBOM | bloquant ≥ HIGH corrigeable |
| IaC | checkov, trivy config | bloquant |
| image | build + trivy | bloquant |

**Sur tag (release)**

| Job | Sortie |
|---|---|
| build reproductible | 2 builds, hashes comparés |
| SBOM | CycloneDX, archivé |
| signature | cosign sign-blob (keyless OIDC) |
| attestation | provenance SLSA |
| bundle OTA | RAUC/SWUpdate signé |
| notes de version | incluant les CVE corrigées |

**En nocturne**

| Job | Durée |
|---|---|
| fuzzing long | 2 h, corpus persistant |
| DAST ZAP + nuclei | 30 min |
| rescan CVE des versions **en production** | 5 min |
| test HIL complet | selon le banc |

**Tests de sécurité sur cible (les plus précieux)**

- [ ] une image non signée est refusée
- [ ] une image signée mais de version antérieure est refusée (anti-rollback)
- [ ] aucun shell n'est accessible sur l'UART
- [ ] `nmap` ne trouve que les ports attendus
- [ ] la coupure d'alimentation pendant une OTA laisse l'objet démarrable
- [ ] aucun identifiant par défaut ne fonctionne

### 3. Documentation

- `architecture.md` avec le diagramme de flux de données et les frontières de confiance
- `threat-model.md` : STRIDE sur le produit **et** sur le pipeline
- `matrice-conformite.md` : ≥ 15 exigences CRA / IEC 62443 avec preuves
- `plan-ir.md` : 2 pages
- `docs/decisions/` : une ADR par choix structurant (pourquoi RAUC et pas Mender, pourquoi
  ECDSA et pas RSA, pourquoi telle limite de CVSS)

### 4. README qui se défend en entretien

```markdown
# Capteur connecté — chaîne DevSecOps de bout en bout

## Ce que ce projet démontre
- Pipeline CI/CD avec 11 gates de sécurité automatisées, de la PR au firmware signé
- Chaîne de confiance complète : secure boot → firmware signé → OTA anti-rollback
- Build reproductible et attestation de provenance (SLSA niveau 2)
- Conformité tracée au Cyber Resilience Act (matrice de 18 exigences)

## Chiffres
- Durée du pipeline de PR : 7 min 30
- Vulnérabilités détectées et corrigées pendant le développement : 14 (dont 3 critiques)
- Couverture de fuzzing : 78 % du parseur de protocole
- Écart entre deux builds du même commit : 0 octet

## Ce que je ferais différemment à plus grande échelle
- Dependency-Track pour historiser les SBOM du parc
- Runners éphémères en conteneur (SLSA L3)
- HSM réseau au lieu d'une clé locale pour la signature de release
```

Cette dernière section — savoir dire les limites de son travail — est ce qui distingue un
candidat sérieux d'un candidat qui récite.

## Planning proposé (5 jours pleins ou 3 semaines à temps partiel)

| Étape | Contenu | Durée |
|---|---|---|
| 1 | Architecture, threat model, squelette du dépôt | 3 h |
| 2 | Firmware minimal + tests + harnais de fuzz | 5 h |
| 3 | Backend + Containerfile durci | 3 h |
| 4 | Pipeline PR complet (toutes les gates) | 6 h |
| 5 | Signature, SBOM, attestation, release | 4 h |
| 6 | OTA signée + anti-rollback | 4 h |
| 7 | Durcissement (Ansible, rootfs, noyau) | 3 h |
| 8 | Nocturne : DAST, fuzz long, rescan | 2 h |
| 9 | Documentation et matrice de conformité | 4 h |
| 10 | Nettoyage, README, démonstration enregistrée | 2 h |

## Grille d'auto-évaluation

| Critère | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| Gates de sécurité | aucune | quelques scans non bloquants | bloquantes sur le critique | bloquantes + exceptions datées |
| Secrets | en clair | `.gitignore` | chiffrés | OIDC, aucun secret statique |
| SBOM | absent | généré | archivé par release | rescanné quotidiennement |
| Signature | absente | signature de release | + vérification au déploiement | + attestation de provenance |
| Firmware | build manuel | build CI | + reproductible | + secure boot testé en CI |
| OTA | manuelle | automatisée | signée | anti-rollback + A/B + canary |
| Tests | unitaires | + intégration | + fuzzing | + tests de sécurité sur cible |
| Documentation | README | + architecture | + threat model | + matrice de conformité |

**24/24 n'est pas l'objectif.** Vise ≥ 16 et sache expliquer pourquoi les autres cases ne sont
pas prioritaires **pour ce produit** : c'est exactement la conversation d'un entretien senior.

## Comment le présenter

1. **Démo de 5 minutes, enregistrée** (asciinema ou vidéo) : tu pousses un commit contenant un
   défaut → le pipeline le refuse → tu corriges → la release est signée et vérifiée. Cette vidéo
   vaut plus que le dépôt lui-même, parce que personne ne lit un dépôt.
2. **Un article** sur ton blog (`~/blog`) : « Construire une chaîne DevSecOps pour un objet
   connecté ». Découpe-le en 3–4 parties.
3. **Le dépôt public**, propre, avec un README qui va droit au but.

## Idées de variantes selon ton orientation

| Orientation | Variante |
|---|---|
| Automobile | bus CAN + ISO 21434 + Uptane |
| Industriel / OT | Modbus/OPC-UA + IEC 62443 SL2 + segmentation réseau |
| Médical | IEC 62304 + traçabilité des exigences |
| Défense / souverain | ANSSI BP-028, crypto qualifiée, build hors ligne |
| Cloud/IoT | AWS IoT Core ou Azure IoT Edge, provisioning à grande échelle |
