#!/usr/bin/env bash
# =====================================================================
#  verifier_sante.sh — Contrôle de santé d'une instance PostgreSQL
#  Formation DBA PostgreSQL
#
#  Codes de sortie (convention Nagios/Icinga) :
#     0 = OK        1 = WARNING        2 = CRITICAL        3 = UNKNOWN
#
#  Contrôles : accessibilité, ratio de connexions, sessions bloquées,
#  idle in transaction, retard de réplication, âge des XID, archivage WAL.
#
#  Usage : verifier_sante.sh
#  Variables d'environnement : PGHOST PGPORT PGUSER PGDATABASE et les seuils.
#  Cron : */5 * * * * /usr/local/bin/verifier_sante.sh || echo ALERTE | mail ...
# =====================================================================

set -uo pipefail

# --------- Configuration (seuils) ------------------------------------
export PGHOST="${PGHOST:-/var/run/postgresql}"
export PGPORT="${PGPORT:-5432}"
export PGUSER="${PGUSER:-postgres}"
export PGDATABASE="${PGDATABASE:-postgres}"
export PGCONNECT_TIMEOUT=5

CONN_WARN="${CONN_WARN:-70}"          # % de connexions
CONN_CRIT="${CONN_CRIT:-85}"
IDLE_TX_WARN="${IDLE_TX_WARN:-300}"   # secondes idle in transaction
REPL_WARN_MO="${REPL_WARN_MO:-100}"   # retard de rejeu réplication (Mo)
REPL_CRIT_MO="${REPL_CRIT_MO:-1024}"
XID_WARN="${XID_WARN:-300000000}"     # âge des XID
XID_CRIT="${XID_CRIT:-800000000}"

# --------- Agrégation du statut --------------------------------------
STATUT=0            # 0 OK, 1 WARN, 2 CRIT
MESSAGES=()

ajuste() {  # $1 = niveau (1 ou 2), $2 = message
    (( $1 > STATUT )) && STATUT=$1
    MESSAGES+=("$2")
}

pgq() {     # exécute une requête et renvoie une valeur scalaire
    psql -Atqc "$1" 2>/dev/null
}

# --------- 1. Accessibilité ------------------------------------------
if ! pg_isready -q; then
    echo "CRITICAL - instance injoignable (${PGHOST}:${PGPORT})"
    exit 2
fi

# --------- 2. Ratio de connexions ------------------------------------
PCT_CONN="$(pgq "SELECT round(100.0 * count(*) / current_setting('max_connections')::int) FROM pg_stat_activity")"
if [[ -n "${PCT_CONN}" ]]; then
    if   (( PCT_CONN >= CONN_CRIT )); then ajuste 2 "connexions ${PCT_CONN}% (>= ${CONN_CRIT}%)"
    elif (( PCT_CONN >= CONN_WARN )); then ajuste 1 "connexions ${PCT_CONN}% (>= ${CONN_WARN}%)"
    fi
fi

# --------- 3. Sessions bloquées par un verrou ------------------------
NB_BLOQUEES="$(pgq "SELECT count(*) FROM pg_stat_activity WHERE cardinality(pg_blocking_pids(pid)) > 0")"
if [[ -n "${NB_BLOQUEES}" ]] && (( NB_BLOQUEES > 0 )); then
    ajuste 1 "${NB_BLOQUEES} session(s) en attente de verrou"
fi

# --------- 4. Idle in transaction longues ----------------------------
NB_IDLE_TX="$(pgq "SELECT count(*) FROM pg_stat_activity
                   WHERE state = 'idle in transaction'
                     AND now() - state_change > interval '${IDLE_TX_WARN} seconds'")"
if [[ -n "${NB_IDLE_TX}" ]] && (( NB_IDLE_TX > 0 )); then
    ajuste 1 "${NB_IDLE_TX} session(s) idle in transaction > ${IDLE_TX_WARN}s"
fi

# --------- 5. Retard de réplication (sur le primaire) ----------------
EN_RECOVERY="$(pgq "SELECT pg_is_in_recovery()")"
if [[ "${EN_RECOVERY}" == "f" ]]; then
    RETARD_MO="$(pgq "SELECT coalesce(max(
                        round(pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) / 1048576.0)
                      ), 0)::bigint FROM pg_stat_replication")"
    NB_REPL="$(pgq "SELECT count(*) FROM pg_stat_replication")"
    if [[ -n "${RETARD_MO}" ]] && (( NB_REPL > 0 )); then
        if   (( RETARD_MO >= REPL_CRIT_MO )); then ajuste 2 "réplication en retard de ${RETARD_MO} Mo"
        elif (( RETARD_MO >= REPL_WARN_MO )); then ajuste 1 "réplication en retard de ${RETARD_MO} Mo"
        fi
    fi
fi

# --------- 6. Âge des XID (wraparound) -------------------------------
XID_MAX="$(pgq "SELECT max(age(datfrozenxid)) FROM pg_database")"
if [[ -n "${XID_MAX}" ]]; then
    if   (( XID_MAX >= XID_CRIT )); then ajuste 2 "âge XID ${XID_MAX} (>= ${XID_CRIT}) : wraparound imminent"
    elif (( XID_MAX >= XID_WARN )); then ajuste 1 "âge XID ${XID_MAX} (>= ${XID_WARN})"
    fi
fi

# --------- 7. Échec d'archivage WAL ----------------------------------
ARCH_MODE="$(pgq "SELECT current_setting('archive_mode')")"
if [[ "${ARCH_MODE}" == "on" || "${ARCH_MODE}" == "always" ]]; then
    ECHECS_RECENTS="$(pgq "SELECT CASE
        WHEN last_failed_time IS NULL THEN 0
        WHEN last_archived_time IS NULL THEN failed_count
        WHEN last_failed_time > last_archived_time THEN 1 ELSE 0 END
        FROM pg_stat_archiver")"
    if [[ -n "${ECHECS_RECENTS}" ]] && (( ECHECS_RECENTS > 0 )); then
        ajuste 2 "échec d'archivage WAL récent"
    fi
fi

# --------- Restitution -----------------------------------------------
case "${STATUT}" in
    0) echo "OK - PostgreSQL en bonne santé (connexions ${PCT_CONN:-?}%)" ;;
    1) echo "WARNING - $(IFS='; '; echo "${MESSAGES[*]}")" ;;
    2) echo "CRITICAL - $(IFS='; '; echo "${MESSAGES[*]}")" ;;
esac
exit "${STATUT}"
