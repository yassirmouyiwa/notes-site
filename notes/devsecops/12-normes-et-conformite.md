---
title: DevSecOps 12 · Normes et conformité
date: 2026-09-20
tags: devsecops, cra, iec-62443
description: Cyber Resilience Act, IEC 62443-4-1, NIST SSDF : ce qui s'applique à un produit connecté vendu en Europe, et la matrice de conformité à tenir.
---

# Module 12 — Normes, réglementation et conformité

> Durée : 5–7 h. Objectif : savoir **nommer** ce que tu fais. C'est ce qui transforme un bon
> technicien en interlocuteur crédible face à un client, un auditeur ou un jury.

## Objectifs

- Connaître les textes qui s'appliquent à un produit connecté vendu en Europe.
- Faire correspondre chaque contrôle de ton pipeline à une exigence normative.
- Produire la documentation attendue (SBOM, analyse de risque, politique de divulgation).

## La carte des référentiels

```
RÉGLEMENTATION (obligatoire)
├── Cyber Resilience Act (UE) ───── produits avec éléments numériques   ⟵ te concerne
├── RED DA (UE) 2022/30 ─────────── équipements radio (art. 3.3 d/e/f)  ⟵ te concerne
├── NIS2 (UE) ───────────────────── opérateurs et entités essentielles
├── RGPD ────────────────────────── données personnelles
└── Loi 09-08 (Maroc) ───────────── protection des données personnelles

NORMES PRODUIT / PROCESSUS
├── IEC 62443 ──── automatismes industriels (-4-1 processus, -4-2 composant)  ⟵ te concerne
├── ISO/SAE 21434 ─ cybersécurité automobile
├── EN 18031 ───── norme harmonisée pour le RED DA
├── ETSI EN 303 645 ─ IoT grand public (baseline, très lisible)              ⟵ commence ici
├── IEC 62304 ──── logiciel de dispositif médical
└── ISO 27001 ──── management de la sécurité de l'information (organisation)

CADRES DE BONNES PRATIQUES (volontaires, très utiles)
├── NIST SSDF (SP 800-218) ── pratiques de développement sécurisé
├── SLSA ──────────────────── intégrité de la chaîne d'approvisionnement
├── OWASP SAMM / DSOMM ────── maturité
├── OWASP ASVS / MASVS ────── exigences de vérification applicative
└── CIS Controls ──────────── contrôles opérationnels
```

## Cyber Resilience Act — l'essentiel

Le texte qui change le métier pour un fabricant d'objets connectés en Europe.

**Calendrier** : entré en vigueur le 10 décembre 2024. Obligations de **notification** des
vulnérabilités activement exploitées à partir du **11 septembre 2026**. Application pleine le
**11 décembre 2027**.

**Portée** : tout produit comportant des éléments numériques mis sur le marché européen —
matériel *et* logiciel, y compris composants. Peu importe où tu le fabriques.

**Obligations principales** (annexe I) :

| Exigence | Ce que tu as déjà construit dans ce parcours |
|---|---|
| Sécurité par conception et par défaut | modules 01, 09 |
| Pas de vulnérabilité connue exploitable à la livraison | modules 04, 05 (gates CVE) |
| Configuration sécurisée par défaut, remise à l'état initial possible | module 09 |
| Protection contre les accès non autorisés | modules 06, 10 (secure boot, mTLS) |
| Confidentialité et intégrité des données | modules 06, 09 |
| Minimisation des données et de la surface d'attaque | modules 07, 09 |
| Journalisation des accès et événements de sécurité | module 11 |
| **Mises à jour de sécurité, si possible automatiques, gratuites** | module 10 (OTA) |
| **SBOM** des dépendances de premier niveau | module 05 |
| **Politique de divulgation coordonnée** | module 11 |
| **Période de support** ≥ 5 ans (ou durée de vie attendue) | organisation |
| Notification ENISA : **24 h** alerte, 72 h rapport, 14 j rapport final | module 11 |

**Sanctions** : jusqu'à 15 M€ ou 2,5 % du chiffre d'affaires mondial.

Point souvent mal compris : la période de support de 5 ans signifie que tu dois pouvoir
**reconstruire, corriger et redéployer** un firmware cinq ans après sa sortie. C'est
exactement pourquoi le build reproductible et l'environnement de build conteneurisé du module 07
ne sont pas du luxe.

## IEC 62443-4-1 — le processus, en 8 pratiques

Si tu vises l'industriel (ce qui est probable avec un profil embarqué au Maroc : automatisme,
énergie, automobile), c'est la norme à connaître.

