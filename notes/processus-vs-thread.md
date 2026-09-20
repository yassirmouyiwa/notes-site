# Processus vs Thread

> Note prise le 2026-09-20

## 1. L'idée en une phrase

Un **processus** est un programme en cours d'exécution avec **son propre espace
mémoire**. Un **thread** (fil d'exécution) est une unité d'exécution **à
l'intérieur** d'un processus : plusieurs threads d'un même processus **partagent
la même mémoire**.

Autrement dit : le processus est le *conteneur de ressources*, le thread est le
*flot d'exécution*. Un processus contient toujours au moins un thread (le thread
principal).

```
        PROCESSUS A                          PROCESSUS B
 ┌──────────────────────────┐        ┌──────────────────────────┐
 │  Code  │  Données  │ Tas │        │  Code  │  Données  │ Tas │   <- partagés
 ├────────┴───────────┴─────┤        ├────────┴───────────┴─────┤      entre les
 │ Th.1 │ Th.2 │ Th.3       │        │ Th.1                     │      threads
 │ pile │ pile │ pile       │        │ pile                     │   <- propres à
 │ regs │ regs │ regs       │        │ regs                     │      chaque thread
 └──────────────────────────┘        └──────────────────────────┘
        └──── mémoires totalement isolées l'une de l'autre ────┘
```

## 2. Qui possède quoi

| Ressource                         | Partagée entre threads | Partagée entre processus |
|-----------------------------------|------------------------|--------------------------|
| Code (segment texte)              | oui                    | non (sauf `mmap`/fork COW) |
| Variables globales / statiques    | oui                    | non                      |
| Tas (`malloc`, objets)            | oui                    | non                      |
| Descripteurs de fichiers          | oui                    | non (copiés au `fork`)   |
| Table des pages / espace d'adressage | oui                 | non                      |
| Pile d'exécution                  | **non** (une par thread) | non                    |
| Registres, compteur ordinal       | **non**                | non                      |
| Variables locales                 | **non**                | non                      |
| Signal handlers                   | oui                    | non                      |
| PID (identifiant de processus)    | oui (même PID)         | non                      |

Point essentiel : ce qui distingue un thread, c'est **sa pile et ses registres**.
Tout le reste, il le partage avec ses frères.

## 3. Coût : création et commutation

Créer un processus implique de dupliquer (au moins logiquement) l'espace
d'adressage ; créer un thread ne demande qu'une pile et une structure noyau.

| Opération                      | Ordre de grandeur |
|--------------------------------|-------------------|
| Création d'un thread           | ~10–50 µs         |
| Création d'un processus (`fork`) | ~100–500 µs     |
| Changement de contexte thread→thread (même processus) | rapide : pas de vidage du TLB |
| Changement de contexte processus→processus | plus coûteux : changement de table des pages, TLB invalidé |

Linux atténue le coût du `fork` avec le **copy-on-write** : les pages ne sont
réellement copiées qu'à la première écriture.

## 4. Ce que ça change en pratique

**Isolation / robustesse**
Un thread qui fait un segfault tue **tout le processus**, donc tous ses frères.
Un processus qui plante laisse les autres intacts. C'est pourquoi Chrome ou
systemd isolent les composants sensibles dans des processus séparés.

**Communication**
- Entre threads : une simple variable partagée. Rapide mais **dangereux** —
  il faut des mutex, sémaphores, variables de condition, ou des atomiques.
- Entre processus : IPC explicite — `pipe`, socket UNIX, mémoire partagée
  (`shm_open`/`mmap`), file de messages, signaux. Plus lourd, mais l'isolation
  est garantie par le MMU.

**Bugs typiques des threads**
*Race condition* (deux threads écrivent la même variable sans synchronisation),
*deadlock* (verrous pris dans un ordre différent), *famine*. Ces bugs sont
non-déterministes, donc pénibles à reproduire.

**Sécurité**
L'isolation mémoire entre processus est appliquée par le matériel. Entre threads,
il n'y en a aucune : un thread compromis lit toute la mémoire du processus.

## 5. Sous Linux : tout est une « task »

Le noyau ne fait pas de distinction fondamentale entre processus et thread : il
ordonnance des **tasks** (`struct task_struct`). La différence tient uniquement
aux *flags* passés à l'appel système `clone(2)`.

