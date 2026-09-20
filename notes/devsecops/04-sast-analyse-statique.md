---
title: DevSecOps 04 · SAST et analyse statique
date: 2026-09-20
tags: devsecops, sast, c
description: Semgrep avec règles maison, chaîne C/C++ (clang-tidy, cppcheck, sanitizers), MISRA et flags de durcissement du compilateur.
---

# Module 04 — SAST : analyse statique

> Durée : 8–10 h. Objectif : faire échouer un build sur une vulnérabilité de code, en C comme
> en Python, avec un taux de faux positifs supportable.

## Objectifs

- Comprendre ce que l'analyse statique peut et ne peut pas trouver.
- Écrire une **règle Semgrep maison** pour un défaut propre à ton projet.
- Outiller le C/C++ : `clang-tidy`, `cppcheck`, analyseurs, sanitizers, flags durcis.
- Situer MISRA C et CERT C dans un contexte embarqué.
- Gérer les faux positifs sans tout désactiver.

## Théorie utile

### Ce que le SAST trouve bien / mal

| Trouve bien | Trouve mal |
|---|---|
| Injections (SQL, commande, path) | Logique métier fausse |
| Crypto faible (MD5, ECB, IV statique) | Contrôle d'accès manquant |
| Buffer overflow évident, format string | Race conditions |
| Secrets en dur, code mort dangereux | Vulnérabilités de conception |
| Mauvais usage d'API (`strcpy`, `system`) | Tout ce qui dépend de l'environnement |

Le SAST **sur-détecte** (faux positifs) et **sous-détecte** (faux négatifs) en même temps. Ce
n'est pas un défaut d'outil : c'est mathématique (indécidabilité). D'où la règle : on bloque sur
un sous-ensemble à haute confiance, on rapporte le reste.

### Taxonomie à connaître

- **CWE** — catégorie de faiblesse (CWE-120 buffer overflow, CWE-798 identifiants en dur).
- **CVE** — instance concrète dans un produit donné.
- **CVSS** — score de sévérité (base / temporel / environnemental).
- **EPSS** — probabilité d'exploitation réelle dans les 30 jours. Beaucoup plus utile que le
  CVSS pour prioriser.
- **KEV** (CISA) — liste des vulnérabilités **activement exploitées**. Priorité absolue.

## Lab 1 — Semgrep sur le fil rouge

```bash
cd ~/devsecops/labs/fil-rouge
source ~/.venvs/devsecops/bin/activate

semgrep --config=auto --sarif -o semgrep.sarif .
semgrep --config=p/c --config=p/secrets --config=p/cwe-top-25 .
```

### Écrire ta propre règle

C'est ça qui fait la différence entre « j'ai lancé un scanner » et « je fais du DevSecOps ».
Cas typique en embarqué : interdire les fonctions de copie non bornées et l'usage d'un PRNG
faible pour du matériel cryptographique.

`.semgrep/regles-embarque.yaml` :

```yaml
rules:
  - id: copie-non-bornee
    languages: [c, cpp]
    severity: ERROR
    message: >-
      $FUNC ne borne pas la copie (CWE-120). Utiliser snprintf/strlcpy avec
      sizeof(destination).
    pattern-either:
      - pattern: strcpy(...)
      - pattern: strcat(...)
      - pattern: sprintf(...)
      - pattern: gets(...)

  - id: prng-faible-pour-crypto
    languages: [c, cpp]
    severity: ERROR
    message: >-
      rand()/srand() n'est pas cryptographiquement sûr. Utiliser le TRNG matériel
      ou getrandom(2).
    patterns:
      - pattern-either:
          - pattern: rand()
          - pattern: srand(...)
      - pattern-inside: |
          $TYPE $F(...) { ... }
      - metavariable-regex:
          metavariable: $F
          regex: '(?i).*(key|nonce|iv|token|seed|salt|session).*'

  - id: delai-sans-timeout
    languages: [c]
    severity: WARNING
    message: Boucle d'attente matérielle sans timeout — risque de blocage définitif.
    pattern: |
      while (!$REG) { }

  - id: retour-crypto-ignore
    languages: [c]
    severity: ERROR
    message: Le code de retour d'une opération cryptographique doit être vérifié.
    pattern-not: |
      if (mbedtls_$F(...) != 0) { ... }
    pattern: mbedtls_$F(...);
```

Test :

```bash
semgrep --config=.semgrep/regles-embarque.yaml firmware/ --error
```

### Intégration CI (job bloquant + rapport)

```yaml
  sast:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@v4
      - uses: returntocorp/semgrep-action@v1
        with:
          config: >-
            p/default
            p/c
            p/secrets
            .semgrep/regles-embarque.yaml
          generateSarif: "1"
      - uses: github/codeql-action/upload-sarif@v3
        with: { sarif_file: semgrep.sarif }
```

## Lab 2 — chaîne C/C++ complète

C'est le cœur du module pour un profil embarqué.

