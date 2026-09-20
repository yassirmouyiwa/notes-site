---
title: DevSecOps 11 · Runtime, détection et réponse
date: 2026-09-20
tags: devsecops, detection, incident-response
description: Journalisation exploitable, règles Falco et auditd, plan de réponse à incident pour un parc d'objets, gestion des vulnérabilités entrantes.
---

# Module 11 — Runtime : détection, réponse, gestion des vulnérabilités

> Durée : 6–8 h. Objectif : savoir ce qui se passe **après** le déploiement, et réagir vite.

## Objectifs

- Instrumenter une application et un objet pour produire des journaux exploitables.
- Détecter un comportement anormal (Falco, Wazuh, auditd).
- Écrire un plan de réponse à incident réaliste pour un produit embarqué.
- Organiser la gestion des vulnérabilités : réception, triage, correctif, divulgation.

## Théorie utile

### Le DevSecOps ne s'arrête pas au déploiement

Le cycle complet : `Plan → Code → Build → Test → Release → Deploy → Operate → Monitor → Plan`.
Les modules 01–10 couvrent jusqu'à *Deploy*. Ici, on ferme la boucle : ce qu'on observe en
production redevient une exigence de conception.

### Trois piliers d'observabilité

| Pilier | Question | Outil |
|---|---|---|
| **Logs** | que s'est-il passé ? | journald, syslog, Loki, ELK |
| **Métriques** | dans quel état est le système ? | Prometheus, Grafana |
| **Traces** | où est passé le temps / la requête ? | OpenTelemetry, Jaeger |

En embarqué, ajoute un quatrième pilier : **la télémétrie d'intégrité** (le secure boot a-t-il
vérifié ? y a-t-il eu un rollback ? le watchdog a-t-il redémarré ? le boîtier a-t-il été ouvert ?).

### Ce qu'il faut journaliser (et ne pas journaliser)

À journaliser :
- authentification (succès **et** échec), avec source
- changement de privilège, de configuration, de clé
- mise à jour firmware : version avant/après, résultat de la vérification de signature
- échec de vérification d'intégrité, redémarrage watchdog, détection d'ouverture du boîtier
- connexions réseau sortantes inattendues

À ne **jamais** journaliser : mots de passe, jetons, clés, données personnelles brutes, contenu
de trames complet en production.

Format : structuré (JSON), horodaté en UTC avec source de temps fiable, identifiant d'appareil,
version de firmware. Un log sans version de firmware est inutilisable lors d'un incident de parc.

## Lab 1 — journalisation structurée + détection

```python
# labs/11-runtime/journal.py — journalisation structurée d'événements de sécurité
import json, logging, sys, time, os

class FormateurJSON(logging.Formatter):
    def format(self, record):
        base = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "niveau": record.levelname,
            "evenement": record.getMessage(),
            "appareil": os.getenv("DEVICE_ID", "inconnu"),
            "firmware": os.getenv("FW_VERSION", "inconnu"),
        }
        base.update(getattr(record, "extra_champs", {}))
        return json.dumps(base, ensure_ascii=False)

log = logging.getLogger("securite")
h = logging.StreamHandler(sys.stdout); h.setFormatter(FormateurJSON())
log.addHandler(h); log.setLevel(logging.INFO)

def evenement(nom, **champs):
    log.info(nom, extra={"extra_champs": champs})

evenement("auth_echec", utilisateur="admin", source="192.168.1.50", tentative=4)
evenement("ota_verification", resultat="signature_invalide", version_proposee="1.3.0")
```

### Falco (conteneurs / Linux) — détection comportementale

```yaml
# /etc/falco/rules.d/embarque.yaml
- rule: Shell inattendu dans un conteneur de production
  desc: Un shell interactif ne devrait jamais démarrer dans ces conteneurs
  condition: >
    spawned_process and container
    and proc.name in (bash, sh, dash, zsh, busybox)
    and not container.image.repository in (debug-tools)
  output: "Shell dans un conteneur (utilisateur=%user.name conteneur=%container.name cmd=%proc.cmdline)"
  priority: WARNING
  tags: [container, mitre_execution]

- rule: Lecture d'un fichier de clé de signature
  desc: Accès en lecture au matériel cryptographique
  condition: >
    open_read and fd.name glob "/etc/keys/*.pem"
    and not proc.name in (rauc, swupdate)
  output: "Accès aux clés (proc=%proc.name utilisateur=%user.name fichier=%fd.name)"
  priority: CRITICAL
```

### auditd — pour un Linux embarqué sans conteneurs

```bash
# /etc/audit/rules.d/embarque.rules
-w /etc/shadow -p wa -k identifiants
-w /etc/rauc/keyring.pem -p wa -k cles
-w /usr/bin/ -p wa -k binaires_systeme
-a always,exit -F arch=b64 -S execve -F euid=0 -k execution_root
-a always,exit -F arch=b64 -S mount -k montage

# consultation
ausearch -k cles -ts today
aureport --summary
```

> Sur cible contrainte, auditd coûte cher (CPU, flash). Sélectionne 5–10 règles à forte valeur
> plutôt qu'un jeu complet, et fais tourner les journaux en RAM avec export distant.

## Lab 2 — Wazuh (SIEM open source, réaliste pour un parc)

```bash
podman run -d --name wazuh -p 1514:1514/udp -p 55000:55000 \
  docker.io/wazuh/wazuh-manager:4.9.0
```

