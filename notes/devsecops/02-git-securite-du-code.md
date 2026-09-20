---
title: DevSecOps 02 · Git et sécurité du code
date: 2026-09-20
tags: devsecops, git, secrets
description: Détecter les secrets avant le commit, nettoyer un secret de l'historique, signer ses commits et protéger une branche.
---

# Module 02 — Git et sécurité du code

> Durée : 6–8 h. Objectif : rendre impossible (ou au moins très visible) l'arrivée d'un secret
> ou d'un commit non attribué dans le dépôt.

## Objectifs

- Détecter les secrets **avant** le commit, pas après.
- Nettoyer un secret déjà présent dans l'historique — et savoir que le nettoyage ne suffit pas.
- Signer ses commits et faire vérifier la signature par la CI.
- Configurer les protections de branche et `CODEOWNERS`.

## Théorie utile

### Pourquoi un secret commité est mort

Une clé poussée sur GitHub, même sur un dépôt privé, doit être considérée comme **compromise** :

1. Git conserve l'objet dans l'historique, les forks, les caches, les PR fermées.
2. Les dépôts publics sont scannés en continu par des bots — délai d'exploitation observé pour
   une clé AWS : **moins de 5 minutes**.
3. `git rm` ne supprime rien de l'historique ; `git push --force` après réécriture n'atteint ni
   les clones existants ni le cache de GitHub.

**Règle absolue : on révoque d'abord, on nettoie ensuite.** Jamais l'inverse.

### Les trois lignes de défense

1. **Pre-commit** (poste dev) — rapide, contournable (`--no-verify`), sert d'aide.
2. **CI** (serveur) — non contournable, c'est la vraie barrière.
3. **Scan côté plateforme** (GitHub secret scanning + push protection) — filet de sécurité.

Mets les trois. Le pre-commit seul est une illusion de sécurité.

## Lab 1 — pre-commit + gitleaks

```bash
cd ~/devsecops/labs/fil-rouge
source ~/.venvs/devsecops/bin/activate

cat > .pre-commit-config.yaml <<'YAML'
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: check-added-large-files
        args: ['--maxkb=512']
      - id: check-merge-conflict
      - id: detect-private-key
      - id: end-of-file-fixer
      - id: trailing-whitespace

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.4
    hooks:
      - id: gitleaks

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
YAML

detect-secrets scan > .secrets.baseline
pre-commit install
pre-commit run --all-files
```

Teste que ça mord :

```bash
echo 'AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY' > config.env
git add config.env && git commit -m "test"   # doit être REFUSÉ
rm config.env
```

### Personnaliser les règles (clés propres à l'embarqué)

Les détecteurs génériques ne connaissent pas tes formats. Ajoute `.gitleaks.toml` :

```toml
[extend]
useDefault = true

[[rules]]
id = "cle-signature-firmware"
description = "Clé privée de signature de firmware"
regex = '''-----BEGIN (EC|RSA|OPENSSH|PGP) PRIVATE KEY-----'''
tags = ["firmware", "critique"]

[[rules]]
id = "psk-lorawan"
description = "AppKey / NwkKey LoRaWAN (32 hex)"
regex = '''(?i)(app|nwk|join)_?key\s*[:=]\s*["']?[0-9a-f]{32}'''

[[rules]]
id = "uart-credentials"
description = "Identifiants console série en dur"
regex = '''(?i)(root|admin)\s*[:=]\s*["'][^"']{4,}["']'''
```

## Lab 2 — nettoyer un secret de l'historique

Simule la fuite puis répare :

```bash
cd /tmp && git clone ~/devsecops/labs/fil-rouge fuite && cd fuite
echo "API_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" > secrets.env
git add -f secrets.env && git commit -m "oups"
echo "suite du travail" >> README.md && git commit -am "feature"

# 1) RÉVOQUER le token (dans la vraie vie : d'abord, toujours)
# 2) Nettoyer
pip install git-filter-repo      # dans le venv
git filter-repo --invert-paths --path secrets.env --force
git log --all --oneline --name-only | grep secrets.env   # doit être vide
```

Puis écris dans `labs/02-git/postmortem.md` :
- ce qui a fuité, depuis quand, qui y a eu accès ;
- la date/heure de révocation ;
- ce qui a été changé pour que ça ne se reproduise pas.

## Lab 3 — commits signés

Tu as déjà GPG sur la machine. Alternative plus simple : **SSH signing**.

```bash
ssh-keygen -t ed25519 -C "signature-commits" -f ~/.ssh/id_sign
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_sign.pub
git config --global commit.gpgsign true
git config --global tag.gpgsign true

# déclarer la clé comme clé de SIGNATURE (pas d'authentification) sur GitHub
gh ssh-key add ~/.ssh/id_sign.pub --type signing --title "signature commits"

git commit --allow-empty -m "test signature"
git log --show-signature -1
```

## Lab 4 — protections côté plateforme

```bash
gh api -X PUT repos/:owner/devsecops-fil-rouge/branches/main/protection \
  -f "required_status_checks[strict]=true" \
  -f "required_status_checks[contexts][]=secrets-scan" \
  -F "enforce_admins=true" \
  -F "required_pull_request_reviews[required_approving_review_count]=1" \
  -F "restrictions=null"
```

Et `CODEOWNERS` — indispensable dès qu'il y a du code critique :

```bash
mkdir -p .github && cat > .github/CODEOWNERS <<'OWN'
*                       @yassirmouyiwa
/firmware/crypto/       @yassirmouyiwa
/.github/workflows/     @yassirmouyiwa
/tools/signing/         @yassirmouyiwa
OWN
```

> Le dossier `.github/workflows/` dans CODEOWNERS n'est pas un détail : sans ça, n'importe qui
> qui peut modifier un workflow peut exfiltrer les secrets du pipeline.

## Critères de validation

- [ ] Un commit contenant une fausse clé AWS est refusé localement
- [ ] `.gitleaks.toml` contient ≥ 2 règles propres à ton domaine
- [ ] Tu as nettoyé un fichier de l'historique et vérifié qu'il a disparu
- [ ] `git log --show-signature` montre `Good "git" signature`
- [ ] `main` est protégée : pas de push direct, revue requise
- [ ] `postmortem.md` écrit

## Pièges classiques

- **Nettoyer sans révoquer.** Le nettoyage réduit l'exposition future ; il ne fait rien contre
  une clé déjà copiée.
- **Baseline `detect-secrets` gonflée** pour faire taire l'outil : tu masques la vraie fuite du
  mois prochain. Justifie chaque entrée.
- **`--no-verify` devenu réflexe** : si les hooks durent plus de 5 s, les gens les contournent.
  Garde le pre-commit rapide, mets le lourd en CI.
- **Secrets dans les fichiers de config d'exemple** (`config.example.json` avec une vraie clé) —
  vu très souvent.

## Pour aller plus loin

- GitHub *push protection* : à activer sur l'organisation
- `git-filter-repo` (remplace `filter-branch`, qui est déconseillé)
- TruffleHog v3 : vérifie en plus si le secret trouvé est **encore valide**
