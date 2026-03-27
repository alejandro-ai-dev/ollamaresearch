#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# OllamaResearch — Instalador para Linux y macOS
# Instalación automática sin conocimientos técnicos requeridos
# ═══════════════════════════════════════════════════════════════════════════════

set -e

# ─── Colores ────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ─── Funciones de salida ────────────────────────────────────────────────────
info()    { echo -e "${CYAN}  ℹ  ${NC}$1"; }
success() { echo -e "${GREEN}  ✓  ${NC}$1"; }
warning() { echo -e "${YELLOW}  ⚠  ${NC}$1"; }
error()   { echo -e "${RED}  ✗  ${NC}$1"; }
header()  { echo -e "\n${BOLD}${BLUE}$1${NC}"; }
step()    { echo -e "\n${BOLD}▶ $1${NC}"; }

# ─── Banner ─────────────────────────────────────────────────────────────────
clear
echo -e "${CYAN}"
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║          🔬 OllamaResearch — Instalador                  ║"
echo "  ║     Framework de Deep Research con IA en la Terminal     ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo -e "  ${BOLD}Compatible con:${NC} Linux (Ubuntu, Fedora, Arch) • macOS"
echo ""

# ─── Detectar OS ─────────────────────────────────────────────────────────────
OS="$(uname -s)"
ARCH="$(uname -m)"
info "Sistema detectado: ${OS} / ${ARCH}"

# ─── Paso 1: Verificar Python ─────────────────────────────────────────────────
step "Paso 1/5: Verificando Python"

if command -v python3 &>/dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
    
    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 9 ]; then
        success "Python ${PYTHON_VERSION} encontrado"
        PYTHON_CMD="python3"
    else
        error "Python ${PYTHON_VERSION} es demasiado antiguo. Se requiere Python 3.9+"
        echo ""
        if [ "$OS" = "Darwin" ]; then
            echo "  Instala Python con: brew install python3"
            echo "  O descarga desde: https://python.org/downloads"
        else
            echo "  Ubuntu/Debian: sudo apt install python3.11"  
            echo "  Fedora:        sudo dnf install python3.11"
            echo "  Arch:          sudo pacman -S python"
        fi
        exit 1
    fi
else
    error "Python 3 no encontrado"
    echo ""
    if [ "$OS" = "Darwin" ]; then
        echo "  Instala Python con Homebrew: brew install python3"
        echo "  O visita: https://python.org/downloads"
    else
        echo "  Ubuntu/Debian: sudo apt update && sudo apt install python3 python3-pip"  
        echo "  Fedora:        sudo dnf install python3 python3-pip"
        echo "  Arch:          sudo pacman -S python python-pip"
    fi
    exit 1
fi

# ─── Paso 2: Verificar/Instalar pip ──────────────────────────────────────────
step "Paso 2/5: Verificando pip"

if ! $PYTHON_CMD -m pip --version &>/dev/null; then
    warning "pip no encontrado. Instalando..."
    if [ "$OS" = "Darwin" ]; then
        $PYTHON_CMD -m ensurepip --upgrade 2>/dev/null || brew install python3
    else
        curl -sSL https://bootstrap.pypa.io/get-pip.py | $PYTHON_CMD
    fi
fi

PIP_VERSION=$($PYTHON_CMD -m pip --version 2>&1 | awk '{print $2}')
success "pip ${PIP_VERSION} disponible"

# ─── Paso 3: Instalar/Verificar Ollama ───────────────────────────────────────
step "Paso 3/5: Verificando Ollama"

if command -v ollama &>/dev/null; then
    OLLAMA_VERSION=$(ollama --version 2>&1 | head -1)
    success "Ollama ya está instalado: ${OLLAMA_VERSION}"
else
    warning "Ollama no encontrado. Instalando..."
    echo ""
    
    if [ "$OS" = "Darwin" ]; then
        if command -v brew &>/dev/null; then
            info "Instalando Ollama via Homebrew..."
            brew install ollama
        else
            info "Descargando Ollama para macOS..."
            curl -fsSL https://ollama.com/download/ollama-darwin.zip -o /tmp/ollama.zip
            unzip -o /tmp/ollama.zip -d /usr/local/bin/
            chmod +x /usr/local/bin/ollama
            rm /tmp/ollama.zip
        fi
    else
        info "Descargando e instalando Ollama para Linux..."
        curl -fsSL https://ollama.com/install.sh | bash
    fi
    
    if command -v ollama &>/dev/null; then
        success "Ollama instalado correctamente"
    else
        error "No se pudo instalar Ollama automáticamente"
        echo ""
        echo "  Por favor instala manualmente:"
        echo "  → Visita: https://ollama.com/download"
        echo "  → Linux: curl -fsSL https://ollama.com/install.sh | bash"
        echo "  → macOS: Descarga el .dmg desde ollama.com"
        echo ""
        echo "  Continúa la instalación de OllamaResearch después."
        OLLAMA_MISSING=true
    fi
fi

# ─── Paso 4: Instalar OllamaResearch ─────────────────────────────────────────
step "Paso 4/5: Instalando OllamaResearch"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Intentar instalar con pipx primero (instalación global aislada)
if command -v pipx &>/dev/null; then
    info "Instalando con pipx (aislado del sistema)..."
    pipx install "$SCRIPT_DIR" --force 2>/dev/null || {
        info "Fallback: instalando con pip..."
        $PYTHON_CMD -m pip install "$SCRIPT_DIR" --quiet --user
    }
