# Cambios

## 3.3.1 — 2026-10-09

Sensores corregidos (comprobado contra psutil y nvidia-smi en un equipo real):

- El disco muestra la unidad del sistema (C:) y no la unidad desde la que se
  ejecuta el programa.
- La RAM usada y los datos de red se calculan en GiB reales; antes salían
  un 7 % más bajos.
- Más contraste en `TablonPolaroid_H` y `HudPlataformas_H`.

Generador de temas con IA: el modo nuevo **taller** (`tools/taller_ia.py`) hace
los temas de 3,5" horizontal igual que los de 3.2.1–3.3.0:

- La IA elige un arquetipo de disposición que no se haya usado y un estilo, y
  describe un fondo dibujado con primitivas (degradados, astros, montañas,
  rejillas, paneles, biseles…), las etiquetas en español y la caja exacta de
  cada widget (hora según `CLOCK_FORMAT`, tiempo con sensación y humedad, CPU,
  GPU con VRAM, RAM, disco y red).
- Las herramientas del taller dibujan el fondo, escriben `theme.yaml` y pintan
  la vista previa con los valores más largos (`12:59 p. m.`,
  `Parcialmente nublado`, `131072 M`, `1023.9 MB/s`, `100°C`…).
- Revisión automática: texto que no cabe en su caja (igual que `library/lcd`),
  solapes, etiquetas pegadas a un valor, contraste bajo, fondo cargado bajo un
  texto, radiales fuera de pantalla y disposición repetida. Los fallos se le
  devuelven a la IA y se reintenta (hasta 4 veces); si no sale, se usa el
  generador anterior.
- Se elige un modelo local instruct/coder y se descartan los modelos que Jan
  reenvía a servicios externos. Aviso en el registro si se usa DeepSeek (de pago).
- `CENTRO_TURING_IA_TALLER=0` desactiva el taller; `CENTRO_TURING_IA_ESPERA`
  cambia el tiempo máximo por respuesta.
- `python3 tools/taller_ia.py --revisar diseno.json vista.png` revisa un diseño a mano.
- Más contraste en `TablonPolaroid_H` y `HudPlataformas_H`.


## 3.3.0 — 2026-10-09

Veinte temas retro de 3,5" en horizontal (480×320), con estilos y
disposiciones que no se habían usado: ventana de escritorio de los 90,
pantalla de configuración azul, consola de bolsillo, marcador de plataformas,
televisor con carta de ajuste, casete con vúmetro, vídeo doméstico con REC,
atardecer synthwave, equipo hi-fi de madera con agujas, tubos nixie,
calculadora LCD, teletexto, arranque BASIC de 8 bits, pantalla de pinball,
gramola, periódico antiguo, menú de rol de 8 bits, reloj de paletas,
osciloscopio y tablón de corcho con fotos. Español, reloj según
`CLOCK_FORMAT`, tiempo Open-Meteo, CPU, GPU (uso, temperatura y VRAM), RAM,
disco y red. Fondos dibujados desde cero, sin personajes ni logotipos con
copyright. No cambia el tema activo de `config.yaml`.

- Ordenadores: `Ventana95_H`, `PantallaBIOS_H`, `ArranqueBasic_H`, `Teletexto_H`.
- Consolas y juegos: `BolsilloGB_H`, `HudPlataformas_H`, `PinballDMD_H`, `MenuRPG_H`.
- Imagen y sonido: `CartaAjuste_H`, `CintaCasete_H`, `GrabandoVHS_H`, `HifiMadera_H`, `Jukebox_H`.
- Aparatos: `TubosNixie_H`, `CalculadoraLCD_H`, `RelojFlip_H`, `Osciloscopio_H`.
- Estética: `Synthwave80_H`, `PeriodicoAntiguo_H`, `TablonPolaroid_H`.


## 3.2.2 — 2026-10-08

Veinte temas nuevos de 3,5" en horizontal (480×320), además de los de 3.2.1.
Cada uno tiene una disposición distinta (no es un cambio de color): reloj
gigante, lista lateral, tiempo dominante, barra de medidores, cuatro esferas,
esquinas HUD, diagonal, gráficas de historial, consola, chips, anillo, tres
columnas, bahías, perímetro, teletipo, tacómetro, marcador, bandas, bloque
asimétrico y marquesina. Español, reloj según `CLOCK_FORMAT`, tiempo Open-Meteo,
CPU, GPU (uso, temperatura y VRAM), RAM, disco y red. Fondos dibujados, sin
personajes con copyright. No cambia el tema activo de `config.yaml`.

