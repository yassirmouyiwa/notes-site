---
title: DevSecOps 05 · SCA, CVE et SBOM
date: 2026-09-20
tags: devsecops, sbom, cve
description: Générer un SBOM CycloneDX pour du code, une image et un firmware, prioriser par EPSS et KEV, gérer les CVE sous Yocto et Buildroot.
---

# Module 05 — SCA, CVE et SBOM

> Durée : 7–9 h. Objectif : savoir dire, à tout instant, **ce qu'il y a exactement dans ton
> firmware** et si l'un de ces composants est vulnérable.

## Objectifs

- Générer un SBOM CycloneDX/SPDX pour du code source, une image conteneur et une image firmware.
- Croiser le SBOM avec les bases de vulnérabilités et prioriser autrement qu'au CVSS.
- Faire échouer un build sur une CVE critique — sans bloquer sur 300 faux positifs.
- Traiter le cas Yocto / Buildroot, qui est ton cas réel.

## Théorie utile

### Pourquoi le SBOM est devenu obligatoire

- **Log4Shell (CVE-2021-44228)** : la question qui a coûté des semaines à tout le monde n'était
  pas « comment corriger » mais **« où est-ce que j'ai du log4j ? »**. Beaucoup n'ont jamais su.
- **Cyber Resilience Act (UE)** : pour tout produit avec des éléments numériques vendu dans
  l'UE, le SBOM des composants de premier niveau fait partie de la documentation technique.
  Entrée en application principale : **11 décembre 2027** (obligations de notification dès
  septembre 2026). Si tu vends un objet connecté en Europe, ça te concerne directement.
- **US Executive Order 14028** : SBOM exigé pour les fournisseurs fédéraux.

### Formats

| Format | Origine | Remarque |
|---|---|---|
| **CycloneDX** | OWASP | orienté sécurité, supporte VEX, le plus pratique en pratique |
| **SPDX** | Linux Foundation, ISO/IEC 5962 | orienté licences et conformité, normalisé ISO |

Les deux sont acceptés. En embarqué, CycloneDX est plus répandu côté outillage sécurité.

### VEX — le document qui évite de se noyer

Un SBOM dit « j'utilise openssl 3.0.8 ». Grype dit « 40 CVE ». La réalité : 35 concernent des
modules que tu ne compiles pas.

**VEX** (Vulnerability Exploitability eXchange) exprime ça formellement, avec 4 états :
`not_affected`, `affected`, `fixed`, `under_investigation`. Pour `not_affected`, il faut une
justification (`vulnerable_code_not_present`, `vulnerable_code_not_in_execute_path`, …).

C'est le document qui transforme « 400 CVE » en « 6 à traiter », de façon auditable.

### Priorisation : CVSS ne suffit pas

Ordre de priorité recommandé :

1. **CISA KEV** — exploitée dans la nature → à traiter maintenant.
2. **EPSS > 0.1** — forte probabilité d'exploitation.
3. **CVSS critique + accessible depuis l'extérieur** dans *ton* architecture.
4. Le reste — plan de fond.

Une CVSS 9.8 dans un parseur XML que ton firmware n'appelle jamais passe après une CVSS 6.5 sur
ta pile TLS exposée.

## Lab 1 — SBOM du code et d'une image

```bash
cd ~/devsecops/labs/fil-rouge

# SBOM du répertoire source
syft dir:. -o cyclonedx-json=sbom-source.cdx.json -o spdx-json=sbom-source.spdx.json

# SBOM d'une image conteneur
podman pull docker.io/library/python:3.11-slim
syft podman:docker.io/library/python:3.11-slim -o cyclonedx-json=sbom-image.cdx.json

# Analyse de vulnérabilités à partir du SBOM (et non de l'image : plus rapide, reproductible)
grype sbom:sbom-image.cdx.json -o table
grype sbom:sbom-image.cdx.json -o json > vulns.json

# Combien par sévérité
jq -r '.matches[].vulnerability.severity' vulns.json | sort | uniq -c | sort -rn
```

Enrichir avec l'EPSS :

```bash
jq -r '.matches[].vulnerability.id' vulns.json | grep '^CVE' | sort -u | head -50 \
 | paste -sd, - \
 | xargs -I{} curl -s "https://api.first.org/data/v1/epss?cve={}" \
 | jq -r '.data[] | "\(.cve)\t\(.epss)\t\(.percentile)"' | sort -k2 -rn | head -20
```

## Lab 2 — la gate CVE

`grype.yaml` :

```yaml
fail-on-severity: high
ignore:
  # Justifié : outil de build uniquement, absent de l'image finale
  - vulnerability: CVE-2023-45853
    package:
      name: zlib
      version: 1.2.13
  # Pas de correctif disponible, compensé par l'isolation réseau — revoir le 2026-12-01
  - vulnerability: CVE-2024-XXXXX
```

Dans la CI :

