---
title: DevSecOps 08 · DAST et fuzzing
date: 2026-09-20
tags: devsecops, fuzzing, dast
description: Automatiser ZAP et nuclei, écrire un harnais libFuzzer pour un parseur C, fuzzer un protocole série et trier les crashs.
---

# Module 08 — DAST et fuzzing

> Durée : 8–10 h. Objectif : trouver des défauts que le SAST ne peut pas voir, en exécutant le
> logiciel. C'est le module le plus proche de ton réflexe pentest — la différence est qu'ici,
> tout doit tourner **sans humain**, toutes les nuits.

## Objectifs

- Automatiser un scan DAST sur une API dans le pipeline.
- Écrire un harnais de fuzzing pour un parseur C et l'intégrer en CI.
- Fuzzer un protocole embarqué (trames série, Modbus, CAN, BLE).
- Savoir trier : un crash n'est pas forcément une vulnérabilité.

## Théorie utile

### DAST vs pentest

| | DAST automatisé | Pentest manuel |
|---|---|---|
| Fréquence | chaque nuit | 1–2 fois par an |
| Couverture | connu, répétable | créatif, chaînes d'attaques |
| Logique métier | ❌ | ✓ |
| Coût marginal | ~0 | élevé |

Le DAST ne remplace pas le pentest ; il évite que le pentesteur perde 3 jours sur des choses
qu'un script trouve.

### Types de fuzzing

| Type | Principe | Usage |
|---|---|---|
| **Mutation** | part d'entrées valides et les altère | AFL++, libFuzzer — le plus rentable |
| **Génération** | construit des entrées depuis une grammaire | protocoles structurés, boofuzz |
| **Guidé par couverture** | instrumente le binaire pour explorer de nouveaux chemins | l'état de l'art |
| **Structuré** | garde une structure valide (protobuf) | parseurs complexes |

Le fuzzing guidé par couverture + sanitizers, c'est **le** meilleur rapport effort/résultat pour
du code C embarqué.

## Lab 1 — DAST sur l'API du fil rouge

```bash
# API cible (démo) dans un conteneur
podman run -d --name api -p 8080:8080 mon-api:1.0

# Scan de base ZAP
podman run --rm --network=host -v "$PWD:/zap/wrk/:z" \
  docker.io/zaproxy/zap-stable zap-baseline.py \
  -t http://localhost:8080 -r rapport-zap.html -w rapport-zap.md

# Scan piloté par la spec OpenAPI : bien plus efficace qu'un crawl
podman run --rm --network=host -v "$PWD:/zap/wrk/:z" \
  docker.io/zaproxy/zap-stable zap-api-scan.py \
  -t http://localhost:8080/openapi.json -f openapi -r rapport-api.html

# nuclei : templates de CVE et de mauvaises configurations
podman run --rm --network=host docker.io/projectdiscovery/nuclei \
  -u http://localhost:8080 -severity critical,high,medium
```

En CI, en nocturne (jamais sur chaque PR — trop lent) :

```yaml
on:
  schedule: [{ cron: '0 2 * * *' }]
  workflow_dispatch:
jobs:
  dast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker compose up -d && ./tools/attendre-sante.sh
      - uses: zaproxy/action-api-scan@v0
        with:
          target: http://localhost:8080/openapi.json
          format: openapi
          fail_action: true
          rules_file_name: .zap/rules.tsv     # faux positifs justifiés
```

## Lab 2 — fuzzing d'un parseur C avec libFuzzer

C'est l'exercice central du module. Cible : un parseur de trames capteur.

`firmware/src/parseur.c` :

```c
#include <stdint.h>
#include <string.h>
#include "parseur.h"

/* Trame : [0xAA][len:1][type:1][payload:len][crc:1] */
int parser_trame(const uint8_t *data, size_t taille, trame_t *sortie) {
    if (taille < 4) return -1;
    if (data[0] != 0xAA) return -1;

    uint8_t len = data[1];
    sortie->type = data[2];
    sortie->longueur = len;

    /* défaut volontaire : len n'est pas comparé à `taille` ni à sizeof(payload) */
    memcpy(sortie->payload, &data[3], len);

    uint8_t crc = 0;
    for (size_t i = 0; i < (size_t)len + 3; i++) crc ^= data[i];
    return (crc == data[len + 3]) ? 0 : -2;
}
```

