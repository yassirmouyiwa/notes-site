# Cours — Bus & protocoles de communication embarqués

> Support de cours structuré, du niveau **base** au niveau **poussé**, orienté **systèmes embarqués & cybersécurité**.
> Chaque protocole a son propre fichier `.md`. Les schémas sont dans `images/` (générés localement, lisibles hors-ligne).

---

## Comment lire ce cours

Chaque fiche suit le même plan pour que tu puisses comparer les protocoles entre eux :

1. **Carte d'identité** (tableau récapitulatif)
2. **Le problème que ça résout** — le *pourquoi*
3. **Couche physique & électrique**
4. **Trame / protocole** — le *comment*, bit à bit
5. **Aspects poussés** — timing, arbitrage, tolérance aux fautes…
6. **Sécurité** — surface d'attaque, attaques connues, contre-mesures
7. **Pratique** — comment l'observer/l'attaquer (matériel, outils)
8. **Sources** — datasheets, specs officielles, références

---

## Plan des fichiers

| # | Fichier | Protocole | Domaine dominant |
|---|---------|-----------|------------------|
| 00 | [`00_introduction_concepts.md`](00_introduction_concepts.md) | **Concepts transverses** (série/parallèle, synchrone, codages, différentiel, OSI…) | Fondations |
| 01 | [`01_UART.md`](01_UART.md) | **UART / RS-232** | Intra-carte, debug |
| 02 | [`02_SPI.md`](02_SPI.md) | **SPI** | Intra-carte rapide |
| 03 | [`03_I2C.md`](03_I2C.md) | **I²C / SMBus** | Intra-carte, capteurs |
| 04 | [`04_1Wire.md`](04_1Wire.md) | **1-Wire** | Capteurs mono-fil |
| 05 | [`05_CAN.md`](05_CAN.md) | **CAN & CAN FD** | Automobile / industriel |
| 06 | [`06_LIN.md`](06_LIN.md) | **LIN** | Automobile bas coût |
| 07 | [`07_FlexRay.md`](07_FlexRay.md) | **FlexRay** | Automobile critique (x-by-wire) |
| 08 | [`08_RS485_Modbus.md`](08_RS485_Modbus.md) | **RS-485, Modbus, Profibus, EtherCAT** | Bus de terrain industriels |
| 09 | [`09_USB.md`](09_USB.md) | **USB** | Haut débit périphérique |
| 10 | [`10_Ethernet_PCIe_MIPI.md`](10_Ethernet_PCIe_MIPI.md) | **Ethernet, PCIe, MIPI** | Haut débit |
| 11 | [`11_sansfil_IoT.md`](11_sansfil_IoT.md) | **BLE, Zigbee, LoRa, Wi-Fi, NB-IoT** | Sans fil / IoT |
| 12 | [`12_synthese_securite.md`](12_synthese_securite.md) | **Synthèse comparative & sécurité offensive/défensive** | Transverse |

---

## Avertissement (échelle & sécurité)

- Les **chronogrammes** générés (`images/`) sont **didactiques** : les proportions de temps ne sont pas contractuelles. Pour du dimensionnement réel, se référer **toujours** aux *datasheets* et aux specs officielles citées.
- Les sections **sécurité** sont fournies dans un **cadre défensif / pédagogique** (audit, durcissement, compréhension des menaces). N'attaque que du matériel **que tu possèdes** ou pour lequel tu as une **autorisation écrite**.

---

## Crédits images

Tous les schémas de `images/` ont été **générés** pour ce cours (matplotlib) : chronogrammes UART/SPI/I²C, arbitrage CAN, cycle FlexRay, différentiel RS-485, spectrogramme LoRa, etc. Ils sont donc **libres de droits** pour ton usage.
Les liens vers des *figures externes* (datasheets, Wikipedia…) sont donnés dans chaque fiche, section **Sources**.