```yaml
  sca:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: anchore/sbom-action@v0
        with:
          format: cyclonedx-json
          output-file: sbom.cdx.json
      - uses: anchore/scan-action@v4
        with:
          sbom: sbom.cdx.json
          fail-build: true
          severity-cutoff: high
      - uses: actions/upload-artifact@v4
        with:
          name: sbom                 # le SBOM est un livrable, il s'archive
          path: sbom.cdx.json
```

> **Toute ignorance de CVE porte une date de revue.** Sans date, la liste d'exceptions devient
> la vraie configuration de sécurité du projet, et personne ne la relit.

## Lab 3 — le cas embarqué : Yocto / Buildroot

C'est ici que ça devient spécifique à ton domaine.

### Yocto

```bash
# dans conf/local.conf
INHERIT += "cve-check"
CVE_CHECK_REPORT_PATCHED = "0"
CVE_CHECK_FORMAT_JSON = "1"

# SBOM SPDX natif (Yocto 4.x+)
INHERIT += "create-spdx"
SPDX_PRETTY = "1"
```

Résultats dans `build/tmp/log/cve/` et `tmp/deploy/spdx/`.

Ignorer une CVE au niveau d'une recette :

```bitbake
# recipes-xxx/paquet/paquet_1.2.bb
CVE_STATUS[CVE-2024-1234] = "not-applicable-config: le module concerné n'est pas compilé"
```

### Buildroot

```bash
make BR2_JLEVEL=0 pkg-stats        # génère output/pkg-stats.html : CVE + versions obsolètes
```

### Images binaires sans arborescence de build

Cas fréquent : tu reçois un `.bin` d'un fournisseur. Tu dois quand même savoir ce qu'il y a
dedans.

```bash
binwalk -Me firmware.bin              # extraction récursive
syft dir:_firmware.bin.extracted -o cyclonedx-json=sbom-firmware.cdx.json
grype sbom:sbom-firmware.cdx.json

# Détection de versions dans les binaires quand syft ne trouve rien
strings -n 8 rootfs/usr/bin/busybox | grep -iE 'BusyBox v[0-9.]+'
strings -n 8 rootfs/usr/lib/libssl.so* | grep -iE 'OpenSSL [0-9.]+[a-z]?'
```

Outils dédiés à connaître : **cve-bin-tool** (Intel, détecte ~350 composants par signature
binaire), **EMBA** (analyse complète d'images firmware), **FACT**.

```bash
~/.venvs/devsecops/bin/pip install cve-bin-tool
~/.venvs/devsecops/bin/cve-bin-tool --sbom-output sbom.cdx.json -f json -o rapport.json rootfs/
```

## Lab 4 — écrire un VEX

```bash
cat > vex.cdx.json <<'JSON'
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.5",
  "vulnerabilities": [
    {
      "id": "CVE-2023-45853",
      "source": { "name": "NVD" },
      "analysis": {
        "state": "not_affected",
        "justification": "code_not_present",
        "detail": "zlib n'est présent que dans l'image de build ; l'image finale distroless ne l'embarque pas (vérifié par syft sur l'image finale le 2026-09-20).",
        "response": ["will_not_fix"]
      },
      "affects": [{ "ref": "pkg:generic/zlib@1.2.13" }]
    }
  ]
}
JSON
grype sbom:sbom-image.cdx.json --vex vex.cdx.json
```

## Critères de validation

- [ ] Tu produis un SBOM CycloneDX pour : source, image conteneur, image firmware extraite
- [ ] La CI échoue sur une CVE `high` et archive le SBOM comme artefact
- [ ] Ta liste d'exceptions a une justification **et une date de revue** par ligne
- [ ] Tu as trié 20 CVE par EPSS et tu expliques pourquoi l'ordre diffère du CVSS
- [ ] Tu sais activer `cve-check` sur Yocto et lire son rapport
- [ ] Un VEX réduit visiblement le bruit de ton rapport Grype

## Pièges classiques

- **SBOM généré mais jamais rescanné.** Une image ne change pas ; la base CVE, si. Programme un
  rescan **quotidien** des SBOM des versions en production (`schedule: cron`).
- **SBOM du dépôt au lieu du SBOM de l'artefact livré.** Ce qui compte, c'est ce qui part chez
  le client, dépendances transitives et paquets système compris.
- **Ignorer les dépendances de build** : `xz` était une dépendance de build.
- **Versions Yocto patchées** : Yocto rétroporte des correctifs sans changer le numéro de
  version ; un scanner naïf lève des faux positifs. C'est à ça que sert `CVE_STATUS`.

## Pour aller plus loin

- CycloneDX 1.6, spécification VEX
- *cve-bin-tool*, *EMBA*, *Dependency-Track* (serveur : historise les SBOM et alerte quand une
  nouvelle CVE touche une version déjà livrée — la brique qui manque le plus souvent)
- NTIA — *Minimum Elements For a Software Bill of Materials*
