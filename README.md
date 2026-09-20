# notes-site

Mes notes en Markdown, publiées automatiquement en site statique.

```
notes/ma-note.md  ──git push──▶  GitHub Actions lance build.py  ──wrangler──▶  Cloudflare Pages
```

## Publier une note

```bash
./publier.sh ~/Downloads/ma-note.md
```

Le script copie le fichier dans `notes/`, vérifie que le site se construit, commit et push.
GitHub Actions reconstruit et publie le site en une minute environ.

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

## Publication

Le site est déployé par **GitHub Actions** (`.github/workflows/deploy.yml`) : à chaque push sur
`main`, le workflow installe `requirements.txt`, lance `build.py` et envoie `dist/` au projet
Pages **`notes-perso`** → https://notes-perso.pages.dev/

Secrets du dépôt (déjà configurés) : `CLOUDFLARE_API_TOKEN` (portée *Cloudflare Pages — Edit*)
et `CLOUDFLARE_ACCOUNT_ID`.

⚠️ Pourquoi pas la build automatique de Cloudflare ? Elle est pourtant configurée sur
`notes-perso` (preset None, `pip install -r requirements.txt && python build.py`, sortie `dist`),
mais **les webhooks GitHub → Cloudflare n'arrivent plus sur ce compte** : aucun push ne
déclenche de build, ni ici ni sur le blog (resté figé du 15/09 au 20/09 sans que ça se voie).
Si l'intégration est réparée un jour, il suffira de supprimer le workflow.

Relancer une publication sans rien modifier (par exemple après un échec) :

```bash
gh workflow run deploy.yml --repo yassirmouyiwa/notes-site
gh run list --repo yassirmouyiwa/notes-site --limit 3
```

Aucun identifiant Cloudflare n'est stocké sur la machine : seuls les secrets du dépôt servent
au déploiement. Pour publier depuis un poste, il faut créer un jeton *Cloudflare Pages — Edit*
et lancer `wrangler pages deploy dist --project-name=notes-perso --branch=main`.
