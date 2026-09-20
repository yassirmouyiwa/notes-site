---
title: DevSecOps 10 · Supply chain du firmware
date: 2026-09-20
tags: devsecops, embarque, secure-boot
description: Chaîne de confiance complète : secure boot, image FIT signée, build Yocto en CI, build reproductible, OTA anti-rollback, CI matérielle, SLSA.
---

# Module 10 — Supply chain et sécurité du firmware

> Durée : 10–14 h. **C'est le module central de ce parcours pour ton profil.** Tout ce qui
> précède converge ici : c'est ce qui te distingue d'un profil DevSecOps purement web.

## Objectifs

- Construire une chaîne de confiance complète : secure boot → firmware signé → OTA signée.
- Automatiser le build d'image Yocto/Buildroot en CI, avec gates sécurité.
- Obtenir un build **reproductible** et comprendre pourquoi ça compte.
- Mettre en place une CI matérielle (hardware-in-the-loop) et un banc de test.
- Situer ton niveau sur l'échelle SLSA.

## Théorie utile

### La chaîne de confiance (secure boot)

```
[Racine de confiance matérielle]  ROM immuable + hash/clé publique en eFuse (OTP)
        │ vérifie la signature de
        ▼
[Bootloader de 1er niveau]  (SPL / BL2)
        │ vérifie
        ▼
[Bootloader de 2e niveau]  (U-Boot avec FIT signé, ou TF-A BL33)
        │ vérifie
        ▼
[Noyau + device tree + initramfs]  (image FIT signée)
        │ vérifie (dm-verity)
        ▼
[Rootfs]  arbre de hachage signé
        │
        ▼
[Applications]  signature applicative / IMA-EVM
```

Trois règles qui font la différence entre une vraie chaîne et une chaîne décorative :

1. **Chaque maillon vérifie le suivant avant de lui donner la main.** Un seul maillon non
   vérifié annule tout ce qui est en dessous.
2. **La racine est immuable** : en ROM ou en fusible OTP. Si la clé publique est en flash
   réinscriptible, l'attaquant la remplace par la sienne.
3. **La vérification a lieu avant l'exécution**, pas après (un hash calculé après le boot ne
   sert à rien).

### Secure boot ≠ chiffrement