elif $PYTHON_CMD -m pip install pipx --quiet --user 2>/dev/null; then
    PIPX_CMD="$PYTHON_CMD -m pipx"
    info "Instalando con pipx..."
    $PIPX_CMD install "$SCRIPT_DIR" --force 2>/dev/null || {
        info "Fallback: instalando con pip..."  
        $PYTHON_CMD -m pip install "$SCRIPT_DIR" --quiet --user
    }
else
    info "Instalando con pip..."
    $PYTHON_CMD -m pip install "$SCRIPT_DIR" --quiet --user
fi

success "OllamaResearch instalado correctamente"

# ─── Paso 5: Configurar shortcuts de terminal ──────────────────────────────
step "Paso 5/5: Configurando shortcuts de terminal"

# Detectar archivos de configuración del shell
SHELL_FILES=()
[ -f "$HOME/.bashrc" ]                && SHELL_FILES+=("$HOME/.bashrc")
[ -f "$HOME/.bash_profile" ]          && SHELL_FILES+=("$HOME/.bash_profile")
[ -f "$HOME/.zshrc" ]                 && SHELL_FILES+=("$HOME/.zshrc")
[ -f "$HOME/.profile" ]               && SHELL_FILES+=("$HOME/.profile")
[ -f "$HOME/.config/fish/config.fish" ] && SHELL_FILES+=("$HOME/.config/fish/config.fish")

# Si no hay shells, crear .bashrc
if [ ${#SHELL_FILES[@]} -eq 0 ]; then
    touch "$HOME/.bashrc"
    SHELL_FILES=("$HOME/.bashrc")
fi

ALIAS_BASH='
# OllamaResearch shortcuts — agregado por install.sh
alias ia="python3 -m ollamaresearch"
alias research="python3 -m ollamaresearch"
'

ALIAS_FISH='
# OllamaResearch shortcuts
alias ia "python3 -m ollamaresearch"
alias research "python3 -m ollamaresearch"
'

ADDED=0
for SHELL_FILE in "${SHELL_FILES[@]}"; do
    if grep -q "OllamaResearch shortcuts" "$SHELL_FILE" 2>/dev/null; then
        info "Shortcuts ya presentes en ${SHELL_FILE}"
    else
        if [[ "$SHELL_FILE" == *"fish"* ]]; then
            echo "$ALIAS_FISH" >> "$SHELL_FILE"
        else
            echo "$ALIAS_BASH" >> "$SHELL_FILE"
        fi
        success "Alias añadido a ${SHELL_FILE}"
        ADDED=1
    fi
done

# También intentar agregar al PATH si el binario no está accesible
if ! command -v ia &>/dev/null; then
    # Buscar el binario ollamaresearch
    POSSIBLE_PATHS=(
        "$HOME/.local/bin"
        "$HOME/Library/Python/3.10/bin"
        "$HOME/Library/Python/3.11/bin"
        "$HOME/Library/Python/3.12/bin"
        "/usr/local/bin"
    )
    for path in "${POSSIBLE_PATHS[@]}"; do
        if [ -f "$path/ollamaresearch" ]; then
            for SHELL_FILE in "${SHELL_FILES[@]}"; do
                if ! grep -q "$path" "$SHELL_FILE" 2>/dev/null; then
                    echo "" >> "$SHELL_FILE"
                    echo "export PATH=\"$path:\$PATH\"  # OllamaResearch" >> "$SHELL_FILE"
                fi
            done
            break
        fi
    done
fi

# ─── Resumen final ────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  ✅ ¡Instalación completada exitosamente!${NC}"
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BOLD}  Para usar OllamaResearch:${NC}"
echo ""
echo -e "  ${CYAN}1.${NC} Recarga tu terminal (cierra y abre de nuevo)"
echo -e "     ${YELLOW}o ejecuta:${NC} source ~/.bashrc  ${YELLOW}(ó ~/.zshrc)${NC}"
echo ""  
echo -e "  ${CYAN}2.${NC} Escribe ${BOLD}ia${NC} y presiona Enter:"
echo -e "     ${GREEN}\$${NC} ia"
echo -e "     ${GREEN}\$${NC} ia \"¿qué es la inteligencia artificial?\""
echo ""
if [ "${OLLAMA_MISSING:-false}" = "true" ]; then
    echo -e "  ${YELLOW}⚠  Recuerda instalar Ollama primero:${NC}"
    echo -e "     https://ollama.com/download"
    echo ""
    echo -e "  ${YELLOW}⚠  Y descargar un modelo (por ejemplo):${NC}"
    echo -e "     ${GREEN}\$${NC} ollama pull llama3.2"
    echo ""
else
    echo -e "  ${CYAN}3.${NC} Si es la primera vez, descarga un modelo:"
    echo -e "     ${GREEN}\$${NC} ollama pull llama3.2"
    echo ""
fi
echo -e "  ${BOLD}Atajos disponibles:${NC}"
echo -e "    ${CYAN}ia${NC}               → Abre la interfaz completa"
echo -e "    ${CYAN}ia \"pregunta\"${NC}   → Investiga directamente"
echo -e "    ${CYAN}research${NC}         → Alias alternativo"
echo ""
