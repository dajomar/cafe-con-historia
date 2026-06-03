
# ============================================================
# Café con Historia — Setup del Scheduler
# Ejecutar como Administrador en PowerShell
# ============================================================
# Uso:
#   cd D:\proyectos\cafe-con-historia
#   .\scripts\setup_scheduler.ps1
# ============================================================

$PROYECTO = "D:\proyectos\cafe-con-historia"
$PYTHON   = "python"
$HORA     = "12:00PM"
$TAREA    = "CafeConHistoria"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Café con Historia — Configurando Scheduler" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# Verifica que Python existe
try {
    $version = & python --version 2>&1
    Write-Host "Python encontrado: $version" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python no encontrado. Instala Python 3.11 primero." -ForegroundColor Red
    exit 1
}

# Verifica que el proyecto existe
if (-Not (Test-Path "$PROYECTO\main.py")) {
    Write-Host "ERROR: No se encontró main.py en $PROYECTO" -ForegroundColor Red
    exit 1
}

# Elimina la tarea si ya existe
$tareaExiste = Get-ScheduledTask -TaskName $TAREA -ErrorAction SilentlyContinue
if ($tareaExiste) {
    Unregister-ScheduledTask -TaskName $TAREA -Confirm:$false
    Write-Host "Tarea anterior eliminada." -ForegroundColor Yellow
}

# Crea la tarea nueva
$action = New-ScheduledTaskAction `
    -Execute $PYTHON `
    -Argument "$PROYECTO\main.py" `
    -WorkingDirectory $PROYECTO

$trigger = New-ScheduledTaskTrigger -Daily -At $HORA

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

Register-ScheduledTask `
    -TaskName $TAREA `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -RunLevel Highest `
    -Description "Café con Historia — Pipeline diario de contenido" | Out-Null

Write-Host ""
Write-Host "Tarea programada creada exitosamente:" -ForegroundColor Green
Write-Host "  Nombre : $TAREA" -ForegroundColor White
Write-Host "  Hora   : $HORA diario" -ForegroundColor White
Write-Host "  Script : $PROYECTO\main.py" -ForegroundColor White
Write-Host ""
Write-Host "Para verificar: Abre el Programador de Tareas y busca '$TAREA'" -ForegroundColor Cyan
Write-Host "Para correr manualmente ahora:" -ForegroundColor Cyan
Write-Host "  Start-ScheduledTask -TaskName '$TAREA'" -ForegroundColor White