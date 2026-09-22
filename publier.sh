#!/usr/bin/env bash
# Publie des notes : copie dans notes/, vérifie le build, commit et push.
# GitHub Actions (.github/workflows/deploy.yml) reconstruit et déploie sur
# Cloudflare Pages (projet « notes-perso ») à chaque push sur main (~1 min).
#
#   ./publier.sh ~/Downloads/ma-note.md [autre.md …]    ajoute / remplace des notes
#   ./publier.sh ~/Downloads/devsecops/                 ajoute / remplace un dossier de notes
#   ./publier.sh --supprimer ma-note.md [devsecops …]   retire des notes ou un dossier du site
#   ./publier.sh                                        publie les modifs déjà faites dans notes/
set -euo pipefail
cd "$(dirname "$0")"

noms=()
retrait=false

if [[ "${1:-}" == "--supprimer" ]]; then
  shift
  [[ $# -gt 0 ]] || { echo "Quoi supprimer ? ex. ./publier.sh --supprimer ma-note.md" >&2; exit 1; }
  retrait=true
  for cible in "$@"; do
    cible="${cible#notes/}"
    cible="${cible%/}"
    [[ -e "notes/$cible" ]] || { echo "Introuvable : notes/$cible" >&2; exit 1; }
    rm -r "notes/$cible"
    echo "- notes/$cible"
    noms+=("$(basename "$cible" .md)")
    # Une autre note pointait-elle vers celle-ci ? Le lien resterait mort sur le site.
    if refs=$(grep -rlF "$(basename "$cible")" notes --include='*.md' 2>/dev/null); then
      echo "  ⚠ encore cité dans :" $refs
    fi
  done
else
  for src in "$@"; do
    src="${src%/}"
    if [[ -d "$src" ]]; then
      nom="$(basename "$src")"
      n=$(find "$src" -name '*.md' | wc -l)
      [[ $n -gt 0 ]] || { echo "Aucun .md dans : $src" >&2; exit 1; }
      mkdir -p "notes/$nom"
      cp -r "$src"/. "notes/$nom"/
      echo "+ notes/$nom/ ($n notes)"
      noms+=("$nom ($n notes)")
    elif [[ "$src" == *.md && -f "$src" ]]; then
      cp "$src" notes/
      echo "+ notes/$(basename "$src")"
      noms+=("$(basename "$src" .md)")
    else
      echo "Ni un .md ni un dossier : $src" >&2
      exit 1
    fi
  done
fi

# Vérification locale : on ne pousse pas une note qui casse le build
if [[ -x .venv/bin/python ]]; then
  .venv/bin/python build.py
fi

git add notes          # prend aussi en compte les fichiers supprimés
if git diff --cached --quiet; then
  echo "Rien de nouveau à publier."
  exit 0
fi

if [[ ${#noms[@]} -gt 0 ]]; then
  liste=$(printf '%s\n' "${noms[@]}" | paste -sd ',' | sed 's/,/, /g')
  if $retrait; then msg="notes: retrait de $liste"; else msg="notes: $liste"; fi
else
  msg="notes: mise à jour"
fi
git commit -q -m "$msg"
git push -q
echo "Poussé : « $msg ». GitHub Actions publie le site : https://notes-perso.pages.dev/"
