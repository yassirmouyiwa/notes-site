---
title: DevSecOps 06 · Gestion des secrets
date: 2026-09-20
tags: devsecops, secrets, embarque
description: SOPS + age, jetons OIDC éphémères en CI, et le problème dur de l'embarqué : où mettre une clé dans un objet que l'attaquant tient en main.
---

# Module 06 — Gestion des secrets

> Durée : 6–8 h. Objectif : plus aucun secret en clair dans un dépôt, une image ou un firmware.

## Objectifs

- Chiffrer les secrets versionnés avec SOPS + age.
- Remplacer les secrets statiques de CI par de l'**OIDC** (jetons éphémères).
- Traiter le problème spécifique de l'embarqué : où mettre une clé dans un objet que l'attaquant
  tient physiquement dans la main.
- Savoir faire une rotation de clé.

## Théorie utile

### Hiérarchie des solutions (du pire au meilleur)

1. Secret en dur dans le code ❌
2. Secret dans un `.env` non versionné — mieux, mais se retrouve en clair partout
3. Secret **chiffré** et versionné (SOPS + age) ✓ bon pour la config
4. Gestionnaire centralisé (Vault, cloud KMS) ✓ pour l'infrastructure
5. **Identité fédérée, jeton éphémère (OIDC)** ✓✓ le secret n'existe plus
6. **Matériel** (HSM, TPM, Secure Element) ✓✓✓ la clé ne sort jamais du silicium

Le meilleur secret est celui qui n'existe pas : un jeton OIDC valide 15 minutes ne peut pas
fuiter durablement.

### Le problème dur de l'embarqué

Une application serveur garde ses secrets sur une machine que tu contrôles. Ton objet connecté
est **chez l'attaquant**, qui peut dessouder la flash, sonder le bus SPI, faire du *glitching*
ou une attaque par canaux auxiliaires.

| Où | Protection | Verdict |
|---|---|---|
| Dans le code / flash en clair | aucune | ❌ `strings firmware.bin` suffit |
| Flash chiffrée, clé dans le code | obfuscation | ❌ ça retarde de 2 heures |
| OTP / eFuse du MCU | lecture bloquée par fusible | ✓ correct si le MCU le supporte bien |
| Secure Element (ATECC608, SE050) | clé non extractible, crypto dans la puce | ✓✓ |
| TrustZone / TEE | isolation matérielle monde sûr | ✓✓ |
| TPM 2.0 (Linux embarqué) | scellement sur l'état de boot (PCR) | ✓✓ |

Principe essentiel : **une clé par appareil, jamais une clé globale partagée**. Une clé globale
extraite d'un seul objet compromet le parc entier — c'est l'erreur de conception la plus
coûteuse de l'IoT.

## Lab 1 — SOPS + age

```bash
# installation
go install github.com/getsops/sops/v3/cmd/sops@latest   # ou binaire de release
sudo dnf install -y age

age-keygen -o ~/.config/sops/age/keys.txt
PUB=$(grep 'public key' ~/.config/sops/age/keys.txt | awk '{print $NF}')

cd ~/devsecops/labs/fil-rouge
cat > .sops.yaml <<YAML
creation_rules:
  - path_regex: secrets/.*\.yaml$
    age: ${PUB}
    encrypted_regex: '^(password|token|key|secret|psk)$'
YAML

mkdir -p secrets
cat > secrets/prod.yaml <<'YAML'
mqtt_broker: broker.exemple.ma
mqtt_port: 8883
username: capteur-01
password: ChangeMoiVraiment
device_key: 0123456789abcdef0123456789abcdef
YAML

sops -e -i secrets/prod.yaml   # chiffre EN PLACE
cat secrets/prod.yaml          # les clés restent lisibles, les valeurs sont chiffrées
git add secrets/prod.yaml && git commit -m "config prod chiffrée"

sops -d secrets/prod.yaml      # déchiffrement
sops secrets/prod.yaml         # édition dans $EDITOR, rechiffrement automatique
```

Avantage décisif : le diff Git reste lisible (on voit *quelle* clé a changé, pas sa valeur).

## Lab 2 — OIDC au lieu de secrets statiques

Exemple avec AWS — le principe est identique pour Azure, GCP, HashiCorp Vault :

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      id-token: write        # indispensable : autorise la demande du jeton OIDC
      contents: read
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-deploy
          aws-region: eu-west-3
          # aucune clé d'accès : GitHub prouve son identité, AWS émet des creds temporaires
      - run: aws s3 cp firmware.bin s3://ota-bucket/
