# 12 — Synthèse comparative & sécurité matérielle

> La fiche transversale : un **tableau maître** de tous les protocoles, une **méthodologie d'audit hardware**, et la **boîte à outils** du hacker matériel (cadre défensif). À relire avant un examen ou avant d'attaquer une carte inconnue.

---

## 1. Tableau maître (à connaître par cœur)

| Protocole | Fils | Sync | Horloge | Débit typique | Distance | Adressage | Multi-maître | Détection erreur | Différentiel | Domaine |
|---|---|---|---|---|---|---|---|---|---|---|
| **UART** | 2 | asynchrone | non | ≤ 3 Mbit/s | ~15 m (RS-232) | aucun | non | parité | non | debug, GPS, modems |
| **SPI** | 3+CS | synchrone | maître | 1–50+ MHz | cm | par CS | non | aucune | non | ADC, flash, écrans |
| **I²C** | 2 | synchrone | maître | 0,1–3,4 MHz | ~1 m | 7/10 bits | oui | ACK (PEC SMBus) | non | capteurs, EEPROM |
| **1-Wire** | 1 | asynchrone | non | ~16 kbit/s | ~100 m | ROM 64 bits | non | CRC-8 | non | temp., ID |
| **CAN** | 2 | asynchrone | non | ≤ 1 Mbit/s | 40–1000 m | par message | oui (CSMA/CR) | CRC-15++ | **oui** | auto, indus |
| **CAN FD** | 2 | asynchrone | non | ≤ 8 Mbit/s | dizaines m | par message | oui | CRC-17/21 | **oui** | auto récent |
| **LIN** | 1 | asynchrone | non | ≤ 20 kbit/s | 40 m | par ID | non | checksum | non | auto bas coût |
| **FlexRay** | 2×2 | synchrone (TDMA) | globale | 10 Mbit/s | dizaines m | par slot | TDMA | CRC + guardian | **oui** | auto critique |
| **RS-485** | 2/4 | (porteur) | — | ≤ 35 Mbit/s | 1200 m | protocole | selon | protocole | **oui** | indus |
| **Modbus** | (RS-485/TCP) | — | — | ≤ 115 k / Eth | selon | 1–247 | non | CRC-16 | selon | indus/SCADA |
| **EtherCAT** | 2 (Eth) | synchrone (DC) | globale | 100 Mbit/s | 100 m/segм | position | maître | CRC (Eth) | **oui** | motion control |
| **USB** | 4 (2.0) | (host-polled) | hôte | 12 M–40 Gbit/s | ~5 m | 1–127 dyn. | non (host) | CRC-5/16 | **oui** | périphériques |
| **Ethernet** | 2/4 paires | — | — | 10 M–400 Gbit/s | 100 m | MAC 48 bits | commuté | CRC-32 | **oui** | réseau |
| **PCIe** | ×N lanes | — | — | GT/s par lane | cm | BDF/BAR | commuté | LCRC | **oui** | interne SoC/FPGA |
| **MIPI CSI/DSI** | lanes | source-sync | dédiée | Gbit/s/lane | cm | — | non | ECC+CRC | **oui** | caméra/écran |
| **BLE** | radio 2,4 G | — | — | ≤ 2 Mbit/s | 10–100 m | @48 bits | — | CRC-24 | — | IoT pile |
| **Zigbee** | radio 2,4 G | — | — | 250 kbit/s | 10–100 m | 16/64 bits | mesh | CRC-16 | — | domotique |
| **Wi-Fi** | radio | — | — | Mbit–Gbit/s | 10–150 m | MAC | CSMA/CA | CRC-32 | — | réseau IoT |
| **LoRaWAN** | radio sub-G | — | — | 0,3–50 kbit/s | 2–15 km | DevAddr | Aloha | CRC + MIC | — | IoT longue portée |
| **NB-IoT** | radio licenciée | — | — | ≤ 250 kbit/s | 1–15 km | cellulaire | cellulaire | 3GPP | — | IoT cellulaire |

---

## 2. Comment choisir un bus (arbre de décision)

