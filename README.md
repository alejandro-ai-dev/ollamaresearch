# 🔬 OllamaResearch

> **Framework de Deep Research con IA en la Terminal**  
> Multi-plataforma • Linux • macOS • Windows

<div align="center">

```
  ╔══════════════════════════════════════════════════════════╗
  ║          🔬 OllamaResearch                               ║
  ║     Deep Research con IA • Búsqueda Web en Vivo         ║
  ╚══════════════════════════════════════════════════════════╝
```

</div>

OllamaResearch es una herramienta de investigación profunda que combina **modelos de IA locales de Ollama** con **búsqueda web en tiempo real**. Diseñado para ser extremadamente fácil de instalar y usar, incluso para personas sin experiencia técnica.

---

## ✨ Características

- 🔬 **Deep Research** — Investigación iterativa con múltiples búsquedas y síntesis inteligente
- 🌐 **Búsqueda Web en Vivo** — DuckDuckGo (gratis, sin API key) + soporte para Tavily y Serper
- 🤖 **Modelos Locales y del Catálogo** — Usa modelos instalados o descarga nuevos desde Ollama
- 💻 **Interfaz TUI** — Interfaz visual completa dentro de la terminal (no se necesita navegador)
- ⌨️ **Shortcut `ia`** — Lánzalo con solo escribir `ia` en la terminal
- 🔄 **Streaming en tiempo real** — Ve la respuesta generarse palabra por palabra
- 💾 **Guarda resultados** — Exporta informes en Markdown
- 🌍 **Multi-plataforma** — Linux, macOS y Windows

---

## 🚀 Instalación Rápida

> **Nota:** OllamaResearch se distribuye compartiendo la carpeta del proyecto (o en formato ZIP).  
> No está publicado en PyPI ni en un repositorio público por el momento.

---

### Opción 1 — Desde la carpeta del proyecto (recomendado)

Si ya tienes la carpeta `ollamaresearch/`, simplemente ejecuta el instalador:

```bash
cd /ruta/a/ollamaresearch
bash install.sh
```

El instalador hará todo automáticamente:
✅ Verifica Python → ✅ Instala Ollama (si no existe) → ✅ Instala dependencias → ✅ Configura el alias `ia`

---

### Opción 2 — Desde un archivo ZIP

1. Recibe o descarga el archivo `ollamaresearch.zip`
2. Descomprímelo:
   ```bash
   unzip ollamaresearch.zip
   cd ollamaresearch
   ```
3. Ejecuta el instalador:
   ```bash
   bash install.sh
   ```
4. Recarga tu terminal:
   ```bash
   source ~/.zshrc   # o source ~/.bashrc
   ```
5. ¡Listo! Escribe `ia` para abrir la interfaz.

---

### Instalación manual (con venv)

Si prefieres instalar manualmente sin el script:

```bash
cd ollamaresearch
python3 -m venv .venv
.venv/bin/pip install -e .
# Luego agrega a tu shell:
echo 'alias ia="/ruta/completa/a/ollamaresearch/.venv/bin/ia"' >> ~/.zshrc
source ~/.zshrc
```

---

### Windows

1. Descomprime el ZIP o copia la carpeta `ollamaresearch/`
2. Haz **doble clic** en `install.bat`  
   O en PowerShell:
   ```powershell
   powershell -ExecutionPolicy Bypass -File install.ps1
   ```
3. Cierra y reabre PowerShell
4. Escribe `ia` para iniciar

---

## 📖 Uso

### Interfaz completa (TUI)

```bash
ia
```

### Investigar directamente

```bash
ia "¿Qué es la computación cuántica?"
ia "Últimos avances en inteligencia artificial 2024"
ia "¿Cómo funciona CRISPR?"
```

### Opciones avanzadas

```bash
ia --model llama3.2          # Usar modelo específico
ia --mode chat               # Modo chat simple
ia --mode search             # Búsqueda web rápida
ia --mode research           # Deep research (default)
ia --host http://remoto:11434  # Ollama remoto
ia --list-models             # Ver modelos instalados
ia --version                 # Ver versión
```

---

## 🎮 Atajos dentro de la interfaz

| Tecla | Acción |
|-------|--------|
| `Enter` | Enviar pregunta |
| `Ctrl+M` | Cambiar modelo |
| `Ctrl+N` | Nueva sesión |
| `Ctrl+L` | Limpiar pantalla |
| `Ctrl+C` | Copiar respuesta al portapapeles |
| `Ctrl+S` | Guardar respuesta en archivo |
| `Ctrl+Q` | Salir |
| `F1` | Ayuda |

---

## 🔬 Modos de uso

### Deep Research (default)
El agente realiza investigación iterativa:
1. **Analiza** tu pregunta con el LLM
2. **Genera** sub-consultas de búsqueda
3. **Busca** en DuckDuckGo (o Tavily/Serper)
4. **Extrae** contenido de las páginas web
5. **Sintetiza** con el modelo de IA
6. **Identifica gaps** y repite si necesita más información
7. **Genera** un informe final en Markdown con fuentes citadas

