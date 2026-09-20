---
title: DevSecOps 07 · Sécurité des conteneurs
date: 2026-09-20
tags: devsecops, conteneurs, podman
description: Image multi-stage distroless et non-root, scan Trivy en gate, signature Cosign, et conteneur de build firmware reproductible.
---

# Module 07 — Sécurité des conteneurs

> Durée : 6–8 h. Objectif : construire une image minimale, non-root, scannée et signée — et
> comprendre pourquoi ça compte aussi quand on fait de l'embarqué.

## Objectifs

- Écrire un Containerfile multi-stage durci.
- Scanner une image (Trivy) et refuser la publication sur critère.
- Signer une image avec Cosign et **vérifier la signature au déploiement**.
- Appliquer ces mêmes principes à un environnement de build firmware reproductible.

## Pourquoi ça te concerne en embarqué

1. Ta **chaîne de compilation croisée** vit dans un conteneur (c'est ce qui rend le build
   reproductible et identique entre ton poste et la CI).
2. Les passerelles IoT modernes font tourner des conteneurs (Balena, Azure IoT Edge, systemd-
   nspawn, Docker sur Yocto via `meta-virtualization`).
3. Les techniques — surface minimale, non-root, capabilities, FS en lecture seule, signature —
   sont **exactement** celles du durcissement d'un Linux embarqué. Tu apprends les deux d'un coup.

## Théorie utile

### Un conteneur n'est pas une VM

Namespaces (isolation de vue) + cgroups (limitation de ressources) + capabilities + seccomp +
LSM (SELinux sur Fedora). **Le noyau est partagé** : une faille noyau = évasion possible.

### Les couches sont publiques et permanentes

```bash
podman history image:tag
# un secret ajouté puis supprimé dans un RUN ultérieur reste dans la couche précédente
```

### Rootless (podman) — ton avantage par défaut

