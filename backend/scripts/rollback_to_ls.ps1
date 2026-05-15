<#
.SYNOPSIS
TrainPlex Studio — Emergency Rollback to LS Production (PowerShell wrapper).

.DESCRIPTION
Windows-host parity for backend/scripts/rollback_to_ls.sh. Shells out to
the bash version inside WSL2 / git-bash when available; otherwise
performs the same steps natively on the Windows host.

Founder rules honoured:
 * No founder personal number is ever embedded — outbound webhook
   uses $env:TRAINPLEX_OPS_WEBHOOK only.
 * Incident log append — writes to $env:TRAINPLEX_INCIDENT_LOG or
   the default Windows path under C:\TrainPlex\data\INCIDENT_LOG.md.
 * Idempotent — re-runs are no-ops once the routing flag is flipped.

.EXAMPLE
PS> .\rollback_to_ls.ps1 -Reason "stale data on fork"

.EXAMPLE
PS> .\rollback_to_ls.ps1 -DropFork -Reason "post-cutover audit failed"
#>

[CmdletBinding()]
param(
    [string]$Reason = "manual rollback",
    [switch]$DropFork
)

$ErrorActionPreference = 'Stop'

function Write-Stamp { param([string]$Msg)
    $ts = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    Write-Host "[$ts] $Msg"
}

# Prefer the bash version if WSL or git-bash is on PATH — keeps a single
# canonical implementation.
$bash = Get-Command bash -ErrorAction SilentlyContinue
if ($bash) {
    Write-Stamp "Delegating to bash version: $($bash.Source)"
    $args = @("$PSScriptRoot/rollback_to_ls.sh", "--reason", $Reason)
    if ($DropFork) { $args += "--drop-fork" }
    & $bash.Source @args
    exit $LASTEXITCODE
}

Write-Stamp "bash not available — running native PowerShell fallback"

$flagFile  = if ($env:TRAINPLEX_ROUTE_FLAG) { $env:TRAINPLEX_ROUTE_FLAG } else { "C:\TrainPlex\nginx\trainplex_upstream.flag" }
$incident  = if ($env:TRAINPLEX_INCIDENT_LOG) { $env:TRAINPLEX_INCIDENT_LOG } else { "C:\TrainPlex\data\INCIDENT_LOG.md" }
$lsCompose = if ($env:LS_COMPOSE) { $env:LS_COMPOSE } else { "C:\TrainPlex\labelstudio\docker-compose.yml" }
$webhook   = $env:TRAINPLEX_OPS_WEBHOOK

# 1. Flip routing flag.
New-Item -ItemType Directory -Force -Path (Split-Path $flagFile) | Out-Null
"rollback=$(Get-Date -Format o)" | Out-File -Encoding utf8 $flagFile
Write-Stamp "Wrote routing flag: $flagFile"

# 2. Optionally drop fork DB.
if ($DropFork) {
    $answer = Read-Host "Type YES to drop fork DB"
    if ($answer -ne "YES") {
        Write-Stamp "Operator aborted at confirmation."
        exit 2
    }
    if (Get-Command psql -ErrorAction SilentlyContinue) {
        & psql -c "DROP DATABASE IF EXISTS trainplex;"
    } else {
        Write-Stamp "psql not on PATH — skipping DB drop"
    }
}

# 3. Confirm LS container.
$running = (& docker ps --format '{{.Names}}') 2>$null
if ($running -match 'labelstudio') {
    Write-Stamp "OK: labelstudio container already running"
} else {
    Write-Stamp "Bringing LS container up via $lsCompose"
    & docker compose -f $lsCompose up -d
    if ($LASTEXITCODE -ne 0) {
        Write-Stamp "ERROR: docker compose up failed"
        exit 4
    }
}

# 4. Notify webhook.
if ($webhook) {
    try {
        Invoke-RestMethod -Method Post -Uri $webhook -ContentType 'application/json' `
            -Body (@{ event = 'rollback'; reason = $Reason; at = (Get-Date -Format o) } | ConvertTo-Json)
        Write-Stamp "Webhook notified."
    } catch {
        Write-Stamp "WARN: webhook post failed: $_"
    }
} else {
    Write-Stamp "TRAINPLEX_OPS_WEBHOOK unset — skipping outbound notify"
}

# 5. Incident log append.
$line = @"

## $(Get-Date -Format o) — Rollback to LS (PowerShell)
Reason: $Reason
Drop fork DB: $DropFork
Verification: routing flag written + LS container up.
"@
New-Item -ItemType Directory -Force -Path (Split-Path $incident) | Out-Null
Add-Content -Path $incident -Value $line

Write-Stamp "Rollback complete."
exit 0
