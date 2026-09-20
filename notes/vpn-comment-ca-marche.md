# Comment fonctionne un VPN ?

> Note prise le 2026-09-20

## 1. L'idée en une phrase

Un VPN (*Virtual Private Network*) crée un **tunnel chiffré** entre ta machine et
un serveur distant. Tout ton trafic passe par ce tunnel : ton fournisseur d'accès
(FAI) ne voit plus *ce que* tu fais, et les sites que tu visites voient l'adresse IP
du serveur VPN, pas la tienne.

```
[ Toi ]  ==== tunnel chiffré ====>  [ Serveur VPN ]  ----> [ Internet ]
   IP réelle : 88.x.x.x                IP vue par les sites : 45.y.y.y
```

## 2. Ce qui se passe réellement, étape par étape

### a. Connexion et authentification
Le client VPN contacte le serveur et prouve son identité : certificat, clé publique,
ou login/mot de passe selon le protocole.

### b. Négociation des clés
Les deux côtés dérivent une clé de session partagée, typiquement via un
**échange Diffie-Hellman** (souvent sur courbes elliptiques, ECDH). Point clé :
la clé n'est jamais transmise sur le réseau, elle est *calculée* de chaque côté.
La **forward secrecy** vient du renouvellement régulier de ces clés : si une clé
long terme fuite plus tard, le trafic passé reste illisible.

### c. Création de l'interface virtuelle
Le système crée une carte réseau virtuelle (`tun0`, `wg0`...). La table de routage
est modifiée pour que la route par défaut pointe vers cette interface.

```bash
ip addr show wg0        # interface virtuelle
ip route show default   # doit pointer vers le tunnel
```

### d. Encapsulation
Chaque paquet IP sortant est :
1. **chiffré** (AES-256-GCM, ChaCha20-Poly1305...),
2. **authentifié** (un MAC garantit qu'il n'a pas été modifié),
3. **encapsulé** dans un nouveau paquet adressé au serveur VPN.

Le paquet original devient la *charge utile* du nouveau paquet. C'est le
principe du tunnel : de l'extérieur, on ne voit qu'un flux UDP/TCP vers une seule IP.

### e. Sortie et retour
Le serveur déchiffre, fait une **NAT** vers Internet avec sa propre IP, reçoit la
réponse, la re-chiffre et te la renvoie dans le tunnel.

## 3. Les protocoles courants

| Protocole | Chiffrement | Points forts | Limites |
|---|---|---|---|
| **WireGuard** | ChaCha20-Poly1305 | ~4 000 lignes de code, très rapide, dans le noyau Linux | IP statiques par pair, pas de furtivité |
| **OpenVPN** | OpenSSL (AES-GCM) | Mature, très configurable, TCP/443 possible | Lent, gros code, en espace utilisateur |
| **IPsec/IKEv2** | AES-GCM | Natif sur mobiles, reconnecte vite en 4G/WiFi | Complexe, ports souvent bloqués |
| **L2TP/PPTP** | — / MPPE | — | **PPTP est cassé, ne pas utiliser** |

## 4. Les fuites classiques (à vérifier)

- **Fuite DNS** : le tunnel est actif mais les requêtes DNS partent encore vers le
  résolveur du FAI → il voit les noms de domaines visités.
- **Fuite IPv6** : le VPN ne route que l'IPv4, l'IPv6 sort en clair.
- **Fuite WebRTC** : le navigateur expose l'IP locale/réelle via STUN.
- **Chute du tunnel** : sans *kill switch*, le trafic repart en clair sans prévenir.

```bash
# IP publique vue de l'extérieur
curl -s https://ifconfig.me

# Résolveurs DNS réellement utilisés
resolvectl status | grep -i 'DNS Server'

# Le trafic passe-t-il bien dans le tunnel ?
ip route get 1.1.1.1
```

Un *kill switch* se fait côté pare-feu : on bloque tout ce qui ne sort pas par
l'interface du tunnel (règles `nftables`/`iptables`, ou `firewalld`).

## 5. Ce qu'un VPN protège... et ne protège pas

**Protège**
- Le contenu et les destinations vis-à-vis du FAI ou d'un WiFi public hostile.
- Ton IP réelle vis-à-vis des sites visités.
- L'accès distant à un réseau privé (le cas d'usage d'origine en entreprise).

**Ne protège pas**
- Tu **déplaces** la confiance du FAI vers le fournisseur VPN : lui voit tout.
  Un VPN gratuit se paye d'une autre manière.
- Les cookies, comptes connectés et *fingerprinting* du navigateur.
- Les malwares, le phishing, les mots de passe faibles.
- TLS fait déjà le chiffrement de bout en bout : sur du HTTPS, le VPN masque
  surtout *à qui* tu parles, pas le contenu déjà protégé.
- L'anonymat fort — c'est le rôle de Tor, avec un modèle de menace différent.

## 6. Les deux grands cas d'usage

1. **VPN d'accès distant** : rejoindre le réseau interne d'une entreprise
   (serveurs, partages, machines non exposées sur Internet).
2. **VPN commercial** : masquer son IP, contourner une restriction géographique,
   se protéger sur un réseau non maîtrisé.

Auto-hébergé (WireGuard sur un VPS), on garde le contrôle des logs — mais l'IP
du serveur ne sert qu'à soi, donc elle est très identifiante.

## 7. Monter un WireGuard minimal

```bash
# Fedora
sudo dnf install wireguard-tools

# Générer une paire de clés
wg genkey | tee privatekey | wg pubkey > publickey
```

`/etc/wireguard/wg0.conf` côté client :

```ini
[Interface]
PrivateKey = <clé privée du client>
Address = 10.0.0.2/24
DNS = 1.1.1.1          # évite la fuite DNS

[Peer]
PublicKey = <clé publique du serveur>
Endpoint = serveur.example.com:51820
AllowedIPs = 0.0.0.0/0, ::/0   # tout le trafic dans le tunnel
PersistentKeepalive = 25       # utile derrière un NAT
```

```bash
sudo wg-quick up wg0
sudo wg show           # état des pairs, dernier handshake
sudo wg-quick down wg0
```

## 8. À retenir

- Un VPN = **tunnel chiffré + changement d'IP apparente**, rien de plus.
- C'est un **transfert de confiance**, pas une suppression de la confiance.
- Les fuites (DNS, IPv6, WebRTC) annulent en pratique le bénéfice : toujours tester.
- WireGuard est le meilleur défaut aujourd'hui ; OpenVPN sur TCP/443 quand il faut
  passer un réseau filtrant.
