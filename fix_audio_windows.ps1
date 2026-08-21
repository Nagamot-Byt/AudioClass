# fix_audio_windows.ps1 — Diagnóstico y reparación de micrófono en Windows
#
# Ejecuta:
#   powershell -ExecutionPolicy Bypass -File fix_audio_windows.ps1
#
# Requiere permisos de administrador para reiniciar servicios.
# Si no tiene admin, solo muestra diagnóstico (sin reparación).

param(
    [switch]$AutoFix    # Aplicar correcciones automáticas
)

$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  DIAGNOSTICO Y REPARACION DE MICROFONO - Windows" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

if ($IsAdmin) {
    Write-Host "[OK] Ejecutando como Administrador" -ForegroundColor Green
} else {
    Write-Host "[WARN] Sin permisos de Administrador - solo diagnostico (sin reparacion)" -ForegroundColor Yellow
    Write-Host "       Para reparar: clic derecho > Ejecutar como administrador" -ForegroundColor Yellow
}
Write-Host ""

# ── PASO 1: Permisos de microfono ──────────────────────────────────────────
Write-Host "=== PASO 1: Permisos de microfono ===" -ForegroundColor White

$regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"
if (Test-Path $regPath) {
    $value = Get-ItemProperty -Path $regPath -Name "Value" -ErrorAction SilentlyContinue
    if ($value.Value -eq "Allow") {
        Write-Host "  [OK] Permisos de microfono: Permitido" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] Permisos de microfono: Bloqueado ($($value.Value))" -ForegroundColor Red
        if ($AutoFix -and $IsAdmin) {
            Write-Host "  -> Corrigiendo..." -ForegroundColor Yellow
            Set-ItemProperty -Path $regPath -Name "Value" -Value "Allow"
            Write-Host "  [FIX] Permisos cambiados a Permitido" -ForegroundColor Green
        } else {
            Write-Host "  -> Solucion: Configuracion > Privacidad > Microfono > Permitir" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "  [WARN] Clave de registro no encontrada" -ForegroundColor Yellow
}

# Verificar permisos para apps de escritorio
$regPath2 = "HKCU:\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"
$valorDecentralized = Get-ItemProperty -Path $regPath2 -Name "Value" -ErrorAction SilentlyContinue
Write-Host ""

# ── PASO 2: Servicios de audio ────────────────────────────────────────────
Write-Host "=== PASO 2: Servicios de audio ===" -ForegroundColor White

$services = @(
    @{Name="Audiosrv"; DisplayName="Windows Audio"},
    @{Name="AudioEndpointBuilder"; DisplayName="Constructor de endpoints de audio"}
)

foreach ($svc in $services) {
    $service = Get-Service -Name $svc.Name -ErrorAction SilentlyContinue
    if ($service) {
        $status = $service.Status
        if ($status -eq "Running") {
            Write-Host "  [OK] $($svc.DisplayName): $status" -ForegroundColor Green
        } else {
            Write-Host "  [FAIL] $($svc.DisplayName): $status" -ForegroundColor Red
            if ($AutoFix -and $IsAdmin) {
                Write-Host "  -> Iniciando servicio..." -ForegroundColor Yellow
                Start-Service -Name $svc.Name -ErrorAction SilentlyContinue
                Start-Sleep -Seconds 2
                $service.Refresh()
                if ($service.Status -eq "Running") {
                    Write-Host "  [FIX] $($svc.DisplayName) iniciado" -ForegroundColor Green
                } else {
                    Write-Host "  [ERROR] No se pudo iniciar $($svc.DisplayName)" -ForegroundColor Red
                }
            }
        }
    } else {
        Write-Host "  [WARN] Servicio $($svc.Name) no encontrado" -ForegroundColor Yellow
    }
}
Write-Host ""

# ── PASO 3: Dispositivos de audio ─────────────────────────────────────────
Write-Host "=== PASO 3: Dispositivos de audio ===" -ForegroundColor White

try {
    $audioDevices = Get-PnpDevice -Class "AudioEndpoint" -ErrorAction SilentlyContinue
    if ($audioDevices) {
        foreach ($dev in $audioDevices) {
            $status = $dev.Status
            $friendly = $dev.FriendlyName
            $instanceId = $dev.InstanceId
            
            if ($status -eq "OK") {
                Write-Host "  [OK] $friendly" -ForegroundColor Green
            } elseif ($status -eq "Error") {
                Write-Host "  [FAIL] $friendly (Error)" -ForegroundColor Red
                if ($AutoFix -and $IsAdmin) {
                    Write-Host "  -> Intentando habilitar..." -ForegroundColor Yellow
                    Enable-PnpDevice -InstanceId $instanceId -Confirm:$false -ErrorAction SilentlyContinue
                }
            } elseif ($status -eq "Unknown") {
                Write-Host "  [WARN] $friendly (Desconocido)" -ForegroundColor Yellow
            } else {
                Write-Host "  [INFO] $friendly ($status)" -ForegroundColor Gray
            }
        }
    } else {
        Write-Host "  [WARN] No se encontraron dispositivos de audio" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  [ERROR] No se pudieron enumerar dispositivos: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# ── PASO 4: Drivers de audio ──────────────────────────────────────────────
Write-Host "=== PASO 4: Drivers de audio ===" -ForegroundColor White

try {
    $audioDrivers = Get-WmiObject Win32_PnPSignedDriver | Where-Object { 
        $_.DeviceClass -eq "MEDIA" -and $_.DeviceName -like "*Audio*" -or $_.DeviceName -like "*Realtek*"
    }
    
    if ($audioDrivers) {
        foreach ($drv in $audioDrivers) {
            $name = $drv.DeviceName
            $version = $drv.DriverVersion
            $date = $drv.DriverDate
            if ($date) {
                try {
                    $dateStr = [Management.ManagementDateTimeConverter]::ToDateTime($date).ToString("yyyy-MM-dd")
                } catch {
                    $dateStr = $date
                }
            } else {
                $dateStr = "N/A"
            }
            
            Write-Host "  Driver: $name" -ForegroundColor White
            Write-Host "    Version: $version | Fecha: $dateStr" -ForegroundColor Gray
        }
    } else {
        Write-Host "  [WARN] No se encontraron drivers de audio" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  [ERROR] No se pudieron enumerar drivers: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# ── PASO 5: Nivel del microfono (si hay Python) ───────────────────────────
Write-Host "=== PASO 5: Nivel del microfono ===" -ForegroundColor White

$pythonPaths = @(
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "python",
    "python3"
)

$pythonExe = $null
foreach ($p in $pythonPaths) {
    if (Test-Path $p) {
        $pythonExe = $p
        break
    }
}

if ($pythonExe) {
    Write-Host "  Python encontrado: $pythonExe" -ForegroundColor Gray
    
    $testScript = @"
import sys
try:
    import sounddevice as sd
    import numpy as np
    
    devs = sd.query_devices()
    input_devs = [(i, d) for i, d in enumerate(devs) if d['max_input_channels'] >= 1]
    
    print(f'  Dispositivos de entrada: {len(input_devs)}')
    
    for i, d in input_devs[:3]:
        name = str(d['name'])[:40]
        try:
            rec = sd.rec(int(0.5 * 16000), samplerate=16000, channels=1, dtype='float32', device=i)
            sd.wait()
            flat = rec.flatten()
            rms = float(np.sqrt(np.mean(flat.astype(np.float64)**2)))
            peak = float(np.max(np.abs(flat)))
            
            if rms < 0.005:
                tag = 'SILENCIO'
                color = 'RED'
            elif rms < 0.03:
                tag = 'DEBIL'
                color = 'YELLOW'
            else:
                tag = 'OK'
                color = 'GREEN'
            
            print(f'  [{i:2d}] {name}')
            print(f'       RMS={rms:.4f} Peak={peak:.4f} -> {tag}')
        except Exception as e:
            print(f'  [{i:2d}] {name}: ERROR - {e}')
except ImportError:
    print('  [WARN] sounddevice no instalado')
except Exception as e:
    print(f'  [ERROR] {e}')
"@
    
    $result = & $pythonExe -c $testScript 2>&1
    foreach ($line in $result) {
        Write-Host "  $line" -ForegroundColor Gray
    }
} else {
    Write-Host "  [WARN] Python no encontrado - saltando prueba de nivel" -ForegroundColor Yellow
}
Write-Host ""

# ── PASO 6: Reiniciar servicios (si AutoFix) ─────────────────────────────
if ($AutoFix -and $IsAdmin) {
    Write-Host "=== PASO 6: Reiniciando servicios de audio ===" -ForegroundColor White
    
    Write-Host "  Deteniendo Windows Audio..." -ForegroundColor Yellow
    Stop-Service -Name "Audiosrv" -Force -ErrorAction SilentlyContinue
    Stop-Service -Name "AudioEndpointBuilder" -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
    
    Write-Host "  Iniciando Windows Audio..." -ForegroundColor Yellow
    Start-Service -Name "AudioEndpointBuilder" -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Start-Service -Name "Audiosrv" -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
    
    # Verificar
    $audiosrv = Get-Service -Name "Audiosrv" -ErrorAction SilentlyContinue
    if ($audiosrv.Status -eq "Running") {
        Write-Host "  [OK] Windows Audio reiniciado correctamente" -ForegroundColor Green
    } else {
        Write-Host "  [ERROR] Windows Audio no pudo iniciarse" -ForegroundColor Red
    }
    Write-Host ""
}

# ── RESUMEN ───────────────────────────────────────────────────────────────
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  RESUMEN" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

if ($IsAdmin) {
    Write-Host "  Modo: Reparacion completa (Admin)" -ForegroundColor Green
} else {
    Write-Host "  Modo: Solo diagnostico (sin Admin)" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "  PASOS MANUALES SI EL MICROFONO SIGUE SIN FUNCIONAR:" -ForegroundColor White
Write-Host "  1. Configuracion > Privacidad > Microfono > Permitir" -ForegroundColor Gray
Write-Host "  2. Configuracion > Sistema > Sonido > Entrada" -ForegroundColor Gray
Write-Host "  3. Verificar que el microfono NO este muteado" -ForegroundColor Gray
Write-Host "  4. Actualizar driver Realtek desde el sitio del fabricante" -ForegroundColor Gray
Write-Host "  5. Reiniciar el equipo" -ForegroundColor Gray
Write-Host ""
