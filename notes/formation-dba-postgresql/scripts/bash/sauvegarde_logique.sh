#!/usr/bin/env bash
# =====================================================================
#  sauvegarde_logique.sh — Sauvegarde logique chiffrée avec rotation
#  Formation DBA PostgreSQL
#
#  - pg_dump au format custom (-Fc), compressé
#  - chiffrement GPG asymétrique (clé publique du destinataire)
#  - rétention configurable, vérification, journalisation
#
#  Usage : sauvegarde_logique.sh <base> [repertoire]
#  Prérequis : rôle de sauvegarde dans ~/.pgpass, clé publique GPG importée
#  Planification cron (compte postgres) :
#     30 1 * * * /usr/local/bin/sauvegarde_logique.sh banque >> /var/log/postgresql/sauvegarde.log 2>&1
# =====================================================================

set -euo pipefail

# --------- Paramètres (adapter à l'environnement) --------------------
BASE="${1:-banque}"
REP_SAUV="${2:-/var/lib/postgresql/sauvegardes}"
RETENTION_JOURS="${RETENTION_JOURS:-14}"
GPG_DEST="${GPG_DEST:-dba@cliniquenord.ma}"   # destinataire de la clé publique GPG
# PGHOST : 127.0.0.1 exige un mot de passe (via ~/.pgpass) selon pg_hba.conf ;
# pour une auth 'peer' locale sans mot de passe, utiliser la socket : PGHOST=/var/run/postgresql
PGHOST="${PGHOST:-127.0.0.1}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"

HORODATAGE="$(date +%Y%m%d_%H%M%S)"
PREFIXE="${REP_SAUV}/${BASE}_${HORODATAGE}"
FICHIER_DUMP="${PREFIXE}.dump"
FICHIER_CHIFFRE="${FICHIER_DUMP}.gpg"

# --------- Fonctions utilitaires -------------------------------------
log()  { echo "$(date '+%Y-%m-%d %H:%M:%S') [$1] ${*:2}"; }
info() { log INFO "$@"; }
err()  { log ERREUR "$@" >&2; }

nettoyage_erreur() {
    err "Échec de la sauvegarde ; nettoyage des fichiers partiels."
    rm -f "${FICHIER_DUMP}" "${FICHIER_CHIFFRE}"
    exit 1
}
trap nettoyage_erreur ERR

# --------- Vérifications préalables -----------------------------------
command -v pg_dump >/dev/null || { err "pg_dump introuvable dans le PATH."; exit 1; }
command -v gpg     >/dev/null || { err "gpg introuvable ; installer gnupg."; exit 1; }
mkdir -p "${REP_SAUV}"
chmod 700 "${REP_SAUV}"

if ! gpg --list-keys "${GPG_DEST}" >/dev/null 2>&1; then
    err "Clé publique GPG absente pour ${GPG_DEST}. Importer avec : gpg --import cle_publique.asc"
    exit 1
fi

# --------- Sauvegarde -------------------------------------------------
info "Début de la sauvegarde de la base '${BASE}' vers ${FICHIER_CHIFFRE}"

# 1) Dump au format custom (compressé, restauration sélective possible)
pg_dump -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" \
        -Fc --no-password -d "${BASE}" -f "${FICHIER_DUMP}"
TAILLE_DUMP="$(du -h "${FICHIER_DUMP}" | cut -f1)"
info "Dump créé (${TAILLE_DUMP})."

# 2) Chiffrement asymétrique : seule la clé PRIVÉE du destinataire déchiffrera
gpg --batch --yes --trust-model always \
    --encrypt --recipient "${GPG_DEST}" \
    --output "${FICHIER_CHIFFRE}" "${FICHIER_DUMP}"
info "Chiffrement GPG effectué pour ${GPG_DEST}."

# 3) Suppression du dump en clair
shred -u "${FICHIER_DUMP}" 2>/dev/null || rm -f "${FICHIER_DUMP}"
info "Dump en clair supprimé."

# 4) Vérification d'intégrité du fichier chiffré (déchiffrement structurel)
if gpg --list-packets "${FICHIER_CHIFFRE}" >/dev/null 2>&1; then
    info "Fichier chiffré vérifié (structure GPG valide)."
else
    err "Le fichier chiffré semble corrompu."
    exit 1
fi

TAILLE_FINALE="$(du -h "${FICHIER_CHIFFRE}" | cut -f1)"
info "Sauvegarde terminée : ${FICHIER_CHIFFRE} (${TAILLE_FINALE})."

# --------- Rotation ---------------------------------------------------
info "Application de la rétention (${RETENTION_JOURS} jours)."
NB_SUPPR="$(find "${REP_SAUV}" -name "${BASE}_*.dump.gpg" -type f -mtime "+${RETENTION_JOURS}" -print | wc -l)"
find "${REP_SAUV}" -name "${BASE}_*.dump.gpg" -type f -mtime "+${RETENTION_JOURS}" -delete
info "${NB_SUPPR} ancienne(s) sauvegarde(s) supprimée(s)."

# --------- Inventaire -------------------------------------------------
NB_TOTAL="$(find "${REP_SAUV}" -name "${BASE}_*.dump.gpg" -type f | wc -l)"
info "Inventaire : ${NB_TOTAL} sauvegarde(s) conservée(s) pour '${BASE}'."

trap - ERR
info "Succès."
exit 0

# =====================================================================
#  RESTAURATION (mémo — à exécuter manuellement) :
#    gpg --decrypt banque_YYYYMMDD_HHMMSS.dump.gpg > restauré.dump
#    createdb banque_restore
#    pg_restore -d banque_restore --clean --if-exists restauré.dump
#  Puis vérifier, et supprimer le fichier déchiffré (shred -u).
# =====================================================================
