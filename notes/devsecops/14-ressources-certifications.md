---
title: DevSecOps 14 · Ressources, certifications, veille
date: 2026-09-20
tags: devsecops, ressources, certifications
description: Livres, plateformes de pratique, certifications qui valent le coup pour un profil embarqué, dispositif de veille et état du marché.
---

# Module 14 — Ressources, certifications et veille

> À lire en continu, pas en une fois.

## Livres

**Fondations DevSecOps**
- *Securing DevOps* — Julien Vehent. Le plus concret du domaine, écrit par un praticien.
- *The DevOps Handbook* — Kim, Humble, Debois, Willis. Le « pourquoi ».
- *Accelerate* — Forsgren, Humble, Kim. Les métriques DORA, et leur justification empirique.
- *Building Secure and Reliable Systems* — Google (gratuit en PDF). Le meilleur sur la sécurité
  vue comme une propriété d'ingénierie.

**Embarqué et matériel**
- *The Hardware Hacking Handbook* — Jasper van Woudenberg, Colin O'Flynn. Attaques matérielles,
  glitching, canaux auxiliaires. Indispensable pour comprendre ce que le secure boot protège.
- *Practical IoT Hacking* — Chantzis et al. Méthodologie offensive complète sur objets connectés.
- *Practical Hardware Pentesting* — Jean-Georges Valle.
- *Embedded Systems Security* — Kleidermacher.

**Code et exploitation**
- *The Art of Software Security Assessment* — Dowd, McDonald, Schuh. Ancien mais inégalé sur
  l'audit de code C.
- *Hacking: The Art of Exploitation* — Erickson.

## En ligne

| Ressource | Pourquoi |
|---|---|
| OWASP DevSecOps Guideline | vue d'ensemble structurée, gratuite |
| OWASP Cheat Sheet Series | réponses courtes et justes, à garder en favori |
| *The Fuzzing Book* | théorie + code, gratuit |
| Yocto Project Security Manual | le seul document officiel sérieux sur le sujet |
| OpenSSF (guides, Scorecard) | les guides de durcissement compilateur et de supply chain |
| NIST SP 800-218, SLSA.dev | les cadres à citer |
| ENISA — guides CRA | pour la partie réglementaire |

## Chaînes et blogs

- **LiveOverflow** — le meilleur pédagogue en sécurité bas niveau
- **stacksmashing** — hacking matériel, très pratique
- **Colin O'Flynn / NewAE** — canaux auxiliaires et glitching
- **Quarkslab blog** — recherche française, souvent embarqué
- **Synacktiv blog** — exploitation, IoT, très technique
- **Google Project Zero** — pour voir à quoi ressemble une analyse de haut niveau

## Pratique

| Plateforme | Contenu |
|---|---|
| **Hack The Box** (pistes IoT/hardware) | tu as déjà un compte HackerOne, le réflexe est là |
| **Microcorruption** | exploitation de firmware MSP430 dans le navigateur — excellent, gratuit |
| **Damn Vulnerable IoT Device (DVID)** | firmware volontairement vulnérable |
| **IoTGoat** | l'équivalent OWASP Juice Shop pour l'IoT |
| **picoCTF**, **CTFtime** (catégories hardware/rev) | entraînement régulier |
| **Google/OSS-Fuzz** | contribuer un harnais de fuzz à un projet réel = ligne de CV forte |

Conseil concret : contribuer **un** correctif de sécurité à un projet open source embarqué
(Zephyr, U-Boot, mbedTLS, Buildroot, Yocto) vaut plus qu'une certification de plus.

## Certifications

### Utiles pour ton profil

| Certification | Coût indicatif | Valeur |
|---|---|---|
| **Certified DevSecOps Professional (CDP)** — Practical DevSecOps | ~€1000 | 100 % pratique, orienté pipeline, très aligné avec ce parcours |
| **OSCP** — OffSec | ~€1600 | la référence offensive ; ouvre des portes partout |
| **eWPTX / eCPPT** — INE | ~€400 | bon rapport qualité/prix, pratique |
| **GIAC GRID / GICSP** | cher (>€7000) | référence en ICS/OT ; à viser si ton employeur paie |
| **ISA/IEC 62443 Cybersecurity Specialist** | ~€1000 | **très pertinent** pour l'industriel embarqué |
| **CKS** (Kubernetes Security) | ~€400 | seulement si tu vas vers le cloud |

### À relativiser

- **CEH** : peu de valeur technique, encore demandée par certains RH.
- **CISSP** : management, 5 ans d'expérience requis. Plus tard, si tu vises un poste RSSI.

### Ordre recommandé pour toi

1. Ce parcours + le projet final (gratuit, et c'est le plus convaincant)
2. Une contribution open source visible
3. **OSCP** si tu veux garder une identité offensive forte
4. **IEC 62443 Specialist** si tu vises l'industriel au Maroc/Europe
5. CDP si un employeur finance

## Veille : le dispositif minimal

**Quotidien (15 min)**
- Flux RSS : Yocto security, oss-security (seclists.org), advisories des composants de ton SBOM
- CISA KEV (nouvelles entrées) — c'est la seule liste vraiment urgente

**Hebdomadaire (1 h)**
- Blogs de recherche (Quarkslab, Synacktiv, Project Zero)
- Notes de version des outils de ton pipeline

**Mensuel (2 h)**
- Un sujet nouveau creusé à fond (post-quantique, eBPF, confidential computing…)
- Relecture de ta matrice de conformité et de tes exceptions CVE datées

**Automatise** : `dependabot`/`renovate` sur les dépôts, alertes GitHub, rescan quotidien du SBOM
(module 05). Ce qui n'est pas automatisé n'est pas fait.

## Communautés

- **OWASP chapitre local** (Maroc, ou en ligne)
- Conférences : **SSTIC** (Rennes, très technique, en français), **Hardwear.io**, **Troopers**,
  **Black Alps**, **CanSecWest**. Les vidéos sont souvent en ligne gratuitement.
- Meetups embarqué / Yocto, listes de diffusion Zephyr et Buildroot

## Le marché — où atterrir

| Poste | Ce qu'on attend | Ton atout |
|---|---|---|
| **Product Security Engineer** (IoT/embarqué) | sécuriser un produit de bout en bout | ✓✓✓ profil exact |
| **DevSecOps Engineer** | pipeline, cloud, conteneurs | ✓✓ (ajoute du cloud) |
| **Security Architect embarqué** | secure boot, crypto, normes | ✓✓✓ après 3–5 ans |
| **Pentester IoT/hardware** | offensif matériel | ✓✓ si tu accentues l'offensif |
| **Consultant conformité CRA/62443** | audit, documentation, accompagnement | ✓✓ marché en forte croissance 2026-2027 |

Le CRA crée une demande forte et récente pour des gens capables de faire **et** de documenter.
Peu de monde sait faire les deux : c'est précisément l'intersection que ce parcours construit.

## Ce qui te manquera encore après ce parcours

Sois lucide, ça se sent en entretien :

- **Le cloud à l'échelle** : Kubernetes, IAM, architecture multi-comptes. Si tu vises du cloud,
  ajoute un parcours dédié.
- **L'expérience de l'incident réel** : rien ne remplace une vraie crise vécue.
- **La conduite du changement** : convaincre une équipe qui ne veut pas de gates. C'est souvent
  la partie la plus difficile du métier, et elle n'est pas technique.
- **La cryptographie appliquée en profondeur** : si tu implémentes du crypto, il te faut bien
  plus que ce parcours (et la règle reste : n'implémente pas ta propre crypto).
