# Qué se ha dejado fuera (y dónde sigue)

Este repositorio es la versión limpia y propia de Centro Turing. Se creó desde
cero con **solo lo que se usa hoy**: el panel, el monitor, los sensores, nuestros
temas ES y las herramientas de instalación/empaquetado.

El repositorio anterior (`E:\turing-smart-screen-python`, rama `windows-es-1.1`)
**no se ha tocado**: sigue completo, con todo el legado, y sirve de archivo. Ahí
queda también un punto de seguridad antes de esta limpieza:

- Commit **`ba2195a`** — *«WIP: estado completo antes de crear Centro Turing»*.
- Rama **`respaldo/antes-de-limpiar`** — apunta a ese mismo commit.
- Commit anterior sin esos cambios: **`3e595f4`**.

## No copiado: variantes antiguas del panel

| Qué | Por qué |
| --- | --- |
| `tools/centro_turing.py` (v2.3, 701 líneas) | Sustituido por `tools/turing_center.py` (3.3.0), que ya cubre todo |
| `tools/centro_pro/` + `centro_pro_main.py` ("Centro Turing Pro, Fase 1") | Prototipo abandonado; el panel actual hace lo mismo |
| `tools/PantallaTuringUI.cs`, `LaunchTuring.cs`, `CentroTuringLauncher.cs` (+ `.bak-*`) | Lanzadores C# duplicaban el panel y abrían dos procesos (fallos de COM3) |
| `tools/centro_ui.json`, `tools/pantalla-turing-ui.json` | Estado que guardaban esos lanzadores |
| `Centro-Turing-3.cmd`, `Cambiar-Tema.ps1`, `Elegir-Tema.bat`, `tools/elegir-tema.py` | Formas antiguas de abrir/cambiar tema; el panel ya lo hace |

## No copiado: generadores de un solo uso

`tools/build_quantum.py`, `tools/build_synapse.py`, `tools/build_es_themes.py`,
`tools/gen_clima.py`, `tools/gen_horiz_themes.py`, `tools/gen_nuevos_temas.py`,
`tools/fix_onepiece_stats.py`, `tools/fix-theme-display-size.ps1`,
`tools/traducir_temas.py`, `tools/portrait_to_landscape.py`,
`tools/compare-images.py`, `tools/theme-preview-generator.py`,
`tools/turing-theme-extractor.py`, `tools/es_textures/`.

Generaron temas y ajustes que ya están dentro del repositorio. Si hay que
regenerar algo, están en el repo antiguo.

## No copiado: restos del proyecto original

| Qué | Por qué |
| --- | --- |
| `configure.py.no-usar` | El panel sustituye a la interfaz de configuración original |
| `theme-editor.py`, `simple-program.py` | Ejemplos/editor del proyecto original; el panel previsualiza y `--mockup` exporta pantallas |
| `turing-system-monitor.spec`, `-debug.spec`, `tools/windows-installer/` | Empaquetado antiguo de Windows; usamos `centro-turing.spec` |
| `.github/`, `tests/` | CI y tests del proyecto original: dependen de ficheros que ya no usamos |
| `README.md` original, `README-WINDOWS-ES.md`, `LEEME-WINDOWS.md`, `README-LINUX.md`, `COMUNIDAD-TEMAS.txt` | Documentación obsoleta (hablaba de `Centro-Turing.bat` y `PantallaTuring.exe`); reescrita en `README.md` |
| `res/themes/<73 temas originales>` | Se han traído solo nuestros temas (68): los del proyecto original eran de otros tamaños/estilos |
| `res/fonts/` (GlowSansSC, SourceHanSansCN, BoutiqueBitmap9x9, …) | 180 MB de fuentes CJK que nuestros temas no usan |
| `*.bak*`, `background_original.*`, `*.xcf`, `screencap.png`, `log.log`, `build/`, `dist/`, `venv/`, `dist-lanzadores/`, `tmp/` (scripts sueltos) | Restos de trabajo y artefactos |

## Diferencias de comportamiento

- **Un único punto de entrada**: el panel (`tools/turing_center.py`, también como
  `dist\Centro-Turing-*.exe`). Antes había tres formas distintas de abrirlo.
- **La bandeja del monitor** (`main.py`) abre *nuestro* panel; antes buscaba
  `PantallaTuring.exe` y `configure.py`, que ya no existen.
- **`centro-turing.sh`** (Linux) lanzaba el panel antiguo v2.3; ahora lanza el actual.
- **`tools/build_deb.py`** ya no empaqueta el menú de texto `turing-menu`
  (`scripts/` no existe); el `.deb` instala solo el panel.
- **Rutas**: el panel busca el proyecto en `E:\centro-turing`, `/opt/centro-turing`,
  `/usr/share/centro-turing` o la carpeta del ejecutable.

¿Falta algo de esta lista? Está en el repo antiguo: se puede copiar cuando haga
falta.