- **Secure boot** = authenticité et intégrité (seul du code signé par toi s'exécute).
- **Flash chiffrée** = confidentialité (l'attaquant ne peut pas lire ton code).

Ils répondent à des menaces différentes. Le secure boot est prioritaire : sans lui, l'attaquant
n'a pas besoin de lire ton code, il met le sien.

### Signature : quelle clé, où

| Élément | Algorithme usuel | Où vit la clé privée |
|---|---|---|
| Firmware / FIT | RSA-4096 ou ECDSA P-256 | **HSM hors ligne**, jamais sur un poste |
| Paquets OTA | Ed25519 / ECDSA | HSM, accès via la CI par OIDC |
| Certificat d'appareil | ECC P-256 | généré **dans** le Secure Element |
| Signature de release | Sigstore / GPG | keyless OIDC ou clé matérielle (YubiKey) |

Prépare aussi la **post-quantique** : le CRA et le NIST poussent vers ML-DSA (Dilithium) pour
les signatures de firmware à longue durée de vie. Un objet industriel déployé en 2027 pour 15 ans
doit pouvoir migrer. Concevoir la **crypto-agilité** (identifiant d'algorithme dans l'en-tête du
paquet, place pour une signature plus grande) coûte peu maintenant et beaucoup plus tard.

## Lab 1 — U-Boot, image FIT signée

```bash
# 1) générer la clé de signature (en vrai : dans un HSM)
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 -out keys/dev.key
openssl req -batch -new -x509 -key keys/dev.key -out keys/dev.crt -days 3650 \
        -subj "/CN=Cle de signature firmware DEV/"

# 2) décrire l'image
cat > image.its <<'ITS'
/dts-v1/;
/ {
    description = "Image FIT signée — capteur v1";
    #address-cells = <1>;

    images {
        kernel {
            description = "Linux";
            data = /incbin/("./zImage");
            type = "kernel";  arch = "arm";  os = "linux";
            compression = "none";
            load = <0x80008000>;  entry = <0x80008000>;
            hash-1 { algo = "sha256"; };
        };
        fdt {
            description = "Device tree";
            data = /incbin/("./board.dtb");
            type = "flat_dt";  arch = "arm";  compression = "none";
            hash-1 { algo = "sha256"; };
        };
    };

    configurations {
        default = "conf";
        conf {
            description = "Configuration par défaut";
            kernel = "kernel";
            fdt = "fdt";
            /* la signature couvre kernel + fdt : empêche le mélange d'un noyau
               légitime avec un device tree modifié */
            signature {
                algo = "sha256,rsa4096";
                key-name-hint = "dev";
                sign-images = "kernel", "fdt";
            };
        };
    };
};
ITS

# 3) signer et injecter la clé publique dans le device tree d'U-Boot
mkimage -f image.its -k keys -K u-boot.dtb -r image.fit

# 4) vérifier
fit_check_sign -f image.fit -k u-boot.dtb
```

Côté U-Boot, il faut `CONFIG_FIT_SIGNATURE=y`, `CONFIG_RSA=y` et surtout
**`CONFIG_FIT_SIGNATURE_MAX_SIZE`** + un environnement U-Boot **verrouillé** (sinon l'attaquant
change `bootcmd` depuis la console série et contourne toute la vérification).

## Lab 2 — Yocto en CI avec gates sécurité

`.github/workflows/firmware.yml` :

```yaml
name: Build firmware
on:
  push: { tags: ['v*'] }
  schedule: [{ cron: '0 3 * * *' }]    # rescan CVE quotidien même sans changement

permissions: { contents: read, id-token: write }

jobs:
  build:
    runs-on: [self-hosted, linux, x64, builder]   # un build Yocto : ~50 Go, 2–6 h
    steps:
      - uses: actions/checkout@v4
        with: { submodules: recursive, fetch-depth: 0 }

      - name: Vérifier les révisions des couches (pas de branche flottante)
        run: python3 tools/verifier-revisions.py  # échoue si un SRCREV vaut AUTOREV

      - name: Build
        run: |
          source poky/oe-init-build-env build
          echo 'INHERIT += "cve-check create-spdx"' >> conf/local.conf
          bitbake image-capteur

      - name: Gate CVE
        run: python3 tools/gate-cve.py build/tmp/log/cve/cve-summary.json \
               --bloquer-au-dessus-de 7.0 --exceptions cve-exceptions.yaml

      - name: Gate durcissement du rootfs
        run: python3 tools/verifier-durcissement.py --rootfs build/tmp/work/*/rootfs

      - name: SBOM
        run: |
          syft dir:build/tmp/deploy/images -o cyclonedx-json=sbom-firmware.cdx.json

      - name: Signer l'image
        run: |
          cosign sign-blob --yes \
            --output-signature image.sig --output-certificate image.pem \
            build/tmp/deploy/images/capteur/image.fit

      - uses: actions/upload-artifact@v4
        with:
          name: release-${{ github.ref_name }}
          path: |
            build/tmp/deploy/images/capteur/image.fit
            image.sig
            image.pem
            sbom-firmware.cdx.json
```

`tools/gate-cve.py` (squelette à écrire toi-même — c'est l'exercice) :

```python
#!/usr/bin/env python3
"""Échoue si une CVE non justifiée dépasse le seuil CVSS."""
import json, sys, argparse, datetime, yaml

p = argparse.ArgumentParser()
p.add_argument("rapport"); p.add_argument("--bloquer-au-dessus-de", type=float, default=7.0)
p.add_argument("--exceptions", default=None)
a = p.parse_args()

exceptions = {}
if a.exceptions:
    for e in yaml.safe_load(open(a.exceptions))["exceptions"]:
        revoir = datetime.date.fromisoformat(str(e["revoir_avant"]))
        if revoir < datetime.date.today():
            sys.exit(f"Exception expirée pour {e['cve']} (à revoir avant {revoir})")
        exceptions[e["cve"]] = e["raison"]

bloquants = []
for paquet in json.load(open(a.rapport))["package"]:
    for issue in paquet.get("issue", []):
        if issue["status"] != "Unpatched":
            continue
        score = float(issue.get("scorev3") or 0)
        if score >= a.bloquer_au_dessus_de and issue["id"] not in exceptions:
            bloquants.append((issue["id"], paquet["name"], score))

for cve, pkg, score in sorted(bloquants, key=lambda x: -x[2]):
    print(f"BLOQUANT {cve} {pkg} CVSS={score}")
print(f"\n{len(bloquants)} CVE bloquantes, {len(exceptions)} exceptions actives")
sys.exit(1 if bloquants else 0)
```

> Note le contrôle d'**expiration des exceptions** : c'est ce qui empêche la liste de devenir un
> cimetière. Une exception qui expire casse le build — donc quelqu'un la regarde.

## Lab 3 — build reproductible

Deux builds du même commit doivent produire le **même** binaire, octet pour octet. Sans ça, tu
ne peux pas prouver qu'un binaire vient bien de ce code source (c'est le cœur du problème
SolarWinds).

Sources de non-déterminisme et parades :

| Source | Parade |
|---|---|
| Horodatages | `SOURCE_DATE_EPOCH=<date du commit>` |
| Chemins de build absolus | `-ffile-prefix-map=/build=.` |
| Ordre de listage des fichiers | trier explicitement (`find | sort`) |
| `__DATE__` / `__TIME__` | interdits (règle Semgrep à ajouter !) |
| UID/GID dans les archives | `tar --owner=0 --group=0 --numeric-owner --sort=name` |
| Aléa d'édition de liens | `-Wl,--build-id=none` ou build-id déterministe |
| Version de la toolchain | conteneur de build épinglé par digest (module 07) |

```bash
export SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct)
make clean && make && sha256sum firmware.bin > somme1
make clean && make && sha256sum firmware.bin > somme2
diff somme1 somme2 && echo "REPRODUCTIBLE"

# diagnostiquer un écart
sudo dnf install -y diffoscope
diffoscope build1/firmware.bin build2/firmware.bin
```

En CI : un job `reproductibilite` qui rebuild et compare. C'est une gate simple et très parlante
en audit.

## Lab 4 — mise à jour OTA signée

Le mécanisme d'OTA est **la fonction de sécurité la plus critique** d'un objet connecté : c'est
le seul moyen de corriger, et c'est aussi la meilleure porte d'entrée si elle est mal faite.

Exigences (à cocher sur ton implémentation) :

- [ ] Signature vérifiée **sur l'appareil, avant écriture**, avec une clé publique en OTP/ROM
- [ ] Transport en TLS avec vérification du certificat serveur (et mTLS si possible)
- [ ] **Anti-rollback** : compteur de version monotone en eFuse — sinon l'attaquant réinstalle
      une ancienne version vulnérable **signée**, donc acceptée
- [ ] **A/B partitions** ou mise à jour atomique : jamais d'état « à moitié flashé »
- [ ] Watchdog + rollback automatique si la nouvelle image ne confirme pas son bon démarrage
- [ ] Reprise sur coupure d'alimentation en cours d'écriture
- [ ] Déploiement progressif (canary 1 % → 10 % → 100 %)
- [ ] Journalisation des versions installées par appareil (traçabilité CRA)

Frameworks à connaître : **RAUC**, **SWUpdate**, **Mender**, **libostree**, et surtout
**TUF / Uptane** (Uptane est la norme du secteur automobile, elle traite explicitement les
attaques par rejeu, par gel de version et la compromission du serveur de mise à jour).

Exemple RAUC (`system.conf` sur la cible) :

```ini
[system]
compatible=capteur-v1
bootloader=uboot
bundle-formats=verity

[keyring]
path=/etc/rauc/keyring.pem       # certificat racine, en rootfs vérifié par dm-verity

[slot.rootfs.0]
device=/dev/mmcblk0p2
type=ext4
bootname=A

[slot.rootfs.1]
device=/dev/mmcblk0p3
type=ext4
bootname=B
```

```bash
# création d'un bundle signé (dans la CI, clé via OIDC/HSM)
rauc bundle --cert=cert.pem --key="pkcs11:object=cle-firmware" \
            --signing-keyring=ca.pem rootfs-dir/ update-1.2.0.raucb

# vérification (à faire aussi en CI : on teste la vérification, pas seulement la signature)
rauc info --keyring=ca.pem update-1.2.0.raucb
```

## Lab 5 — CI matérielle (hardware-in-the-loop)

```
[Runner GitHub auto-hébergé]
   ├── USB → programmateur (ST-Link / J-Link / DFU)
   ├── USB → UART de la cible (logs, console)
   ├── USB → relais ou alim pilotable (reset, test de coupure)
   └── USB → analyseur logique (optionnel : vérifier qu'aucune trace de debug ne sort)
        │
        └── Carte cible
```

```yaml
  test-materiel:
    runs-on: [self-hosted, banc-de-test]
    needs: build
    steps:
      - uses: actions/download-artifact@v4
        with: { name: release-${{ github.ref_name }} }
      - name: Flasher
        run: openocd -f interface/stlink.cfg -f target/stm32f4x.cfg \
               -c "program image.fit verify reset exit"
      - name: Tests fonctionnels
        run: python3 tests/hil/lancer.py --port /dev/ttyUSB0 --timeout 120
      - name: Tests de sécurité sur cible
        run: |
          python3 tests/hil/test_secure_boot.py    # une image non signée doit être REFUSÉE
          python3 tests/hil/test_antirollback.py   # une version antérieure doit être REFUSÉE
          python3 tests/hil/test_console.py        # aucun shell sur l'UART
          python3 tests/hil/test_ports.py          # nmap : seuls les ports attendus sont ouverts
      - name: Toujours remettre le firmware de référence
        if: always()
        run: ./tools/restaurer-reference.sh
```

Les quatre tests de sécurité ci-dessus sont ceux que presque personne n'automatise, et qui
détectent les régressions les plus graves (un `CONFIG_` perdu lors d'une montée de version de
Yocto désactive silencieusement la vérification de signature).

## SLSA — mesurer ta maturité supply chain

| Niveau | Exigence | Ce que ça demande chez toi |
|---|---|---|
| **L1** | provenance existante | générer une attestation au build |
| **L2** | build sur service hébergé + provenance signée | CI GitHub + cosign |
| **L3** | build isolé, provenance non falsifiable | runner éphémère, clé inaccessible au job |
| **L4** (v0.1) | build hermétique et reproductible, double revue | Lab 3 + revue à 2 |

```yaml
      - uses: actions/attest-build-provenance@v1
        with:
          subject-path: build/tmp/deploy/images/capteur/image.fit
```

Vérification côté consommateur :

```bash
gh attestation verify image.fit --repo yassirmouyiwa/devsecops-fil-rouge
```

## Critères de validation

- [ ] Tu dessines la chaîne de confiance complète de mémoire, avec le rôle de l'OTP
- [ ] Une image FIT signée boote ; une image modifiée d'un octet est **refusée** (testé)
- [ ] Ton build Yocto échoue sur une CVE > 7.0 non justifiée, et sur une exception expirée
- [ ] Deux builds successifs produisent le même hash
- [ ] Ton bundle OTA est signé, vérifié sur cible, et le rollback est bloqué
- [ ] Un test automatisé prouve qu'une image non signée est rejetée par la cible
- [ ] Tu situes ton projet sur l'échelle SLSA et tu sais ce qui manque pour le niveau suivant

## Pièges classiques

- **Secure boot activé, environnement U-Boot modifiable** : contournement en 1 minute par UART.
- **Même clé de signature pour dev et production** : une fuite côté dev compromet le parc.
- **Pas d'anti-rollback** : la faille corrigée reste exploitable à vie par réinstallation d'une
  version ancienne mais signée.
- **Fusibles non brûlés en production** : JTAG ouvert, secure boot en mode « warning ».
- **Aucun moyen de révoquer une clé compromise** : prévois une liste de révocation dès la
  conception, et **plusieurs clés** (racine hors ligne + clés de signature intermédiaires).
- **OTA testée seulement sur le chemin nominal** : teste la coupure d'alimentation pendant
  l'écriture, l'image corrompue, le disque plein, la signature invalide.

## Pour aller plus loin

- *Yocto Project Security Manual* — la section sur `cve-check` et le durcissement
- **Uptane** — norme de mise à jour sécurisée (automobile), lecture très formatrice
- TF-A (Trusted Firmware-A), OP-TEE — monde sécurisé ARM
- IEC 62443-4-1 (processus de développement) et 4-2 (exigences techniques) — module 12
- `binwalk`, `EMBA`, `firmwalker` — analyser le firmware de tes concurrents (ou le tien, vu par
  un attaquant)
