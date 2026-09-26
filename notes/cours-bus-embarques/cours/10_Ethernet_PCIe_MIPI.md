# 10 — Haut débit : Ethernet, Automotive Ethernet, PCIe, MIPI

> Les liens **rapides** de l'embarqué moderne. Ethernet (dont la variante automobile), PCIe (le bus interne des SoC/FPGA/SSD), et MIPI (caméras et écrans). On monte en débit et en complexité d'intégrité du signal.

---

## A. ETHERNET

### Carte d'identité
| Caractéristique | Valeur |
|---|---|
| Type | Trame, **commuté**, full-duplex |
| Débits | 10 Mbit/s → 10/25/100/400 Gbit/s |
| Adressage | **MAC 48 bits** + (au-dessus) IP |
| Détection d'erreur | **CRC-32 (FCS)** |
| Normes | **IEEE 802.3** |

### 1. Principe
Ethernet définit les **couches 1 (PHY)** et **2 (MAC)**. La **trame** : `Préambule | @MAC dest | @MAC source | EtherType | Données (46–1500) | FCS(CRC-32)`. Le CSMA/CD historique (détection de collision sur bus partagé) a **disparu** : le **commutateur (switch)** en full-duplex a supprimé les collisions.
Au-dessus s'empilent **IP / TCP-UDP / applicatif** (voir modèle OSI, fiche 00). En embarqué on trouve Ethernet sur les SoC Linux, les passerelles, l'IIoT, l'automobile.

### 2. Automotive Ethernet ⭐
Adaptation de l'Ethernet aux contraintes auto (poids, coût, CEM, une seule paire) :
- **100BASE-T1 / 1000BASE-T1** (IEEE 802.3bw / 802.3bp) : Ethernet **sur une seule paire torsadée non blindée**, full-duplex, jusqu'à 15 m. Remplace des faisceaux coûteux pour l'**ADAS, les caméras, l'infotainment**.
- **10BASE-T1S** : bas débit multidrop, concurrent du CAN sur segments courts.
- **TSN (Time-Sensitive Networking, IEEE 802.1)** : rend Ethernet **déterministe** (files par le temps, synchro 802.1AS, réservation de bande) → permet à Ethernet de porter du trafic **critique** temps réel, convergence auto/indus.
- **AVB/TSN, SOME/IP, DoIP** : couches applicatives auto (SOME/IP = middleware service-oriented ; DoIP = diagnostic UDS sur IP).

