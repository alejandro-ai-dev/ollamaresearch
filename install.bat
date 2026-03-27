@echo off
REM ═══════════════════════════════════════════════════════════════════════════════
REM OllamaResearch — Instalador Windows (CMD Batch)
REM Doble clic para ejecutar
REM ═══════════════════════════════════════════════════════════════════════════════

title OllamaResearch — Instalador

REM Obtener directorio del script SIN barra final (fix para pip en Windows)
set "INSTALL_DIR=%~dp0"
if "%INSTALL_DIR:~-1%"=="\" set "INSTALL_DIR=%INSTALL_DIR:~0,-1%"

cls
color 0B
echo.
echo   ============================================================
echo     OllamaResearch -- Instalador para Windows
echo     Framework de Deep Research con IA en la Terminal
echo   ============================================================
echo.
echo   Directorio de instalacion: %INSTALL_DIR%
echo.
echo   Presiona cualquier tecla para continuar...
pause > nul

REM ─── [1/5] Verificar Python ──────────────────────────────────────────────────
echo.
echo   [1/5] Verificando Python...

set PYTHON_CMD=
for %%p in (python py python3) do (
    if not defined PYTHON_CMD (
        %%p --version >nul 2>&1
        if not errorlevel 1 (
            set PYTHON_CMD=%%p
        )
    )
)

if not defined PYTHON_CMD (
    echo   ERROR: Python no encontrado.
    echo.
    echo   Instala Python desde: https://www.python.org/downloads
    echo   IMPORTANTE: Marca "Add Python to PATH" durante la instalacion
    echo.
    start https://www.python.org/downloads/windows/
    echo   Instala Python y vuelve a ejecutar este instalador.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('%PYTHON_CMD% --version 2^>^&1') do set PYTHON_VER=%%v
echo   OK: Python %PYTHON_VER% encontrado (%PYTHON_CMD%)

REM ─── [2/5] Verificar entorno virtual ─────────────────────────────────────────
echo.
echo   [2/5] Creando entorno virtual en .venv ...

if exist "%INSTALL_DIR%\.venv\Scripts\python.exe" (
    echo   OK: Entorno virtual ya existe, usando el existente.
) else (
    %PYTHON_CMD% -m venv "%INSTALL_DIR%\.venv"
    if errorlevel 1 (
        echo   ERROR: No se pudo crear el entorno virtual.
        echo   Intenta ejecutar este instalador como Administrador.
        pause
        exit /b 1
    )
    echo   OK: Entorno virtual creado.
)

set VENV_PYTHON="%INSTALL_DIR%\.venv\Scripts\python.exe"
set VENV_PIP="%INSTALL_DIR%\.venv\Scripts\pip.exe"

REM ─── [3/5] Verificar/Instalar Ollama ─────────────────────────────────────────
echo.
echo   [3/5] Verificando Ollama...

ollama --version >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=*" %%v in ('ollama --version 2^>^&1') do echo   OK: Ollama instalado: %%v
    goto instalar_paquete
)

echo   Ollama no encontrado. Descargando instalador...
powershell -Command "try { Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile '%TEMP%\OllamaSetup.exe' -UseBasicParsing; Write-Host 'OK' } catch { Write-Host 'ERROR' }"

if exist "%TEMP%\OllamaSetup.exe" (
    echo   Ejecutando instalador de Ollama (proceso silencioso)...
    start /wait "%TEMP%\OllamaSetup.exe" /S
    del "%TEMP%\OllamaSetup.exe" 2>nul
    echo   Ollama instalado. Puede requerir reiniciar la terminal.
) else (
    echo   No se pudo descargar Ollama automaticamente.
    echo   Descarga manualmente: https://ollama.com/download/windows
    start https://ollama.com/download/windows
    echo   Continua la instalacion sin Ollama (instala Ollama despues).
)

:instalar_paquete
REM ─── [4/5] Instalar OllamaResearch en el venv ────────────────────────────────
echo.
echo   [4/5] Instalando OllamaResearch...
echo   (Esto puede tardar 1-3 minutos descargando dependencias)
echo.

REM Actualizar pip primero dentro del venv
%VENV_PYTHON% -m pip install --upgrade pip --quiet

REM Instalar el paquete desde el directorio actual
%VENV_PYTHON% -m pip install "%INSTALL_DIR%" --quiet

if errorlevel 1 (
    echo.
    echo   ERROR en instalacion silenciosa. Intentando con salida detallada...
    %VENV_PYTHON% -m pip install "%INSTALL_DIR%"
    if errorlevel 1 (
        echo.
        echo   ERROR: No se pudo instalar OllamaResearch.
        echo   Por favor reporta este error en:
        echo   https://github.com/alejandro-ai-dev/ollamaresearch/issues
        pause
        exit /b 1
    )
)

echo   OK: OllamaResearch instalado correctamente.

REM ─── [5/5] Crear lanzadores ──────────────────────────────────────────────────
echo.
echo   [5/5] Creando accesos directos...

REM Crear script lanzador ia.bat en la carpeta del proyecto
echo @echo off > "%INSTALL_DIR%\ia.bat"
echo title OllamaResearch >> "%INSTALL_DIR%\ia.bat"
echo "%INSTALL_DIR%\.venv\Scripts\python.exe" -m ollamaresearch %%* >> "%INSTALL_DIR%\ia.bat"

REM Crear acceso directo en el escritorio
powershell -Command ^
    "$shell = New-Object -ComObject WScript.Shell; ^
     $shortcut = $shell.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\OllamaResearch (ia).lnk'); ^
     $shortcut.TargetPath = '%INSTALL_DIR%\ia.bat'; ^
     $shortcut.WorkingDirectory = '%INSTALL_DIR%'; ^
     $shortcut.IconLocation = 'shell32.dll,137'; ^
     $shortcut.Description = 'OllamaResearch - Deep Research con IA'; ^
     $shortcut.Save()"

if not errorlevel 1 (
    echo   OK: Acceso directo creado en el Escritorio
) else (
    echo   ADVERTENCIA: No se pudo crear el acceso directo
)

REM Intentar agregar carpeta al PATH del usuario
powershell -Command "[Environment]::SetEnvironmentVariable('PATH', [Environment]::GetEnvironmentVariable('PATH', 'User') + ';%INSTALL_DIR%', 'User')" 2>nul
echo   OK: Carpeta agregada al PATH del usuario

REM ─── Resumen ─────────────────────────────────────────────────────────────────
echo.
echo   ============================================================
echo     INSTALACION COMPLETADA EXITOSAMENTE
echo   ============================================================
echo.
echo   COMO USAR OllamaResearch:
echo.
echo   Opcion 1: Doble clic en "OllamaResearch (ia)" en el Escritorio
echo.
echo   Opcion 2: Abre CMD o PowerShell y escribe:
echo     ia
echo.
echo     (Si 'ia' no funciona, cierra y abre una nueva ventana de CMD)
echo.
echo   Opcion 3: Ruta completa:
echo     "%INSTALL_DIR%\ia.bat"
echo.
echo   Para descargar un modelo de IA (en CMD):
echo     ollama pull llama3.2
echo.
echo   NOTA: Si es la primera vez, descarga un modelo antes de usar ia.
echo.

pause