```

Côté IAM, la condition de confiance **doit** restreindre le dépôt et la branche :

```json
{
  "Condition": {
    "StringEquals": {
      "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
      "token.actions.githubusercontent.com:sub": "repo:yassirmouyiwa/devsecops-fil-rouge:ref:refs/heads/main"
    }
  }
}
```

⚠️ Erreur fréquente et grave : `"sub": "repo:org/*"` avec `StringLike`. N'importe quelle branche,
y compris une branche de PR, peut alors prendre le rôle.

## Lab 3 — provisioning de secret dans un firmware

Modèle correct pour une clé par appareil :

```
[Usine]
  1. Le Secure Element génère sa paire de clés EN INTERNE (la privée ne sort jamais)
  2. Il produit un CSR signé par sa clé de fabrication
  3. L'infra d'usine signe le certificat avec la CA produit (CA hors ligne, clé en HSM)
  4. Le certificat (public) est écrit dans la flash
  5. L'identifiant + le certificat sont enregistrés dans le référentiel de parc
[Terrain]
  6. L'objet s'authentifie en mTLS avec sa clé jamais extraite
  7. Révocation possible par appareil (CRL / liste de blocage côté serveur)
```

Ce que ça évite : clé unique partagée, clé générée sur le PC de production (et donc copiable),
impossibilité de révoquer un seul objet.

Simulation en Python (à défaut de matériel) — `labs/06-secrets/provisioning.py` :

```python
"""Simule le provisioning par appareil. Le vrai code parlerait au SE via I2C."""
import hashlib, hmac, os, json, pathlib

MASTER = os.urandom(32)          # en vrai : jamais sur disque, dans un HSM

def cle_appareil(uid: bytes) -> bytes:
    """Dérivation par appareil : la compromission d'un objet n'expose que lui."""
    return hmac.new(MASTER, b"device-key|" + uid, hashlib.sha256).digest()

parc = {}
for i in range(5):
    uid = os.urandom(8)
    parc[uid.hex()] = cle_appareil(uid).hex()   # à ne stocker QUE côté serveur

pathlib.Path("parc.json").write_text(json.dumps(parc, indent=2))
print("5 appareils provisionnés, clés distinctes :", len(set(parc.values())) == 5)
```

## Rotation : la procédure que personne n'écrit

Écris `labs/06-secrets/rotation.md` avec, pour chaque secret :

| Secret | Où il vit | Qui y accède | Durée de vie | Procédure de rotation | Dernière rotation |
|---|---|---|---|---|---|
| Clé de signature firmware | HSM hors ligne | 2 personnes, double contrôle | 3 ans | cérémonie de clés documentée | — |
| Jeton de déploiement CI | OIDC | aucun humain | 15 min | automatique | n/a |
| Certificat MQTT appareil | Secure Element | l'appareil | 5 ans | renouvellement OTA | — |

Le test qui compte : **combien de temps pour révoquer et remplacer la clé de signature si elle
fuit demain matin ?** Si tu ne sais pas répondre, la procédure n'existe pas.

## Critères de validation

- [ ] Un fichier de secrets chiffré est versionné, déchiffrable par toi seul
- [ ] Le pre-commit refuse un fichier `secrets/*.yaml` en clair
- [ ] Tu expliques le flux OIDC en 5 étapes, et l'erreur du `sub` trop permissif
- [ ] Ton schéma de provisioning garantit : une clé par objet, non extractible, révocable
- [ ] `rotation.md` couvre tous les secrets du fil rouge

## Pièges classiques

- **Secret dans un `ARG` de Containerfile** : il reste dans l'historique des couches. Utiliser
  `RUN --mount=type=secret`.
- **Secret passé en argument de ligne de commande** : visible dans `ps`, dans les logs CI, dans
  l'historique du shell. Passer par l'environnement ou un fichier.
- **Chiffrer un fichier de secrets et versionner la clé age à côté.** Ça arrive.
- **Croire que l'obfuscation protège une clé en flash.** Elle ne fait que rallonger l'analyse.
- **Le même secret en dev, préprod et prod.**

## Pour aller plus loin

- HashiCorp Vault : *dynamic secrets* (identifiants de base de données créés à la demande,
  expirés automatiquement) — le concept vaut le détour même si tu n'utilises pas Vault
- Documentation ATECC608 / SE050 ; `tpm2-tools` et le scellement sur PCR
- NIST SP 800-57 (gestion de clés), SP 800-63B