- Anime: `CerezoLuna_H`, `EscenarioIdol_H`, `NubeKawaii_H`, `SumiEspada_H`, `CabinaMecha_H`.
- Cyberpunk: `ReticulaNeon_H`, `DiagonalNC_H`, `GraficaLluvia_H`, `ConsolaFallo_H`.
- Técnica: `ChipDorado_H`, `AnilloHolo_H`, `ColumnasMatrix_H`, `BahiasRack_H`, `SatelitePlano_H`.
- Otros: `SolVapor_H`, `TacometroRace_H`, `MarcadorPixel_H`, `BandasMar_H`, `AsimetricaNebula_H`, `MarquesinaArcade_H`.


## 3.2.1 — 2026-10-08

Veinte temas nuevos de 3,5" en horizontal (480×320), en español, con reloj
según `CLOCK_FORMAT` y tiempo en vivo (Open-Meteo). Cada uno trae CPU, GPU
(uso, temperatura y VRAM), RAM, disco y red, y el fondo está dibujado (no es
una pantalla vacía). No cambia el tema activo de `config.yaml`.

- Anime: `SakuraNoche_H`, `IdolNeon_H`, `ChibiPastel_H`, `TintaNinja_H`, `MechaES_H`.
- Cyberpunk: `CiberMagenta_H`, `AmarilloNC_H`, `LluviaHolo_H`, `FalloRojo_H`.
- Técnica: `PlacaPCB_H`, `HoloHUD_H`, `MatrixLluvia_H`, `RackServo_H`, `PlanoAzul_H`.
- Otros: `VaporOcaso_H`, `CarbonoRace_H`, `PixelBloque_H`, `MarProfundo_H`, `NebulosaES_H`, `ArcadeRetro_H`.


## 3.2.0 — 2026-10-08

Actualización del monitor y de los temas de 3,5". No cambia `config.yaml`:
el puerto, el tema activo y las coordenadas del tiempo siguen en cada máquina
(el ejemplo del repositorio deja latitud y longitud en 0).

### Conexión de la pantalla

- Reintentos al abrir el COM, en la línea de los arreglos `9b3d106` y `d2dbe88`
  de turing-smart-screen-python.
- Si el puerto es `AUTO`, se busca la pantalla por VID/PID y número de serie.
- Si no aparece, el monitor espera con pausas cada vez más largas. Se puede
  limitar con `COM_WAIT_SECONDS`.
- Si el USB se cae con la pantalla encendida, vuelve a conectar solo. El dibujo
  del tema se repite al reconectar.
- La imagen de la revisión A se manda de una vez, y no se encola nada mientras
  está desconectada. El envío y la reconexión no se pisan.
- Si el hilo de la pantalla se queda colgado, el proceso termina en lugar de
  quedarse congelado.
- Nuevo `library/recuperar_usb.py`: en Windows, si el USB queda como
  dispositivo desconocido, se intenta reiniciar (hace falta el lanzador de
  administrador).

### Lanzador (`tools/lanzar.py`)

- Al entrar en Windows ya no sale un aviso emergente.
- `config.yaml` se escribe de forma segura (no se deja a medias).
- Vigilante `python tools/lanzar.py --vigilar`: vuelve a abrir el monitor solo
  si se cerró de golpe, y no más de unas pocas veces por hora.

### Sensores

- `sensors_librehardwaremonitor.py` incorpora el arreglo `64d9674` del proyecto
  original (lectura de LibreHardwareMonitor en Windows).

### Temas de 3,5" horizontal

Seis temas nuevos, en español, con reloj (12 h o 24 h, según `CLOCK_FORMAT`),
tiempo en vivo (Open-Meteo) y CPU, GPU, RAM, disco y red:

- `Glitch404_H` — negro, rojo y rosa, estilo glitch.
- `CristalES_H` — cristal claro, reloj grande.
- `OrbitaES_H` — azul oscuro, cuatro indicadores en fila.
- `TerminalCRT_H` — terminal de fósforo verde.
- `NumerosES_H` — números grandes sobre fondo claro.
- `SakuraES_H` — rosa pastel.

Además se repararon 46 temas de 3,5" que ya estaban: el reloj y el tiempo se
cortaban (sobre todo en 12 h), algunos medidores salían estirados y otros se
salían de la pantalla. Entre ellos `AtardecerES`, el resto de temas `*ES`,
`OnePiece4`, `bash-dark-green*_H`, `Simple*Gauge_H`, `BloqueES*`, `ViceES*`,
`MiTema`, `ClimaES`, `NocheNeon`, `QuantumES`, `Cyberpunk_H`,
`Cyberpunk-net_H`, `GenIA_35H_*` y `MonodarkSimpleLandscape`.

El tema que está puesto en `config.yaml` no se cambia solo. Para usar uno
nuevo, cambia la línea `THEME:` y reinicia el monitor.