- **Sur la carte, très proche, rapide, peu de composants ?** → **SPI** (rapide) ou **I²C** (économe en broches).
- **Un capteur température / un ID unique sur 1 fil ?** → **1-Wire**.
- **Console de debug / modem / GPS ?** → **UART**.
- **Réseau robuste multi-nœuds, environnement bruité, criticité moyenne ?** → **CAN / CAN FD**.
- **Fonctions auto non critiques et bon marché ?** → **LIN**.
- **Auto critique, déterministe (freinage, direction) ?** → **FlexRay** (ou TSN/Ethernet).
- **Longue distance industrielle, automates ?** → **RS-485 + Modbus** (ou PROFIBUS/PROFINET).
- **Contrôle de mouvement multi-axes en µs ?** → **EtherCAT**.
- **Périphérique PC / haut débit / hot-plug ?** → **USB**.
- **Très haut débit interne (SSD, FPGA, accélérateur) ?** → **PCIe**.
- **Caméra / écran vers un SoC ?** → **MIPI CSI / DSI**.
- **Objet sur pile, courte portée ?** → **BLE / Zigbee**.
- **Objet longue portée basse conso ?** → **LoRaWAN** (ISM) ou **NB-IoT** (cellulaire).

---

## 3. Récapitulatif sécurité par protocole

| Protocole | Auth. native | Chiffrement natif | Faiblesse clé | Attaque emblématique |
|---|---|---|---|---|
| UART | ❌ | ❌ | console debug ouverte | shell root / U-Boot |
| SPI | ❌ | ❌ | flash externe lisible | dump firmware (CH341A) |
| I²C | ❌ | ❌ | EEPROM config accessible | reconfig / spoof capteur |
| 1-Wire | selon puce | selon puce | ID clonable | rejeu d'ID d'accessoire |
| CAN | ❌ | ❌ | pas de contrôle d'accès | injection (Jeep 2015), bus-off, DoS 0x000 |
| LIN | ❌ | ❌ | 1 fil, aucun contrôle | spoof capteur, pivot vers CAN |
| FlexRay | ❌ | ❌ | pas d'auth | injection segment dyn., atteinte à la synchro |
| Modbus | ❌ | ❌ | exposé sur Internet | write registres (Shodan port 502) |
| EtherCAT/PROFINET | ❌ | ❌ | temps réel fragile | injection RT, DoS (Stuxnet-like) |
| USB | ❌ | ❌ | on fait confiance au device | **BadUSB**, DMA (Thunderclap) |
| PCIe | ❌ | ❌ | DMA vers la RAM | **PCILeech**, Thunderclap |
| MIPI | ❌ | ❌ | accès nappe | injection/spoof de flux vidéo |
| BLE | ✔ (pairing) | ✔ | *Just Works* / legacy | KNOB, BLESA, SweynTooth |
| Zigbee | ✔ (AES) | ✔ | clés par défaut/échange join | IoT Goes Nuclear (ver Hue) |
| Wi-Fi | ✔ | ✔ | handshake / gestion trames | KRACK, deauth, evil twin |
| LoRaWAN | ✔ (AES-128) | ✔ | clés en dur (ABP), frame counter | rejeu, extraction AppKey |
| NB-IoT | ✔ (SIM) | ✔ | baseband / IMSI catcher | fausse station de base |

> **Constat central** : les bus **filaires historiques** (UART, SPI, I²C, CAN, LIN, Modbus) n'ont **aucune sécurité native** — ils supposaient un **support physique de confiance**. La sécurité doit venir de **l'architecture** (isolation, gateway, secure boot, secure elements) et de l'**applicatif** (MAC, chiffrement). Les protocoles **sans fil récents** intègrent de la crypto, mais souvent **mal configurée** (clés par défaut, modes faibles).

---

## 4. Méthodologie d'audit hardware (défensif / pentest embarqué)

Démarche type face à une **carte inconnue** :

