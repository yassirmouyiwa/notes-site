---
title: DevSecOps 01 · Fondamentaux
date: 2026-09-20
tags: devsecops, threat-modeling, supply-chain
description: Où se placent les contrôles de sécurité dans un cycle de livraison, et comment modéliser la menace du pipeline lui-même (SolarWinds, Codecov, XZ).
---

# Module 01 — Fondamentaux DevSecOps

> Durée : 5–7 h. Objectif : comprendre où la sécurité s'insère dans un cycle de livraison, et
> savoir modéliser la menace **du pipeline lui-même**.

## Objectifs

- Expliquer DevOps → DevSecOps sans slogan marketing.
- Situer chaque contrôle de sécurité dans le cycle de vie (qui, quand, coût d'un défaut).
- Modéliser la menace d'une chaîne CI/CD.
- Traduire ton réflexe pentest en réflexe « gate automatisée ».

## Théorie utile

### 1. Le problème que DevSecOps résout

Modèle classique : dev pendant 6 mois → audit sécurité 2 semaines avant la mise en production →
rapport de 80 vulnérabilités → 6 sont corrigées, le reste passe en « risque accepté ».

Coût de correction d'un défaut selon le moment où il est trouvé (ordre de grandeur, NIST /
IBM SSE) :

| Trouvé en… | Coût relatif |
|---|---|
| Conception | 1× |
| Codage | 5× |
| Test / intégration | 10× |
| Production | 30–100× |
| **Firmware déjà déployé sur 50 000 objets** | **rappel matériel possible : 1000×+** |

La dernière ligne est ta réalité en embarqué : en web on redéploie en 3 minutes, sur une carte
en production on ne peut parfois **pas** corriger. D'où l'importance du « shift-left » pour toi
en particulier.

### 2. Les trois voies (Gene Kim, *The DevOps Handbook*)

1. **Flux** — du code vers la production, sans retour en arrière. Sécurité : les contrôles
   doivent être *dans* le flux, pas à côté.
2. **Feedback** — rapide, du plus en aval vers le plus en amont. Sécurité : le dev voit
   l'alerte en 3 minutes dans sa PR, pas dans un PDF 3 mois après.
3. **Apprentissage continu** — post-mortems sans blâme, expérimentation.

### 3. Où se placent les contrôles

```
IDÉE ──► CODE ──► BUILD ──► TEST ──► RELEASE ──► DEPLOY ──► RUN
  │        │        │         │         │          │         │
  │        │        │         │         │          │         └─ détection, IR, télémétrie,
  │        │        │         │         │          │            gestion de vulnérabilités
  │        │        │         │         │          └─ durcissement, IaC scan, secrets runtime
  │        │        │         │         └─ signature, SBOM, attestation, provenance
  │        │        │         └─ DAST, fuzzing, tests d'abus, HIL (hardware-in-the-loop)
  │        │        └─ SCA, SBOM, flags de compilation durcis, reproductibilité
  │        └─ SAST, secrets scanning, revue de code, pre-commit
  └─ threat modeling, exigences sécurité, choix d'architecture
```

Apprends ce schéma par cœur : chaque module suivant remplit une case.

### 4. Vocabulaire à ne plus confondre

| Terme | Ce que c'est | Ce que ce n'est pas |
|---|---|---|
| SAST | analyse du **code source** sans l'exécuter | une preuve d'exploitabilité |
| DAST | test de l'application **en fonctionnement** | une couverture exhaustive du code |
| SCA | analyse des **dépendances** et de leurs CVE | de l'analyse de ton code à toi |
| IAST | instrumentation à l'exécution | du SAST en temps réel |
| SBOM | **inventaire** des composants | un rapport de vulnérabilités |
| Fuzzing | génération d'entrées pour faire planter | un remplacement des tests unitaires |
| Gate | règle qui **bloque** le pipeline | un warning que personne ne lit |

