<#
=====================================================================
  verifier_sante.ps1 — Controle de sante PostgreSQL (Windows)
  Formation DBA PostgreSQL — equivalent PowerShell de verifier_sante.sh

  Codes de sortie (convention Nagios/Icinga) :
     0 = OK        1 = WARNING        2 = CRITICAL        3 = UNKNOWN

  Prerequis : psql.exe dans le PATH (voir lab-windows.md), et un mot de
  passe fourni via la variable d'environnement PGPASSWORD ou le fichier
  %APPDATA%\postgresql\pgpass.conf.

  Exemple :
     $env:PGPASSWORD = "..." ; .\verifier_sante.ps1
  Planificateur de taches : declencheur toutes les 5 min, action
     powershell.exe -File C:\chemin\verifier_sante.ps1
  NOTE : script non execute dans l'environnement de preparation (pas de
  Windows sous la main) ; teste-le sur ton poste avant mise en production.
=====================================================================
#>

# --------- Configuration (seuils, surchargeables par l'environnement) ---
$PGHOST     = if ($env:PGHOST)     { $env:PGHOST }     else { "127.0.0.1" }
$PGPORT     = if ($env:PGPORT)     { $env:PGPORT }     else { "5432" }
$PGUSER     = if ($env:PGUSER)     { $env:PGUSER }     else { "postgres" }
$PGDATABASE = if ($env:PGDATABASE) { $env:PGDATABASE } else { "postgres" }
$env:PGCONNECT_TIMEOUT = "5"

$ConnWarn  = 70          # % de connexions
$ConnCrit  = 85
$IdleTxWarn = 300        # secondes idle in transaction
$ReplWarnMo = 100        # retard de rejeu replication (Mo)
$ReplCritMo = 1024
$XidWarn   = 300000000   # age des XID
$XidCrit   = 800000000

# --------- Agregation du statut ----------------------------------------
$Statut   = 0            # 0 OK, 1 WARN, 2 CRIT
$Messages = @()

function Ajuste([int]$niveau, [string]$message) {
    if ($niveau -gt $script:Statut) { $script:Statut = $niveau }
    $script:Messages += $message
}

function Pgq([string]$sql) {
    # Execute une requete et renvoie une valeur scalaire (chaine)
    $res = & psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -Atqc $sql 2>$null
    return ($res | Select-Object -First 1)
}

# --------- 1. Accessibilite --------------------------------------------
& pg_isready -h $PGHOST -p $PGPORT -q
if ($LASTEXITCODE -ne 0) {
    Write-Output "CRITICAL - instance injoignable ($PGHOST`:$PGPORT)"
    exit 2
}

# --------- 2. Ratio de connexions --------------------------------------
$pctConn = Pgq "SELECT round(100.0 * count(*) / current_setting('max_connections')::int) FROM pg_stat_activity"
if ($pctConn) {
    $pctConn = [int]$pctConn
    if     ($pctConn -ge $ConnCrit) { Ajuste 2 "connexions $pctConn% (>= $ConnCrit%)" }
    elseif ($pctConn -ge $ConnWarn) { Ajuste 1 "connexions $pctConn% (>= $ConnWarn%)" }
}

# --------- 3. Sessions bloquees par un verrou --------------------------
$nbBloquees = Pgq "SELECT count(*) FROM pg_stat_activity WHERE cardinality(pg_blocking_pids(pid)) > 0"
if ($nbBloquees -and [int]$nbBloquees -gt 0) {
    Ajuste 1 "$nbBloquees session(s) en attente de verrou"
}

# --------- 4. Idle in transaction longues ------------------------------
$nbIdleTx = Pgq "SELECT count(*) FROM pg_stat_activity WHERE state = 'idle in transaction' AND now() - state_change > interval '$IdleTxWarn seconds'"
if ($nbIdleTx -and [int]$nbIdleTx -gt 0) {
    Ajuste 1 "$nbIdleTx session(s) idle in transaction > ${IdleTxWarn}s"
}

# --------- 5. Retard de replication (sur le primaire) ------------------
$enRecovery = Pgq "SELECT pg_is_in_recovery()"
if ($enRecovery -eq "f") {
    $nbRepl = Pgq "SELECT count(*) FROM pg_stat_replication"
    if ($nbRepl -and [int]$nbRepl -gt 0) {
        $retardMo = Pgq "SELECT coalesce(max(round(pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) / 1048576.0)), 0)::bigint FROM pg_stat_replication"
        if ($retardMo) {
            $retardMo = [int64]$retardMo
            if     ($retardMo -ge $ReplCritMo) { Ajuste 2 "replication en retard de $retardMo Mo" }
            elseif ($retardMo -ge $ReplWarnMo) { Ajuste 1 "replication en retard de $retardMo Mo" }
        }
    }
}

# --------- 6. Age des XID (wraparound) ---------------------------------
$xidMax = Pgq "SELECT max(age(datfrozenxid)) FROM pg_database"
if ($xidMax) {
    $xidMax = [int64]$xidMax
    if     ($xidMax -ge $XidCrit) { Ajuste 2 "age XID $xidMax (>= $XidCrit) : wraparound imminent" }
    elseif ($xidMax -ge $XidWarn) { Ajuste 1 "age XID $xidMax (>= $XidWarn)" }
}

# --------- 7. Echec d'archivage WAL ------------------------------------
$archMode = Pgq "SELECT current_setting('archive_mode')"
if ($archMode -eq "on" -or $archMode -eq "always") {
    $echecs = Pgq "SELECT CASE WHEN last_failed_time IS NULL THEN 0 WHEN last_archived_time IS NULL THEN failed_count WHEN last_failed_time > last_archived_time THEN 1 ELSE 0 END FROM pg_stat_archiver"
    if ($echecs -and [int]$echecs -gt 0) {
        Ajuste 2 "echec d'archivage WAL recent"
    }
}

# --------- Restitution -------------------------------------------------
switch ($Statut) {
    0 { Write-Output "OK - PostgreSQL en bonne sante (connexions $pctConn%)" }
    1 { Write-Output ("WARNING - " + ($Messages -join "; ")) }
    2 { Write-Output ("CRITICAL - " + ($Messages -join "; ")) }
}
exit $Statut