### Chat
Conversación directa con el modelo seleccionado. Historial de conversación incluido.

### Búsqueda Rápida
Busca en la web y el LLM resume los resultados. Más rápido que Deep Research.

---

## ⚙️ Configuración

Presiona el botón `⚙️ Configuración` en la pantalla inicial o:

```bash
ia --config
```

### Configuración disponible

| Opción | Descripción | Default |
|--------|-------------|---------|
| Ollama Host | URL del servidor Ollama | `http://localhost:11434` |
| Motor de búsqueda | DuckDuckGo / Tavily / Serper | DuckDuckGo |
| Tavily API Key | Para usar Tavily (opcional) | Vacío |
| Serper API Key | Para usar Serper (opcional) | Vacío |
| Profundidad | light / medium / deep | medium |
| Máx. fuentes | Fuentes por iteración | 8 |

Configuración guardada en:
- **Linux**: `~/.config/ollamaresearch/config.json`
- **macOS**: `~/Library/Application Support/ollamaresearch/config.json`
- **Windows**: `%APPDATA%\ollamaresearch\config.json`

---

## 📦 Requisitos

- **Python** 3.9 o superior
- **Ollama** instalado (se instala automáticamente con `install.sh` / `install.ps1`)
- Al menos un modelo de Ollama descargado

### Modelos recomendados

| Modelo | Tamaño | Recomendado para |
|--------|--------|-----------------|
| `llama3.2:3b` | ~2GB | Máquinas con poca RAM |
| `llama3.2:latest` | ~2GB | Uso general, rápido |
| `gemma2:9b` | ~5GB | Alta calidad, balanceado |
| `deepseek-r1:7b` | ~4GB | Tareas de razonamiento |
| `llama3.1:8b` | ~5GB | El más completo en 8B |

Descargar un modelo:
```bash
ollama pull llama3.2
ollama pull gemma2:9b
```

---

## 🛠️ Motores de búsqueda

### DuckDuckGo (default) — Gratuito
- Sin API key requerida
- Resultados de calidad
- Funciona inmediatamente

### Tavily — Optimizado para AI
- Requiere API key gratuita en [tavily.com](https://tavily.com)
- 1,000 búsquedas/mes gratis
- Mejor calidad de resultados para investigación

### Serper — Resultados de Google
- Requiere API key en [serper.dev](https://serper.dev)
- Resultados de Google
- ~$50/mes para uso intensivo

---

## 📁 Estructura del proyecto

```
ollamaresearch/
├── install.sh          → Instalador Linux/macOS
├── install.ps1         → Instalador Windows (PowerShell)  
├── install.bat         → Instalador Windows (CMD)
├── pyproject.toml      → Configuración del paquete
└── ollamaresearch/
    ├── cli.py          → Entrada principal (comando `ia`)
    ├── core/
    │   ├── ollama_client.py    → Cliente Ollama
    │   ├── search_engine.py   → Motor de búsqueda
    │   ├── web_scraper.py     → Extractor de contenido
    │   └── research_agent.py  → Agente Deep Research
    ├── tui/
    │   ├── app.py             → App principal Textual
    │   └── screens/
    │       ├── model_selector.py  → Selección de modelo
    │       ├── research_view.py   → Vista principal
    │       └── settings.py        → Configuración
    └── utils/
        └── config.py          → Gestión de configuración
```

---

## 🔧 Desarrollo / Contribuir

```bash
# Desde la carpeta del proyecto
cd ollamaresearch

# Instalar en modo desarrollo (con entorno virtual)
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# Ejecutar directamente
.venv/bin/python -m ollamaresearch

# O con el alias instalado
ia
```

### Publicar en GitHub (opcional)

Si quieres compartir el proyecto públicamente:

```bash
# 1. Crear repositorio en github.com (botón "New repository")
# 2. Luego desde la carpeta del proyecto:
cd /ruta/a/ollamaresearch
git init
git add .
git commit -m "Initial commit — OllamaResearch v1.0.0"
git remote add origin https://github.com/TU_USUARIO/ollamaresearch.git
git push -u origin main
```

> Reemplaza `TU_USUARIO` con tu nombre de usuario de GitHub.

---

## 📄 Licencia

MIT License — Libre para uso personal y comercial.

---

## 🙏 Tecnologías usadas

- [Textual](https://github.com/Textualize/textual) — Framework TUI
- [Ollama](https://ollama.com) — Motor de modelos de IA
- [DuckDuckGo Search](https://github.com/deedy5/duckduckgo_search) — Búsqueda web gratuita
- [httpx](https://www.python-httpx.org/) — Cliente HTTP async
- [BeautifulSoup4](https://beautiful-soup-4.readthedocs.io/) — Extracción de contenido web
- [Rich](https://github.com/Textualize/rich) — Formato de texto en terminal