| Pratique | Contenu | Où c'est dans ton pipeline |
|---|---|---|
| **SM** Gestion de la sécurité | rôles, formation, processus documenté | organisation |
| **SR** Spécification des exigences | exigences de sécurité écrites, modèle de menace | module 01 |
| **SD** Conception sécurisée | défense en profondeur, surface minimale | modules 09, 10 |
| **SI** Implémentation sécurisée | règles de codage, revue, SAST | modules 02, 04 |
| **SVV** Vérification et validation | tests de sécurité, fuzzing, pentest | modules 08, 10 |
| **DM** Gestion des défauts | triage, correction, suivi | module 11 |
| **SUM** Gestion des mises à jour | correctifs, distribution, vérification | module 10 |
| **SG** Directives de sécurité | documentation pour l'intégrateur et l'exploitant | à écrire |

Les niveaux **SL 1 à 4** (Security Level) qualifient la résistance visée : SL1 = erreur
accidentelle, SL2 = attaquant avec moyens faibles, SL3 = attaquant avec compétences et
ressources spécifiques ICS, SL4 = attaquant étatique. La plupart des produits industriels visent
SL2, parfois SL3.

## NIST SSDF (SP 800-218) — la grille la plus opérationnelle

4 groupes, ~40 pratiques. Parfait pour un tableau de correspondance :

| Groupe | Exemple de pratique | Preuve dans ton dépôt |
|---|---|---|
| **PO** Préparer l'organisation | PO.5 : environnements séparés et durcis | runner éphémère, modules 03, 07 |
| **PS** Protéger le logiciel | PS.2 : mécanisme de vérification d'intégrité | cosign, attestations (modules 07, 10) |
| **PW** Produire un logiciel sûr | PW.7 : revue et/ou analyse du code | CODEOWNERS + SAST (modules 02, 04) |
| **RV** Répondre aux vulnérabilités | RV.1 : identifier et confirmer en continu | rescan quotidien du SBOM (module 05) |

## Lab — matrice de conformité

Le livrable le plus utile de ce module. `labs/12-conformite/matrice.md` :

```markdown
| Exigence | Source | Contrôle mis en place | Preuve | Statut | Responsable | Revue |
|---|---|---|---|---|---|---|
| Pas de vulnérabilité connue à la livraison | CRA An.I §2(a) | Gate Grype/cve-check, seuil CVSS 7.0 | `.github/workflows/firmware.yml` L42, rapports archivés | ✅ | moi | 2027-03 |
| SBOM des dépendances | CRA An.I §2(1) | syft → CycloneDX, publié avec la release | `sbom-firmware.cdx.json` | ✅ | moi | 2027-03 |
| Divulgation coordonnée | CRA An.I §2(5) | security.txt + politique | `/.well-known/security.txt` | 🟡 rédigé, non publié | moi | 2026-11 |
| Mises à jour sécurisées | CRA An.I §1(2)(c) | RAUC, bundle signé, anti-rollback | test HIL `test_antirollback.py` | ✅ | moi | 2027-03 |
| Journalisation des accès | CRA An.I §1(2)(j) | logs JSON + export syslog TLS | `journal.py`, config rsyslog | 🟡 partiel | moi | 2026-12 |
| Revue de code | IEC 62443-4-1 SI-2 | PR obligatoire, CODEOWNERS | protection de branche | ✅ | moi | — |
| Modèle de menace | IEC 62443-4-1 SR-2 | STRIDE produit + pipeline | `labs/01-threat-model/` | 🟡 à mettre à jour | moi | 2026-10 |
```

Règles de rédaction :
1. Une ligne = une exigence **vérifiable**.
2. La colonne « preuve » pointe un fichier ou un identifiant de run, jamais « oui ».
3. 🟡 et ❌ assumés sont mieux vus en audit qu'un tableau tout vert non étayé.

## Critères de validation

- [ ] Tu expliques le CRA en 3 minutes : portée, calendrier, 5 obligations, sanctions
- [ ] Tu cites les 8 pratiques de l'IEC 62443-4-1
- [ ] Ta matrice couvre ≥ 15 exigences avec des preuves réelles
- [ ] Tu sais quelle norme s'applique à : un capteur LoRa industriel, un calculateur auto, une
      caméra grand public, une pompe à perfusion
- [ ] Tu distingues obligation réglementaire et bonne pratique volontaire

## Pièges classiques

- **Conformité en fin de projet** : c'est 10× plus cher. La matrice se remplit au fil de l'eau.
- **Documentation détachée du code** : si la doc vit ailleurs que le dépôt, elle devient fausse
  en 3 mois. Mets la matrice **dans** le dépôt, relue en PR.
- **Confondre certifié et sécurisé** : un produit certifié IEC 62443 mal exploité reste
  vulnérable.
- **Ignorer le CRA parce qu'on vend hors UE** : dès qu'un revendeur met le produit sur le marché
  européen, il s'applique.

## Pour aller plus loin

- Texte du CRA : règlement (UE) 2024/2847 — lire au moins l'annexe I, c'est court et concret
- ETSI EN 303 645 — 13 provisions, la meilleure porte d'entrée pour l'IoT
- ENISA — guides d'implémentation du CRA
- NIST SP 800-218 (SSDF) et NISTIR 8259 (IoT)
