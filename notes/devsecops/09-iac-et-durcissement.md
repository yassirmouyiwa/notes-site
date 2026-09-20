---
title: DevSecOps 09 · IaC et durcissement système
date: 2026-09-20
tags: devsecops, iac, durcissement
description: Playbook Ansible de durcissement, scan d'IaC avec Checkov, audit OpenSCAP, et durcissement d'un Linux embarqué (noyau, rootfs, services).
---

# Module 09 — Infrastructure as Code et durcissement système

> Durée : 6–8 h. Objectif : décrire l'infrastructure dans du code versionné, la scanner comme du
> code, et durcir un Linux — serveur comme embarqué.

## Objectifs

- Écrire un playbook Ansible idempotent qui durcit un hôte.
- Scanner de l'IaC (Terraform, Ansible, Containerfile, workflows) avec Checkov/Trivy.
- Auditer un système contre un benchmark (CIS / OpenSCAP / Lynis).
- Transposer le durcissement à un Linux embarqué (noyau, rootfs, services).

## Théorie utile

### Pourquoi l'IaC change la sécurité

| Sans IaC | Avec IaC |
|---|---|
| Configuration dans la tête de l'admin | dans Git, relue, versionnée |
| Dérive silencieuse entre machines | écart détecté à chaque exécution |
| Audit = connexion manuelle sur 40 machines | audit = lecture d'un dépôt |
| Correctif appliqué à 37 machines sur 40 | appliqué partout ou échec visible |

Corollaire : **une mauvaise configuration IaC se réplique aussi parfaitement.** D'où le scan.

### Les mauvaises configurations qui coûtent le plus cher

