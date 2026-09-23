<#
=====================================================================
  sauvegarde_logique.ps1 — Sauvegarde logique chiffree (Windows)
  Formation DBA PostgreSQL — equivalent PowerShell de sauvegarde_logique.sh

  - pg_dump au format custom (-Fc), compresse
  - chiffrement GPG asymetrique (cle publique du destinataire)
  - retention configurable, verification, journalisation

  Prerequis :
    - psql.exe / pg_dump.exe dans le PATH (voir lab-windows.md)
    - Gpg4win installe (gpg.exe dans le PATH), cle publique importee
    - mot de passe via PGPASSWORD ou %APPDATA%\postgresql\pgpass.conf

  Usage :
    .\sauvegarde_logique.ps1 -Base banque -RepSauv "C:\pg_sauvegardes"
  Planificateur de taches (quotidien) :
    powershell.exe -File C:\chemin\sauvegarde_logique.ps1 -Base banque

  NOTE : script non execute dans l'environnement de preparation (pas de
  Windows sous la main) ; teste-le sur ton poste avant mise en production.
=====================================================================
#>

param(
    [string]$Base    = "banque",
    [string]$RepSauv = "C:\pg_sauvegardes",
    [int]$RetentionJours = 14,
    [string]$GpgDest = "dba@cliniquenord.ma",
    [string]$PgHost  = "127.0.0.1",
    [string]$PgPort  = "5432",
    [string]$PgUser  = "postgres"
)

$ErrorActionPreference = "Stop"

function Log([string]$niveau, [string]$msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Output "$ts [$niveau] $msg"
}

$horodatage    = Get-Date -Format "yyyyMMdd_HHmmss"
$prefixe       = Join-Path $RepSauv "${Base}_${horodatage}"
$fichierDump   = "$prefixe.dump"
$fichierChiffre = "$fichierDump.gpg"

try {
    # --------- Verifications prealables --------------------------------
    if (-not (Get-Command pg_dump -ErrorAction SilentlyContinue)) {
        throw "pg_dump introuvable dans le PATH."
    }
    if (-not (Get-Command gpg -ErrorAction SilentlyContinue)) {
        throw "gpg introuvable ; installer Gpg4win."
    }
    if (-not (Test-Path $RepSauv)) {
        New-Item -ItemType Directory -Path $RepSauv | Out-Null
    }
    & gpg --list-keys $GpgDest *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Cle publique GPG absente pour $GpgDest. Importer avec : gpg --import cle_publique.asc"
    }

    Log "INFO" "Debut de la sauvegarde de la base '$Base' vers $fichierChiffre"

    # --------- 1. Dump format custom ----------------------------------
    & pg_dump -h $PgHost -p $PgPort -U $PgUser -Fc --no-password -d $Base -f $fichierDump
    if ($LASTEXITCODE -ne 0) { throw "pg_dump a echoue (code $LASTEXITCODE)." }
    $tailleDump = "{0:N1} Mo" -f ((Get-Item $fichierDump).Length / 1MB)
    Log "INFO" "Dump cree ($tailleDump)."

    # --------- 2. Chiffrement asymetrique -----------------------------
    & gpg --batch --yes --trust-model always --encrypt --recipient $GpgDest --output $fichierChiffre $fichierDump
    if ($LASTEXITCODE -ne 0) { throw "Le chiffrement GPG a echoue." }
    Log "INFO" "Chiffrement GPG effectue pour $GpgDest."

    # --------- 3. Suppression du dump en clair -------------------------
    # Windows n'a pas 'shred' ; on ecrase sommairement puis on supprime.
    $fs = [System.IO.File]::OpenWrite($fichierDump)
    try {
        $len = $fs.Length
        $buf = New-Object byte[] 65536
        (New-Object Random).NextBytes($buf)
        $ecrit = 0
        while ($ecrit -lt $len) {
            $n = [Math]::Min($buf.Length, $len - $ecrit)
            $fs.Write($buf, 0, $n); $ecrit += $n
        }
    } finally { $fs.Close() }
    Remove-Item $fichierDump -Force
    Log "INFO" "Dump en clair supprime."

    # --------- 4. Verification d'integrite du fichier chiffre ---------
    & gpg --list-packets $fichierChiffre *> $null
    if ($LASTEXITCODE -ne 0) { throw "Le fichier chiffre semble corrompu." }
    $tailleFinale = "{0:N1} Mo" -f ((Get-Item $fichierChiffre).Length / 1MB)
    Log "INFO" "Sauvegarde terminee : $fichierChiffre ($tailleFinale)."

    # --------- 5. Rotation --------------------------------------------
    Log "INFO" "Application de la retention ($RetentionJours jours)."
    $limite = (Get-Date).AddDays(-$RetentionJours)
    $anciens = Get-ChildItem -Path $RepSauv -Filter "${Base}_*.dump.gpg" |
               Where-Object { $_.LastWriteTime -lt $limite }
    $anciens | Remove-Item -Force
    Log "INFO" "$($anciens.Count) ancienne(s) sauvegarde(s) supprimee(s)."

    $total = (Get-ChildItem -Path $RepSauv -Filter "${Base}_*.dump.gpg").Count
    Log "INFO" "Inventaire : $total sauvegarde(s) conservee(s) pour '$Base'."
    Log "INFO" "Succes."
    exit 0
}
catch {
    Log "ERREUR" $_.Exception.Message
    # nettoyage des fichiers partiels
    if (Test-Path $fichierDump)    { Remove-Item $fichierDump -Force -ErrorAction SilentlyContinue }
    if (Test-Path $fichierChiffre) { Remove-Item $fichierChiffre -Force -ErrorAction SilentlyContinue }
    exit 1
}

<#
=====================================================================
  RESTAURATION (memo — a executer manuellement) :
    gpg --decrypt banque_YYYYMMDD_HHMMSS.dump.gpg > restaure.dump
    createdb -U postgres banque_restore
    pg_restore -U postgres -d banque_restore --clean --if-exists restaure.dump
  Puis verifier, et supprimer le fichier dechiffre.
=====================================================================
#>
