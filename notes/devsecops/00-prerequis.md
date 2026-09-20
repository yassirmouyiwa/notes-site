---
title: DevSecOps 00 · Prérequis et mise en place
date: 2026-09-20
tags: devsecops, linux, outillage
description: Auto-évaluation des socles (Linux, réseau, Git, conteneurs), installation de la boîte à outils sur Fedora et création du dépôt fil rouge.
---

# Module 00 — Prérequis et mise en place

> Durée : 4–6 h. Objectif : ne plus jamais être bloqué par l'outillage pendant les modules suivants.

## Objectifs

- Vérifier honnêtement ton niveau sur les 5 socles : Linux, réseau, Git, scripting, conteneurs.
- Installer la base d'outils sur Fedora.
- Créer le dépôt de travail qui servira de fil rouge à tout le parcours.

## Auto-évaluation (sois honnête, 5 min)

Coche ce que tu sais faire **sans chercher** :

**Linux**
- [ ] Lire `/proc/<pid>/`, comprendre `ps`, `lsof`, `ss -tulpn`
- [ ] Écrire un service `systemd` avec `Restart=on-failure` et des options de durcissement
- [ ] Comprendre uid/gid, capabilities (`getcap`), umask, `chattr +i`
- [ ] Lire un `journalctl -u service -p err --since "1 hour ago"`

**Réseau**
- [ ] Différencier TLS 1.2 / 1.3, comprendre une chaîne de certificats
- [ ] Lire une capture Wireshark d'un handshake TLS
- [ ] Savoir ce que fait un reverse proxy, un NAT, un bastion

**Git**
- [ ] `rebase -i`, `cherry-pick`, `bisect`, `reflog`
- [ ] Expliquer pourquoi supprimer un fichier ≠ le supprimer de l'historique

**Scripting**
- [ ] Bash : `set -euo pipefail`, traps, substitution de process
- [ ] Python : venv, `argparse`, `subprocess`, parsing JSON/YAML

**Conteneurs**
- [ ] Écrire un Containerfile multi-stage
- [ ] Expliquer namespaces + cgroups en deux phrases

> Moins de 70 % coché ? Comble d'abord les trous : sur ce parcours, DevSecOps = outillage
> autour de ces socles, pas à la place.

## Installation de la base

⚠️ `sudo` ne fonctionne pas depuis Claude Code (pas de TTY) : ouvre un **vrai terminal**.

```bash
# Socle build + analyse
sudo dnf install -y gcc gcc-c++ make cmake git-lfs jq yq \
     python3-pip python3-devel golang \
     clang clang-tools-extra cppcheck \
     strace ltrace gdb valgrind \
     nmap tcpdump wireshark-cli \
     podman podman-compose buildah skopeo

# Chaîne embarquée (utile à partir du module 04)
sudo dnf install -y arm-none-eabi-gcc-cs arm-none-eabi-newlib \
     qemu-system-arm qemu-user-static \
     binwalk squashfs-tools dtc
```

Outils sécurité livrés en binaire unique (pas de root nécessaire) :

```bash
mkdir -p ~/.local/bin && export PATH="$HOME/.local/bin:$PATH"
# à ajouter dans ~/.bashrc si ce n'est pas déjà fait

# gitleaks (secrets)
curl -sSL https://github.com/gitleaks/gitleaks/releases/latest/download/gitleaks_$(curl -s https://api.github.com/repos/gitleaks/gitleaks/releases/latest | jq -r .tag_name | tr -d v)_linux_x64.tar.gz \
  | tar -xz -C ~/.local/bin gitleaks

# syft + grype (SBOM et CVE)
curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh   | sh -s -- -b ~/.local/bin
curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh  | sh -s -- -b ~/.local/bin

# trivy (conteneurs, FS, IaC)
curl -sSfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b ~/.local/bin
```

Outils Python — **toujours en venv**, pip n'est pas en système :

```bash
python3 -m venv ~/.venvs/devsecops
~/.venvs/devsecops/bin/pip install semgrep checkov pre-commit detect-secrets
# usage : ~/.venvs/devsecops/bin/semgrep --version
# ou :   source ~/.venvs/devsecops/bin/activate
```

## Podman au lieu de Docker

Toute la doc DevSecOps parle de `docker`. Sur cette machine :

```bash
echo 'alias docker=podman' >> ~/.bashrc
```

Différences à connaître :

| Docker | Podman | Remarque |
|---|---|---|
| daemon root | **sans daemon, rootless par défaut** | meilleure posture sécurité, c'est un avantage |
| `Dockerfile` | `Containerfile` (les deux marchent) | |
| `docker-compose` | `podman-compose` | quelques options non supportées |
| socket `/var/run/docker.sock` | `podman system service` | nécessaire pour Trivy/certains outils |

## Lab — créer le dépôt fil rouge

```bash
mkdir -p ~/devsecops/labs/fil-rouge && cd ~/devsecops/labs/fil-rouge
git init -b main

cat > README.md <<'MD'
# Fil rouge DevSecOps
Application de démonstration : capteur embarqué + API de collecte.
Sert de support aux labs du parcours.
MD

mkdir -p firmware/src api tools .github/workflows
cat > firmware/src/main.c <<'C'
#include <stdio.h>
#include <string.h>

void handle_frame(const char *input) {
    char buf[32];
    strcpy(buf, input);           /* défaut volontaire : CWE-120 */
    printf("frame=%s\n", buf);
}

int main(int argc, char **argv) {
    if (argc > 1) handle_frame(argv[1]);
    return 0;
}
C

git add -A && git commit -m "init: squelette du fil rouge"
gh repo create devsecops-fil-rouge --private --source=. --remote=origin --push
```

Le défaut dans `main.c` est **volontaire** : il servira de cible aux modules SAST et fuzzing.

## Critères de validation

- [ ] `podman run --rm docker.io/library/alpine echo ok` affiche `ok`
- [ ] `gitleaks version`, `syft version`, `grype version`, `trivy --version` répondent
- [ ] `~/.venvs/devsecops/bin/semgrep --version` répond
- [ ] Le dépôt `devsecops-fil-rouge` existe sur GitHub et contient le squelette
- [ ] Tu sais expliquer la différence rootless / rootful

## Pièges classiques

- **Installer les outils Python en `sudo pip`** : ça casse `dnf` à terme. Venv, toujours.
- **Mettre `~/.local/bin` dans le PATH seulement dans la session courante** : ajoute-le à
  `~/.bashrc`, sinon la CI locale et les hooks Git ne trouveront rien.
- **Confondre « installé » et « compris »** : après chaque install, lance l'outil sur un cas
  connu pour voir la forme de sa sortie (c'est ce que tu parseras en CI).

## Pour aller plus loin

- `man 7 capabilities`, `man 5 systemd.exec` (section *Sandboxing*)
- *The Linux Programming Interface*, chapitres 9 (credentials) et 39 (capabilities)
