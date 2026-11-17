# OKO-1: build and flash a board over its own USB with arduino-cli.
#   tools\flash.ps1 main                  main ESP32 DevKit
#   tools\flash.ps1 cam                   ESP32-CAM on an ESP32-CAM-MB / USB-UART programmer
#   tools\flash.ps1 cam -NoPsram          ESP32-CAM without working PSRAM (tracks at 160x120)
#   add -Port COM5 to pick the port, -BuildOnly to compile without uploading
# Needs: arduino-cli on PATH and the ESP32 core 2.0.17 (face-detection headers were removed in 3.x):
#   arduino-cli core install esp32:esp32@2.0.17 --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
param([Parameter(Mandatory = $true)][ValidateSet('main', 'cam')][string]$Board, [string]$Port, [switch]$NoPsram, [switch]$BuildOnly)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$extra = @()
if ($Board -eq 'main') { $sk = 'FT_main'; $fqbn = 'esp32:esp32:esp32'; $out = Join-Path $root 'build\FT_main' }
elseif ($NoPsram) { $sk = 'FT_cam'; $fqbn = 'esp32:esp32:esp32:PSRAM=disabled,PartitionScheme=huge_app'; $out = Join-Path $root 'build\FT_cam_nopsram' }
else {
  $sk = 'FT_cam'; $fqbn = 'esp32:esp32:esp32:PSRAM=enabled,PartitionScheme=huge_app'; $out = Join-Path $root 'build\FT_cam'
  # core 2.0.17 + PSRAM: point the C++ compiler at the psram-aware libstdc++ headers
  $data = (arduino-cli config get directories.data | Out-String).Trim()
  $psram = Get-ChildItem (Join-Path $data 'packages\esp32\tools\xtensa-esp32-elf-gcc') -Recurse -Directory -Filter 'esp32-psram' -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match '\\c\+\+\\' } | Select-Object -First 1
  if ($psram) { $extra = @('--build-property', "compiler.cpp.extra_flags=-isystem `"$($psram.FullName)`"") }
}
$dir = Join-Path $root "firmware\$sk"
arduino-cli compile --fqbn $fqbn @extra --output-dir $out $dir
if ($LASTEXITCODE) { Write-Host 'Build failed' -ForegroundColor Red; exit 1 }
if ($BuildOnly) { Write-Host "$sk built in $out" -ForegroundColor Green; exit 0 }
if (-not $Port) {
  $devs = @(Get-PnpDevice -PresentOnly | Where-Object { $_.FriendlyName -match 'CH340|CH910|CP210|USB Serial|USB-SERIAL' -and $_.FriendlyName -match '\((COM\d+)\)' })
  if ($devs.Count -ne 1) { Write-Host 'Plug in exactly one board, or pass -Port COMx' -ForegroundColor Red; exit 1 }
  $null = $devs[0].FriendlyName -match '\((COM\d+)\)'; $Port = $Matches[1]
}
Write-Host "$sk -> $Port"
arduino-cli upload --fqbn $fqbn -p $Port --input-dir $out $dir
if ($LASTEXITCODE) {
  if ($Board -eq 'cam') { Write-Host 'Upload failed: on the ESP32-CAM-MB hold IO0, tap RST, release IO0 and retry' -ForegroundColor Red }
  else { Write-Host 'Upload failed: hold BOOT while it says Connecting...' -ForegroundColor Red }
  exit 1
}
Write-Host "Done: $sk flashed" -ForegroundColor Green
