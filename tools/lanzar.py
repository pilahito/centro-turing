# -*- coding: utf-8 -*-
"""Arranque del monitor Turing: Windows, Ubuntu y Arch."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PID_FILE = ROOT / "tmp" / "monitor.pid"
LOG = ROOT / "lanzador.log"
CFG = ROOT / "config.yaml"
WIN = os.name == "nt"


def log(msg: str) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n"
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line)
    print(msg)


def popup(msg: str, detalle: str = "") -> None:
    log("ERROR " + msg + (("\n" + detalle) if detalle else ""))
    if WIN:
        try:
            # Show the box from a detached process so this launcher (and the
            # scheduled task) ends now; otherwise IgnoreNew skips later runs.
            texto = " ".join(msg.split())[:200]
            codigo = ("import ctypes,sys;ctypes.windll.user32.MessageBoxW"
                      "(0,sys.argv[1],'Pantalla Turing',0x10|0x40000)")
            exe = Path(sys.executable)
            w = exe.with_name("pythonw.exe")
            subprocess.Popen([str(w if w.exists() else exe), "-c", codigo, texto],
                             creationflags=0x00000008 | 0x00000200,
                             close_fds=True)
            return
        except Exception:
            pass
    print(msg, file=sys.stderr)


def python_exe() -> Path:
    if WIN:
        p = ROOT / "venv" / "Scripts" / "python.exe"
    else:
        p = ROOT / "venv" / "bin" / "python"
        if not p.exists():
            p = ROOT / "venv" / "bin" / "python3"
    if p.exists():
        return p
    # sistema
    import shutil
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            return Path(found)
    raise RuntimeError("No hay Python. En Windows: Instalar.ps1  |  En Linux: ./iniciar.sh --install")


def is_our_monitor(pid: int) -> bool:
    """Verifica que el PID sea de verdad nuestro monitor antes de matarlo.

    Windows reutiliza los PID: si el monitor murio y su numero se reasigno a otro
    programa, matarlo por PID cerraria un proceso ajeno (por eso se mira la linea
    de comandos).
    """
    if pid <= 0:
        return False
    try:
        import psutil

        proc = psutil.Process(pid)
        cmdline = " ".join(proc.cmdline() or []).replace("\\", "/")
        if "python" not in (proc.name() or "").lower() or "main.py" not in cmdline:
            return False
        raiz = str(ROOT).replace("\\", "/").lower()
        if raiz in cmdline.lower():
            return True
        # "pythonw.exe main.py" (ruta relativa): se mira el ejecutable y la carpeta de trabajo
        exe = (proc.exe() or "").replace("\\", "/").lower()
        try:
            cwd = (proc.cwd() or "").replace("\\", "/").lower().rstrip("/")
        except Exception:
            cwd = ""
        return exe.startswith(raiz + "/") or cwd == raiz
    except Exception:
        return False


def kill_pid(pid: int) -> None:
    if not is_our_monitor(pid):
        return
    try:
        if WIN:
            # CREATE_NO_WINDOW: sin consola, taskkill abriria una ventana negra
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, timeout=8,
                           creationflags=0x08000000)
        else:
            os.kill(pid, 15)
            time.sleep(0.3)
            try:
                os.kill(pid, 9)
            except OSError:
                pass
    except Exception:
        pass


def kill_previous() -> None:
    if WIN:
        subprocess.run(["taskkill", "/IM", "UsbPCMonitor.exe", "/F"], capture_output=True, timeout=8,
                       creationflags=0x08000000)
    if PID_FILE.exists():
        try:
            kill_pid(int(PID_FILE.read_text(encoding="utf-8").strip()))
        except Exception:
            pass
        try:
            PID_FILE.unlink()
        except Exception:
            pass
    try:
        import psutil
        me = os.getpid()
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            if p.info["pid"] == me:
                continue
            cmd = " ".join(p.info.get("cmdline") or [])
            if "main.py" in cmd:
                kill_pid(int(p.info["pid"]))  # kill_pid solo mata el main.py de ESTA carpeta
    except Exception as e:
        log("psutil: " + str(e))


def set_config(theme: str) -> None:
    original = text = CFG.read_text(encoding="utf-8")
    if theme:
        if not re.search(r"(?m)^(\s*THEME:\s*).+$", text):
            raise RuntimeError("No hay THEME en config.yaml")
        text = re.sub(r"(?m)^(\s*THEME:\s*).+$", r"\g<1>" + theme, text)
    if WIN:
        text = re.sub(r"(?m)^(\s*HW_SENSORS:\s*).+$", r"\g<1>AUTO", text)
    else:
        text = re.sub(r"(?m)^(\s*HW_SENSORS:\s*).+$", r"\g<1>PYTHON", text)
        # COM3 es Windows; en Linux auto-detecta /dev/ttyACM*
        text = re.sub(r"(?m)^(\s*COM_PORT:\s*).+$", r"\g<1>AUTO", text)
    if text == original:
        return  # nada que cambiar: no se reescribe config.yaml en cada arranque
    # Escritura atomica: si Windows se apaga o el proceso muere a mitad, config.yaml no
    # queda cortado (ya paso: config.yaml.broken-160007)
    tmp = CFG.with_name(CFG.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, CFG)


ARRANQUE_PAUSA = 5.0     # s de pausa con --arranque (inicio de Windows)
_MUTEX = None


def _un_solo_lanzador(espera_s: float) -> bool:
    """Evita dos lanzadores a la vez (p. ej. tarea de inicio + carpeta Inicio).

    Mutex con nombre de Windows. Con espera 0 (arranque de sesion) el segundo
    lanzador se retira; al aplicar un tema se espera a que termine el anterior.
    """
    global _MUTEX
    if not WIN:
        return True
    try:
        import ctypes

        k32 = ctypes.windll.kernel32
        k32.CreateMutexW.restype = ctypes.c_void_p
        _MUTEX = k32.CreateMutexW(None, False, "Local\\CentroTuringLanzar")
        r = k32.WaitForSingleObject(ctypes.c_void_p(_MUTEX), int(espera_s * 1000))
        return r in (0, 0x80)  # WAIT_OBJECT_0 / WAIT_ABANDONED
    except Exception:
        return True


def _arranque_de_sesion() -> bool:
    """True si Windows acaba de arrancar (la tarea de inicio de sesion)."""
    try:
        import psutil

        return time.time() - psutil.boot_time() < 240
    except Exception:
        return False
ESPERA_MONITOR = 90.0    # s maximos esperando a que main.py empiece a dibujar


# --------------------------------------------------------------------------
# Recuperacion del USB: en arranque en frio la pantalla a veces falla al
# enumerar ("Dispositivo USB desconocido (Error de solicitud de descriptor)",
# codigo 43) y COM3 no aparece. Reiniciar ese dispositivo con pnputil (hace
# falta administrador: la tarea "Centro Turing (admin)" lo es) la recupera.
# --------------------------------------------------------------------------
VID_PID = ("1A86", "5722")


def _puerto_config() -> str:
    try:
        m = re.search(r"(?m)^\s*COM_PORT:\s*['\"]?([^'\"\s#]+)", CFG.read_text(encoding="utf-8-sig"))
        return m.group(1).upper() if m else "AUTO"
    except Exception:
        return "AUTO"


def _pantalla_presente() -> bool:
    try:
        from serial.tools import list_ports

        puerto = _puerto_config()
        puertos = list(list_ports.comports())
        for p in puertos:
            if (p.serial_number or "") == "USB35INCHIPSV2":
                return True
            if p.vid is not None and "%04X" % p.vid == VID_PID[0] and "%04X" % (p.pid or 0) == VID_PID[1]:
                return True
        # Sin datos USB (otro modelo / driver): basta con que exista el puerto de config.yaml
        for p in puertos:
            if p.vid is None and (p.device or "").upper() == puerto:
                return True
    except Exception:
        return True  # sin pyserial no se puede comprobar: que lo intente main.py
    return False


def _es_admin() -> bool:
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _usb_en_error() -> list:
    """Dispositivos USB que fallaron al enumerar (desconocidos, VID_0000)."""
    ps = ("Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { "
          "$_.InstanceId -like 'USB\\VID_0000&PID_000*' -and $_.Status -ne 'OK' } | "
          "ForEach-Object { $_.InstanceId }")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                           timeout=30, creationflags=0x08000000)
        return [x.strip() for x in r.stdout.splitlines() if x.strip()]
    except Exception:
        return []


def _esperar_pantalla(segundos: float) -> bool:
    final = time.time() + segundos
    while time.time() < final:
        if _pantalla_presente():
            return True
        time.sleep(1.0)
    return _pantalla_presente()


def recuperar_pantalla(espera_inicial: float = 20.0) -> bool:
    """Espera a la pantalla y, si Windows la dejo en error (codigo 43), la reinicia."""
    if not WIN or _esperar_pantalla(espera_inicial):
        return True
    for intento in (1, 2):
        averiados = _usb_en_error()
        if not averiados:
            log("pantalla ausente y sin dispositivos USB en error: no hay nada que reiniciar")
            return False
        if not _es_admin():
            log("pantalla en error USB %s, pero sin administrador no se puede reiniciar" % averiados)
            return False
        for ident in averiados:
            r = subprocess.run(["pnputil", "/restart-device", ident], capture_output=True, text=True,
                               timeout=60, creationflags=0x08000000, errors="replace")
            log("reinicio USB (intento %d) %s -> %s" % (intento, ident, " ".join(r.stdout.split())[:120]))
        if _esperar_pantalla(20.0):
            log("pantalla recuperada tras reiniciar el USB")
            return True
    return False


def log_desde_marca() -> str:
    lf = ROOT / "log.log"
    if not lf.exists():
        return ""
    lines = lf.read_text(encoding="utf-8", errors="replace").splitlines()
    start = 0
    for i, line in enumerate(lines):
        if "--- lanzar start ---" in line:
            start = i
    return "\n".join(lines[start:])


# --------------------------------------------------------------------------
# Vigilante: el monitor puede morir sin avisar (p. ej. 08/10 21:20, al resetearse el
# driver de NVIDIA, LibreHardwareMonitor lanzo AccessViolationException en
# NvmlDeviceGetPowerUsage y cerro python.exe de golpe: la pantalla se quedo congelada).
# Un proceso aparte, sin ventana, espera a que termine y, si no fue un cierre normal
# (Salir, apagado de Windows, --detener, cambio de tema), lo vuelve a arrancar.
# --------------------------------------------------------------------------
MAX_RELANZAMIENTOS_HORA = 5


def _pid_actual() -> int:
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return 0


def _kwargs_monitor() -> dict:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"  # prints de main.py en UTF-8 (sin "Â°C")
    kwargs = {"env": env, "cwd": str(ROOT), "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if WIN:
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    return kwargs


def _lanzar_vigilante(pid: int) -> None:
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    try:
        kwargs = {"cwd": str(ROOT), "close_fds": True,
                  "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if WIN:
            kwargs["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED | NEW_GROUP | NO_WINDOW
        subprocess.Popen([str(w if w.exists() else exe), str(Path(__file__).resolve()), "--vigilar", str(pid)],
                         **kwargs)
    except Exception as e:
        log("no se pudo arrancar el vigilante: %s" % e)


def _otro_monitor_vivo(excepto: int = 0) -> bool:
    try:
        import psutil
        for p in psutil.process_iter(["pid", "cmdline"]):
            if p.info["pid"] != excepto and "main.py" in " ".join(p.info.get("cmdline") or []) \
                    and is_our_monitor(int(p.info["pid"])):
                return True
    except Exception:
        pass
    return False


def vigilar(pid: int) -> int:
    import psutil

    relanzamientos = []
    while True:
        try:
            codigo = psutil.Process(pid).wait()
        except psutil.NoSuchProcess:
            codigo = None
        except Exception as e:
            log("vigilante: %s" % e)
            return 1
        time.sleep(3)  # lanzar.py --detener / cambio de tema borran o cambian monitor.pid justo despues
        if _pid_actual() != pid:
            return 0  # lo cerro otro lanzador a proposito
        if codigo == 0 or codigo is None:
            return 0  # cierre normal (Salir, apagado de Windows...)
        if _otro_monitor_vivo(pid):
            return 0
        ahora = time.time()
        relanzamientos = [t for t in relanzamientos if ahora - t < 3600]
        if len(relanzamientos) >= MAX_RELANZAMIENTOS_HORA:
            log("vigilante: el monitor se ha cerrado %d veces en una hora; no se relanza mas"
                % len(relanzamientos))
            return 1
        relanzamientos.append(ahora)
        log("vigilante: el monitor (pid %s) se cerro inesperadamente (codigo 0x%X): se relanza"
            % (pid, codigo & 0xFFFFFFFF))
        time.sleep(5)
        try:
            with (ROOT / "log.log").open("a", encoding="utf-8") as lf:
                lf.write(time.strftime("%d/%m/%Y %H:%M:%S") + " [INFO] --- lanzar start ---\n")
        except Exception:
            pass
        proc = subprocess.Popen([str(python_exe()), "main.py"], **_kwargs_monitor())
        PID_FILE.write_text(str(proc.pid), encoding="utf-8")
        pid = proc.pid
        log("vigilante: monitor relanzado pid=%s" % pid)


def ensure_tmp() -> None:
    tmp = PID_FILE.parent
    if tmp.exists() and not tmp.is_dir():
        tmp.unlink()
    tmp.mkdir(parents=True, exist_ok=True)


def main() -> int:
    os.chdir(ROOT)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    theme = args[0].strip() if args else ""
    if "--vigilar" not in flags:
        log("lanzar os=%s theme=%r %s" % (sys.platform, theme, " ".join(flags)))
    if "--vigilar" in flags:
        try:
            return vigilar(int(args[0]))
        except Exception as e:
            log("vigilante: %s" % e)
            return 1
    if "--detener" in flags:
        # Lo usa la tarea "Centro Turing (admin) detener": el panel (sin admin) no
        # puede cerrar un monitor que corre como administrador.
        kill_previous()
        log("monitor detenido (--detener)")
        return 0
    if "--tarea" in flags and _arranque_de_sesion():
        flags.append("--arranque")
    if not _un_solo_lanzador(0 if "--arranque" in flags else 100):
        log("ya hay otro lanzador en marcha: este se retira (evita dos monitores)")
        return 0
    if "--arranque" in flags:
        # Arranque de Windows: pequena pausa para que se enumeren los USB
        time.sleep(ARRANQUE_PAUSA)
    try:
        kill_previous()
        time.sleep(0.5)
        if theme:
            theme_dir = ROOT / "res" / "themes" / theme
            if not (theme_dir / "theme.yaml").exists():
                popup("No existe el tema:\n" + theme)
                return 2
            set_config(theme)
            log("THEME=" + theme)
        else:
            set_config("")
        py = python_exe()
        ensure_tmp()
        if WIN and not _esperar_pantalla(10.0 if "--arranque" in flags else 3.0):
            # main.py espera a la pantalla en segundo plano sin limite (y reinicia de vez en
            # cuando los USB en error): aqui no se bloquea ni se avisa con ventanas.
            log("pantalla aun no detectada por USB: el monitor la esperara en segundo plano")
            if "--arranque" in flags:
                recuperar_pantalla(0)
        kwargs = _kwargs_monitor()
        # Mark a fresh start in log so popup does not show stale errors
        try:
            with (ROOT / "log.log").open("a", encoding="utf-8") as lf:
                lf.write(time.strftime("%d/%m/%Y %H:%M:%S") + " [INFO] --- lanzar start ---\n")
        except Exception:
            pass
        proc = subprocess.Popen([str(py), "main.py"], **kwargs)
        PID_FILE.write_text(str(proc.pid), encoding="utf-8")
        # main.py espera por si solo a la pantalla (COM_WAIT_SECONDS, 60 s por defecto):
        # aqui solo se avisa si el monitor muere o si no arranca tras agotar la espera.
        limite = time.time() + ESPERA_MONITOR
        estado = "esperando"
        while time.time() < limite:
            time.sleep(1.0)
            if proc.poll() is not None:
                estado = "muerto"
                break
            if "Starting system monitoring" in log_desde_marca():
                estado = "ok"
                break
        if estado == "muerto" and WIN and "no ha aparecido" in log_desde_marca() and recuperar_pantalla(0):
            # El USB se ha recuperado: un segundo intento antes de molestar con el aviso
            log("relanzando el monitor tras recuperar la pantalla")
            with (ROOT / "log.log").open("a", encoding="utf-8") as lf:
                lf.write(time.strftime("%d/%m/%Y %H:%M:%S") + " [INFO] --- lanzar start ---\n")
            proc = subprocess.Popen([str(py), "main.py"], **kwargs)
            PID_FILE.write_text(str(proc.pid), encoding="utf-8")
            limite = time.time() + ESPERA_MONITOR
            estado = "esperando"
            while time.time() < limite:
                time.sleep(1.0)
                if proc.poll() is not None:
                    estado = "muerto"
                    break
                if "Starting system monitoring" in log_desde_marca():
                    estado = "ok"
                    break
        if estado == "muerto":
            texto = log_desde_marca()
            tail = "\n".join(texto.splitlines()[-20:])
            sin_pantalla = ("no ha aparecido" in texto or "no existe en el sistema" in texto
                            or "Cannot open COM port after" in texto)
            if sin_pantalla and ("--tarea" in flags or "--arranque" in flags):
                # Inicio de sesion: nada de ventanas de error; queda en lanzador.log
                log("el monitor termino sin encontrar la pantalla (sin aviso al iniciar sesion)\n" + tail)
                return 3
            if sin_pantalla:
                corto = "Windows no detecta la pantalla Turing por USB: desenchufa y vuelve a enchufar su cable (detalles en log.log)."
            else:
                corto = "El monitor de la pantalla Turing no ha podido arrancar (detalles en log.log)."
            popup(corto, tail)
            return 3
        if estado == "esperando":
            if "Esperando a que Windows detecte la pantalla" in log_desde_marca():
                log("el monitor esta esperando a que aparezca la pantalla por USB (pid=%s): "
                    "empezara a dibujar en cuanto Windows la detecte" % proc.pid)
            else:
                log("aviso: el monitor sigue vivo pero aun no dibuja (pid=%s)" % proc.pid)
        log("ok pid=%s python=%s" % (proc.pid, py))
        _lanzar_vigilante(proc.pid)
        return 0
    except Exception as e:
        popup(str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