Harnais `tests/fuzz_parseur.c` :

```c
#include <stdint.h>
#include <stddef.h>
#include "../firmware/src/parseur.h"

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t taille) {
    trame_t t = {0};
    parser_trame(data, taille, &t);
    return 0;   /* on ne retourne jamais autre chose que 0 */
}
```

```bash
clang -g -O1 -fsanitize=fuzzer,address,undefined \
      -fno-omit-frame-pointer \
      -o fuzz_parseur tests/fuzz_parseur.c firmware/src/parseur.c

mkdir -p corpus && printf '\xAA\x02\x01\x41\x42\x00' > corpus/trame-valide.bin

./fuzz_parseur corpus/ -max_total_time=120 -print_final_stats=1
```

Tu obtiens un `crash-<sha1>` en quelques secondes. Rejoue-le :

```bash
./fuzz_parseur crash-xxxx          # rapport ASan : stack trace + type de dépassement
```

Corrige (`if (len > sizeof(sortie->payload) || (size_t)len + 4 > taille) return -1;`) puis
refuzz : le corpus sert de test de non-régression.

### Intégration CI

```yaml
  fuzz:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: actions/cache@v4         # le corpus s'accumule entre les exécutions
        with:
          path: corpus
          key: corpus-${{ github.sha }}
          restore-keys: corpus-
      - run: clang -g -O1 -fsanitize=fuzzer,address,undefined -o fuzz tests/fuzz_parseur.c firmware/src/parseur.c
      - run: ./fuzz corpus/ -max_total_time=600 -timeout=10 -rss_limit_mb=2048
      - if: failure()
        uses: actions/upload-artifact@v4
        with: { name: crashs, path: crash-* }
```

Sur PR : 60 s (détection de régression). En nocturne : plusieurs heures, corpus persistant.

## Lab 3 — fuzzer un protocole embarqué

Quand la cible est une vraie carte, on ne peut pas instrumenter : on fuzze **en boîte noire**
depuis l'extérieur, avec détection de plantage par heartbeat.

`labs/08-fuzz/fuzz_serie.py` :

```python
#!/usr/bin/env python3
"""Fuzzer de trames série avec détection de plantage de la cible."""
import random, struct, time, sys
import serial   # .venv/bin/pip install pyserial

PORT, BAUD = "/dev/ttyUSB0", 115200

def trame_valide() -> bytes:
    payload = bytes(random.getrandbits(8) for _ in range(random.randint(0, 8)))
    corps = bytes([0xAA, len(payload), 0x01]) + payload
    crc = 0
    for b in corps:
        crc ^= b
    return corps + bytes([crc])

def muter(t: bytes) -> bytes:
    t = bytearray(t)
    choix = random.choice(["bitflip", "longueur", "tronque", "allonge", "octet"])
    if choix == "bitflip" and t:
        i = random.randrange(len(t)); t[i] ^= 1 << random.randrange(8)
    elif choix == "longueur" and len(t) > 1:
        t[1] = random.choice([0x00, 0x01, 0x7F, 0x80, 0xFE, 0xFF])
    elif choix == "tronque" and len(t) > 1:
        t = t[:random.randrange(1, len(t))]
    elif choix == "allonge":
        t += bytes(random.getrandbits(8) for _ in range(random.randint(1, 512)))
    elif choix == "octet" and t:
        t[random.randrange(len(t))] = random.getrandbits(8)
    return bytes(t)

def vivante(s: serial.Serial) -> bool:
    """Ping applicatif : si la cible ne répond plus, elle a planté ou est bloquée."""
    s.reset_input_buffer()
    s.write(b"\xAA\x00\xFF\x55")      # commande PING
    return s.read(4) != b""

def main(iterations=100_000):
    s = serial.Serial(PORT, BAUD, timeout=0.5)
    journal = open("cas-interessants.log", "ab")
    for i in range(iterations):
        cas = muter(trame_valide())
        s.write(cas)
        time.sleep(0.005)
        if not vivante(s):
            print(f"[!] cible muette après {i} cas : {cas.hex()}")
            journal.write(cas + b"\n"); journal.flush()
            input("Redémarre la cible puis Entrée...")   # ou reset automatique via relais/GPIO
        if i % 1000 == 0:
            print(f"{i} cas envoyés", file=sys.stderr)

if __name__ == "__main__":
    main()
```

