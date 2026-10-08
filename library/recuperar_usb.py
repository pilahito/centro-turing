# -*- coding: utf-8 -*-
"""Centro Turing: recuperacion del USB de la pantalla mientras se espera a que aparezca.

En arranque en frio la pantalla (USB\\VID_1A86&PID_5722, serie USB35INCHIPSV2) a veces
falla al enumerar en el hub: Windows la deja como "Dispositivo USB desconocido (Error de
solicitud de descriptor)" (USB\\VID_0000&PID_0002\\...) y COM3 no existe. Reiniciar ese
dispositivo con pnputil puede recuperarla (hace falta administrador; la tarea
"Centro Turing (admin)" lo es). Aqui se reintenta de vez en cuando, en silencio, mientras
lcd_comm.openSerial() espera a la pantalla.
"""
import os
import subprocess
import time

from library.log import logger

# Segundos de espera (desde que se empieza a esperar) en los que se intenta el reinicio;
# despues, cada INTERVALO_FINAL segundos.
HITOS = (40, 120, 300, 900)
INTERVALO_FINAL = 1800

_inicio = None
_siguiente = 0


def _es_admin() -> bool:
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _usb_en_error() -> list:
    ps = ("Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { "
          "$_.InstanceId -like 'USB\\VID_0000&PID_000*' -and $_.Status -ne 'OK' } | "
          "ForEach-Object { $_.InstanceId }")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                           timeout=30, creationflags=0x08000000)
        return [x.strip() for x in r.stdout.splitlines() if x.strip()]
    except Exception:
        return []


def reiniciar_usb_en_error() -> int:
    """Reinicia los USB que fallaron al enumerar. Devuelve cuantos se reiniciaron."""
    if os.name != "nt" or not _es_admin():
        return 0
    n = 0
    for ident in _usb_en_error():
        try:
            r = subprocess.run(["pnputil", "/restart-device", ident], capture_output=True, text=True,
                               timeout=60, creationflags=0x08000000, errors="replace")
            logger.info("Reinicio USB %s -> %s", ident, " ".join(r.stdout.split())[:100])
            n += 1
        except Exception as e:
            logger.debug("pnputil %s: %s", ident, e)
    return n


def reiniciar_espera() -> None:
    global _inicio
    _inicio = None


def quizas_recuperar() -> None:
    """Llamar en cada reintento de apertura del puerto; actua solo en los hitos de tiempo."""
    global _inicio, _siguiente
    if os.name != "nt":
        return
    ahora = time.monotonic()
    if _inicio is None:
        _inicio = ahora
        _siguiente = 0
    transcurrido = ahora - _inicio
    objetivo = HITOS[_siguiente] if _siguiente < len(HITOS) else \
        HITOS[-1] + INTERVALO_FINAL * (_siguiente - len(HITOS) + 1)
    if transcurrido < objetivo:
        return
    _siguiente += 1
    try:
        if reiniciar_usb_en_error():
            logger.info("Pantalla ausente %.0f s: reiniciados los USB en error, se sigue esperando", transcurrido)
    except Exception as e:
        logger.debug("recuperar USB: %s", e)
