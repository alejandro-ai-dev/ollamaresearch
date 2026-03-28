@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title OllamaResearch — Instalador Windows (CMD)

:: ═══════════════════════════════════════════════════════════════════════════════
:: OllamaResearch — Instalador para Windows (CMD / Símbolo del sistema)
:: Uso: Doble clic en install.bat  -O-  desde CMD: install.bat
:: Compatible con Windows 10 y Windows 11
:: ═══════════════════════════════════════════════════════════════════════════════

echo.
echo   =============================================================
echo     OllamaResearch — Instalador Windows (CMD)
echo     Framework de Deep Research con IA en la Terminal
echo   =============================================================
echo.
echo   Compatible con: Windows 10, Windows 11
echo.

:: Guardar directorio del script (siempre relativo al .bat)
set "SCRIPT_DIR=%~dp0"
:: Quitar barra final
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

set "VENV_DIR=%SCRIPT_DIR%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "VENV_PIP=%VENV_DIR%\Scripts\pip.exe"

:: ─── Paso 1: Buscar Python ─────────────────────────────────────────────────
echo [1/5] Buscando Python 3.9+ ...
echo.

set "PYTHON_CMD="

:: Intentar "python"
python --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
    echo   [OK] python encontrado: !PY_VER!
    set "PYTHON_CMD=python"
    goto :python_found
)

:: Intentar "python3"
python3 --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=2" %%v in ('python3 --version 2^>^&1') do set "PY_VER=%%v"
    echo   [OK] python3 encontrado: !PY_VER!
    set "PYTHON_CMD=python3"
    goto :python_found
)

:: Intentar "py" (Python Launcher de Windows)
py --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=2" %%v in ('py --version 2^>^&1') do set "PY_VER=%%v"
    echo   [OK] py encontrado: !PY_VER!
    set "PYTHON_CMD=py"
    goto :python_found
)

echo   [ERROR] Python 3.9+ no encontrado en el PATH.
echo.
echo   Opciones para instalar Python:
echo     1. Microsoft Store: busca "Python 3.12"
echo     2. Sitio oficial:   https://python.org/downloads
echo     3. Winget:          winget install Python.Python.3.12
echo.
echo   IMPORTANTE: Al instalar, marca la opcion "Add Python to PATH"
echo.
set /p "OPEN_BROWSER=   Abrir pagina de descarga de Python? (S/N): "
if /i "%OPEN_BROWSER%"=="S" start https://www.python.org/downloads/windows/
echo.
echo   Instala Python, cierra esta ventana y vuelve a ejecutar install.bat
pause
exit /b 1

:python_found

:: ─── Paso 2: Verificar pip ─────────────────────────────────────────────────
echo.
echo [2/5] Verificando pip ...
%PYTHON_CMD% -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   pip no encontrado. Instalando...
    %PYTHON_CMD% -m ensurepip --upgrade
)
echo   [OK] pip disponible

:: ─── Paso 3: Verificar Ollama ───────────────────────────────────────────────
echo.
echo [3/5] Verificando Ollama ...
ollama --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%v in ('ollama --version 2^>^&1') do set "OLLAMA_VER=%%v"
    echo   [OK] Ollama instalado: !OLLAMA_VER!
    set "OLLAMA_OK=1"
) else (
    echo   [AVISO] Ollama no encontrado.
    echo   Descargalo desde: https://ollama.com/download/windows
    set "OLLAMA_OK=0"
    echo.
    set /p "OPEN_OLLAMA=   Abrir pagina de descarga de Ollama? (S/N): "
    if /i "!OPEN_OLLAMA!"=="S" start https://ollama.com/download/windows
)

:: ─── Paso 4: Crear venv e instalar OllamaResearch ───────────────────────────
echo.
echo [4/5] Instalando OllamaResearch ...
echo   Directorio: %SCRIPT_DIR%
echo.

:: Verificar si el venv existe y es valido
if exist "%VENV_PYTHON%" (
    echo   Entorno virtual encontrado (.venv)
) else (
    :: Si el directorio existe pero python.exe no, borrarlo y recrear
    if exist "%VENV_DIR%" (
        echo   Entorno virtual corrupto. Recreando...
        rmdir /s /q "%VENV_DIR%"
    ) else (
        echo   Creando entorno virtual (.venv)...
    )
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo.
        echo   [ERROR] No se pudo crear el entorno virtual.
        echo   Intenta ejecutar install.bat como Administrador.
        pause
        exit /b 1
    )
    echo   [OK] Entorno virtual creado
)

