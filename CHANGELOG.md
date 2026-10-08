# Cambios

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
