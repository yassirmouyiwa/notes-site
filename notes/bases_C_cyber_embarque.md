# Les bases du C pour la cybersécurité et les systèmes embarqués

> Guide de référence : syntaxe, concepts mémoire, algorithmes utiles et programmation sécurisée.
> Chaque section contient des exemples compilables avec :
> `gcc -Wall -Wextra -g fichier.c -o prog`

---

## Sommaire

1. [Pourquoi le C dans ce domaine](#1-pourquoi-le-c-dans-ce-domaine)
2. [Structure d'un programme](#2-structure-dun-programme)
3. [Types de données](#3-types-de-données)
4. [Opérateurs](#4-opérateurs)
5. [Manipulation de bits](#5-manipulation-de-bits)
6. [Structures de contrôle](#6-structures-de-contrôle)
7. [Fonctions](#7-fonctions)
8. [Tableaux](#8-tableaux)
9. [Chaînes de caractères](#9-chaînes-de-caractères)
10. [Pointeurs](#10-pointeurs)
11. [Organisation de la mémoire](#11-organisation-de-la-mémoire)
12. [Allocation dynamique](#12-allocation-dynamique)
13. [struct, union, enum, typedef](#13-struct-union-enum-typedef)
14. [Préprocesseur](#14-préprocesseur)
15. [Mots-clés essentiels en embarqué](#15-mots-clés-essentiels-en-embarqué)
16. [Accès aux registres matériels](#16-accès-aux-registres-matériels)
17. [Endianness](#17-endianness)
18. [Algorithmes fondamentaux](#18-algorithmes-fondamentaux)
19. [Programmation sécurisée : les vulnérabilités classiques](#19-programmation-sécurisée--les-vulnérabilités-classiques)
20. [Compilation, outils et débogage](#20-compilation-outils-et-débogage)
21. [Exercices progressifs](#21-exercices-progressifs)

---

## 1. Pourquoi le C dans ce domaine

Le C est le langage de référence à l'intersection de tes deux spécialités :

- **Systèmes embarqués** : firmware des microcontrôleurs (STM32, AVR, ESP32), noyaux (Linux, FreeRTOS, Zephyr), pilotes. Le C donne un accès direct à la mémoire et au matériel, avec un coût d'exécution prévisible.
- **Cybersécurité** : la majorité des vulnérabilités historiques (buffer overflow, use-after-free, format string) viennent du C. Pour exploiter, auditer ou corriger du code, faire de la rétro-ingénierie ou comprendre un exploit, il faut maîtriser le C et sa représentation en mémoire.

L'idée clé à retenir dès maintenant : **le C ne te protège de rien**. Il fait exactement ce que tu écris, même si c'est faux. C'est sa puissance et sa dangerosité.

---

## 2. Structure d'un programme

```c
#include <stdio.h>   // directive préprocesseur : inclut les déclarations de printf, etc.

// Point d'entrée du programme
int main(void)
{
    printf("Hello, ENSA\n");   // \n = retour à la ligne
    return 0;                  // 0 = succès, transmis au système (echo $? dans le terminal)
}
```

Règles de base :

- Chaque instruction se termine par `;`.
- Les blocs sont délimités par `{ }`.
- Commentaires : `// sur une ligne` ou `/* sur plusieurs lignes */`.
- Le C est **sensible à la casse** : `Valeur` et `valeur` sont deux identifiants différents.
- `main` peut aussi recevoir les arguments de la ligne de commande :

```c
int main(int argc, char *argv[])
{
    // argc : nombre d'arguments (le nom du programme compte pour 1)
    // argv : tableau de chaînes, argv[0] = nom du programme
    for (int i = 0; i < argc; i++)
        printf("argv[%d] = %s\n", i, argv[i]);
    return 0;
}
```

```bash
./prog test 42
# argv[0] = ./prog
# argv[1] = test
# argv[2] = 42
```

---

## 3. Types de données

### 3.1 Types de base

| Type | Taille typique (x86-64) | Usage |
|------|------------------------|-------|
| `char` | 1 octet | caractère ou petit entier |
| `short` | 2 octets | entier court |
| `int` | 4 octets | entier « naturel » |
| `long` | 8 octets (Linux 64 bits), 4 sur Windows / ARM 32 bits | entier long |
| `long long` | 8 octets | entier très long |
| `float` | 4 octets | réel simple précision |
| `double` | 8 octets | réel double précision |

**Point critique** : la norme C ne fixe que des tailles *minimales*. Un `int` fait 2 octets sur un AVR (Arduino Uno) et 4 sur un STM32. En embarqué et en sécurité, on ne doit **jamais supposer la taille** d'un type de base.

```c
printf("%zu\n", sizeof(int));   // sizeof donne la taille en octets, %zu pour size_t
```

### 3.2 Types à taille fixe : `<stdint.h>` (à utiliser systématiquement)

```c
#include <stdint.h>

uint8_t  octet   = 0xFF;        // non signé 8 bits  : 0 à 255
int8_t   s8      = -128;        // signé 8 bits      : -128 à 127
uint16_t mot     = 0xABCD;      // 0 à 65535
uint32_t registre = 0x40021000; // 0 à 4 294 967 295
int32_t  temp    = -40;
uint64_t compteur = 0;
```

Ce sont ces types que tu verras partout dans les HAL (STM32), les pilotes et le code crypto.

### 3.3 Signé vs non signé

- Un entier **signé** utilise le complément à deux : sur 8 bits, `0xFF` vaut `-1`.
- Un entier **non signé** ne peut pas être négatif et « boucle » (wrap-around) : `uint8_t x = 255; x++;` donne `0`. Ce comportement est **défini** pour les non signés.
- Un dépassement sur un entier **signé** est un **comportement indéfini** (UB) : le compilateur peut faire n'importe quoi. C'est une source classique de bugs de sécurité.

### 3.4 Littéraux

```c
int dec = 42;        // décimal
int hex = 0x2A;      // hexadécimal (le plus utilisé en bas niveau)
int oct = 052;       // octal (attention : un 0 devant = octal !)
int bin = 0b101010;  // binaire (extension GCC, standard en C23)
char c  = 'A';       // caractère = valeur 65 (ASCII)
unsigned int u = 42u;
uint32_t big = 0xFFFFFFFFUL;
```

### 3.5 Formats de `printf` / `scanf`

| Spécificateur | Type |
|---------------|------|
| `%d` / `%i` | `int` |
| `%u` | `unsigned int` |
| `%ld`, `%lld` | `long`, `long long` |
| `%x`, `%X` | hexadécimal |
| `%08X` | hexa sur 8 chiffres complétés par des zéros |
| `%c` | caractère |
| `%s` | chaîne |
| `%f` | `float`/`double` |
| `%p` | adresse (pointeur) |
| `%zu` | `size_t` |

Pour les types `<stdint.h>`, utilise `<inttypes.h>` pour être portable :

```c
#include <inttypes.h>
uint32_t v = 0xDEADBEEF;
printf("v = 0x%08" PRIX32 "\n", v);
```

### 3.6 Conversions (cast)

```c
int a = 7, b = 2;
double r1 = a / b;           // 3.0 : division entière AVANT la conversion
double r2 = (double)a / b;   // 3.5 : cast explicite

uint8_t petit = (uint8_t)300; // 44 : troncature (300 mod 256)
```

Les conversions implicites entre signé et non signé sont piégeuses :

```c
int n = -1;
unsigned int u = 1;
if (n < u)          // FAUX ! n est converti en unsigned -> 4294967295
    printf("jamais affiché\n");
```

`-Wextra` te signale ce genre de comparaison.

---

## 4. Opérateurs

### 4.1 Arithmétiques

`+  -  *  /  %` (le `%` = reste de la division entière, uniquement sur les entiers).

```c
int q = 17 / 5;   // 3
int r = 17 % 5;   // 2
```

### 4.2 Affectation composée et incrémentation

```c
x += 3;   // x = x + 3
x <<= 1;  // x = x << 1
i++;      // post-incrémentation : utilise i puis l'incrémente
++i;      // pré-incrémentation : incrémente puis utilise
```

### 4.3 Comparaison et logique

- Comparaison : `==  !=  <  >  <=  >=`
- Logique : `&&` (ET), `||` (OU), `!` (NON)
- En C, **0 = faux**, toute autre valeur = vrai.
- `&&` et `||` sont évalués en **court-circuit** : `if (p != NULL && p->x > 0)` est sûr, car `p->x` n'est évalué que si `p` n'est pas nul.

Piège classique :

```c
if (x = 5)   // AFFECTATION, toujours vrai ! Il fallait ==
```

### 4.4 Opérateur ternaire

```c
int max = (a > b) ? a : b;
```

### 4.5 Priorité : en cas de doute, parenthèse

```c
if (reg & MASK == 0)     // FAUX : == est prioritaire sur &
if ((reg & MASK) == 0)   // CORRECT
```

---

## 5. Manipulation de bits

C'est **la** compétence centrale en embarqué (registres) et très présente en cybersécurité (crypto, protocoles, flags, parsing de binaires).

### 5.1 Opérateurs bit à bit

| Opérateur | Nom | Exemple (sur 8 bits) |
|-----------|-----|----------------------|
| `&` | ET | `1100 & 1010 = 1000` |
| `\|` | OU | `1100 \| 1010 = 1110` |
| `^` | OU exclusif (XOR) | `1100 ^ 1010 = 0110` |
| `~` | NON (complément) | `~0000 1111 = 1111 0000` |
| `<<` | décalage à gauche | `0001 << 3 = 1000` (× 2³) |
| `>>` | décalage à droite | `1000 >> 2 = 0010` (÷ 2²) |

### 5.2 Les quatre opérations à connaître par cœur

```c
uint32_t reg = 0;
int n = 5;

reg |=  (1U << n);    // METTRE le bit n à 1 (set)
reg &= ~(1U << n);    // METTRE le bit n à 0 (clear)
reg ^=  (1U << n);    // INVERSER le bit n (toggle)
if (reg & (1U << n))  // TESTER le bit n
    printf("bit %d actif\n", n);
```

Note le `1U` : décaler un `int` signé `1` de 31 positions est un comportement indéfini. Utilise toujours `1U` (ou `1UL`) pour les masques.

### 5.3 Manipuler un champ de plusieurs bits

Exemple : un registre où les bits 4 à 6 (3 bits) codent un mode.

```c
#define MODE_POS   4
#define MODE_MASK  (0x7U << MODE_POS)   // 0b0111_0000

// Lire le champ
uint32_t mode = (reg & MODE_MASK) >> MODE_POS;

// Écrire le champ (sans toucher aux autres bits) : read-modify-write
reg = (reg & ~MODE_MASK) | ((nouveau_mode << MODE_POS) & MODE_MASK);
```

### 5.4 Extraire des octets

```c
uint32_t v = 0x12345678;
uint8_t b0 = v & 0xFF;          // 0x78 (octet de poids faible)
uint8_t b1 = (v >> 8)  & 0xFF;  // 0x56
uint8_t b2 = (v >> 16) & 0xFF;  // 0x34
uint8_t b3 = (v >> 24) & 0xFF;  // 0x12 (octet de poids fort)

// Reconstruire
uint32_t w = ((uint32_t)b3 << 24) | ((uint32_t)b2 << 16) |
             ((uint32_t)b1 << 8)  |  (uint32_t)b0;
```

### 5.5 Propriétés du XOR (base de beaucoup de crypto)

- `a ^ a = 0`
- `a ^ 0 = a`
- `(a ^ k) ^ k = a` : chiffrer puis déchiffrer avec la même clé redonne le message.

### 5.6 Décalage à droite d'un signé

`>>` sur un nombre **négatif signé** dépend de l'implémentation (généralement arithmétique, le bit de signe est recopié). Pour de la manipulation de bits, travaille **toujours en non signé**.

---

## 6. Structures de contrôle

### 6.1 Conditions

```c
if (temp > 80) {
    alarme();
} else if (temp > 60) {
    ventilateur_on();
} else {
    ventilateur_off();
}
```

### 6.2 `switch` (idéal pour les machines à états et les commandes)

```c
switch (commande) {
    case 'A':
        led_on();
        break;          // sans break, l'exécution continue dans le case suivant
    case 'E':
        led_off();
        break;
    default:
        erreur();
        break;
}
```

### 6.3 Boucles

```c
for (int i = 0; i < 10; i++) { /* ... */ }

while (!(STATUS & READY)) { }   // attente active (polling) d'un bit matériel

do {
    lire_capteur();
} while (valeur_invalide());    // exécuté au moins une fois
```

La **boucle infinie** est la norme dans un firmware sans OS :

```c
int main(void)
{
    init_materiel();
    for (;;) {          // ou while (1)
        tache();
    }
}
```

### 6.4 `break`, `continue`, `goto`

- `break` : sort de la boucle (ou du `switch`).
- `continue` : passe à l'itération suivante.
- `goto` : généralement déconseillé, sauf pour un usage accepté (y compris dans le noyau Linux) : la **libération de ressources en cas d'erreur**.

```c
int traiter(void)
{
    char *a = malloc(100);
    if (!a) goto err_a;
    char *b = malloc(100);
    if (!b) goto err_b;

    /* ... travail ... */

    free(b);
    free(a);
    return 0;

err_b:
    free(a);
err_a:
    return -1;
}
```

---

## 7. Fonctions

### 7.1 Déclaration, définition, appel

```c
#include <stdint.h>

// Prototype (déclaration) : souvent dans un .h
uint16_t somme(const uint8_t *data, int len);

int main(void)
{
    uint8_t buf[] = {1, 2, 3};
    uint16_t s = somme(buf, 3);   // appel
    return s == 6 ? 0 : 1;
}

// Définition
uint16_t somme(const uint8_t *data, int len)
{
    uint16_t total = 0;
    for (int i = 0; i < len; i++)
        total += data[i];
    return total;
}
```

### 7.2 Passage par valeur

En C, **tout est passé par valeur** : la fonction reçoit une copie.

```c
void incrementer(int x) { x++; }         // ne modifie pas la variable de l'appelant

void incrementer_ptr(int *x) { (*x)++; } // modifie via son adresse

int a = 5;
incrementer(a);       // a vaut toujours 5
incrementer_ptr(&a);  // a vaut 6
```

C'est pour cette raison que les pointeurs sont indispensables : c'est le seul moyen pour une fonction de modifier une variable externe ou de « renvoyer » plusieurs résultats.

### 7.3 Convention de retour d'erreur

Convention courante en C système : **retourner un code d'erreur, et renvoyer le résultat via un pointeur**.

```c
int lire_capteur(uint16_t *valeur)
{
    if (valeur == NULL)
        return -1;          // erreur
    *valeur = 1234;
    return 0;               // succès
}
```

### 7.4 Récursivité

```c
unsigned long factorielle(unsigned int n)
{
    return (n <= 1) ? 1 : n * factorielle(n - 1);
}
```

À éviter en embarqué : la pile est très petite (quelques Ko) et une récursion trop profonde provoque un **débordement de pile** silencieux.

### 7.5 Pointeurs de fonction

Très utilisés pour les callbacks, les tables de vecteurs d'interruption, et les machines à états. Leur corruption est aussi une cible classique d'exploitation.

```c
typedef void (*handler_t)(void);

void action_a(void) { printf("A\n"); }
void action_b(void) { printf("B\n"); }

handler_t table[] = { action_a, action_b };

int main(void)
{
    int choix = 1;
    if (choix >= 0 && choix < 2)   // TOUJOURS vérifier l'indice
        table[choix]();
    return 0;
}
```

---

## 8. Tableaux

### 8.1 Déclaration et accès

```c
int notes[5] = {12, 15, 9, 18, 14};
uint8_t buffer[64] = {0};          // tout initialisé à 0
int n = sizeof(notes) / sizeof(notes[0]);   // nombre d'éléments : 5

notes[0] = 20;    // premier élément
notes[4] = 10;    // dernier élément
notes[5] = 0;     // HORS LIMITES : comportement indéfini, aucune erreur du compilateur
```

**Le C ne vérifie jamais les bornes.** Écrire en dehors d'un tableau écrase la mémoire voisine : c'est le principe même du buffer overflow.

### 8.2 Tableaux et fonctions

Un tableau passé à une fonction **devient un pointeur** vers son premier élément : sa taille est perdue.

```c
void afficher(const int *tab, size_t taille)   // il faut TOUJOURS passer la taille
{
    for (size_t i = 0; i < taille; i++)
        printf("%d ", tab[i]);
    printf("\n");
}

void piege(int tab[10])
{
    // sizeof(tab) == sizeof(int*) == 8, PAS 40 !
}
```

### 8.3 Tableaux à deux dimensions

```c
uint8_t image[3][4] = {
    {0, 1, 2, 3},
    {4, 5, 6, 7},
    {8, 9, 10, 11}
};
// Stocké en mémoire ligne par ligne (row-major) : 0,1,2,...,11
uint8_t px = image[1][2];   // 6
```

---

## 9. Chaînes de caractères

### 9.1 Principe

Une chaîne C est un **tableau de `char` terminé par l'octet nul `'\0'`**. Il n'y a pas de type « string ».

```c
char s1[] = "ENSA";          // 5 octets : 'E','N','S','A','\0'
char s2[10] = "Tet";         // 10 octets, le reste est rempli de '\0'
const char *s3 = "Fedora";   // pointeur vers une chaîne littérale (lecture seule !)

s3[0] = 'f';   // comportement indéfini : les littéraux sont en mémoire non modifiable
```

Si le `'\0'` manque, toutes les fonctions de chaîne continuent de lire la mémoire jusqu'à tomber par hasard sur un zéro : fuite d'informations ou crash.

### 9.2 Fonctions de `<string.h>` et leurs dangers

| Fonction | Rôle | Danger |
|----------|------|--------|
| `strlen(s)` | longueur (sans `'\0'`) | lit jusqu'au `'\0'` |
| `strcpy(dst, src)` | copie | **aucune vérification de taille** |
| `strcat(dst, src)` | concatène | **aucune vérification de taille** |
| `strcmp(a, b)` | compare (0 si égales) | non constant en temps |
| `strncpy(dst, src, n)` | copie au plus n | **n'ajoute pas `'\0'`** si src ≥ n |
| `snprintf(dst, n, ...)` | écrit formaté au plus n-1 + `'\0'` | la plus sûre |
| `memcpy(dst, src, n)` | copie n octets bruts | zones ne doivent pas se chevaucher |
| `memmove` | comme memcpy, chevauchement autorisé | |
| `memset(p, v, n)` | remplit n octets avec v | |
| `memcmp(a, b, n)` | compare n octets | |

### 9.3 Copie sécurisée

```c
char dst[16];
const char *src = "une chaine potentiellement tres longue";

// Mauvais
strcpy(dst, src);                         // overflow

// Correct
snprintf(dst, sizeof(dst), "%s", src);    // tronque proprement, toujours terminé par '\0'

// Correct aussi, avec strncpy
strncpy(dst, src, sizeof(dst) - 1);
dst[sizeof(dst) - 1] = '\0';
```

### 9.4 Lire une entrée utilisateur

```c
char nom[32];

// JAMAIS : gets(nom);  -> supprimée du standard (C11) car impossible à sécuriser
// Dangereux : scanf("%s", nom);  -> pas de limite

// Correct
if (fgets(nom, sizeof(nom), stdin) != NULL) {
    nom[strcspn(nom, "\n")] = '\0';   // retire le '\n' final éventuel
}

// Avec scanf, préciser la largeur maximale (taille - 1)
scanf("%31s", nom);
```

### 9.5 Parcourir une chaîne

```c
size_t ma_strlen(const char *s)
{
    const char *p = s;
    while (*p != '\0')
        p++;
    return (size_t)(p - s);
}
```

---

## 10. Pointeurs

C'est le concept le plus important du C. Une fois maîtrisé, tout le reste (tableaux, chaînes, allocation, registres, exploitation) devient logique.

### 10.1 Définition

Un pointeur est une **variable qui contient une adresse mémoire**.

```c
int x = 42;
int *p = &x;     // & = « adresse de » ; p contient l'adresse de x

printf("x        = %d\n", x);     // 42
printf("&x       = %p\n", (void*)&x);  // ex : 0x7ffd5c3a1b2c
printf("p        = %p\n", (void*)p);   // même adresse
printf("*p       = %d\n", *p);    // * = « valeur pointée » (déréférencement) : 42

*p = 100;        // modifie x via le pointeur
printf("x = %d\n", x);   // 100
```

Représentation mémoire :

```
Adresse        Contenu
0x...1b2c      [ 100 ]   <- x
0x...1b30      [ 0x...1b2c ]   <- p (pointe vers x)
```

### 10.2 Le type du pointeur compte

Le type indique **combien d'octets lire** et **de combien avancer** avec l'arithmétique.

```c
uint32_t v = 0x11223344;
uint8_t *pb = (uint8_t *)&v;   // voir v octet par octet

for (int i = 0; i < 4; i++)
    printf("%02X ", pb[i]);    // sur x86 : 44 33 22 11 (little-endian, voir §17)
```

### 10.3 Arithmétique des pointeurs

```c
int tab[4] = {10, 20, 30, 40};
int *p = tab;          // équivaut à &tab[0]

printf("%d\n", *p);        // 10
printf("%d\n", *(p + 2));  // 30 : p + 2 avance de 2 * sizeof(int) = 8 octets
p++;                       // pointe maintenant vers tab[1]

// Équivalence fondamentale :  tab[i]  ==  *(tab + i)
```

### 10.4 Pointeur NULL

```c
int *p = NULL;     // ne pointe vers rien de valide
if (p != NULL)
    *p = 5;        // toujours vérifier avant de déréférencer
```

Déréférencer `NULL` provoque un crash (segmentation fault) sur un PC. Sur un microcontrôleur sans MMU, l'adresse 0 est souvent **valide** (table des vecteurs), donc l'erreur peut passer inaperçue et corrompre le système.

### 10.5 `const` et pointeurs

```c
const int *p1;        // la VALEUR pointée est constante (on ne peut pas faire *p1 = ...)
int *const p2 = &x;   // le POINTEUR est constant (on ne peut pas le rediriger)
const int *const p3 = &x;   // les deux
```

Astuce de lecture : lire de droite à gauche. `int *const p2` = « p2 est un pointeur constant vers un int ».

Utilise `const` pour tout paramètre qu'une fonction ne doit pas modifier : c'est une documentation et une protection.

### 10.6 Pointeur générique `void *`

```c
void *p = &x;            // peut contenir n'importe quelle adresse
int *pi = (int *)p;      // doit être converti avant déréférencement
```

`malloc`, `memcpy`, `memset` utilisent `void *`.

### 10.7 Pointeur de pointeur

```c
int x = 5;
int *p = &x;
int **pp = &p;
printf("%d\n", **pp);    // 5
```

Utilisé pour `char *argv[]` (tableau de chaînes), ou pour qu'une fonction modifie un pointeur :

```c
int allouer(uint8_t **buf, size_t n)
{
    *buf = malloc(n);
    return (*buf == NULL) ? -1 : 0;
}

uint8_t *data = NULL;
allouer(&data, 128);
```

### 10.8 Pointeurs pendants (dangling)

```c
int *mauvais(void)
{
    int local = 42;
    return &local;   // ERREUR : local est détruite à la sortie de la fonction
}
```

L'adresse renvoyée pointe vers une zone de pile qui sera réutilisée : comportement indéfini. GCC le signale avec `-Wall`.

---

## 11. Organisation de la mémoire

Comprendre où vivent les données est indispensable, aussi bien pour optimiser un firmware que pour comprendre un exploit.

### 11.1 Les segments d'un processus (Linux)

```
Adresses hautes
+------------------------+
|        Pile (stack)    |  variables locales, adresses de retour, paramètres
|           |            |  grandit vers le BAS
|           v            |
|                        |
|           ^            |
|           |            |
|        Tas (heap)      |  malloc / free, grandit vers le HAUT
+------------------------+
|   .bss                 |  variables globales/static NON initialisées (mises à 0)
+------------------------+
|   .data                |  variables globales/static initialisées
+------------------------+
|   .rodata              |  constantes, chaînes littérales (lecture seule)
+------------------------+
|   .text                |  code machine (lecture + exécution)
+------------------------+
Adresses basses
```

```c
int globale_init = 5;          // .data
int globale_zero;              // .bss
const char *msg = "salut";     // "salut" dans .rodata, msg dans .data

void f(void)
{
    int locale = 3;            // pile
    static int compteur = 0;   // .data (persiste entre les appels)
    int *dyn = malloc(4);      // dyn sur la pile, la zone pointée dans le tas
    free(dyn);
}
```

### 11.2 Sur un microcontrôleur

- `.text` et `.rodata` sont en **Flash** (non volatile).
- `.data` est stocké en Flash puis **copié en RAM** au démarrage par le code de startup.
- `.bss` est mis à zéro en RAM au démarrage.
- La pile et le tas partagent la RAM restante (souvent quelques dizaines de Ko). S'ils se rejoignent, le système se corrompt sans message d'erreur.

Tu peux voir la taille de chaque section avec :

```bash
size prog
```

### 11.3 La pile et les appels de fonction

À chaque appel, une **stack frame** est créée : paramètres (ou registres), **adresse de retour**, ancien pointeur de base, variables locales. Si un tableau local déborde, il peut écraser l'adresse de retour : à la fin de la fonction, le processeur saute là où l'attaquant l'a décidé. C'est le **stack buffer overflow** (voir §19).

---

## 12. Allocation dynamique

```c
#include <stdlib.h>

size_t n = 100;
int *tab = malloc(n * sizeof(*tab));   // contenu NON initialisé
if (tab == NULL) {
    // toujours vérifier : l'allocation peut échouer
    return -1;
}

int *zeros = calloc(n, sizeof(*zeros)); // initialisé à 0, vérifie le dépassement n*taille

int *plus = realloc(tab, 2 * n * sizeof(*tab));
if (plus == NULL) {
    free(tab);     // realloc a échoué : l'ancien bloc est toujours valide
    return -1;
}
tab = plus;        // ne jamais écrire tab = realloc(tab, ...) directement (fuite si échec)

free(tab);
tab = NULL;        // bonne pratique : évite le use-after-free et le double free
free(zeros);
```

Règles d'or :

1. Chaque `malloc` a **exactement un** `free`.
2. Ne jamais utiliser un pointeur après `free` (use-after-free).
3. Ne jamais libérer deux fois (double free).
4. Ne jamais libérer un pointeur qui ne vient pas de `malloc`/`calloc`/`realloc`.

**En embarqué**, l'allocation dynamique est souvent **interdite** (normes MISRA C, systèmes critiques) : risque de fragmentation, temps non déterministe. On utilise des tableaux statiques ou des pools de mémoire de taille fixe.

---

## 13. `struct`, `union`, `enum`, `typedef`

### 13.1 Structures

```c
#include <stdint.h>

struct capteur {
    uint8_t  id;
    uint16_t valeur;
    float    seuil;
};

struct capteur c1 = { .id = 1, .valeur = 512, .seuil = 3.3f };  // initialisation désignée
c1.valeur = 600;                 // accès par .

struct capteur *pc = &c1;
pc->valeur = 700;                // accès via pointeur : -> équivaut à (*pc).valeur
```

### 13.2 `typedef`

```c
typedef struct {
    uint32_t src_ip;
    uint32_t dst_ip;
    uint16_t src_port;
    uint16_t dst_port;
} flux_t;

flux_t f = {0};
```

Convention fréquente : suffixe `_t` pour les types.

### 13.3 Alignement et padding

Le compilateur insère des octets de remplissage pour aligner les champs :

```c
struct exemple {
    uint8_t  a;   // 1 octet + 3 octets de padding
    uint32_t b;   // 4 octets (aligné sur 4)
    uint8_t  c;   // 1 octet + 3 octets de padding
};
// sizeof(struct exemple) == 12, pas 6 !
```

Réordonner les champs du plus grand au plus petit réduit le padding. Pour coller exactement à un format binaire (en-tête réseau, trame), on force l'absence de padding :

```c
struct __attribute__((packed)) entete {
    uint8_t  type;
    uint16_t longueur;
    uint32_t sequence;
};  // sizeof == 7
```

**Sécurité** : le padding n'est pas initialisé. Copier une structure locale vers l'utilisateur ou le réseau peut **divulguer des données de la pile** (fuite d'informations, déjà vue dans le noyau Linux). Solution : `memset(&s, 0, sizeof(s))` avant de remplir.

### 13.4 Unions

Tous les champs partagent la **même zone mémoire**.

```c
typedef union {
    uint32_t mot;
    uint8_t  octets[4];
} conv_t;

conv_t u;
u.mot = 0xAABBCCDD;
printf("%02X\n", u.octets[0]);   // DD sur une machine little-endian
```

Utile pour interpréter une même donnée de plusieurs façons (trames, registres).

### 13.5 Champs de bits

```c
struct flags {
    unsigned int actif   : 1;
    unsigned int erreur  : 1;
    unsigned int mode    : 3;
    unsigned int reserve : 3;
};
```

Pratique, mais l'ordre des bits dépend du compilateur : pour les registres matériels, on préfère les masques et décalages du §5.

### 13.6 Énumérations

```c
typedef enum {
    ETAT_REPOS,       // 0
    ETAT_MESURE,      // 1
    ETAT_ENVOI,       // 2
    ETAT_ERREUR = 99
} etat_t;

etat_t etat = ETAT_REPOS;
```

---

## 14. Préprocesseur

Le préprocesseur agit **avant** la compilation : il fait du remplacement de texte.

### 14.1 `#include`

```c
#include <stdio.h>      // en-tête système (cherché dans /usr/include)
#include "capteur.h"    // en-tête du projet (cherché d'abord dans le dossier courant)
```

### 14.2 `#define` : constantes et macros

```c
#define TAILLE_BUF   64
#define LED_PIN      5
#define BIT(n)       (1U << (n))
#define MAX(a, b)    ((a) > (b) ? (a) : (b))
```

Toujours **parenthéser** les paramètres et le résultat :

```c
#define CARRE(x) x * x
int r = CARRE(2 + 1);   // devient 2 + 1 * 2 + 1 = 5, pas 9 !

#define CARRE_OK(x) ((x) * (x))
```

Attention aux effets de bord : `MAX(i++, j)` incrémente `i` deux fois. Pour ce genre de cas, préfère une fonction `static inline`.

### 14.3 Compilation conditionnelle

```c
#define DEBUG 1

#if DEBUG
    #define LOG(msg) printf("[DBG] %s\n", msg)
#else
    #define LOG(msg)
#endif

#ifdef __ARM_ARCH
    // code spécifique ARM
#endif
```

Tu peux aussi définir une macro à la compilation : `gcc -DDEBUG=1 main.c`.

### 14.4 Garde d'inclusion (indispensable dans chaque .h)

```c
// capteur.h
#ifndef CAPTEUR_H
#define CAPTEUR_H

#include <stdint.h>

typedef struct {
    uint8_t id;
    uint16_t valeur;
} capteur_t;

int capteur_lire(capteur_t *c);

#endif /* CAPTEUR_H */
```

### 14.5 Organisation d'un projet en plusieurs fichiers

```
projet/
├── main.c        -> #include "capteur.h", contient main()
├── capteur.c     -> implémente capteur_lire()
├── capteur.h     -> prototypes et types
└── Makefile
```

Makefile minimal :

```makefile
CC      = gcc
CFLAGS  = -Wall -Wextra -g -std=c11
OBJ     = main.o capteur.o

prog: $(OBJ)
	$(CC) $(CFLAGS) -o $@ $^

%.o: %.c
	$(CC) $(CFLAGS) -c $<

clean:
	rm -f *.o prog
```

(Les lignes de commande dans un Makefile doivent commencer par une **tabulation**, pas des espaces.)

---

## 15. Mots-clés essentiels en embarqué

### 15.1 `volatile`

Indique au compilateur que la variable **peut changer en dehors du flux normal du programme** (matériel, interruption, autre thread). Il doit donc la relire en mémoire à chaque accès, sans optimiser.

```c
volatile uint8_t flag_uart = 0;

void USART1_IRQHandler(void)   // routine d'interruption
{
    flag_uart = 1;
}

int main(void)
{
    while (flag_uart == 0) { }   // sans volatile, avec -O2, cette boucle peut devenir infinie
    traiter();
}
```

Utilisations obligatoires : registres matériels, variables partagées avec une interruption.
`volatile` **ne rend pas** une opération atomique et ne remplace pas un mutex.

### 15.2 `static`

Deux sens différents :

```c
static int compteur_module = 0;   // global au FICHIER : invisible depuis les autres .c
                                  // (encapsulation, équivalent de « private »)

void f(void)
{
    static int appels = 0;        // local mais PERSISTANT entre les appels
    appels++;
}

static void aide_interne(void) { } // fonction visible uniquement dans ce fichier
```

Bonne pratique : tout ce qui n'a pas besoin d'être visible hors du fichier doit être `static`.

### 15.3 `extern`

Déclare une variable définie dans un autre fichier.

```c
// config.c
int vitesse_uart = 115200;

// main.c
extern int vitesse_uart;
```

### 15.4 `const`

En embarqué, les données `const` globales sont placées en **Flash** au lieu de la RAM, ce qui économise une ressource rare :

```c
static const uint8_t table_sinus[256] = { /* ... */ };
```

### 15.5 `inline`

```c
static inline uint32_t bit(uint8_t n) { return 1U << n; }
```

Suggère au compilateur de remplacer l'appel par le corps de la fonction (pas d'overhead d'appel), avec la sécurité de typage d'une fonction.

---

## 16. Accès aux registres matériels

Sur un microcontrôleur, les périphériques (GPIO, UART, timers) sont contrôlés par des **registres situés à des adresses fixes** (memory-mapped I/O). En C, on y accède par un pointeur `volatile` vers cette adresse.

### 16.1 Accès direct

```c
#define GPIOA_BASE  0x40020000UL
#define GPIOA_MODER (*(volatile uint32_t *)(GPIOA_BASE + 0x00))
#define GPIOA_ODR   (*(volatile uint32_t *)(GPIOA_BASE + 0x14))

void led_init(void)
{
    // PA5 en sortie : bits 10-11 de MODER = 01
    GPIOA_MODER &= ~(3U << (5 * 2));
    GPIOA_MODER |=  (1U << (5 * 2));
}

void led_toggle(void)
{
    GPIOA_ODR ^= (1U << 5);
}
```

(Adresses d'exemple inspirées d'un STM32F4 : vérifie toujours dans le *Reference Manual* de ta carte.)

Décomposition de `(*(volatile uint32_t *)(0x40020014))` :

1. `0x40020014` : un simple nombre.
2. `(volatile uint32_t *)` : converti en pointeur vers un registre 32 bits volatile.
3. `*` : déréférencé, donc on lit/écrit directement à cette adresse.

### 16.2 Méthode structurée (celle des fichiers CMSIS)

```c
typedef struct {
    volatile uint32_t MODER;    // offset 0x00
    volatile uint32_t OTYPER;   // offset 0x04
    volatile uint32_t OSPEEDR;  // offset 0x08
    volatile uint32_t PUPDR;    // offset 0x0C
    volatile uint32_t IDR;      // offset 0x10
    volatile uint32_t ODR;      // offset 0x14
} GPIO_TypeDef;

#define GPIOA ((GPIO_TypeDef *)0x40020000UL)

GPIOA->ODR |= (1U << 5);
```

C'est exactement ce que tu retrouveras dans les en-têtes fournis par ST, NXP ou Microchip.

### 16.3 Lien avec le FPGA

Sur un SoC FPGA (Zynq, ou un softcore comme MicroBlaze / NIOS / RISC-V), un périphérique que tu décris en VHDL/Verilog et que tu connectes au bus (AXI, Avalon, Wishbone) apparaît côté processeur comme… un ensemble de registres à une adresse de base. Le code C pour le piloter est identique au principe ci-dessus.

---

## 17. Endianness

L'**endianness** est l'ordre de stockage des octets d'un entier multi-octets en mémoire.

Valeur `0x12345678` stockée à l'adresse `0x100` :

| Adresse | Little-endian (x86, ARM par défaut) | Big-endian (réseau, certains PowerPC) |
|---------|------|------|
| 0x100 | 78 | 12 |
| 0x101 | 56 | 34 |
| 0x102 | 34 | 56 |
| 0x103 | 12 | 78 |

Les protocoles réseau (TCP/IP) sont en **big-endian** (« network byte order »).

```c
#include <arpa/inet.h>   // Linux

uint16_t port_net = htons(8080);     // host to network short
uint32_t ip_net   = htonl(0xC0A80001);
uint16_t port     = ntohs(port_net); // network to host short
```

Conversion manuelle (portable, utile en embarqué) :

```c
uint32_t swap32(uint32_t v)
{
    return ((v & 0x000000FFU) << 24) |
           ((v & 0x0000FF00U) << 8)  |
           ((v & 0x00FF0000U) >> 8)  |
           ((v & 0xFF000000U) >> 24);
}

// Lecture big-endian depuis un buffer, indépendante de la machine
uint32_t lire_be32(const uint8_t *p)
{
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8)  |  (uint32_t)p[3];
}
```

Pour le parsing de fichiers binaires (ELF, PE, captures réseau) et la rétro-ingénierie, c'est un réflexe permanent.

---

## 18. Algorithmes fondamentaux

Chaque algorithme est accompagné de sa complexité et du contexte où tu le rencontreras.

### 18.1 Recherche linéaire — O(n)

```c
int recherche(const int *tab, size_t n, int cible)
{
    for (size_t i = 0; i < n; i++)
        if (tab[i] == cible)
            return (int)i;
    return -1;
}
```

### 18.2 Recherche dichotomique — O(log n), tableau trié

```c
int dichotomie(const int *tab, size_t n, int cible)
{
    size_t bas = 0, haut = n;          // intervalle [bas, haut[
    while (bas < haut) {
        size_t mil = bas + (haut - bas) / 2;   // évite le dépassement de (bas + haut)
        if (tab[mil] == cible)
            return (int)mil;
        if (tab[mil] < cible)
            bas = mil + 1;
        else
            haut = mil;
    }
    return -1;
}
```

Le calcul `bas + (haut - bas) / 2` au lieu de `(bas + haut) / 2` est un vrai correctif de sécurité : ce dépassement d'entier a existé pendant des années dans la bibliothèque standard Java.

### 18.3 Tri par insertion — O(n²), efficace sur petits tableaux

```c
void tri_insertion(int *tab, size_t n)
{
    for (size_t i = 1; i < n; i++) {
        int cle = tab[i];
        size_t j = i;
        while (j > 0 && tab[j - 1] > cle) {
            tab[j] = tab[j - 1];
            j--;
        }
        tab[j] = cle;
    }
}
```

En pratique, pour de gros volumes sur PC, utilise `qsort` de `<stdlib.h>` :

```c
int cmp_int(const void *a, const void *b)
{
    int x = *(const int *)a, y = *(const int *)b;
    return (x > y) - (x < y);   // évite le dépassement de x - y
}

qsort(tab, n, sizeof(tab[0]), cmp_int);
```

### 18.4 Buffer circulaire (ring buffer) — O(1)

**La** structure de données de l'embarqué : réception UART par interruption, file de messages, échantillons audio/DSP.

```c
#include <stdint.h>
#include <stdbool.h>

#define RB_TAILLE 64   // puissance de 2 : permet un masque au lieu d'un modulo

typedef struct {
    uint8_t  data[RB_TAILLE];
    volatile uint16_t tete;    // prochaine écriture
    volatile uint16_t queue;   // prochaine lecture
} ringbuf_t;

static inline bool rb_vide(const ringbuf_t *rb)
{
    return rb->tete == rb->queue;
}

static inline bool rb_plein(const ringbuf_t *rb)
{
    return (uint16_t)(rb->tete - rb->queue) == RB_TAILLE;
}

bool rb_ecrire(ringbuf_t *rb, uint8_t octet)
{
    if (rb_plein(rb))
        return false;                          // refuse plutôt qu'écraser
    rb->data[rb->tete & (RB_TAILLE - 1)] = octet;
    rb->tete++;
    return true;
}

bool rb_lire(ringbuf_t *rb, uint8_t *octet)
{
    if (rb_vide(rb))
        return false;
    *octet = rb->data[rb->queue & (RB_TAILLE - 1)];
    rb->queue++;
    return true;
}
```

Les indices tournent librement sur 16 bits ; le masque `& (RB_TAILLE - 1)` ramène dans le tableau, et la différence `tete - queue` donne le nombre d'éléments grâce à l'arithmétique modulaire des non signés.

### 18.5 Compter les bits à 1 (popcount / poids de Hamming)

```c
unsigned popcount(uint32_t v)
{
    unsigned n = 0;
    while (v) {
        v &= v - 1;   // efface le bit à 1 le plus bas
        n++;
    }
    return n;
}
// GCC fournit aussi __builtin_popcount(v)
```

Utilisé en crypto, en correction d'erreurs, et dans les attaques par canaux auxiliaires (modèle de consommation « Hamming weight »).

### 18.6 Tester si un nombre est une puissance de 2

```c
bool est_puissance2(uint32_t v)
{
    return v != 0 && (v & (v - 1)) == 0;
}
```

### 18.7 Somme de contrôle simple et CRC-8

Vérification d'intégrité des trames (capteurs I²C, protocoles série, firmware).

```c
uint8_t checksum8(const uint8_t *data, size_t len)
{
    uint8_t s = 0;
    for (size_t i = 0; i < len; i++)
        s += data[i];
    return (uint8_t)(~s + 1);   // complément à deux : somme totale = 0
}

// CRC-8, polynôme 0x07 (x^8 + x^2 + x + 1)
uint8_t crc8(const uint8_t *data, size_t len)
{
    uint8_t crc = 0x00;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int b = 0; b < 8; b++) {
            if (crc & 0x80)
                crc = (uint8_t)((crc << 1) ^ 0x07);
            else
                crc = (uint8_t)(crc << 1);
        }
    }
    return crc;
}
// Vérification : crc8("123456789", 9) doit donner 0xF4
```

Important en sécurité : un checksum ou un CRC **détecte les erreurs accidentelles** mais n'offre **aucune protection contre un attaquant**, qui peut recalculer la valeur. Pour l'authenticité, il faut un MAC (HMAC) ou une signature.

### 18.8 Chiffrement XOR (pédagogique)

```c
void xor_chiffre(uint8_t *data, size_t len, const uint8_t *cle, size_t lcle)
{
    for (size_t i = 0; i < len; i++)
        data[i] ^= cle[i % lcle];
}
// Appeler deux fois la fonction avec la même clé restaure le message.
```

Cette technique est **cassable** (analyse de fréquence, clé répétée, texte clair connu). Elle est pourtant très répandue dans les malwares pour masquer des chaînes : savoir la reconnaître fait partie de l'analyse de binaires. Pour de la vraie crypto, on utilise une bibliothèque éprouvée (libsodium, mbedTLS, OpenSSL), jamais une implémentation maison.

### 18.9 Comparaison en temps constant

`memcmp` et `strcmp` s'arrêtent à la première différence : le temps d'exécution révèle combien d'octets sont corrects. Un attaquant peut deviner un mot de passe ou un MAC octet par octet (**timing attack**).

```c
int comparaison_ct(const uint8_t *a, const uint8_t *b, size_t n)
{
    uint8_t diff = 0;
    for (size_t i = 0; i < n; i++)
        diff |= a[i] ^ b[i];    // parcourt TOUJOURS tout le buffer
    return diff == 0;           // 1 si égal
}
```

### 18.10 Affichage hexadécimal (hexdump)

Outil de base pour déboguer des trames, des dumps mémoire ou des paquets.

```c
#include <ctype.h>

void hexdump(const void *adr, size_t len)
{
    const uint8_t *p = adr;
    for (size_t i = 0; i < len; i += 16) {
        printf("%08zx  ", i);
        for (size_t j = 0; j < 16; j++) {
            if (i + j < len) printf("%02x ", p[i + j]);
            else             printf("   ");
        }
        printf(" |");
        for (size_t j = 0; j < 16 && i + j < len; j++)
            putchar(isprint(p[i + j]) ? p[i + j] : '.');
        printf("|\n");
    }
}
```

### 18.11 Machine à états

Structure fondamentale d'un firmware : protocoles, gestion de boutons, séquences.

```c
typedef enum { ATTENTE_ENTETE, LECTURE_LONGUEUR, LECTURE_DATA, TRAME_OK } etat_rx_t;

#define MAX_DATA 32

static etat_rx_t etat = ATTENTE_ENTETE;
static uint8_t buf[MAX_DATA];
static uint8_t attendu, recu;

void recevoir_octet(uint8_t o)
{
    switch (etat) {
    case ATTENTE_ENTETE:
        if (o == 0xAA)
            etat = LECTURE_LONGUEUR;
        break;
    case LECTURE_LONGUEUR:
        if (o == 0 || o > MAX_DATA) {   // VALIDATION : sinon débordement de buf
            etat = ATTENTE_ENTETE;
        } else {
            attendu = o;
            recu = 0;
            etat = LECTURE_DATA;
        }
        break;
    case LECTURE_DATA:
        buf[recu++] = o;
        if (recu == attendu)
            etat = TRAME_OK;
        break;
    case TRAME_OK:
        /* traité ailleurs, puis retour à ATTENTE_ENTETE */
        break;
    }
}
```

La vérification de la longueur annoncée est exactement ce qui manquait dans la faille **Heartbleed** (OpenSSL, 2014) : le serveur faisait confiance à une longueur fournie par le client.

### 18.12 Moyenne glissante (filtre simple, lien avec le DSP)

```c
#define N_ECH 8

uint16_t moyenne_glissante(uint16_t nouvel)
{
    static uint16_t hist[N_ECH];
    static uint32_t somme = 0;
    static uint8_t idx = 0;

    somme -= hist[idx];
    hist[idx] = nouvel;
    somme += nouvel;
    idx = (idx + 1) % N_ECH;
    return (uint16_t)(somme / N_ECH);
}
```

C'est un filtre FIR à coefficients égaux, calculé en O(1) par échantillon.

---

## 19. Programmation sécurisée : les vulnérabilités classiques

Pour chaque faille : le code vulnérable, le mécanisme, et la correction.

### 19.1 Stack buffer overflow

```c
void vulnerable(const char *entree)
{
    char buf[16];
    strcpy(buf, entree);   // si entree > 15 caractères : écriture au-delà de buf
}
```

Mécanisme : les octets en trop écrasent les données voisines sur la pile, dont l'**adresse de retour**. Un attaquant peut rediriger l'exécution.

Correction :

```c
void corrige(const char *entree)
{
    char buf[16];
    snprintf(buf, sizeof(buf), "%s", entree);
}
```

Protections modernes (qui compliquent l'exploitation sans corriger le bug) : **stack canary** (`-fstack-protector-strong`), **NX/DEP** (pile non exécutable), **ASLR** (adresses aléatoires), **PIE**. Sur beaucoup de microcontrôleurs, **aucune** de ces protections n'existe.

### 19.2 Off-by-one

```c
char buf[10];
for (int i = 0; i <= 10; i++)   // <= au lieu de < : écrit buf[10], hors limites
    buf[i] = 'A';
```

Un seul octet de trop suffit parfois à une exploitation (écrasement du `'\0'` ou de l'octet faible d'un pointeur).

### 19.3 Integer overflow menant à un buffer overflow

```c
void *alloue_elements(size_t n)
{
    return malloc(n * sizeof(uint32_t));   // si n est énorme, le produit déborde -> petit bloc
}
```

Correction :

```c
void *alloue_elements_ok(size_t n)
{
    if (n > SIZE_MAX / sizeof(uint32_t))
        return NULL;
    return malloc(n * sizeof(uint32_t));
    // ou simplement : calloc(n, sizeof(uint32_t)), qui fait cette vérification
}
```

Autre piège : le signé utilisé comme taille.

```c
int len = lire_longueur_reseau();   // l'attaquant envoie -1
if (len < 64)                       // passe le test !
    memcpy(buf, src, len);          // len converti en size_t = énorme
```

Toujours valider **les deux bornes**, ou utiliser des types non signés (`size_t`) pour les tailles.

### 19.4 Format string

```c
printf(entree_utilisateur);         // VULNÉRABLE
printf("%s", entree_utilisateur);   // CORRECT
```

Si l'utilisateur envoie `%x %x %x`, printf lit des valeurs de la pile (fuite) ; avec `%n`, il peut **écrire** en mémoire. `-Wall` (via `-Wformat-security`) signale ce cas.

### 19.5 Use-after-free

```c
char *p = malloc(32);
free(p);
strcpy(p, "data");   // la zone peut déjà avoir été réattribuée à autre chose
```

Correction : `p = NULL;` après `free`, et une conception claire de « qui possède quelle mémoire ».

### 19.6 Double free

```c
free(p);
free(p);   // corrompt les structures internes de l'allocateur -> exploitable
```

### 19.7 Pointeur NULL non vérifié

```c
char *p = malloc(n);
p[0] = 'x';   // si malloc a échoué : crash, ou pire en embarqué
```

### 19.8 Variables non initialisées

```c
int acces;
if (verifier_mdp(mdp))
    acces = 1;
if (acces)          // si le mot de passe est faux, acces contient une valeur aléatoire de la pile
    ouvrir();
```

Correction : **initialiser toute variable** à sa déclaration (`int acces = 0;`).

### 19.9 Race condition (TOCTOU)

```c
if (access("fichier", W_OK) == 0) {   // Time Of Check
    /* entre les deux, un attaquant remplace le fichier par un lien symbolique */
    FILE *f = fopen("fichier", "w");  // Time Of Use
}
```

En embarqué, l'équivalent est une variable partagée entre le programme principal et une interruption, modifiée au milieu d'une lecture non atomique. Solution : section critique (désactivation temporaire des interruptions) ou opérations atomiques.

### 19.10 Fuite d'informations sensibles en mémoire

```c
char mdp[64];
lire_mdp(mdp, sizeof(mdp));
verifier(mdp);
memset(mdp, 0, sizeof(mdp));   // peut être SUPPRIMÉ par l'optimiseur (variable plus utilisée)
```

Utiliser une fonction que le compilateur ne supprime pas : `explicit_bzero(mdp, sizeof(mdp));` (glibc) ou `memset_s` (C11 Annexe K, rarement disponible).

### 19.11 Récapitulatif des fonctions

| À bannir | À utiliser |
|----------|-----------|
| `gets` | `fgets` |
| `strcpy`, `strcat` | `snprintf`, ou `strncpy`/`strncat` avec terminaison manuelle |
| `sprintf` | `snprintf` |
| `scanf("%s")` | `scanf("%31s")` ou `fgets` |
| `printf(var)` | `printf("%s", var)` |
| `atoi` (pas de détection d'erreur) | `strtol` avec vérification de `errno` et de `endptr` |
| `memcmp` pour des secrets | comparaison en temps constant |
| `rand()` pour de la crypto | `getrandom()` (Linux) ou le TRNG matériel du MCU |

Exemple `strtol` robuste :

```c
#include <errno.h>
#include <limits.h>

int convertir(const char *s, int *res)
{
    char *fin;
    errno = 0;
    long v = strtol(s, &fin, 10);
    if (errno != 0 || fin == s || *fin != '\0' || v < INT_MIN || v > INT_MAX)
        return -1;
    *res = (int)v;
    return 0;
}
```

---

## 20. Compilation, outils et débogage

### 20.1 Options de compilation recommandées

```bash
# Développement : avertissements max + débogage + détection d'erreurs à l'exécution
gcc -std=c11 -Wall -Wextra -Wpedantic -Wconversion -Wshadow -g \
    -fsanitize=address,undefined main.c -o prog

# Durcissement (hardening) pour un binaire de production
gcc -std=c11 -O2 -Wall -Wextra -D_FORTIFY_SOURCE=2 \
    -fstack-protector-strong -fPIE -pie -Wl,-z,relro,-z,now main.c -o prog
```

| Option | Effet |
|--------|-------|
| `-Wpedantic` | signale les extensions non standard |
| `-Wconversion` | signale les conversions implicites avec perte |
| `-Wshadow` | signale une variable qui en masque une autre |
| `-fsanitize=address` | détecte overflows, use-after-free, fuites (ASan) |
| `-fsanitize=undefined` | détecte les comportements indéfinis (UBSan) |
| `-D_FORTIFY_SOURCE=2` | vérifications à l'exécution sur memcpy, strcpy… (nécessite `-O1` ou plus) |
| `-fstack-protector-strong` | canaris de pile |
| `-fPIE -pie` | exécutable relocalisable (compatible ASLR) |
| `-Wl,-z,relro,-z,now` | GOT en lecture seule |

Vérifier les protections d'un binaire :

```bash
sudo dnf install checksec
checksec --file=./prog
```

### 20.2 Voir les étapes de compilation

```bash
gcc -E main.c -o main.i    # après préprocesseur
gcc -S main.c -o main.s    # code assembleur
gcc -c main.c -o main.o    # fichier objet
gcc main.o -o prog         # édition de liens
```

Regarder l'assembleur généré est un excellent moyen de comprendre ce que fait vraiment ton code.

### 20.3 Outils d'analyse de binaires (utiles en sécurité)

```bash
file prog          # type de fichier (ELF 64 bits, lié dynamiquement…)
size prog          # taille des sections .text, .data, .bss
nm prog            # symboles (fonctions, variables globales)
objdump -d prog    # désassemblage
readelf -a prog    # structure ELF complète
strings prog       # chaînes lisibles (mots de passe codés en dur…)
ltrace ./prog      # appels aux bibliothèques
strace ./prog      # appels système
```

### 20.4 GDB : les commandes essentielles

```bash
gdb ./prog
```

| Commande | Action |
|----------|--------|
| `break main` / `b 42` | point d'arrêt sur une fonction / une ligne |
| `run arg1 arg2` | lancer avec arguments |
| `next` / `n` | ligne suivante (sans entrer dans les fonctions) |
| `step` / `s` | ligne suivante (en entrant dans les fonctions) |
| `continue` / `c` | continuer jusqu'au prochain point d'arrêt |
| `print x` / `p x` | afficher une variable |
| `p/x x` | afficher en hexadécimal |
| `x/16xb &buf` | examiner 16 octets en hexa à l'adresse de buf |
| `info registers` | registres du processeur |
| `backtrace` / `bt` | pile d'appels |
| `watch x` | s'arrêter quand x change |
| `disassemble` | assembleur de la fonction courante |

Astuce : installe l'extension **GEF** ou **pwndbg** (depuis leurs dépôts GitHub) pour une interface bien plus lisible, très utilisée en exploitation.

### 20.5 Valgrind

```bash
sudo dnf install valgrind
valgrind --leak-check=full ./prog
```

Détecte les fuites mémoire et les accès invalides (alternative à ASan, sans recompilation).

### 20.6 Analyse statique

```bash
sudo dnf install cppcheck
cppcheck --enable=all main.c
```

Ou `gcc -fanalyzer main.c` (analyseur statique intégré à GCC récent).

---

## 21. Exercices progressifs

À faire dans l'ordre, chacun compilé avec `-Wall -Wextra -fsanitize=address,undefined`.

**Niveau 1 : syntaxe et bits**

1. Afficher la taille (`sizeof`) de tous les types de base et de `<stdint.h>` sur ta machine.
2. Écrire `set_bit`, `clear_bit`, `toggle_bit`, `test_bit` et une fonction qui affiche un `uint32_t` en binaire.
3. Écrire une fonction qui inverse l'ordre des bits d'un `uint8_t` (`0b00000001` → `0b10000000`).
4. Déterminer par programme si ta machine est little ou big-endian (indice : pointeur `uint8_t *` sur un `uint32_t`).

**Niveau 2 : pointeurs et chaînes**

5. Réécrire `strlen`, `strcpy` (version sécurisée avec taille), `strcmp` et `memcpy` sans utiliser `<string.h>`.
6. Écrire une fonction qui inverse une chaîne sur place avec deux pointeurs.
7. Écrire `swap(int *a, int *b)` puis `swap` générique avec `void *` et une taille.
8. Lire un fichier binaire et afficher son contenu avec ton `hexdump`.

**Niveau 3 : structures et algorithmes**

9. Implémenter et tester le ring buffer (cas vide, plein, débordement des indices).
10. Parser l'en-tête d'un fichier ELF ou BMP en lisant les champs à la main (endianness, `packed`).
11. Implémenter une liste chaînée (ajout, suppression, libération complète) et la valider avec Valgrind : zéro fuite.
12. Écrire la machine à états de réception de trame du §18.11 avec vérification CRC-8.

**Niveau 4 : sécurité**

13. Écrire volontairement un programme avec un stack buffer overflow, le compiler sans protections (`-fno-stack-protector -z execstack -no-pie`), observer l'écrasement de l'adresse de retour dans GDB, puis le recompiler avec protections et observer la différence.
14. Démontrer une fuite d'information par format string (`printf(argv[1])` avec `%p %p %p`).
15. Mesurer le temps d'exécution de `memcmp` vs ta comparaison en temps constant sur un secret de 32 octets (avec `clock_gettime`) et discuter du résultat.
16. Passer un de tes anciens programmes à `cppcheck`, `-fanalyzer` et ASan, et corriger tout ce qui est signalé.

**Niveau 5 : embarqué**

17. Sur une carte (STM32, ou en simulation avec QEMU), faire clignoter une LED **sans HAL**, uniquement avec des accès registres à partir du Reference Manual.
18. Recevoir des caractères UART par interruption dans un ring buffer et les renvoyer en écho.

---

## Ressources pour aller plus loin

- *The C Programming Language*, Kernighan & Ritchie : la référence historique, courte et dense.
- *Modern C*, Jens Gustedt : C moderne (C11/C17), disponible gratuitement par l'auteur.
- *Effective C*, Robert Seacord : C avec une forte orientation sécurité.
- *SEI CERT C Coding Standard* : règles de codage sécurisé, consultable en ligne.
- *Hacking: The Art of Exploitation*, Jon Erickson : C, assembleur et exploitation sous Linux.
- Reference Manuals et datasheets de ta carte : la vraie documentation en embarqué.
- Plateformes d'entraînement : OverTheWire (Narnia, Behemoth), pwn.college, Exploit Education (Phoenix).
