# notes-site

Mes notes en Markdown, publiées automatiquement en site statique.

```
notes/ma-note.md  ──./publier.sh──▶  build.py ──▶  dist/  ──wrangler──▶  Cloudflare Pages
                                    └──▶  git push (archivage des sources)
```

## Publier une note

```bash
./publier.sh ~/Downloads/ma-note.md
```

Le script copie le fichier dans `notes/`, construit le site, archive les sources dans Git,
puis envoie `dist/` à Cloudflare (~10 s au total).

⚠️ Le push GitHub **ne publie rien** : le projet Pages « notes-site » est en upload direct, il
n'est pas relié au dépôt. C'est `wrangler` qui met le site en ligne. Publier à la main :

```bash
cp ma-note.md notes/ && .venv/bin/python build.py
wrangler pages deploy dist --project-name=notes-site --branch=main
```

## Écrire une note

Un fichier `.md` normal suffit. Le site en tire tout seul :

- **le titre** : le premier `# Titre` du fichier ;
- **le résumé** (page d'accueil) : le premier paragraphe ou la première citation `>` ;
- **l'adresse** : le nom du fichier (`notes/xss-dom.md` → `/xss-dom`) ;
- **la date** : celle du dernier commit du fichier ;
- **le sommaire** : les titres `##` et `###`.

Un en-tête optionnel en haut du fichier force ces valeurs :

```markdown
---
title: Mon titre
date: 2026-09-19
tags: web, appsec
description: Une phrase de résumé.
draft: true
---
```

`draft: true` garde la note hors du site. Les fichiers qui commencent par `_` sont ignorés.

Ce qui est pris en charge : tableaux, blocs de code colorés (` ```php `, ` ```js `, ` ```bash `…),
cases à cocher `- [ ]`, notes de bas de page `[^1]`, liens entre notes (`[voir](autre-note.md)`),
images (`![](img/capture.png)` avec l'image placée dans `notes/img/`).

Le HTML brut écrit dans une note est **affiché, jamais exécuté**. Un payload `<script>` écrit
hors d'un bloc de code reste donc du texte.

## Aperçu local

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # une seule fois
.venv/bin/python build.py --serve                                    # http://localhost:8000
```

## Organisation

| Chemin | Rôle |
|---|---|
| `notes/` | les notes `.md` (et leurs images) |
| `build.py` | le générateur : Markdown → HTML dans `dist/` |
| `public/` | copié tel quel dans le site : CSS, JS, favicon, `_headers` (en-têtes de sécurité) |
| `dist/` | le site généré (non versionné, envoyé tel quel à Cloudflare) |

## Configuration Cloudflare Pages

Projet `notes-site` → https://notes-site-a6b.pages.dev/ — **upload direct**, pas de build côté
Cloudflare. La mise en ligne se fait depuis cette machine :

```bash
wrangler pages deploy dist --project-name=notes-site --branch=main   # fait par ./publier.sh
```

Node est installé sans root dans `~/.local/opt/node` (ajouté au PATH par `~/.bashrc.d/node.sh`),
wrangler dans `~/.local/bin`. Les identifiants OAuth sont dans `~/.config/.wrangler/`.

Pour repasser à une build automatique côté Cloudflare (dashboard → Settings → Builds &
deployments → Connect to Git), les réglages seraient :

| Réglage | Valeur |
|---|---|
| Framework preset | None |
| Build command | `pip install -r requirements.txt && python build.py` |
| Build output directory | `dist` |
| Production branch | `main` |