Points de méthode, valables pour Modbus, CAN, BLE :

1. **Détection de plantage** — sans oracle, tu envoies du bruit sans rien observer. Options :
   heartbeat applicatif, ligne GPIO de watchdog, consommation de courant, sortie de debug UART.
2. **Reset automatique** — relais USB ou GPIO pour couper l'alimentation ; sinon le fuzzing
   s'arrête au premier crash.
3. **Reproductibilité** — journalise la graine PRNG, pas seulement les cas.
4. **Émuler plutôt que fuzzer le matériel** quand c'est possible : QEMU, **Renode**, ou extraire
   le parseur et le fuzzer en natif (Lab 2). Des milliers de fois plus rapide.

Outils à connaître : **boofuzz** (protocoles, avec agent de surveillance de cible), **AFL++ en
mode QEMU** (fuzzing de binaires sans source), **Fuzzware** / **Halucinator** (émulation de
firmware MCU), **caringcaribou** (CAN/automobile), **Sweyntooth** (BLE).

## Triage des crashs

Un crash ≠ une vulnérabilité. Classe :

| Observation | Gravité |
|---|---|
| Écriture hors bornes contrôlée par l'attaquant | **critique** — RCE potentielle |
| Lecture hors bornes | élevée — fuite mémoire / contournement d'ASLR |
| Déréférencement de NULL, assert | faible/moyenne — déni de service (grave si l'objet est critique) |
| Dépassement d'entier sans conséquence | à corriger, non exploitable |
| Blocage (watchdog) | dépend de la fonction du produit |

En embarqué, un déni de service est souvent **plus grave** qu'en web : on ne redémarre pas
toujours un objet installé sur un pylône.

```bash
# minimiser un cas de crash avant de le rapporter
./fuzz -minimize_crash=1 -runs=100000 crash-xxxx
```

## Critères de validation

- [ ] Le DAST tourne en nocturne et publie un rapport lisible
- [ ] Ton fuzzer libFuzzer trouve le défaut du parseur en < 60 s
- [ ] Après correction, 10 minutes de fuzzing ne trouvent plus rien
- [ ] Le corpus est mis en cache et grossit d'une exécution à l'autre
- [ ] Ton fuzzer série détecte un plantage sans intervention humaine
- [ ] Tu tries 3 crashs par gravité avec justification

## Pièges classiques

- **Fuzzer sans sanitizer** : tu ne vois que les crashs francs, tu rates les corruptions
  silencieuses. `-fsanitize=address,undefined` toujours.
- **Corpus initial vide** : donne toujours quelques entrées valides, ça change tout.
- **Harnais non déterministe** (aléa, temps, réseau) : les crashs deviennent irreproductibles.
- **Fuzzer le binaire de production** (optimisé, sans symboles) au lieu d'un build de test.
- **DAST sur chaque PR** : pipeline à 40 minutes, équipe qui débranche tout.
- ⚠️ **Ne fuzze jamais un équipement que tu ne possèdes pas** et n'as pas l'autorisation écrite
  de tester.

## Pour aller plus loin

- *The Fuzzing Book* (en ligne, gratuit) — fondations théoriques et pratiques
- OSS-Fuzz / ClusterFuzzLite : intégration continue de fuzzing
- Renode : émulation de cartes entières, scriptable, idéal pour de la CI matérielle sans matériel
