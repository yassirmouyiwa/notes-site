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

Lier la bibliothèque logique `work` au dossier physique `work`. Cette commande crée ou met à jour le fichier `modelsim.ini` :

```tcl
vmap work work
```

---

### 5. Compiler les fichiers .vhd

```tcl
vcom -2008 fichier.vhd
vcom -2008 fichier_tb.vhd
```

> **L'ordre compte** : compiler d'abord les entités/composants de bas niveau, puis le design, puis le testbench en dernier.
> On peut aussi tout compiler en une seule ligne : `vcom -2008 fichier.vhd fichier_tb.vhd`

---

### 6. Charger la simulation

```tcl
vsim work.nom_de_l_entite
```

- **avec testbench** : charger l'entité du **testbench** (ex. `vsim work.fichier_tb`)
- **sans testbench** : charger directement l'entité du design

> Pour voir les signaux **internes** (optimisation activée par défaut dans 10.1d) :
> `vsim -voptargs=+acc work.nom_de_l_entite`  (ou `vsim -novopt ...`)

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
add wave *                        ;# tous les signaux du niveau courant
add wave -r /*                    ;# tous les signaux, récursivement
add wave -radix hex /nom_entite/bus   ;# affichage en hexadécimal (binary, unsigned, decimal...)
```

> Avec un testbench, le chemin commence par le nom du testbench, puis le nom de l'instance :
> `/fichier_tb/uut/signal`

---

### 8. Lancer la simulation

**Avec testbench**

```tcl
run -all
```

> `run -all` ne s'arrête que si le testbench termine la simulation : un `wait;` final dans le process de stimuli, ou en VHDL-2008 `std.env.stop;` (ou `finish`). Sans cela et avec une horloge libre, la simulation tourne à l'infini.

**Sans testbench** (voir section 10)

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

> `restart -f` recharge le design recompilé en conservant les signaux de la fenêtre Wave.
> Si des ports ou l'entité ont changé, faire `quit -sim` puis refaire `vsim`.

---

### 10. Simulation sans testbench (commandes `force`)

On impose les entrées directement depuis la console :

```tcl
vsim work.nom_de_l_entite
view wave
add wave *

# valeurs fixes
force a 0
force b 1
run 20 ns

force a 1
run 20 ns

# séquence temporelle en une commande : valeur temps, valeur temps...
force b 0 0, 1 10 ns -repeat 20 ns
run 100 ns

# horloge : 0 à t=0, 1 à t=5 ns, période 10 ns
force clk 0 0, 1 5 ns -repeat 10 ns

# bus / vecteur
force data 16#A5
force data "10100101"

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
vsim -voptargs=+acc work.fichier_tb
view wave
add wave -r /*
run -all
```

Puis lancer dans ModelSim :

```tcl
do sim.do
```

---

### Commandes utiles

| Commande        | Rôle                                   |
|-----------------|----------------------------------------|
| `quit -sim`     | Fermer la simulation en cours          |
| `wave zoom full`| Ajuster le zoom à toute la simulation  |
| `vdel -all`     | Vider la bibliothèque work             |
| `pwd`           | Afficher le dossier courant            |
