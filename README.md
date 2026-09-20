# notes-site

Mes notes en Markdown, publiées automatiquement en site statique.

```
notes/ma-note.md  ──git push──▶  GitHub  ──▶  Cloudflare Pages lance build.py  ──▶  site en ligne
```

## Publier une note

```bash
./publier.sh ~/Downloads/ma-note.md
```

Le script copie le fichier dans `notes/`, vérifie que le site se construit, commit et push.
Cloudflare détecte le push, relance `build.py` et met le site à jour en une minute environ.

Équivalent à la main : déposer le `.md` dans `notes/`, puis `git add`, `git commit`, `git push`.

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

Projet **`notes-site-git`** → https://notes-site-git.pages.dev/ — relié à ce dépôt, Cloudflare
construit à chaque push sur `main`.

| Réglage | Valeur |
|---|---|
| Framework preset | None |
| Build command | `pip install -r requirements.txt && python build.py` |
| Build output directory | `dist` |
| Production branch | `main` |

L'ancien projet `notes-site` (→ `notes-site-a6b.pages.dev`) était en **upload direct** : un tel
projet ne peut pas être relié à Git après coup, d'où la création de `notes-site-git`.

Déploiement manuel possible en secours (wrangler est installé dans `~/.local/bin`, Node sans
root dans `~/.local/opt/node`) :

```bash
wrangler pages deploy dist --project-name=notes-site-git --branch=main
```
