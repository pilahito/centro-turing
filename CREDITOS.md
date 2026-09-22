# Créditos y licencias

Centro Turing es **software libre (GPL-3.0-or-later)**. Este proyecto es una
versión propia del monitor de mini pantallas USB de la comunidad; sin el trabajo
de las personas que aparecen abajo no existiría.

## Proyecto original

- **turing-smart-screen-python** — monitor y librería para pantallas USB-C tipo
  Turing Smart Screen / XuanFang: <https://github.com/mathoudebine/turing-smart-screen-python>
- Autor y mantenedor: **Matthieu Houdebine** ([@mathoudebine](https://github.com/mathoudebine)),
  © 2021.
- Colaboradores principales (lista completa en [`AUTHORS`](AUTHORS)): Ebag333,
  Charles Ferguson (@gerph), Russ Nelson (@RussNelson), Rollback (@Rollbacke),
  w1ld3r, y el resto de contribuciones que constan en el historial de git.
- Licencia: **GNU GPL v3.0 o posterior** ([`LICENSE`](LICENSE), [`COPYRIGHT`](COPYRIGHT)).
- Gran parte de `main.py` y de `library/` (comunicación serie, protocolos rev A/B/C/D,
  sensores, planificador y temas base) procede de ese proyecto, con modificaciones
  nuestras.

## Nuestra parte (Centro Turing)

Añadido o reescrito en esta versión, bajo la misma licencia GPL-3.0-or-later:

- **Panel Centro Turing** (`tools/turing_center.py`), interfaz 2026
  (`tools/turing_ui2026.py`) y sistema de diseño (`tools/turing_design.py`).
- **Foro español**: temas `*ES` y variantes horizontales, textos y clima en
  español (Open-Meteo), `docs/SENSORES-ES.md`.
- **Sensores y estadísticas propias** en `library/stats.py`, `library/config.py`
  y `library/sensors/`.
- **Lanzadores y empaquetado**: `Iniciar.ps1`, `Iniciar-Admin.ps1`,
  `Instalar.ps1`, `iniciar.sh`, `centro-turing.sh`, `Centro-Turing.cmd`,
  `tools/lanzar.py`, `tools/build_deb.py`, `centro-turing.spec`.
- Autor: **pilahito (David)** — <https://github.com/pilahito>

## Terceros incluidos en `external/`

| Componente | Licencia | Fichero |
| --- | --- | --- |
| LibreHardwareMonitor | Mozilla Public License 2.0 | `external/LibreHardwareMonitor/LICENSE` |
| libusb 1.0 | GNU LGPL 2.1 | `external/libusb-1.0/COPYING` |
| PawnIO | GNU GPL 2.0 | `external/PawnIO/LICENSE` |

## Fuentes (`res/fonts/`)

| Familia | Licencia | Fichero |
| --- | --- | --- |
| Roboto, Roboto Mono | Apache License 2.0 | `res/fonts/roboto/LICENSE.txt`, `res/fonts/roboto-mono/LICENSE.txt` |
| JetBrains Mono | SIL Open Font License 1.1 | `res/fonts/jetbrains-mono/OFL.txt` |
| Generale Mono | ver licencia incluida | `res/fonts/generale-mono/LICENSE.txt` |
| GeForce | uso libre del autor original (fuente de NVIDIA) | — |

## Servicios externos

- **Open-Meteo** (<https://open-meteo.com>) para el clima sin clave de API. Si
  prefieres OpenWeatherMap, pon tu clave en `config.yaml` (`WEATHER_API_KEY`).

## Nota sobre la licencia

Al ser un trabajo derivado de código GPL-3.0, **Centro Turing se distribuye
también bajo GPL-3.0-or-later**: puedes usarlo, estudiarlo, modificarlo y
redistribuirlo, siempre manteniendo esta licencia, los avisos de copyright y los
créditos de arriba. El panel lo resume en su ventana: *«Gratis y libre · GPL-3.0
· sin candados»*.
