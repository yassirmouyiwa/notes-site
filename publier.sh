#!/usr/bin/env bash
# Publie des notes : copie les .md dans notes/, construit dist/, commit + push,
# puis envoie dist/ à Cloudflare Pages.
#
#   ./publier.sh ~/Downloads/ma-note.md [autre.md …]   ajoute / remplace des notes
#   ./publier.sh                                       publie les modifs déjà faites dans notes/
#
# Le projet Pages « notes-site » est en upload direct (pas relié à GitHub) : c'est ce
# script qui met le site en ligne, le push ne sert qu'à archiver les sources.
set -euo pipefail
cd "$(dirname "$0")"

PROJET=notes-site
export PATH="$HOME/.local/opt/node/bin:$PATH"   # Node installé sans root
WRANGLER=${WRANGLER:-$HOME/.local/bin/wrangler}

for f in "$@"; do
  [[ "$f" == *.md && -f "$f" ]] || { echo "Pas un fichier .md : $f" >&2; exit 1; }
  cp "$f" notes/
  echo "+ notes/$(basename "$f")"
done

# Construction locale : on ne publie pas une note qui casse le build
[[ -x .venv/bin/python ]] || { echo "Venv manquant : python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2; exit 1; }
.venv/bin/python build.py

# Archivage des sources dans Git (sans conséquence sur la mise en ligne)
git add notes
if git diff --cached --quiet; then
  echo "Aucune source modifiée ; le site va quand même être redéployé."
else
  if [[ $# -gt 0 ]]; then
    msg="notes: $(for f in "$@"; do basename "$f" .md; done | paste -sd ',' | sed 's/,/, /g')"
  else
    msg="notes: mise à jour"
  fi
  git commit -q -m "$msg"
  git push -q
  echo "Poussé sur GitHub : « $msg »."
fi

# Mise en ligne
if [[ ! -x "$WRANGLER" ]]; then
  echo "wrangler introuvable ($WRANGLER) : le site n'a PAS été mis à jour." >&2
  echo "Installe-le (npm install -g wrangler) ou dépose dist/ dans le dashboard Cloudflare." >&2
  exit 1
fi
"$WRANGLER" pages deploy dist --project-name="$PROJET" --branch=main --commit-dirty=true
echo "En ligne : https://notes-site-a6b.pages.dev/"
