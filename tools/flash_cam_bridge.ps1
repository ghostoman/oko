# OKO-1: flash the ESP32-CAM THROUGH the main ESP32, without a programmer and without moving the working wires.
# The main board (FT_main 2.1 or newer) has a "bridge" mode: it becomes a plain 115200 serial link between USB and the
# camera on IO16/IO17. The camera keeps its normal wiring (U0T -> IO16, U0R -> IO17, 3V3, GND).
# The only extra step: a jumper from the CAMERA's IO0 to GND, then press RST on the camera (download mode).
#   tools\flash_cam_bridge.ps1            build (PSRAM) + flash; waits for Enter after asking you to set the jumper
#   -NoPsram   camera without working PSRAM     -SkipBuild  flash the binaries built last time
#   -Yes       do not wait for Enter             -Probe      only check that the camera answers (stays in bridge mode)
#   -Enter     only switch the main board to bridge mode     -Exit  only switch it back to normal work
# Flash the main board first (tools\flash.ps1 main). Only the main ESP32 may be connected by USB.
param([switch]$NoPsram, [switch]$Probe, [switch]$SkipBuild, [switch]$Yes, [switch]$Enter, [switch]$Exit, [string]$Port)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$data = (arduino-cli config get directories.data | Out-String).Trim()
$esptool = Get-ChildItem (Join-Path $data 'packages\esp32\tools\esptool_py') -Recurse -Filter 'esptool.exe' | Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
$boot0 = Join-Path $data 'packages\esp32\hardware\esp32\2.0.17\tools\partitions\boot_app0.bin'
if (-not $esptool -or -not (Test-Path $boot0)) { Write-Host 'Install the core first: arduino-cli core install esp32:esp32@2.0.17' -ForegroundColor Red; exit 1 }
if (-not $Port) {
  $devs = @(Get-PnpDevice -PresentOnly | Where-Object { $_.FriendlyName -match 'CH340|CH910|CP210|USB Serial|USB-SERIAL' -and $_.FriendlyName -match '\((COM\d+)\)' })
  if ($devs.Count -ne 1) { Write-Host 'Connect exactly one board by USB (the main ESP32), or pass -Port COMx' -ForegroundColor Red; exit 1 }
  $null = $devs[0].FriendlyName -match '\((COM\d+)\)'; $Port = $Matches[1]
}
function Send-Text([int]$baud, [string]$text) {
  $s = New-Object System.IO.Ports.SerialPort $Port, $baud, 'None', 8, 'One'; $s.DtrEnable = $false; $s.RtsEnable = $false; $s.Open()
  Start-Sleep -Milliseconds 2500; $s.Write($text); Start-Sleep -Milliseconds 400; $s.Close()   # opening the port may restart the board
}
function Enter-Bridge { Send-Text 921600 "bridge`n"; Start-Sleep -Milliseconds 1800 }
function Exit-Bridge { Send-Text 115200 '~~FT-EXIT~~'; Start-Sleep -Milliseconds 1500 }
if ($Exit) { Exit-Bridge; Write-Host 'Main board back to normal work' -ForegroundColor Green; exit 0 }
if ($Enter) { Enter-Bridge; Write-Host 'Main board is in bridge mode (115200)' -ForegroundColor Green; exit 0 }
if ($Probe) { Enter-Bridge; & $esptool --chip esp32 --port $Port --baud 115200 --before no_reset --after no_reset flash_id; exit $LASTEXITCODE }
$out = Join-Path $root ($(if ($NoPsram) { 'build\FT_cam_nopsram' } else { 'build\FT_cam' }))
if (-not $SkipBuild) {
  $args2 = @('-Board', 'cam', '-BuildOnly'); if ($NoPsram) { $args2 += '-NoPsram' }
  & (Join-Path $PSScriptRoot 'flash.ps1') @args2
  if ($LASTEXITCODE) { exit 1 }
}
Enter-Bridge
if (-not $Yes) { Read-Host 'Put a jumper from the CAMERA IO0 to GND, press RST on the camera, then press Enter' | Out-Null }
& $esptool --chip esp32 --port $Port --baud 115200 --before no_reset --after no_reset write_flash -z --flash_mode dio --flash_freq 80m --flash_size 4MB `
  0x1000 (Join-Path $out 'FT_cam.ino.bootloader.bin') 0x8000 (Join-Path $out 'FT_cam.ino.partitions.bin') 0xe000 $boot0 0x10000 (Join-Path $out 'FT_cam.ino.bin')
$rc = $LASTEXITCODE
Exit-Bridge
if ($rc) { Write-Host 'Flash failed: is the camera in download mode? Check the IO0-GND jumper and press RST on the camera' -ForegroundColor Red; exit 1 }
Write-Host 'Done: FT_cam flashed. Remove the IO0-GND jumper and press RST on the camera.' -ForegroundColor Green