### 5. Le pipeline est une surface d'attaque

C'est le point que les devs oublient et que toi, avec ta formation sécurité, tu dois porter.
Attaques réelles :

- **SolarWinds (2020)** — compromission du serveur de build, injection dans les binaires signés.
- **Codecov (2021)** — script bash de CI modifié, exfiltration des variables d'environnement
  (donc des secrets) de milliers de pipelines.
- **XZ Utils / CVE-2024-3094** — backdoor introduite par un mainteneur infiltré, cachée dans
  des fichiers de test et injectée par le script de build, pas visible dans le dépôt Git.
- **PyPI / npm typosquatting** — paquets malveillants aux noms proches.

Conséquence : la CI doit être traitée comme un **environnement de production**. Un runner qui
a un token d'écriture sur le registre est une cible de plus haute valeur que le laptop d'un dev.

### 6. Modèle de menace d'une CI/CD (STRIDE appliqué)

| Actif | Menace | Contre-mesure |
|---|---|---|
| Dépôt source | commit malveillant | protection de branche, revue obligatoire, commits signés |
| Dépendances | paquet compromis | lockfile + hash pinning, SCA, mirror interne |
| Runner CI | exécution arbitraire via PR | pas de secrets sur `pull_request` de fork, runners éphémères |
| Secrets CI | exfiltration par un job | OIDC à durée de vie courte, portée minimale, masquage |
| Artefact | substitution binaire | signature (cosign), attestation de provenance (SLSA) |
| Registre / serveur OTA | push non autorisé | MFA, clés matérielles, journalisation immuable |

## Lab — modéliser ta propre chaîne

1. Dessine (papier ou Excalidraw) la chaîne de ton dernier projet embarqué : du code jusqu'à la
   carte flashée. Inclus **tout** : ton PC, GitHub, le PC du collègue, la clé USB, le
   programmateur JTAG, le serveur de mise à jour.
2. Pour chaque flèche, réponds : *qui peut modifier ce qui passe ici, et comment le saurais-je ?*
3. Classe les 5 risques principaux : probabilité × impact.
4. Écris le résultat dans `labs/01-threat-model/pipeline.md`, avec une colonne « module du
   parcours qui traite ce risque ».

Trame :

```markdown
| # | Actif | Menace | Impact | Proba | Contre-mesure visée | Module |
|---|-------|--------|--------|-------|---------------------|--------|
| 1 | Clé de signature OTA | vol depuis le poste dev | critique | moyenne | HSM / SE + CI OIDC | 06, 10 |
```

## Critères de validation

- [ ] Tu redessines le schéma IDÉE→RUN de mémoire avec au moins 8 contrôles placés
- [ ] Tu expliques Codecov et XZ à quelqu'un en 2 minutes chacun
- [ ] Ton `pipeline.md` contient ≥ 10 lignes de menaces, dont ≥ 3 spécifiques à l'embarqué
- [ ] Tu sais dire, pour ton projet, **quel maillon te ferait le plus mal** s'il tombait

## Pièges classiques

- **Confondre DevSecOps et « acheter des outils »** : un scanner dont personne ne lit la sortie
  ajoute du bruit, pas de la sécurité. Un contrôle sans décision (bloque / n'bloque pas) est
  décoratif.
- **Tout bloquer dès le premier jour** : l'équipe désactive le pipeline. On commence en mode
  *warning*, on fixe une date de bascule en *blocking*, on ne bloque d'abord que le critique.
- **Oublier le modèle de menace du produit** au profit de celui du pipeline (il faut les deux).

## Pour aller plus loin

- *The DevOps Handbook* — Kim, Humble, Debois, Willis
- *Securing DevOps* — Julien Vehent (le seul livre du domaine qui reste concret)
- OWASP **DevSecOps Maturity Model** (DSOMM) : grille pour situer une équipe
- SLSA v1.0 — https://slsa.dev (on y revient au module 10)