:: Actualizar pip dentro del venv
echo.
echo   Actualizando pip...
"%VENV_PYTHON%" -m pip install --upgrade pip --quiet
echo   [OK] pip actualizado

:: Instalar/actualizar el paquete (--upgrade fuerza reinstalacion si ya existe)
echo.
echo   Instalando dependencias (puede tardar 2-4 minutos la primera vez)...
echo   Por favor espera...
echo.
"%VENV_PYTHON%" -m pip install --upgrade "%SCRIPT_DIR%" --quiet

if %errorlevel% neq 0 (
    echo.
    echo   Reintentando con salida detallada...
    echo.
    "%VENV_PYTHON%" -m pip install --upgrade "%SCRIPT_DIR%"
    if %errorlevel% neq 0 (
        echo.
        echo   [ERROR] No se pudo instalar OllamaResearch.
        echo   Intenta ejecutar install.bat como Administrador.
        pause
        exit /b 1
    )
)

echo   [OK] OllamaResearch instalado y actualizado

:: ─── Paso 5: Crear lanzadores ───────────────────────────────────────────────
echo.
echo [5/5] Creando lanzadores ...

:: Crear ia.bat en la carpeta del proyecto
set "IA_BAT=%SCRIPT_DIR%\ia.bat"
(
    echo @echo off
    echo title OllamaResearch
    echo "%VENV_PYTHON%" -m ollamaresearch %%*
) > "%IA_BAT%"
echo   [OK] Lanzador creado: ia.bat

:: Crear acceso directo en el Escritorio usando VBScript
set "DESKTOP=%USERPROFILE%\Desktop"
set "SHORTCUT_VBS=%TEMP%\create_shortcut.vbs"

(
    echo Set oWS = WScript.CreateObject("WScript.Shell"^)
    echo sLinkFile = "%DESKTOP%\OllamaResearch (ia).lnk"
    echo Set oLink = oWS.CreateShortcut(sLinkFile^)
    echo oLink.TargetPath = "%IA_BAT%"
    echo oLink.WorkingDirectory = "%SCRIPT_DIR%"
    echo oLink.Description = "OllamaResearch - Deep Research con IA"
    echo oLink.IconLocation = "shell32.dll,137"
    echo oLink.Save
) > "%SHORTCUT_VBS%"

cscript //nologo "%SHORTCUT_VBS%" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Acceso directo creado en el Escritorio
) else (
    echo   [AVISO] No se pudo crear el acceso directo (no critico)
)
del "%SHORTCUT_VBS%" >nul 2>&1

:: Agregar directorio al PATH del usuario (permanente)
echo   Agregando directorio al PATH...
for /f "skip=2 tokens=3*" %%a in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "USER_PATH=%%a %%b"
echo !USER_PATH! | findstr /i "%SCRIPT_DIR%" >nul 2>&1
if %errorlevel% neq 0 (
    setx PATH "%SCRIPT_DIR%;!USER_PATH!" >nul 2>&1
    echo   [OK] Directorio agregado al PATH
) else (
    echo   [OK] Ya estaba en el PATH
)

:: ─── Resumen final ──────────────────────────────────────────────────────────
echo.
echo   =============================================================
echo     Instalacion completada exitosamente!
echo   =============================================================
echo.
echo   Para usar OllamaResearch:
echo.
echo   1. Cierra y vuelve a abrir CMD o PowerShell
echo.
echo   2. Escribe "ia" y presiona Enter:
echo      C:\> ia
echo      C:\> ia "que es la inteligencia artificial?"
echo.
echo   3. O haz doble clic en el acceso directo del Escritorio
echo.

if "%OLLAMA_OK%"=="0" (
    echo   AVISO: Recuerda instalar Ollama primero:
    echo     https://ollama.com/download/windows
    echo.
)

echo   4. Si no tienes modelos descargados aun, abre una terminal y escribe:
echo      ollama pull llama3.2
echo.
echo   Atajos disponibles:
echo     ia                   Abre la interfaz completa
echo     ia "pregunta"        Investiga directamente
echo     research             Alias alternativo
echo.

pause
endlocal
