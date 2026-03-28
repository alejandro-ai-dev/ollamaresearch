# ═══════════════════════════════════════════════════════════════════════════════
# OllamaResearch — Instalador para Windows (PowerShell)
# Ejecutar: powershell -ExecutionPolicy Bypass -File install.ps1
# ═══════════════════════════════════════════════════════════════════════════════

param(
    [switch]$SkipOllama,
    [switch]$SkipPython,
    [switch]$NoShortcuts
)

# ─── Colores y funciones ─────────────────────────────────────────────────────
function Write-Header { 
    param([string]$msg)
    Write-Host "`n$msg" -ForegroundColor Blue -BackgroundColor Black
}
function Write-Step { 
    param([string]$msg)
    Write-Host "`n▶ $msg" -ForegroundColor Cyan
}
function Write-Success { 
    param([string]$msg)
    Write-Host "  ✓ $msg" -ForegroundColor Green
}
function Write-Info { 
    param([string]$msg)
    Write-Host "  ℹ $msg" -ForegroundColor Gray
}
function Write-Warn { 
    param([string]$msg)
    Write-Host "  ⚠ $msg" -ForegroundColor Yellow
}
function Write-Fail { 
    param([string]$msg)
    Write-Host "  ✗ $msg" -ForegroundColor Red
}

# ─── Banner ──────────────────────────────────────────────────────────────────
Clear-Host
Write-Host @"
  ╔══════════════════════════════════════════════════════════╗
  ║          🔬 OllamaResearch — Instalador Windows          ║
  ║     Framework de Deep Research con IA en la Terminal     ║
  ╚══════════════════════════════════════════════════════════╝
"@ -ForegroundColor Cyan

Write-Host "  Compatible con: Windows 10, Windows 11`n"

# ─── Verificar modo administrador (recomendado) ───────────────────────────────
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if (-not $isAdmin) {
    Write-Warn "No se está ejecutando como Administrador. Algunas funciones pueden requerir elevación."
}

# ─── Paso 1: Verificar Python ─────────────────────────────────────────────────
Write-Step "Paso 1/5: Verificando Python"

$pythonFound = $false
$pythonCmd = "python"

# Intentar diferentes comandos
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $version = & $cmd --version 2>&1
        if ($version -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 9) {
                Write-Success "Python $($Matches[0].Split(' ')[1]) encontrado ($cmd)"
                $pythonCmd = $cmd
                $pythonFound = $true
                break
            }
        }
    } catch {}
}

if (-not $pythonFound) {
    Write-Fail "Python 3.9+ no encontrado"
    Write-Host ""
    Write-Host "  Opciones para instalar Python:" -ForegroundColor White
    Write-Host "  1. Microsoft Store: busca 'Python 3.12'" -ForegroundColor Gray
    Write-Host "  2. Sitio oficial: https://python.org/downloads" -ForegroundColor Gray
    Write-Host "  3. winget: winget install Python.Python.3.12" -ForegroundColor Gray
    Write-Host ""
    
    $response = Read-Host "  ¿Abrir la página de descarga de Python? (S/N)"
    if ($response -eq "S" -or $response -eq "s") {
        Start-Process "https://www.python.org/downloads/windows/"
    }
    
    Write-Host "`n  Instala Python, reinicia esta ventana y vuelve a ejecutar el instalador." -ForegroundColor Yellow
    exit 1
}

# ─── Paso 2: Verificar pip ────────────────────────────────────────────────────
Write-Step "Paso 2/5: Verificando pip"

try {
    $pipVersion = & $pythonCmd -m pip --version 2>&1
    Write-Success "pip disponible: $pipVersion"
} catch {
    Write-Info "pip no encontrado. Instalando..."
    & $pythonCmd -m ensurepip --upgrade
    Write-Success "pip instalado"
}

# ─── Paso 3: Instalar/Verificar Ollama ───────────────────────────────────────
Write-Step "Paso 3/5: Verificando Ollama"

$ollamaFound = $false
try {
    $ollamaVersion = & ollama --version 2>&1
    Write-Success "Ollama ya está instalado: $ollamaVersion"
    $ollamaFound = $true
} catch {}

if (-not $ollamaFound -and -not $SkipOllama) {
    Write-Warn "Ollama no encontrado. Descargando instalador..."
    
    $ollamaInstaller = "$env:TEMP\ollama-setup.exe"
    $ollamaUrl = "https://ollama.com/download/OllamaSetup.exe"
    
    try {
        Write-Info "Descargando Ollama desde ollama.com..."
        $webClient = New-Object System.Net.WebClient
        $webClient.DownloadFile($ollamaUrl, $ollamaInstaller)
        
        Write-Info "Ejecutando instalador de Ollama..."
        Start-Process $ollamaInstaller -Wait -ArgumentList "/S"
        
        # Actualizar PATH para encontrar ollama
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")
        
        Start-Sleep -Seconds 3
        
        try {
            $ollamaVersion = & ollama --version 2>&1
            Write-Success "Ollama instalado: $ollamaVersion"
            $ollamaFound = $true
        } catch {
            Write-Warn "Ollama instalado pero requiere reiniciar la terminal"
            $ollamaFound = $true
        }
        
        Remove-Item $ollamaInstaller -ErrorAction SilentlyContinue
        
    } catch {
        Write-Fail "No se pudo descargar Ollama automáticamente"
        Write-Host ""
        Write-Host "  Por favor descarga Ollama manualmente:" -ForegroundColor White
        Write-Host "  → https://ollama.com/download/windows" -ForegroundColor Cyan
        Write-Host ""
        $response = Read-Host "  ¿Abrir la página de descarga? (S/N)"
        if ($response -eq "S" -or $response -eq "s") {
            Start-Process "https://ollama.com/download/windows"
        }
        Write-Warn "Instalación de OllamaResearch continúa sin Ollama..."
    }
}