```bash
# 1. compilateur : les warnings sont ta première analyse statique, gratuite
gcc -Wall -Wextra -Wpedantic -Wshadow -Wconversion -Wformat=2 \
    -Wnull-dereference -Wstack-protector -Warray-bounds=2 \
    -Wimplicit-fallthrough=3 -Wcast-qual -Werror \
    -O2 -c firmware/src/main.c

# 2. analyseur statique intégré à GCC
gcc -fanalyzer -Wanalyzer-too-complex -c firmware/src/main.c

# 3. cppcheck
cppcheck --enable=all --inconclusive --std=c11 \
         --suppress=missingIncludeSystem \
         --error-exitcode=1 --xml firmware/src/ 2> cppcheck.xml

# 4. clang-tidy (checks CERT + bugprone)
clang-tidy firmware/src/main.c \
  -checks='-*,clang-analyzer-*,bugprone-*,cert-*,misc-*,readability-non-const-parameter' \
  --warnings-as-errors='cert-*,clang-analyzer-security*' -- -I firmware/include

# 5. scan-build (Clang Static Analyzer, rapport HTML)
scan-build -o rapport-scan make
```

### Sanitizers — analyse dynamique, mais ça se prépare ici

```bash
# ASan + UBSan : à utiliser sur les tests, jamais en production
gcc -fsanitize=address,undefined -fno-omit-frame-pointer -g -O1 \
    -o test-asan firmware/src/main.c
./test-asan "$(python3 -c 'print("A"*100)')"      # doit crasher proprement avec un rapport
```

> En embarqué bare-metal, ASan n'est pas disponible. Solution : **compiler la logique métier en
> natif** (x86) pour les tests, avec une couche d'abstraction matérielle bouchonnée (HAL mockée).
> C'est le design qui rend le firmware testable — pense-y dès la conception.

### Flags de durcissement à connaître par cœur

| Flag | Effet |
|---|---|
| `-D_FORTIFY_SOURCE=3` | vérification de bornes sur les fonctions libc à la compilation/exécution |
| `-fstack-protector-strong` | canaris de pile |
| `-fstack-clash-protection` | empêche le saut de garde de pile |
| `-fcf-protection=full` | CET / protection du flux de contrôle (x86) |
| `-mbranch-protection=standard` | PAC/BTI sur ARMv8.3+ |
| `-fPIE -pie` | ASLR sur l'exécutable |
| `-Wl,-z,relro,-z,now` | GOT en lecture seule après le lien |
| `-Wl,-z,noexecstack` | pile non exécutable |
| `-ftrivial-auto-var-init=zero` | initialise les variables locales (contre les fuites d'info) |

Référence : *OpenSSF Compiler Options Hardening Guide for C and C++*.

## MISRA C et CERT C

| | MISRA C:2023 | CERT C |
|---|---|---|
| But | sûreté de fonctionnement (safety) | sécurité (security) |
| Origine | automobile → généralisé | CMU/SEI |
| Style | règles restrictives sur le langage | règles + recommandations, avec exemples d'exploitation |
| Où c'est exigé | ISO 26262, IEC 61508, DO-178C | souvent cité par IEC 62443 |
| Outils libres | `cppcheck --addon=misra` (couverture partielle) | `clang-tidy -checks=cert-*` |
| Outils commerciaux | Polyspace, PC-lint, Coverity, Parasoft, Helix QAC | idem |

```bash
cppcheck --addon=misra --enable=all firmware/src/
```

Sache expliquer en entretien : *MISRA réduit le champ du langage pour éliminer les
comportements indéfinis ; ce n'est pas un outil de sécurité mais ça supprime une grande partie
du terrain d'où viennent les vulnérabilités mémoire.*

## Gérer les faux positifs

Trois niveaux, du meilleur au pire :

1. **Corriger le code** même si le risque est faible (souvent 2 minutes).
2. **Supprimer localement avec justification** :
   ```c
   /* nosemgrep: copie-non-bornee — taille vérifiée ligne 41, entrée bornée par le protocole */
   ```
3. **Désactiver la règle globalement** — seulement si elle est structurellement inadaptée, et
   c'est écrit dans un fichier de décisions.

Interdit : baseline qui ignore tout l'existant sans plan de résorption.

## Critères de validation

- [ ] Tes 4 règles Semgrep maison détectent les cas voulus et ignorent le code correct
- [ ] Le job SAST bloque la PR sur `ERROR`, rapporte sans bloquer sur `WARNING`
- [ ] `gcc -fanalyzer` et `cppcheck` tournent en CI avec `--error-exitcode=1`
- [ ] Un build ASan détecte le débordement du fil rouge
- [ ] Tu sais expliquer 6 flags de durcissement sans regarder
- [ ] Tu as justifié par écrit au moins une suppression de faux positif

## Pièges classiques

- **`--config=auto` partout** : envoie des métadonnées, résultats génériques. Choisis tes packs.
- **Activer tous les checks clang-tidy** : bruit ingérable. Commence par
  `clang-analyzer-*,bugprone-*,cert-*`.
- **Bloquer sur le stock existant** dès le jour 1 : utilise `semgrep --baseline-commit` pour ne
  bloquer que sur le code **nouveau**, avec un plan de résorption daté pour l'ancien.
- **Croire qu'un binaire compilé sans warning est sûr.**

## Pour aller plus loin

- CodeQL — plus puissant (analyse par flux de données, requêtes en QL), gratuit sur dépôts
  publics ; il supporte C/C++ avec une build manuelle
- `infer` (Meta), `Frama-C` (analyse formelle, très utilisé en embarqué critique en France)
- OpenSSF *Compiler Options Hardening Guide*
