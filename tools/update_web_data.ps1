[CmdletBinding()]
param(
    [string]$Database = "data\ntu_schedule.db",
    [switch]$SkipTests,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    $dbPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $Database))
    if (-not (Test-Path -LiteralPath $dbPath -PathType Leaf)) {
        throw "Database not found: $dbPath"
    }
    $dbItem = Get-Item -LiteralPath $dbPath
    Write-Host "Source database: $dbPath"
    Write-Host "Database size: $($dbItem.Length) bytes"

    @'
import sqlite3, sys
db = sqlite3.connect(sys.argv[1])
result = db.execute("PRAGMA integrity_check").fetchone()[0]
if result != "ok": raise SystemExit(f"SQLite integrity check failed: {result}")
required = {"normalization_runs", "rooms", "class_meetings", "canonical_classes"}
found = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
if not required <= found: raise SystemExit(f"Missing tables: {sorted(required - found)}")
if not db.execute("SELECT 1 FROM normalization_runs WHERE status='completed' LIMIT 1").fetchone():
    raise SystemExit("No completed normalization run")
print("SQLite integrity and normalized-schema checks passed.")
'@ | python - $dbPath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    python -m ntu_room_checker export-web-data --db $dbPath --output "web\public\data"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    if (-not $SkipTests) {
        python -m pytest
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        Push-Location "web"
        try { npm test; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
        finally { Pop-Location }
    }
    if (-not $SkipBuild) {
        Push-Location "web"
        try { npm run build; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
        finally { Pop-Location }
    }

    $manifest = Get-Content -Raw "web\public\data\manifest.json" | ConvertFrom-Json
    $jsonFiles = Get-ChildItem "web\public\data" -Filter "*.json" -Recurse
    $dayFiles = Get-ChildItem "web\public\data\days" -Filter "*.json"
    $sizes = @($dayFiles | ForEach-Object Length | Sort-Object)
    $median = $sizes[[Math]::Floor($sizes.Count / 2)]
    Write-Host "AY / semester: $($manifest.academic_year) / $($manifest.semester)"
    Write-Host "Rooms / canonical meetings: $($manifest.room_count) / $($manifest.canonical_meeting_count)"
    Write-Host "Supported dates: $($manifest.first_supported_date) to $($manifest.last_supported_date)"
    Write-Host "JSON files / raw bytes: $($jsonFiles.Count) / $(($jsonFiles | Measure-Object Length -Sum).Sum)"
    Write-Host "Median / largest daily bytes: $median / $(($sizes | Measure-Object -Maximum).Maximum)"
}
finally {
    Pop-Location
}