1. Stockage objet public (S3/Blob) — la cause n°1 des fuites de données massives
2. Groupe de sécurité `0.0.0.0/0` sur 22/3389/BDD
3. Chiffrement au repos désactivé
4. Journalisation désactivée (pas de flow logs, pas d'audit trail)
5. Rôles IAM avec `*:*`
6. Pas de MFA sur les comptes privilégiés

## Lab 1 — durcissement Ansible

`labs/09-iac/durcissement.yml` :

```yaml
---
- name: Durcissement de base d'un hôte Linux
  hosts: all
  become: true

  vars:
    ssh_port: 22
    utilisateurs_autorises: ['y455ir']

  tasks:
    - name: SSH — désactiver l'authentification par mot de passe et le login root
      ansible.builtin.lineinfile:
        path: /etc/ssh/sshd_config
        regexp: "^#?{{ item.cle }}"
        line: "{{ item.cle }} {{ item.valeur }}"
        validate: /usr/sbin/sshd -t -f %s
      loop:
        - { cle: PermitRootLogin,        valeur: 'no' }
        - { cle: PasswordAuthentication, valeur: 'no' }
        - { cle: KbdInteractiveAuthentication, valeur: 'no' }
        - { cle: X11Forwarding,          valeur: 'no' }
        - { cle: MaxAuthTries,           valeur: '3' }
        - { cle: ClientAliveInterval,    valeur: '300' }
        - { cle: AllowUsers,             valeur: "{{ utilisateurs_autorises | join(' ') }}" }
      notify: redemarrer sshd

    - name: Paramètres noyau de sécurité
      ansible.posix.sysctl:
        name: "{{ item.cle }}"
        value: "{{ item.valeur }}"
        sysctl_set: true
        state: present
        reload: true
      loop:
        - { cle: kernel.kptr_restrict,               valeur: '2' }
        - { cle: kernel.dmesg_restrict,              valeur: '1' }
        - { cle: kernel.yama.ptrace_scope,           valeur: '1' }
        - { cle: kernel.unprivileged_bpf_disabled,   valeur: '1' }
        - { cle: net.ipv4.conf.all.rp_filter,        valeur: '1' }
        - { cle: net.ipv4.conf.all.accept_redirects, valeur: '0' }
        - { cle: net.ipv4.tcp_syncookies,            valeur: '1' }
        - { cle: fs.protected_hardlinks,             valeur: '1' }
        - { cle: fs.protected_symlinks,              valeur: '1' }
        - { cle: fs.suid_dumpable,                   valeur: '0' }

    - name: Désactiver les modules noyau inutiles (systèmes de fichiers exotiques)
      ansible.builtin.copy:
        dest: /etc/modprobe.d/durcissement.conf
        content: |
          install cramfs /bin/true
          install freevxfs /bin/true
          install jffs2 /bin/true
          install hfs /bin/true
          install udf /bin/true
          install usb-storage /bin/true
        mode: '0644'

    - name: Durcir une unité systemd de service applicatif
      ansible.builtin.copy:
        dest: /etc/systemd/system/collecteur.service.d/durcissement.conf
        content: |
          [Service]
          NoNewPrivileges=yes
          PrivateTmp=yes
          PrivateDevices=yes
          ProtectSystem=strict
          ProtectHome=yes
          ProtectKernelTunables=yes
          ProtectKernelModules=yes
          ProtectControlGroups=yes
          RestrictNamespaces=yes
          RestrictRealtime=yes
          RestrictSUIDSGID=yes
          LockPersonality=yes
          MemoryDenyWriteExecute=yes
          SystemCallArchitectures=native
          SystemCallFilter=@system-service
          CapabilityBoundingSet=CAP_NET_BIND_SERVICE
        mode: '0644'
      notify: recharger systemd

  handlers:
    - name: redemarrer sshd
      ansible.builtin.service: { name: sshd, state: restarted }
    - name: recharger systemd
      ansible.builtin.systemd: { daemon_reload: true }
```

Test à blanc, puis vérification d'idempotence (2e passage = 0 `changed`) :

```bash
ansible-playbook -i inventaire durcissement.yml --check --diff
ansible-playbook -i inventaire durcissement.yml
ansible-playbook -i inventaire durcissement.yml | grep 'changed=0'
```

> `systemd-analyze security collecteur.service` donne une note d'exposition de 0 à 10. C'est un
> excellent indicateur à mettre en CI : on exige une note < 4.

## Lab 2 — scanner l'IaC

```bash
source ~/.venvs/devsecops/bin/activate

checkov -d . --framework terraform,ansible,dockerfile,github_actions \
        --compact --quiet --output cli --output sarif

trivy config .            # Terraform, CloudFormation, K8s, Containerfile
trivy fs --scanners misconfig,secret .
```

En CI :

```yaml
  iac:
    runs-on: ubuntu-latest
    permissions: { contents: read, security-events: write }
    steps:
      - uses: actions/checkout@v4
      - uses: bridgecrewio/checkov-action@master
        with:
          directory: .
          soft_fail: false
          output_format: sarif
          output_file_path: checkov.sarif
      - uses: github/codeql-action/upload-sarif@v3
        with: { sarif_file: checkov.sarif }
```

Une exception se déclare **dans le code**, avec sa raison :

```hcl
# checkov:skip=CKV_AWS_18:bucket de logs éphémères, versioning inutile — revoir 2027-01
resource "aws_s3_bucket" "logs" { ... }
```

## Lab 3 — audit par benchmark

```bash
# Lynis : audit généraliste, lisible, sans configuration
sudo dnf install -y lynis
sudo lynis audit system --quick

# OpenSCAP : audit normalisé (profils CIS / ANSSI / PCI-DSS)
sudo dnf install -y openscap-scanner scap-security-guide
oscap info /usr/share/xml/scap/ssg/content/ssg-fedora-ds.xml   # lister les profils

sudo oscap xccdf eval \
  --profile xccdf_org.ssgproject.content_profile_standard \
  --results resultats.xml --report rapport.html \
  /usr/share/xml/scap/ssg/content/ssg-fedora-ds.xml
```

> Le profil **ANSSI-BP-028** (niveaux minimal / intermédiaire / renforcé / élevé) est disponible
> dans SCAP Security Guide. En contexte français/marocain avec exigences étatiques, c'est la
> référence à citer.

## Durcissement d'un Linux embarqué

Là où ça diffère d'un serveur :

| Axe | Mesure |
|---|---|
| Rootfs | **lecture seule** + overlay en RAM pour les données volatiles |
| Intégrité | `dm-verity` (arbre de hachage signé) — toute altération du rootfs est détectée au boot |
| Données | `dm-crypt` / LUKS, clé scellée dans le TPM ou dérivée du SE |
| Noyau | retirer modules et pilotes inutiles, `CONFIG_MODULES=n` si possible |
| Noyau (options) | `CONFIG_STRICT_KERNEL_RWX`, `CONFIG_FORTIFY_SOURCE`, `CONFIG_STACKPROTECTOR_STRONG`, `CONFIG_RANDOMIZE_BASE`, `CONFIG_SLAB_FREELIST_HARDENED`, `CONFIG_INIT_ON_ALLOC_DEFAULT_ON`, `CONFIG_DEBUG_FS=n`, `CONFIG_DEVMEM=n` |
| Ligne de commande | `init_on_free=1 slab_nomerge lockdown=confidentiality` |
| Console série | **désactivée en production** (ou authentifiée). Un `getty` sur UART = root en 30 s |
| JTAG/SWD | désactivé par fusible en production |
| Services | pas de telnet/ftp/dropbear ouvert ; BusyBox compilé sans les applets inutiles |
| Comptes | pas de mot de passe par défaut, pas de compte de maintenance universel |
| Espace utilisateur | `CONFIG_USER_NS` désactivé si inutile, capabilities au lieu de root |

Vérification automatisable :

```bash
# script de conformité à lancer sur l'image générée (Yocto/Buildroot), en CI
python3 tools/verifier-durcissement.py --rootfs output/images/rootfs/
# contrôles : /etc/shadow sans mot de passe vide, pas de fichier SUID inattendu,
# pas de clé privée, pas de getty sur ttyS0, CONFIG_* attendus dans le .config du noyau
```

```bash
# fichiers SUID/SGID inattendus dans le rootfs
find output/images/rootfs -perm /6000 -type f -printf '%M %p\n'
# clés privées oubliées
grep -rl 'BEGIN .*PRIVATE KEY' output/images/rootfs/ 2>/dev/null
# comptes sans mot de passe
awk -F: '($2==""){print "Compte sans mot de passe:",$1}' output/images/rootfs/etc/shadow
```

Ces trois commandes, mises en gate CI, attrapent une bonne partie des incidents réels de l'IoT.

## Critères de validation

- [ ] Le playbook est idempotent (2e passage : `changed=0`)
- [ ] `systemd-analyze security` de ton service passe sous 4.0
- [ ] Checkov tourne en CI, avec exceptions justifiées et datées
- [ ] Tu as un rapport OpenSCAP et tu sais lire un `rule-result`
- [ ] Ton script de vérification de rootfs détecte : SUID inattendu, clé privée, compte vide
- [ ] Tu cites 8 options `CONFIG_*` de durcissement noyau et leur effet

## Pièges classiques

- **Durcir sans tester la fonctionnalité** : `ProtectSystem=strict` casse un service qui écrit
  dans `/var`. Toujours dérouler les tests d'intégration après durcissement.
- **Terraform `state` non chiffré et versionné en clair** : il contient les secrets générés.
- **Appliquer un benchmark CIS à 100 %** sur un embarqué : plusieurs règles sont inapplicables.
  Documente les écarts, ne les ignore pas silencieusement.
- **Laisser la console série active « pour le SAV »** : c'est la porte d'entrée la plus utilisée
  en analyse de firmware.

## Pour aller plus loin

- `systemd-analyze security` sur tous tes services
- Kernel Self Protection Project (KSPP) — liste des options recommandées
- ANSSI — *Recommandations de configuration d'un système GNU/Linux* (BP-028)
