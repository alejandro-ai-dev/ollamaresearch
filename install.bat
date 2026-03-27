@echo off
REM ═══════════════════════════════════════════════════════════════════════════════
REM OllamaResearch — Instalador Windows (CMD Batch - fallback)
REM Para usuarios que no tienen PowerShell disponible
REM Doble clic para ejecutar
REM ═══════════════════════════════════════════════════════════════════════════════

title OllamaResearch — Instalador

cls
color 0B
echo.
echo   ============================================================
echo     OllamaResearch -- Instalador para Windows (CMD)
echo     Framework de Deep Research con IA en la Terminal
echo   ============================================================
echo.
echo   RECOMENDADO: Usa install.ps1 con PowerShell para mejor
echo   compatibilidad. Este es un instalador de emergencia.
echo.
echo   Presiona cualquier tecla para continuar...
pause > nul

REM ─── Verificar Python ───────────────────────────────────────────────────────
echo.
echo   [1/4] Verificando Python...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    python3 --version > nul 2>&1
    if %errorlevel% neq 0 (
        echo   ERROR: Python no encontrado.
        echo.
        echo   Instala Python desde: https://www.python.org/downloads
        echo   IMPORTANTE: Marca "Add Python to PATH" durante la instalacion
        echo.
        echo   Abriendo pagina de descarga...
        start https://www.python.org/downloads/windows/
        echo.
        echo   Instala Python, reinicia este instalador.
        pause
        exit /b 1
    ) else (
        set PYTHON_CMD=python3
    )
) else (
    set PYTHON_CMD=python
)

for /f "tokens=2" %%v in ('%PYTHON_CMD% --version 2^>^&1') do set PYTHON_VER=%%v
echo   OK: Python %PYTHON_VER% encontrado

REM ─── Verificar Ollama ───────────────────────────────────────────────────────
echo.
echo   [2/4] Verificando Ollama...
ollama --version > nul 2>&1
if %errorlevel% neq 0 (
    echo   ADVERTENCIA: Ollama no encontrado.
    echo   Descargando instalador de Ollama...
    
    powershell -Command "Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile '%TEMP%\OllamaSetup.exe'"
    if exist "%TEMP%\OllamaSetup.exe" (
        echo   Ejecutando instalador de Ollama...
        start /wait %TEMP%\OllamaSetup.exe /S
        del "%TEMP%\OllamaSetup.exe" 2>nul
        echo   Ollama instalado. Puede requerir reiniciar el sistema.
    ) else (
        echo   No se pudo descargar Ollama automaticamente.
        echo   Descarga manualmente desde: https://ollama.com/download/windows
        start https://ollama.com/download/windows
    )
) else (
    for /f "tokens=*" %%v in ('ollama --version 2^>^&1') do echo   OK: Ollama instalado: %%v
)

REM ─── Instalar OllamaResearch ─────────────────────────────────────────────────
echo.
echo   [3/4] Instalando OllamaResearch...

%PYTHON_CMD% -m pip install "%~dp0" --quiet --user
if %errorlevel% neq 0 (
    echo   ERROR en la instalacion.
    echo   Intentando con --break-system-packages...
    %PYTHON_CMD% -m pip install "%~dp0" --quiet --user --break-system-packages
)
echo   OK: OllamaResearch instalado

REM ─── Configurar acceso directo ───────────────────────────────────────────────
echo.
echo   [4/4] Creando acceso directo en el escritorio...

powershell -Command "$shell = New-Object -ComObject WScript.Shell; $shortcut = $shell.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\OllamaResearch (ia).lnk'); $shortcut.TargetPath = 'cmd.exe'; $shortcut.Arguments = '/k python -m ollamaresearch'; $shortcut.WorkingDirectory = [Environment]::GetFolderPath('UserProfile'); $shortcut.IconLocation = 'shell32.dll,137'; $shortcut.Description = 'OllamaResearch - Deep Research con IA'; $shortcut.Save()"

if %errorlevel% equ 0 (
    echo   OK: Acceso directo creado en el Escritorio
) else (
    echo   ADVERTENCIA: No se pudo crear el acceso directo
)

REM ─── Resumen ─────────────────────────────────────────────────────────────────
echo.
echo   ============================================================
echo     INSTALACION COMPLETADA
echo   ============================================================
echo.
echo   Como usar OllamaResearch:
echo.
echo   Opcion 1: Doble clic en "OllamaResearch (ia)" en el Escritorio
echo.
echo   Opcion 2: En CMD o PowerShell escribe:
echo     python -m ollamaresearch
echo.
echo   Opcion 3: Instala los shortcuts con PowerShell:
echo     powershell -ExecutionPolicy Bypass -File install.ps1
echo.
echo   Para descargar un modelo de IA:
echo     ollama pull llama3.2
echo.

pause
