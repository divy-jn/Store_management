# Store Intelligence Pipeline Runner

param(
    [Parameter(Mandatory=$true)][string]$StoreId,
    [string]$ApiUrl = "http://localhost:8000",
    [string]$InputDir,
    [string]$OutputDir
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")

# Input paths
if (-not $InputDir) {
    $InputDir = Join-Path $ProjectRoot "Project details\New folder\Store 1"
}
if (-not $OutputDir) {
    $OutputDir = Join-Path $ProjectRoot "output\events"
}

Write-Host "🚀 Starting Store Intelligence Detection Pipeline" -ForegroundColor Cyan
Write-Host "Checking for CCTV videos in $InputDir..."

if (-not (Test-Path $InputDir)) {
    Write-Host "❌ Input directory not found: $InputDir" -ForegroundColor Red
    exit 1
}

# Run Detection
Write-Host "👁️ Running YOLOv8 + ByteTrack detection..." -ForegroundColor Yellow
python (Join-Path $ScriptDir "detect.py") --input-dir $InputDir --output-dir $OutputDir --store-id $StoreId

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Detection failed" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Detection complete!" -ForegroundColor Green

# Replay to API
Write-Host "🌐 Sending events to API..." -ForegroundColor Yellow
python (Join-Path $ScriptDir "replay.py") --events-dir $OutputDir --api-url $ApiUrl

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Ingestion failed" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Pipeline complete!" -ForegroundColor Green
