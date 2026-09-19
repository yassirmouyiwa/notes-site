#!/usr/bin/env bash
# Publie des notes : copie les .md dans notes/, vérifie le build, commit et push.
# Cloudflare Pages détecte le push et met le site en ligne (~1 min).
#
#   ./publier.sh ~/Downloads/ma-note.md [autre.md …]   ajoute / remplace des notes
#   ./publier.sh                                       publie les modifs déjà faites dans notes/
set -euo pipefail
cd "$(dirname "$0")"

for f in "$@"; do
  [[ "$f" == *.md && -f "$f" ]] || { echo "Pas un fichier .md : $f" >&2; exit 1; }
  cp "$f" notes/
  echo "+ notes/$(basename "$f")"
done

# Vérification locale : on ne pousse pas une note qui casse le build
if [[ -x .venv/bin/python ]]; then
  .venv/bin/python build.py
fi

git add notes
if git diff --cached --quiet; then
  echo "Rien de nouveau à publier."
  exit 0
fi

if [[ $# -gt 0 ]]; then
  msg="notes: $(for f in "$@"; do basename "$f" .md; done | paste -sd ',' | sed 's/,/, /g')"
else
  msg="notes: mise à jour"
fi
git commit -q -m "$msg"
git push -q
echo "Poussé : « $msg ». Cloudflare Pages construit le site."