# ─── Paso 4: Instalar OllamaResearch ─────────────────────────────────────────────

Write-Step "Paso 4/5: Instalando OllamaResearch"

$scriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath   = Join-Path $scriptDir ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"

Write-Info "Directorio del proyecto: $scriptDir"

# Crear entorno virtual si no existe
if (Test-Path $venvPython) {
    Write-Info "Entorno virtual ya existe (.venv)"
} else {
    Write-Info "Creando entorno virtual (.venv)..."
    & $pythonCmd -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "No se pudo crear el entorno virtual."
        Write-Host "  Intenta ejecutar como Administrador."
        exit 1
    }
    Write-Success "Entorno virtual creado"
}

# Verificar que el venv tenga python.exe (por si el .venv estaba corrupto)
if (-not (Test-Path $venvPython)) {
    Write-Fail "El entorno virtual está corrupto. Eliminando y recreando..."
    Remove-Item -Recurse -Force $venvPath -ErrorAction SilentlyContinue
    & $pythonCmd -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "No se pudo recrear el entorno virtual."
        exit 1
    }
    Write-Success "Entorno virtual recreado"
}

# Actualizar pip dentro del venv
Write-Info "Actualizando pip..."
& $venvPython -m pip install --upgrade pip --quiet

# Instalar/actualizar el paquete (--upgrade garantiza reinstalacion si ya existía)
Write-Info "Instalando paquete y dependencias (puede tardar 1-3 minutos)..."
& $venvPython -m pip install --upgrade $scriptDir --quiet

if ($LASTEXITCODE -ne 0) {
    Write-Info "Reintentando con salida detallada..."
    & $venvPython -m pip install --upgrade $scriptDir
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Error en la instalacion. Prueba ejecutar como Administrador."
        exit 1
    }
}
Write-Success "OllamaResearch instalado y actualizado correctamente"

# ─── Paso 5: Crear lanzadores ────────────────────────────────────────────────
Write-Step "Paso 5/5: Creando accesos directos y lanzadores"

$venvPath = Join-Path $scriptDir ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"

# Crear ia.bat en la carpeta del proyecto
$iaBatPath = Join-Path $scriptDir "ia.bat"
$iaBatContent = "@echo off`r`ntitle OllamaResearch`r`n`"$venvPython`" -m ollamaresearch %*`r`n"
Set-Content -Path $iaBatPath -Value $iaBatContent -Encoding ASCII
Write-Success "Lanzador ia.bat creado: $iaBatPath"

if (-not $NoShortcuts) {
    # Acceso directo en el escritorio
    try {
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut(
            [Environment]::GetFolderPath('Desktop') + '\OllamaResearch (ia).lnk'
        )
        $shortcut.TargetPath = $iaBatPath
        $shortcut.WorkingDirectory = $scriptDir
        $shortcut.IconLocation = 'shell32.dll,137'
        $shortcut.Description = 'OllamaResearch - Deep Research con IA'
        $shortcut.Save()
        Write-Success "Acceso directo creado en el Escritorio"
    } catch {
        Write-Warn "No se pudo crear el acceso directo: $_"
    }

    # Configurar PowerShell Profile para alias 'ia'
    if (-not (Test-Path $PROFILE)) {
        New-Item -Path $PROFILE -ItemType File -Force | Out-Null
    }
    $profileContent = Get-Content $PROFILE -ErrorAction SilentlyContinue -Raw
    $shortcutBlock = "`r`n# OllamaResearch`r`nfunction ia { & '$iaBatPath' `$args }`r`nfunction research { & '$iaBatPath' `$args }`r`n"

    if ($profileContent -notmatch "OllamaResearch") {
        Add-Content -Path $PROFILE -Value $shortcutBlock
        Write-Success "Funcion 'ia' agregada al perfil de PowerShell"
    } else {
        Write-Info "Funciones 'ia' ya configuradas en PowerShell"
    }

    # Agregar directorio al PATH para que 'ia' funcione en CMD
    $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($userPath -notlike "*$scriptDir*") {
        [Environment]::SetEnvironmentVariable("PATH", "$userPath;$scriptDir", "User")
        Write-Success "Directorio agregado al PATH: $scriptDir"
    }
}

# ─── Resumen final ────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  ✅ ¡Instalación completada exitosamente!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "  Para usar OllamaResearch:" -ForegroundColor White
Write-Host ""
Write-Host "  1. Cierra y vuelve a abrir PowerShell" -ForegroundColor Cyan  
Write-Host ""
Write-Host "  2. Escribe 'ia' y presiona Enter:" -ForegroundColor Cyan
Write-Host "     PS> ia" -ForegroundColor Green
Write-Host "     PS> ia `"¿qué es la inteligencia artificial?`"" -ForegroundColor Green
Write-Host ""

if (-not $ollamaFound) {
    Write-Host "  ⚠ Recuerda instalar Ollama primero:" -ForegroundColor Yellow
    Write-Host "    https://ollama.com/download/windows" -ForegroundColor Cyan
    Write-Host ""
}

Write-Host "  3. En Ollama, descarga un modelo (si no tienes ninguno):" -ForegroundColor Cyan
Write-Host "     PS> ollama pull llama3.2" -ForegroundColor Green
Write-Host ""
Write-Host "  Atajos disponibles:" -ForegroundColor White
Write-Host "    ia               → Abre la interfaz completa" -ForegroundColor Gray
Write-Host "    ia `"pregunta`"   → Investiga directamente" -ForegroundColor Gray
Write-Host "    research         → Alias alternativo" -ForegroundColor Gray
Write-Host ""

pause