À configurer et à savoir expliquer :
- **FIM** (surveillance d'intégrité des fichiers) sur `/etc`, `/usr/bin`, les clés
- détection d'écart de configuration (SCA, benchmarks CIS intégrés)
- corrélation : 5 échecs d'authentification en 60 s → alerte
- réponse active : blocage IP temporaire

## Lab 3 — plan de réponse à incident (embarqué)

Écris `labs/11-runtime/plan-ir.md`. Un plan qui tient en 2 pages et qu'on peut appliquer à 3 h
du matin vaut mieux qu'un document de 60 pages.

```markdown
# Plan de réponse — produit capteur v1

## 0. Avant l'incident (à préparer maintenant)
- Contacts : responsable produit, juridique, CERT national (maCERT pour le Maroc), client
- Accès de secours : comment joindre un parc dont l'OTA est HS ?
- Canal de communication hors bande (si l'infra est compromise)
- Sauvegarde hors ligne des clés de signature et de la procédure de révocation

## 1. Détection et qualification (T+0 → T+2h)
- Source : alerte SIEM / rapport chercheur / CVE amont / client
- Questions : combien d'appareils ? exploitable à distance ? exploitation déjà observée ?
- Décision : incident majeur (cellule de crise) ou traitement normal

## 2. Confinement (T+2h → T+24h)
- Couper la fonction vulnérable à distance si possible (feature flag)
- Bloquer côté serveur (le contrôle côté back-end est souvent plus rapide que l'OTA)
- Révoquer les certificats des appareils compromis
- ⚠️ Ne jamais « briquer » un parc pour se protéger : impact client et juridique

## 3. Éradication et correction (J+1 → J+14)
- Correctif, revue à 4 yeux, tests HIL complets, build reproductible
- Déploiement progressif : 1 % → 10 % → 100 %, avec surveillance du taux d'échec
- Suivi du taux de mise à jour : tout parc a une traîne de 20–40 %

## 4. Communication
- Avis de sécurité public (format CSAF/VEX), CVE demandée si le produit est distribué
- ⚠️ CRA : notification à l'ENISA sous **24 h** pour une vulnérabilité activement exploitée
  ou un incident grave (alerte précoce), rapport sous 72 h, rapport final sous 14 jours

## 5. Retour d'expérience (J+30)
- Chronologie factuelle, sans blâme
- Pourquoi la CI ne l'a pas détecté → **nouveau test / nouvelle règle** (c'est le livrable réel)
- Délai de détection, de correction, de déploiement : à mesurer et à améliorer
```

## Gestion des vulnérabilités : le processus entrant

| Élément | Ce qu'il faut |
|---|---|
| **security.txt** | `/.well-known/security.txt` avec contact, clé PGP, politique |
| **Politique de divulgation** | délai annoncé (90 jours usuels), engagement de non-poursuite |
| **SLA interne** | critique 7 j, élevé 30 j, moyen 90 j |
| **Veille amont** | s'abonner aux avis des composants du SBOM (oss-security, listes Yocto) |
| **Rescan quotidien** | les SBOM des versions **en production**, pas seulement de la branche |
| **Publication** | avis CSAF + VEX, pour que tes clients puissent trier automatiquement |

```
# /.well-known/security.txt
Contact: mailto:security@exemple.ma
Expires: 2027-09-20T00:00:00.000Z
Encryption: https://exemple.ma/pgp-key.txt
Policy: https://exemple.ma/divulgation
Preferred-Languages: fr, en, ar
```

## Métriques à suivre (DORA + sécurité)

| Métrique | Ce qu'elle dit |
|---|---|
| Fréquence de déploiement | capacité à livrer un correctif |
| Délai de mise en production (*lead time*) | temps entre commit et terrain |
| MTTR | temps de rétablissement |
| Taux d'échec des changements | qualité |
| **MTTD sécurité** | délai de détection |
| **MTTR vulnérabilité** | de la publication de la CVE au déploiement du correctif |
| **Taux de couverture OTA** | % du parc à jour à J+30 — la métrique reine en IoT |
| Âge moyen des vulnérabilités ouvertes | dette de sécurité |

## Critères de validation

- [ ] Ton application produit des logs JSON incluant appareil + version de firmware
- [ ] Une règle Falco ou auditd maison déclenche sur un accès aux clés
- [ ] `plan-ir.md` tient en 2 pages et couvre les 5 phases
- [ ] Tu connais les délais de notification du CRA (24 h / 72 h / 14 j)
- [ ] Tu as un `security.txt` et une politique de divulgation rédigée
- [ ] Tu sais dire combien de temps il te faudrait pour corriger un parc de 10 000 objets

## Pièges classiques

- **Tout journaliser** : coût, bruit, et souvent des données personnelles. Journalise les
  événements de sécurité, pas le débit.
- **Alertes sans destinataire** : une alerte qui n'arrive nulle part n'existe pas.
- **Logs stockés uniquement sur l'appareil compromis** : export distant, sinon l'attaquant
  efface.
- **Plan IR jamais testé** : fais un exercice sur table de 2 h par an, minimum.
- **Pas de plan pour les objets hors ligne** (parc en zone blanche, objets sur batterie).

## Pour aller plus loin

- *Site Reliability Engineering* (Google) — chapitres sur les astreintes et les post-mortems
- CSAF 2.0 — format d'avis de sécurité lisible par machine
- MITRE ATT&CK for ICS — tactiques adverses en contexte industriel
- Wazuh, Falco, OSSEC ; Prometheus + Grafana pour les métriques
