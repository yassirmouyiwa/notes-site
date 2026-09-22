## Utilisation de ModelSim 10.1d [code → simulation]

### 1. Créer un dossier de projet

```pwsh
mkdir C:\Users\VHDL
```

---

### 2. Placer les fichiers .vhd dans le dossier **VHDL**

Fichiers de conception (design) **et** fichiers de testbench.

---

### 3. Se placer dans le dossier depuis la console ModelSim

```tcl
cd C:/Users/VHDL
```

> ModelSim accepte les `/` même sous Windows. Éviter les espaces et les accents dans les chemins.

---

### 4. Créer la bibliothèque de travail **work**

```tcl
vlib work
```

Lier la bibliothèque logique `work` au dossier physique `work` (crée ou met à jour `modelsim.ini`) :

```tcl
vmap work work
```

---

### 5. Compiler les fichiers .vhd

```tcl
vcom -2008 fichier.vhd
vcom -2008 fichier_tb.vhd
```

> **L'ordre compte** : composants de bas niveau → design → testbench en dernier.
> En une ligne : `vcom -2008 fichier.vhd fichier_tb.vhd`

---

### 6. Charger la simulation

```tcl
vsim -novopt work.nom_de_l_entite
```

- **avec testbench** : charger l'entité du **testbench** (ex. `vsim -novopt work.fichier_tb`)
- **sans testbench** : charger directement l'entité du design

#### Pourquoi `-novopt` ?

Dans ModelSim 10.1d, `vsim` lance par défaut l'**optimiseur `vopt`**, qui accélère la simulation mais peut **supprimer ou masquer les signaux internes** :
- `add wave` renvoie *"No objects found"*
- des signaux internes (dans `uut`) sont absents de la fenêtre Objects
- des courbes restent vides

| Option                  | Effet                                                    |
|-------------------------|----------------------------------------------------------|
| `-novopt`               | Désactive l'optimisation : tout est visible, un peu plus lent |
| `-voptargs=+acc`        | Garde l'optimisation mais conserve la visibilité (recommandé) |

> ⚠️ `-novopt` est **obsolète** dans les versions récentes (à partir de la 10.7 environ : warning, puis supprimé).
> `-voptargs=+acc` fonctionne partout.
> Pour désactiver l'optimisation par défaut : dans `modelsim.ini`, section `[vsim]`, mettre `VoptFlow = 0`.

---

### 7. Ajouter les signaux au chronogramme

```tcl
view wave
add wave -divider "Entrees"
add wave /nom_entite/a
add wave /nom_entite/b
add wave -divider "Sorties"
add wave /nom_entite/y
```

Raccourcis utiles :

```tcl
add wave *                            ;# signaux du niveau courant
add wave -r /*                        ;# tous les signaux, récursivement
add wave -radix hex /nom_entite/bus   ;# affichage : binary, hex, unsigned, decimal...
```

> Avec un testbench, le chemin passe par l'instance : `/fichier_tb/uut/signal`

---

### 8. Lancer la simulation

**Avec testbench**

```tcl
run -all
```

> `run -all` ne s'arrête que si le testbench termine la simulation : `wait;` final dans le process de stimuli, ou `std.env.stop;` / `std.env.finish;` en VHDL-2008.
> Sinon, avec une horloge libre, la simulation tourne à l'infini (bouton **Break** pour l'arrêter).

**Sans testbench** : durée explicite (voir section 10)

```tcl
run 100 ns
```

---

### 9. Modifier et relancer

```tcl
vcom -2008 fichier.vhd
restart -f
run -all
```

> `restart -f` recharge le design recompilé et conserve les signaux de la fenêtre Wave.
> Si les ports ou l'entité ont changé :
> ```tcl
> quit -sim
> vsim -novopt work.nom_de_l_entite
> ```

---

### 10. Simulation sans testbench : la commande `force`

#### Syntaxe générale

```tcl
force [option] <signal> <valeur> [<temps>] [, <valeur> <temps> ...] [-repeat <période>] [-cancel <temps>]
```

| Élément              | Signification                                                        |
|----------------------|----------------------------------------------------------------------|
| `<signal>`           | Nom ou chemin du signal (`a`, `/nom_entite/a`)                       |
| `<valeur>`           | Valeur à imposer (voir formats ci-dessous)                           |
| `<temps>`            | Instant d'application, **relatif** au temps courant (défaut : 0)     |
| `@<temps>`           | Temps **absolu** (ex. `@50 ns`)                                      |
| `,`                  | Sépare les couples `valeur temps` d'une séquence                     |
| `-repeat <période>`  | Répète la séquence avec cette période (horloges, motifs)             |
| `-cancel <temps>`    | Supprime le forçage après ce délai                                   |

#### Options de forçage

| Option      | Effet                                                                       |
|-------------|-----------------------------------------------------------------------------|
| `-freeze`   | (défaut sur les signaux) La valeur est bloquée et ne peut pas être modifiée par le design |
| `-drive`    | Agit comme un driver supplémentaire ; peut entrer en conflit (→ `X`)       |
| `-deposit`  | Dépose une valeur que le design peut écraser ensuite (initialisation)      |

#### Formats de valeurs

| Type             | Exemple                              |
|------------------|--------------------------------------|
| `std_logic`      | `0`, `1`, `Z`, `X`, `U`, `H`, `L`    |
| Vecteur binaire  | `"10100101"` ou `10100101`           |
| Hexadécimal      | `16#A5`                              |
| Décimal          | `10#165`                             |
| Entier           | `42`                                 |
| Booléen          | `true`, `false`                      |

#### Exemples

```tcl
vsim -novopt work.nom_de_l_entite
view wave
add wave *

# valeurs fixes, appliquées maintenant
force a 0
force b 1
run 20 ns

force a 1
run 20 ns

# séquence : 0 à t+0, 1 à t+10 ns, répétée toutes les 20 ns
force b 0 0, 1 10 ns -repeat 20 ns

# horloge de période 10 ns (0 à t=0, 1 à t=5 ns)
force clk 0 0, 1 5 ns -repeat 10 ns

# reset actif 30 ns puis relâché
force rst 1 0, 0 30 ns

# temps absolu
force a 1 @50 ns

# bus / vecteur
force data 16#A5
force data "10100101"

run 100 ns

# retirer un forçage
noforce a
```

> Pratique pour un test rapide, mais un **testbench** reste préférable (reproductible, auto-vérifiable avec `assert`).

---

### 11. Automatiser avec un script `.do`

Créer `sim.do` :

```tcl
vlib work
vmap work work
vcom -2008 fichier.vhd fichier_tb.vhd
vsim -novopt work.fichier_tb
view wave
add wave -r /*
run -all
wave zoom full
```

Puis dans ModelSim :

```tcl
do sim.do
```

---

### Commandes utiles

| Commande          | Rôle                                  |
|-------------------|---------------------------------------|
| `quit -sim`       | Fermer la simulation en cours         |
| `wave zoom full`  | Zoom sur toute la simulation          |
| `vdel -all`       | Vider la bibliothèque work            |
| `pwd`             | Afficher le dossier courant           |
| `noforce <sig>`   | Retirer un forçage                    |
