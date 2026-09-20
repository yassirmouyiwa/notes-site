---
title: DevSecOps · Checklists
date: 2026-09-20
tags: devsecops, checklist, firmware
description: Aide-mémoire : revue de PR, configuration d'un nouveau dépôt, avant une release, durcissement firmware, 60 premières minutes d'un incident.
---

# Aide-mémoire — checklists DevSecOps

> À garder ouvert pendant les labs et à réutiliser en revue de projet.

## Revue de PR — lunettes sécurité

- [ ] Aucun secret, aucune clé, aucun identifiant (même en commentaire, même « temporaire »)
- [ ] Entrées validées **aux frontières** (longueur, type, plage, encodage)
- [ ] Codes de retour vérifiés, surtout ceux des fonctions crypto et d'allocation
- [ ] Pas de fonction non bornée (`strcpy`, `sprintf`, `gets`, `system`)
- [ ] Arithmétique : risque de dépassement d'entier sur les tailles et index ?
- [ ] Nouvelle dépendance : nécessaire ? maintenue ? licence ? CVE ? épinglée avec hash ?
- [ ] Journalisation : événements de sécurité présents, aucune donnée sensible loguée
- [ ] Gestion d'erreur : pas de fuite d'information dans les messages
- [ ] Tests ajoutés, y compris les cas d'abus (pas seulement le chemin nominal)
- [ ] Modification d'un workflow CI ou d'un script de build → revue renforcée

## Nouveau dépôt — configuration du jour 1

- [ ] `.gitignore` avant le premier commit
- [ ] `.pre-commit-config.yaml` avec gitleaks
- [ ] Protection de branche sur `main` : pas de push direct, revue requise, checks obligatoires
- [ ] `CODEOWNERS`, avec `.github/workflows/` couvert
- [ ] `SECURITY.md` (politique de divulgation)
- [ ] `permissions:` explicites dans chaque workflow
- [ ] Actions tierces épinglées par SHA
- [ ] Dependabot / Renovate activé
- [ ] Commits signés exigés
- [ ] Secret scanning + push protection activés

## Avant une release

- [ ] Pipeline vert sur toutes les gates (aucune désactivée « juste pour cette fois »)
- [ ] SBOM généré et archivé avec l'artefact
- [ ] Aucune CVE critique non justifiée ; exceptions non expirées
- [ ] Artefact signé, signature **vérifiée depuis une autre machine**
- [ ] Attestation de provenance produite
- [ ] Build reproductible vérifié (2 builds, même hash)
- [ ] Notes de version listant les vulnérabilités corrigées
- [ ] Tests HIL passés, dont les 4 tests de sécurité sur cible
- [ ] Procédure de rollback testée
- [ ] Matrice de conformité à jour

## Firmware — checklist de durcissement

**Boot**
- [ ] Secure boot activé et **vérifié par un test automatisé**
- [ ] Clé publique de vérification en OTP/ROM, non réinscriptible
- [ ] Environnement bootloader verrouillé (pas de modification de `bootcmd`)
- [ ] JTAG/SWD désactivé en production (fusible)
- [ ] Anti-rollback par compteur monotone

**Système**
- [ ] Rootfs en lecture seule + dm-verity
- [ ] Aucun compte sans mot de passe, aucun identifiant par défaut
- [ ] Console série désactivée ou authentifiée
- [ ] Services inutiles retirés (telnet, ftp, ssh si non nécessaire)
- [ ] Options de durcissement noyau activées (KSPP)
- [ ] Aucun binaire SUID inattendu
- [ ] Aucune clé privée dans le rootfs
- [ ] Aucun symbole de debug, aucune chaîne de build interne dans l'image livrée

**Communication**
- [ ] TLS 1.2+ avec vérification du certificat serveur (pas de `verify=False`)
- [ ] Certificat client unique par appareil, généré dans le Secure Element
- [ ] Pas de clé partagée entre appareils
- [ ] Révocation possible par appareil

**Mise à jour**
- [ ] Signature vérifiée sur l'appareil avant écriture
- [ ] Mise à jour atomique (A/B) et reprise sur coupure
- [ ] Rollback automatique si le nouveau firmware ne démarre pas
- [ ] Déploiement progressif et suivi du taux de couverture

## Incident — les 60 premières minutes

1. **Noter l'heure** et ouvrir un journal d'incident horodaté (tout y va, même les hypothèses)
2. **Qualifier** : quoi, combien d'appareils/clients, exploitable à distance, exploitation déjà
   observée ?
3. **Prévenir** : responsable produit, juridique si données personnelles ou notification CRA
4. **Préserver** : snapshots, logs exportés, ne pas écraser les preuves en réparant
5. **Contenir** : couper la fonction, bloquer côté serveur, révoquer les accès
6. **Ne pas** : accuser quelqu'un, communiquer publiquement sans validation, redémarrer sans
   collecter, promettre un délai de correction avant d'avoir compris

Rappel réglementaire : CRA → alerte précoce ENISA sous **24 h**, rapport sous 72 h, rapport
final sous 14 jours. RGPD → notification CNDP/CNIL sous 72 h si données personnelles.

## Commandes de référence

```bash
# Secrets
gitleaks detect --source . --redact -v
gitleaks protect --staged                       # avant commit

# SAST
semgrep --config=p/c --config=.semgrep/ --error .
gcc -fanalyzer -Wall -Wextra -Werror -c fichier.c
cppcheck --enable=all --error-exitcode=1 src/
clang-tidy fichier.c -checks='clang-analyzer-*,cert-*,bugprone-*'

# SCA / SBOM
syft dir:. -o cyclonedx-json=sbom.json
grype sbom:sbom.json --fail-on high
trivy image --severity HIGH,CRITICAL --exit-code 1 image:tag

# Conteneurs
podman build -t img:1.0 . && podman history img:1.0
trivy config Containerfile
cosign sign img:1.0 && cosign verify img:1.0 --certificate-identity-regexp '...'

# Binaire
checksec --file=binaire
readelf -d binaire | grep -E 'BIND_NOW|RELRO'
strings -n 8 firmware.bin | grep -iE 'password|key|BEGIN.*PRIVATE'
binwalk -Me firmware.bin

# Fuzzing
clang -fsanitize=fuzzer,address,undefined -g -O1 -o fuzz harnais.c source.c
./fuzz corpus/ -max_total_time=600
./fuzz -minimize_crash=1 -runs=100000 crash-xxxx

# Système
systemd-analyze security monservice.service
lynis audit system --quick
oscap xccdf eval --profile <profil> --report r.html <datastream>
find / -perm /6000 -type f 2>/dev/null
```

## Les 10 erreurs qui reviennent le plus

1. Gates configurées en `continue-on-error` — décoratives
2. Exceptions CVE sans date de revue — la liste devient la vraie politique
3. Secret nettoyé de l'historique mais jamais révoqué
4. Pipeline trop lent → contourné par toute l'équipe
5. Secure boot activé mais environnement bootloader modifiable
6. Clé de signature unique partagée dev/prod, ou stockée sur un poste
7. SBOM généré une fois, jamais rescanné
8. Aucun test automatisé du refus d'une image non signée
9. Console série laissée active « pour le SAV »
10. Documentation de conformité écrite la veille de l'audit