```
fork()            -> clone() sans partage       -> nouveau processus
pthread_create()  -> clone(CLONE_VM | CLONE_FILES | CLONE_SIGHAND | CLONE_THREAD)
                                                 -> thread du même processus
```

`CLONE_VM` = partager l'espace d'adressage. C'est *le* flag qui fait le thread.

Vocabulaire noyau : le `PID` renvoyé par `getpid()` est en réalité le **TGID**
(thread group ID) ; chaque thread a en plus son propre `TID` (`gettid()`).

```bash
# Threads d'un processus, colonne LWP = TID
ps -eLf | head
ps -o pid,tid,comm -L -p <PID>

# Nombre de threads
cat /proc/<PID>/status | grep Threads
ls /proc/<PID>/task/          # un répertoire par thread

# Vue interactive : touche H dans top affiche les threads
top -H -p <PID>
htop                          # F2 > Display options > show custom thread names
```

## 6. Exemples

### fork() — deux processus

```c
#include <stdio.h>
#include <unistd.h>

int x = 0;

int main(void) {
    pid_t pid = fork();
    if (pid == 0) {
        x = 42;                                  // copie du fils uniquement
        printf("fils  : x=%d pid=%d\n", x, getpid());
    } else {
        sleep(1);
        printf("père  : x=%d pid=%d\n", x, getpid());  // x vaut toujours 0
    }
    return 0;
}
```

### pthread — deux threads

```c
#include <stdio.h>
#include <pthread.h>

int x = 0;

void *worker(void *arg) {
    x = 42;                    // visible par le thread principal
    return NULL;
}

int main(void) {
    pthread_t t;
    pthread_create(&t, NULL, worker, NULL);
    pthread_join(t, NULL);
    printf("x=%d\n", x);       // affiche 42
    return 0;
}
```

```bash
gcc -pthread prog.c -o prog
```

### Compteur non protégé : la race condition

```c
for (int i = 0; i < 1000000; i++) counter++;   // FAUX avec 2 threads
```

`counter++` n'est pas atomique : c'est *lire → incrémenter → écrire*. Deux
threads peuvent lire la même valeur et en perdre une. Correctif : `pthread_mutex_lock`
autour de l'incrément, ou un type atomique (`_Atomic int`, `atomic_fetch_add`).

### Python : le cas particulier du GIL

```python
import threading, multiprocessing
```

En CPython « classique », le **GIL** (Global Interpreter Lock) empêche deux
threads d'exécuter du bytecode Python en même temps :
- calcul pur (CPU-bound) → les threads n'accélèrent rien, utiliser
  `multiprocessing` (vrais processus) ;
- attente réseau ou disque (I/O-bound) → les threads fonctionnent très bien,
  le GIL est relâché pendant l'attente.

(Depuis Python 3.13 il existe un build *free-threaded* sans GIL, encore optionnel.)

## 7. Quand choisir quoi

**Threads** quand :
- les tâches doivent partager beaucoup de données (serveur web, rendu, jeu) ;
- on veut du parallélisme fin et peu coûteux ;
- on maîtrise la synchronisation.

**Processus** quand :
- on a besoin d'isolation ou de tolérance aux pannes (un crash ne doit pas tout
  emporter) ;
- les composants ont des privilèges différents (séparation de privilèges) ;
- le code n'est pas thread-safe (bibliothèques anciennes, GIL Python) ;
- les parties sont naturellement indépendantes (architecture type nginx, Chrome).

**Ni l'un ni l'autre** : pour de l'I/O massivement concurrent, l'**asynchrone**
(`epoll`, `async/await`, boucle d'événements) évite le coût des deux — un seul
thread gère des milliers de connexions.

## 8. À retenir

- Processus = **espace mémoire isolé** ; thread = **flot d'exécution partageant
  cette mémoire**.
- Un thread possède en propre : **pile + registres**. Le reste est partagé.
- Threads : rapides et communicants, mais fragiles (un crash tue tout) et sujets
  aux races.
- Processus : robustes et isolés, mais création et communication plus coûteuses.
- Sous Linux les deux sont des `task_struct` ; c'est `clone(CLONE_VM|CLONE_THREAD)`
  qui fait la différence.
- Règle pratique : **partage de données → threads ; besoin d'isolation → processus ;
  beaucoup d'I/O → asynchrone**.