1. **Reconnaissance visuelle** : identifier les puces (MCU/SoC, flash, PMIC, radio) via leurs **marquages** → datasheets → brochages. Repérer les **connecteurs et headers** de test.
2. **Cartographier les bus** : à l'**oscilloscope / analyseur logique**, repérer UART (ligne à 3,3 V au repos qui « bouge » au boot), SPI (SCLK+3 lignes), I²C (2 lignes avec pull-ups), JTAG/SWD.
3. **Chercher les interfaces de debug** :
   - **UART** → console/bootloader (fiche 01).
   - **JTAG/SWD** → contrôle du CPU, dump mémoire (**JTAGulator**/**OpenOCD** pour trouver et parler au TAP).
4. **Extraire le firmware** :
   - **Flash SPI/I²C** → clip SOIC-8 + **flashrom/CH341A** (fiche 02).
   - Via **JTAG/SWD** si la flash est interne.
5. **Analyser le firmware** : `binwalk -e`, `strings`, systèmes de fichiers (squashfs…), puis **désassemblage/décompilation** (**Ghidra**, radare2/Cutter) → recherche de secrets, backdoors, vulnérabilités.
6. **Attaques physiques avancées** (si besoin) :
   - **Injection de fautes (glitching)** : perturber l'alim/l'horloge/EM pour **sauter une instruction** (ex. contourner une vérification de secure boot) → **ChipWhisperer**.
   - **Canaux auxiliaires (side-channel)** : mesurer **consommation** ou **émissions EM** pendant une opération crypto pour **extraire une clé** (DPA/CPA) → ChipWhisperer, oscilloscope + sonde EM.
7. **Analyse radio** (si module sans fil) : **SDR** (RTL-SDR/HackRF) + GNU Radio, outils dédiés (Ubertooth, KillerBee) — fiche 11.
8. **Documenter & durcir** : cartographie des surfaces d'attaque, recommandations (désactiver debug, secure boot, chiffrer flash, secure element, segmentation).

---

## 5. Boîte à outils du hacker matériel

| Catégorie | Outils |
|---|---|
| **Analyse logique** | Saleae, clones **FX2** (~10 €), **sigrok/PulseView** (décodeurs UART/SPI/I²C/CAN/1-Wire…) |
| **Multi-protocole** | **Bus Pirate**, **HydraBus**, FT2232H, **Flipper Zero** |
| **JTAG/SWD** | **JTAGulator** (trouver le brochage), **OpenOCD**, ST-Link, Black Magic Probe |
| **Dump flash** | **CH341A** + clips SOIC-8/SOIC-16, **flashrom** |
| **CAN** | CANable/candleLight, PEAK, **can-utils** (SocketCAN), SavvyCAN |
| **USB** | **Facedancer**, GreatFET, Wireshark+usbmon, USBGuard (défense) |
| **Radio / SDR** | **RTL-SDR**, **HackRF One**, LimeSDR, Ubertooth, KillerBee, GNU Radio |
| **Fault injection** | **ChipWhisperer** (glitch + side-channel), alim programmable |
| **Reverse firmware** | **binwalk**, **Ghidra**, radare2/Cutter, `strings`, QEMU/Firmadyne |
| **Réseau/ICS** | Wireshark, nmap (scripts modbus/s7), Metasploit, bettercap, pymodbus |

---

## 6. Pour aller plus loin — parcours conseillé

Pour ton profil (**cybersécurité + systèmes embarqués**), un ordre d'approfondissement cohérent :

1. **Maîtriser 3 bus filaires à fond** : UART (porte d'entrée), SPI (dump flash), CAN (car hacking). Ce sont les plus « rentables » en audit.
2. **S'entraîner sans risque** : ICSim pour CAN, une carte type ESP32/STM32 + capteurs I²C/SPI pour observer au PulseView, un DS18B20 pour 1-Wire.
3. **Rétro-ingénierie de firmware** : binwalk + Ghidra sur un firmware de routeur/objet connecté (extrait par SPI).
4. **Sécurité radio** : un RTL-SDR pour observer, puis BLE (nRF52) et LoRa (SX127x).
5. **Attaques physiques** : ChipWhisperer (glitching, side-channel) — le cœur de la sécurité matérielle avancée, en lien direct avec ton cours de **sécurité embarquée**.
6. **Angle FPGA** (que tu commences) : implémenter des contrôleurs (UART, SPI, I²C, voire CAN) en **VHDL/Verilog** est le meilleur moyen de comprendre ces protocoles « de l'intérieur », et ouvre vers la sécurité matérielle (interception, chiffrement en ligne, TRNG, side-channel sur FPGA).

---

## 7. Sources & références transverses

- **The Hardware Hacking Handbook** — Jasper van Woudenberg & Colin O'Flynn (No Starch, 2021) : la référence audit/glitch/side-channel.
- **The Car Hacker's Handbook** — Craig Smith (No Starch) : <https://nostarch.com/carhacking>
- **Practical IoT Hacking** — Fotios Chantzis et al. (No Starch, 2021).
- **sigrok / PulseView** (décodeurs de protocoles) : <https://sigrok.org/>
- **NewAE / ChipWhisperer** (fault injection & side-channel) : <https://www.newae.com/chipwhisperer>
- **OWASP IoT / Embedded Application Security** : <https://owasp.org/www-project-internet-of-things/>
- **MITRE ATT&CK for ICS** : <https://attack.mitre.org/matrices/ics/>
- **CISA ICS** (bonnes pratiques OT) : <https://www.cisa.gov/topics/industrial-control-systems>
- **Ghidra** : <https://ghidra-sre.org/> · **binwalk** : <https://github.com/ReFirmLabs/binwalk>

---

> Fin du cours. Tu as maintenant, pour chaque bus : le **pourquoi**, la **couche physique**, la **trame bit à bit**, les **mécanismes poussés**, la **sécurité** (offensive/défensive) et la **pratique**. Bon courage pour la suite à l'ENSA — et pour le FPGA. 🔧🔒