Podman en rootless fait tourner le conteneur sous ton uid via `user_namespaces` : une évasion ne
donne pas root sur l'hôte. Docker avec daemon root est un point d'escalade bien connu
(`docker.sock` accessible = root sur l'hôte).

## Lab 1 — image durcie, multi-stage

`api/Containerfile` :

```dockerfile
# ---------- étape 1 : build ----------
FROM docker.io/library/python:3.11-slim@sha256:<digest> AS build
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt --target /deps
COPY src/ /deps/src/

# ---------- étape 2 : runtime ----------
FROM gcr.io/distroless/python3-debian12:nonroot
COPY --from=build /deps /app
WORKDIR /app
ENV PYTHONPATH=/app PYTHONDONTWRITEBYTECODE=1
USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["python3", "src/main.py"]
```

Points à savoir justifier :

| Choix | Raison |
|---|---|
| image de base **épinglée par digest** | un tag est mutable, un digest non |
| multi-stage | compilateurs et sources absents de l'image finale |
| **distroless** | pas de shell : un RCE ne donne pas de `/bin/sh` |
| `USER nonroot` | le processus n'est pas uid 0 dans le conteneur |
| `--require-hashes` | protège du typosquatting et d'un paquet remplacé en amont |

Exécution durcie :

```bash
podman run --rm \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --cap-drop=ALL \
  --security-opt no-new-privileges \
  --security-opt seccomp=/usr/share/containers/seccomp.json \
  --memory=256m --pids-limit=100 \
  --network=none \
  mon-api:1.0
```

## Lab 2 — Trivy en gate

```bash
trivy image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 mon-api:1.0
trivy image --scanners vuln,secret,misconfig -f json -o trivy.json mon-api:1.0
trivy fs --scanners secret,misconfig .
trivy config api/Containerfile     # bonnes pratiques Dockerfile
```

`--ignore-unfixed` est un choix assumé : on ne bloque pas sur ce qui n'a pas de correctif
disponible, mais ces CVE doivent apparaître dans un rapport suivi.

En CI :

```yaml
  image:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      id-token: write         # pour la signature keyless
    steps:
      - uses: actions/checkout@v4
      - name: Build
        run: podman build -t ghcr.io/${{ github.repository }}:${{ github.sha }} api/
      - name: Scan
        uses: aquasecurity/trivy-action@v0
        with:
          image-ref: ghcr.io/${{ github.repository }}:${{ github.sha }}
          severity: HIGH,CRITICAL
          ignore-unfixed: true
          exit-code: '1'
      - name: Publier
        run: podman push ghcr.io/${{ github.repository }}:${{ github.sha }}
      - name: Signer (keyless, OIDC)
        run: |
          cosign sign --yes ghcr.io/${{ github.repository }}:${{ github.sha }}
```

## Lab 3 — signature et vérification (Cosign / Sigstore)

```bash
# signature avec clé (mode classique)
cosign generate-key-pair
cosign sign --key cosign.key ghcr.io/moi/mon-api:1.0
cosign verify --key cosign.pub ghcr.io/moi/mon-api:1.0

# signature keyless : identité OIDC + certificat éphémère + journal public Rekor
cosign sign ghcr.io/moi/mon-api:1.0
cosign verify ghcr.io/moi/mon-api:1.0 \
  --certificate-identity-regexp 'https://github.com/yassirmouyiwa/.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

Attacher un SBOM et une attestation de provenance :

```bash
syft mon-api:1.0 -o cyclonedx-json=sbom.json
cosign attest --predicate sbom.json --type cyclonedx ghcr.io/moi/mon-api:1.0
cosign verify-attestation --type cyclonedx ghcr.io/moi/mon-api:1.0
```

> **Une signature sans vérification au déploiement ne sert à rien.** Le point de contrôle est
> côté consommateur : admission controller Kubernetes (Kyverno, Connaisseur), ou, côté objet,
> vérification de la signature avant application d'une mise à jour OTA (module 10).

## Lab 4 — conteneur de build firmware reproductible

```dockerfile
FROM docker.io/library/debian:bookworm-slim@sha256:<digest>

ARG TOOLCHAIN_VERSION=13.2.rel1
ARG TOOLCHAIN_SHA256=<sha256 attendu>

RUN apt-get update && apt-get install -y --no-install-recommends \
      make cmake ninja-build python3 git ca-certificates curl xz-utils \
 && rm -rf /var/lib/apt/lists/*

RUN curl -fsSLo /tmp/tc.tar.xz \
      "https://developer.arm.com/-/media/Files/downloads/gnu/${TOOLCHAIN_VERSION}/binrel/arm-gnu-toolchain-${TOOLCHAIN_VERSION}-x86_64-arm-none-eabi.tar.xz" \
 && echo "${TOOLCHAIN_SHA256}  /tmp/tc.tar.xz" | sha256sum -c - \
 && tar -xJf /tmp/tc.tar.xz -C /opt && rm /tmp/tc.tar.xz

ENV PATH="/opt/arm-gnu-toolchain-${TOOLCHAIN_VERSION}-x86_64-arm-none-eabi/bin:${PATH}"
ENV SOURCE_DATE_EPOCH=1700000000
RUN useradd -m build
USER build
WORKDIR /src
```

La vérification `sha256sum -c` sur la toolchain téléchargée est le contrôle qui manque presque
partout. Sans elle, ta chaîne de compilation entière repose sur la confiance dans un CDN.

```bash
podman build -t firmware-build:1.0 -f Containerfile.build .
podman run --rm -v "$PWD:/src:z" -u build firmware-build:1.0 make
```

## Critères de validation

- [ ] Ton image finale fait < 100 Mo et ne contient **pas** de shell (`podman run --rm -it img sh` échoue)
- [ ] Le processus tourne en non-root (`podman top <ctr> user`)
- [ ] Trivy ne remonte plus aucun HIGH/CRITICAL corrigeable
- [ ] L'image est signée et tu sais la vérifier depuis une autre machine
- [ ] Le conteneur de build produit deux fois de suite le **même** binaire (`sha256sum`)

## Pièges classiques

- **`FROM ubuntu:latest`** — non reproductible, gros, souvent vulnérable.
- **`ADD` au lieu de `COPY`** — `ADD` déballe des archives et télécharge des URL.
- **Scanner l'image mais jamais l'image de base** : 90 % des CVE viennent de la base ; mets à
  jour la base **en premier**, la plupart des alertes tombent.
- **`--privileged`** pour « faire marcher » l'accès USB au programmateur : préfère
  `--device=/dev/ttyUSB0` et un groupe dédié.
- **`:z` oublié sur les volumes en Fedora** : SELinux bloque, et on désactive SELinux au lieu
  d'étiqueter correctement. Ne désactive pas SELinux.

## Pour aller plus loin

- CIS Docker Benchmark, `docker-bench-security`
- Kubernetes : Pod Security Standards, NetworkPolicy, Kyverno
- `dive` (analyse des couches), `skopeo` (copie/inspection sans daemon)