### 3. Sécurité 🔒
- Surface d'attaque « réseau classique » : **ARP spoofing, MAC flooding, VLAN hopping, sniffing** sur un segment, DoS.
- En **automobile** : Automotive Ethernet relie caméras/ADAS ↔ calculateurs → une intrusion peut viser des fonctions critiques ; **SOME/IP** et **DoIP** exposent des services à durcir.
- Contre-mesures : **MACsec (802.1AE)** pour chiffrer/authentifier au niveau 2, **802.1X** (contrôle d'accès au port), segmentation VLAN, IDS, TLS au-dessus, et **isolation par gateway** en auto.

---

## B. PCIe (PCI Express)

### Carte d'identité
| Caractéristique | Valeur |
|---|---|
| Type | **Série différentiel**, **commuté**, **point à point** par lien |
| Unité | **lane** = 1 paire TX + 1 paire RX ; liens **x1, x4, x8, x16** |
| Débit/lane | 2,5 (gen1) → 8 (gen3) → 16 (gen4) → 32 (gen5) GT/s |
| Topologie | arbre : **Root Complex → Switches → Endpoints** |
| Codage | 8b/10b (gen1-2), **128b/130b** (gen3+) |
| Organisme | **PCI-SIG** |

### 1. Principe & couches
PCIe n'est **pas un bus partagé** mais un **réseau commuté de liens point-à-point**. Trois couches :
- **Transaction Layer** : unités **TLP** (Transaction Layer Packets) — lectures/écritures mémoire, I/O, config, messages.
- **Data Link Layer** : fiabilité (numéros de séquence, **ACK/NAK**, retransmission), **CRC (LCRC)**.
- **Physical Layer** : sérialisation, égalisation, négociation de largeur/vitesse.

En embarqué, PCIe relie **SoC ↔ FPGA**, **SoC ↔ SSD NVMe**, **SoC ↔ modem/accélérateur**. Sur FPGA, on instancie un **endpoint PCIe** (IP Xilinx/Intel) pour offrir un lien haut débit vers l'hôte (DMA).

### 2. Aspects poussés
- **Enumeration/BAR** : à l'init, le Root Complex découvre les endpoints et leur alloue des **BAR** (Base Address Registers) → fenêtres mémoire.
- **MSI/MSI-X** : interruptions par message (plus de ligne d'IRQ physique).
- **DMA** : les endpoints lisent/écrivent **directement la RAM** → performance… et risque (voir sécurité).
- **Bifurcation, ASPM (économie d'énergie), AER (report d'erreurs)**.

### 3. Sécurité 🔒
- **DMA attacks** : un endpoint PCIe (ou un périphérique **Thunderbolt/USB4** qui *tunnelise* PCIe) peut lire/écrire toute la RAM → **vol de clés, injection, contournement de verrouillage** (**PCILeech**, **Thunderclap**).
- Contre-mesures : **IOMMU (Intel VT-d / AMD-Vi)** pour cloisonner les accès mémoire par périphérique, **Kernel DMA Protection**, **niveaux de sécurité Thunderbolt**, **ATS/PRI** maîtrisés, désactivation des ports externes DMA.

---

## C. MIPI (caméras & écrans)

### Carte d'identité
| Interface | Usage | PHY |
|---|---|---|
| **MIPI CSI-2** | **Caméra** → SoC | D-PHY ou C-PHY |
| **MIPI DSI** | SoC → **écran** | D-PHY |
| **D-PHY** | PHY série différentiel à voies (1 clock lane + N data lanes) | source-synchrone |
| **C-PHY** | PHY à 3 fils/trio (codage sur symboles) | plus efficace |

### 1. Principe
MIPI Alliance normalise les liens **internes** des appareils mobiles/embarqués. **CSI-2** (Camera Serial Interface) transporte les flux **caméra** (capteurs → ISP/SoC) ; **DSI** (Display Serial Interface) pilote les **écrans**. La PHY (**D-PHY**) fonctionne en **voies différentielles source-synchrones** : une *clock lane* + plusieurs *data lanes*, avec des modes **HS (High-Speed, différentiel)** et **LP (Low-Power, single-ended)** pour l'économie d'énergie.
Sur SoC embarqués (Raspberry Pi, i.MX, Jetson), le connecteur caméra est du **CSI-2** ; l'écran, du **DSI**.

### 2. Aspects poussés & sécurité 🔒
- **Débits élevés** (plusieurs Gbit/s par lane) → **intégrité du signal** critique (longueurs appairées, impédances).
- **Packing** : CSI-2 encapsule les pixels (RAW8/10/12, YUV, RGB) avec des en-têtes de paquet courts/longs et **ECC + checksum**.
- **Sécurité** : surface d'attaque surtout **physique/proximité** (interposition sur la nappe caméra pour **injecter/rejouer un flux vidéo** → tromper un système de vision/ADAS ou de surveillance). La confiance dans le **capteur** est un sujet de recherche (spoofing de caméras/LiDAR pour ADAS). Contre-mesures : intégrité/authentification applicative du flux, détection d'anomalie côté perception, sécurité physique.

---

## Pratique — outils

| Domaine | Outils |
|---|---|
| Ethernet | **Wireshark**, `tcpdump`, `ip`, `ethtool`, bettercap (ARP/MITM en audit) |
| Automotive Eth | media converters 100BASE-T1↔100BASE-TX, Wireshark + dissecteurs SOME/IP |
| PCIe | `lspci -vvv`, `setpci`, **PCILeech** (recherche DMA), analyseurs PCIe (pro) |
| MIPI | oscilloscope haut débit + sondes, cartes d'éval SoC (Jetson, RPi CM) |

```bash
lspci -vvv                 # arbre PCIe, BAR, capacités (dont AER, MSI)
ethtool eth0               # vitesse/duplex/capacités du lien Ethernet
tcpdump -i eth0 -w cap.pcap
```

---

## Sources

- **IEEE 802.3** (Ethernet) et **802.1** (VLAN, TSN, MACsec) : <https://www.ieee802.org/>
- **Open Alliance — Automotive Ethernet (100BASE-T1)** : <https://opensig.org/> · Vector *Automotive Ethernet* : <https://www.vector.com/int/en/know-how/automotive-ethernet/>
- **PCI-SIG — spécifications PCIe** : <https://pcisig.com/specifications>
- **Xillybus — *Down to the TLP* (guide PCIe pédagogique)** : <http://xillybus.com/tutorials/pci-express-tlp-pcie-primer-tutorial-guide-1>
- **MIPI Alliance — CSI-2 / DSI / D-PHY / C-PHY** : <https://www.mipi.org/specifications>
- **Thunderclap (DMA)** : <http://thunderclap.io/> · **PCILeech** : <https://github.com/ufrisk/pcileech>
- **MACsec (802.1AE)** — chiffrement niveau 2.
