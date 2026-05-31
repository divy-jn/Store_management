# Store Intelligence Pipeline Runner

$ErrorActionPreference = "Stop"

# Input paths
$InputDir = "..\Project details\CCTV Footage-20260529T160731Z-3-00144614ea (1)\CCTV Footage"
$OutputDir = "..\output\events"

Write-Host "🚀 Starting Store Intelligence Detection Pipeline" -ForegroundColor Cyan
Write-Host "Checking for CCTV videos in $InputDir..."

if (-not (Test-Path $InputDir)) {
    Write-Host "❌ Input directory not found: $InputDir" -ForegroundColor Red
    exit 1
}

# Run Detection
Write-Host "👁️ Running YOLOv8 + ByteTrack detection..." -ForegroundColor Yellow
python detect.py --input-dir $InputDir --output-dir $OutputDir

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Detection failed" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Detection complete!" -ForegroundColor Green

# Replay to API
Write-Host "🌐 Sending events to API..." -ForegroundColor Yellow
python replay.py --events-dir $OutputDir --api-url http://localhost:8000

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Ingestion failed" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Pipeline complete!" -ForegroundColor Green
