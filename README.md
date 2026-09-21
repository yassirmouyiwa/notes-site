# notes-site

Des notes en Markdown, un site statique en ligne.

```
notes/ma-note.md  ──git push──▶  GitHub Actions lance build.py  ──▶  https://notes-perso.pages.dev
```

## Publier une note

```bash
./publier.sh ~/Downloads/ma-note.md
```

Le script copie le fichier dans `notes/`, vérifie que le site se construit, commit et
pousse. En ligne une minute plus tard.

À la main, c'est pareil : déposer le `.md` dans `notes/`, puis `git add`, `commit`, `push`.

## Écrire une note

Un `.md` ordinaire suffit. Le site en déduit tout seul :

| | d'où ça vient |
|---|---|
| le titre | le premier `# Titre` |
| le résumé en page d'accueil | le premier paragraphe, ou la première citation `>` |
| l'adresse | le chemin du fichier — `notes/xss-dom.md` → `/xss-dom`, `notes/devsecops/03-cicd.md` → `/devsecops/03-cicd` |
| la date | le dernier commit du fichier |
| le sommaire | les titres `##` et `###` |

Un en-tête optionnel force ces valeurs :

```markdown
---
title: Mon titre
date: 2026-09-19
tags: web, appsec
description: Une phrase de résumé.
draft: true
---
```

`draft: true` garde la note hors du site. Les fichiers commençant par `_` sont ignorés.

Pris en charge : tableaux, blocs de code colorés (` ```php `, ` ```js `, ` ```bash `…),
cases à cocher `- [ ]`, notes de bas de page `[^1]`, liens entre notes
(`[voir](autre-note.md)`), images (`![](img/capture.png)`, fichier dans `notes/img/`).

**Le HTML brut est affiché, jamais exécuté.** Un `<script>` écrit hors d'un bloc de code
reste du texte à l'écran — indispensable quand les notes contiennent des payloads.

## Aperçu local

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # une seule fois
.venv/bin/python build.py --serve                                    # http://localhost:8000
```

## Organisation

| Chemin | Rôle |
|---|---|
| `notes/` | les notes `.md` et leurs images ; les sous-dossiers deviennent des sous-adresses |
| `build.py` | le générateur : Markdown → HTML dans `dist/` |
| `public/` | copié tel quel à la racine du site : CSS, JS, favicon, `_headers` |
| `dist/` | le site généré — non versionné, envoyé tel quel à Cloudflare |

## Déploiement

À chaque push sur `main`, GitHub Actions installe `requirements.txt`, lance `build.py` et
envoie `dist/` au projet Cloudflare Pages **`notes-perso`**.

```bash
gh run list --repo yassirmouyiwa/notes-site --limit 3        # ça a marché ?
gh workflow run deploy.yml --repo yassirmouyiwa/notes-site   # republier sans rien changer
```

Secrets du dépôt : `CLOUDFLARE_API_TOKEN` (portée *Cloudflare Pages — Edit*) et
`CLOUDFLARE_ACCOUNT_ID`. Aucun identifiant Cloudflare n'est stocké sur la machine : pour
publier depuis un poste, créer un jeton et lancer
`wrangler pages deploy dist --project-name=notes-perso --branch=main`.
