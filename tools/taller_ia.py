#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Taller de temas con IA para Centro Turing (3,5" horizontal, 480x320).

Hace los temas igual que se hicieron a mano los de 3.2.1, 3.2.2 y 3.3.0:

  1. La IA elige un ARQUETIPO de disposicion que aun no se haya usado y un
     estilo, y devuelve un JSON con la ESCENA (fondo dibujado con primitivas:
     degradados, astros, montanas, rejillas, paneles, biseles...), las
     ETIQUETAS en espanol y la posicion exacta de cada widget.
  2. Herramientas de este modulo (no la IA) dibujan el fondo con PIL,
     escriben theme.yaml y renderizan la vista previa con los valores MAS
     LARGOS posibles ("12:59 p. m.", "Parcialmente nublado", "131072 M",
     "1023.9 MB/s", "100°C"...).
  3. Revision automatica de esa vista previa: texto que no cabe (tinta fuera
     de su caja, igual que library/lcd), solapes entre widgets, etiquetas
     pegadas a un valor, contraste bajo, fondo demasiado cargado debajo de un
     texto, radiales fuera de pantalla y disposicion repetida.
  4. Si hay fallos, se le devuelven a la IA con el JSON y se reintenta.

Se usa desde generador_layout_ia.crear_tema cuando la pantalla es 3,5"
horizontal. CENTRO_TURING_IA_TALLER=0 lo desactiva (vuelve al modo anterior).
"""
from __future__ import annotations

import json
import math
import os
import random
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 480, 320

# Fuentes (clave corta -> ruta en res/fonts). Solo las que se ven bien a 480x320.
FUENTES = {
    "rb": "roboto/Roboto-Bold.ttf", "rm": "roboto/Roboto-Medium.ttf", "rr": "roboto/Roboto-Regular.ttf",
    "rk": "roboto/Roboto-Black.ttf", "ri": "roboto/Roboto-BoldItalic.ttf", "rbi": "roboto/Roboto-BlackItalic.ttf",
    "rl": "roboto/Roboto-Light.ttf", "rt": "roboto/Roboto-Thin.ttf",
    "mb": "roboto-mono/RobotoMono-Bold.ttf", "mr": "roboto-mono/RobotoMono-Regular.ttf",
    "jb": "jetbrains-mono/JetBrainsMono-Bold.ttf", "jx": "jetbrains-mono/JetBrainsMono-ExtraBold.ttf",
    "jm": "jetbrains-mono/JetBrainsMono-Medium.ttf",
    "gf": "geforce/GeForce-Bold.ttf", "gl": "geforce/GeForce-Light.ttf",
    "d7": "digital/DIGITAL-7.TTF",
}
# DIGITAL-7 no tiene tildes, letras minusculas reales ni el simbolo de grado
SOLO_NUMEROS = {"d7"}

# Widgets: clave -> (descripcion, textos mas largos posibles)
TEXTOS = {
    "hour": ("hora (12 o 24 h segun CLOCK_FORMAT)", ["12:59 p. m.", "23:59"]),
    "weekday": ("dia de la semana", ["miércoles"]),
    "day": ("fecha", ["30 sept 2026"]),
    "wtemp": ("temperatura exterior", ["-99°C"]),
    "wdesc": ("estado del cielo", ["Parcialmente nublado", "Tiempo no disponible"]),
    "wfelt": ("sensacion termica", ["(-99°C)"]),
    "whum": ("humedad", ["100%"]),
    "cpu_pct": ("uso de CPU", ["100%"]), "cpu_temp": ("temperatura CPU", ["100°C"]),
    "gpu_pct": ("uso de GPU", ["100%"]), "gpu_temp": ("temperatura GPU", ["100°C"]),
    "gpu_mem": ("VRAM usada en %", ["100%"]),
    "ram_pct": ("RAM en %", ["100%"]), "ram_used": ("RAM usada", ["131072 M"]),
    "disk_pct": ("disco en %", ["100%"]), "disk_used": ("disco usado", ["99999 G"]),
    "down": ("red bajada", ["1023.9 MB/s"]), "up": ("red subida", ["1023.9 MB/s"]),
}
OBLIGATORIOS = ["hour", "weekday", "day", "wtemp", "wdesc", "wfelt", "whum", "cpu_temp", "gpu_temp",
                "gpu_mem", "ram_used", "disk_used", "down", "up"]
PORCENTAJES = {"cpu_pct": "cpu_rad", "gpu_pct": "gpu_rad", "ram_pct": "ram_rad", "disk_pct": "disk_rad"}
BARRAS = ["cpu_bar", "gpu_bar", "ram_bar", "disk_bar", "gpu_mem_bar"]
LINEAS = ["cpu_line", "gpu_line", "down_line", "up_line"]
RADIALES = list(PORCENTAJES.values())

ARQUETIPOS = [
    "reloj gigante centrado y una fila minima de cifras abajo",
    "arte a un lado y lista apilada de cifras al otro",
    "temperatura exterior enorme como protagonista, reloj en una esquina",
    "barra lateral estrecha de barras y reloj grande sobre el paisaje",
    "cuatro indicadores circulares 2x2 y columna de reloj",
    "cuatro esquinas con el centro vacio (reticula)",
    "pantalla partida en diagonal",
    "dos graficas de historial grandes (CPU y GPU)",
    "filas tipo consola/htop con barras",
    "cifras repartidas sobre elementos del dibujo (chips, carteles, fotos)",
    "un anillo enorme a un lado y columna de texto al otro",
    "tres columnas de texto sin barras",
    "bahias horizontales a todo el ancho (rack)",
    "reloj en el centro y satelites alrededor",
    "teletipo inferior bajo una gran cifra",
    "tacometro abajo y tira digital arriba",
    "marcador de recreativa sin barras",
    "bandas horizontales de borde a borde",
    "bloque asimetrico tipo revista",
    "ventana de escritorio antigua con grupos y barra de estado",
    "tabla clave-valor de pantalla de configuracion",
    "consola portatil: todo dentro de una pantallita",
    "marcador superior de videojuego con escena debajo",
    "televisor antiguo con carta de ajuste",
    "objeto fisico (casete, radio, calculadora) con cifras en sus piezas",
    "medidores de aguja semicirculares",
    "fila de tubos o paletas con un numero cada uno",
    "pagina de teletexto",
    "listado de codigo con valores tras cada signo igual",
    "matriz de puntos con una cifra gigante",
    "tarjetas en rejilla (gramola, tablon)",
    "periodico con titular, foto y columnas",
    "menu de rol con ventanas y barras de vida",
    "osciloscopio con dos canales y ruedas",
    "linea de tiempo horizontal con hitos",
    "circulo de reloj analogico con cifras en las horas",
    "mapa o plano con marcadores",
    "pila de notas adhesivas",
    "pantalla de ascensor o aeropuerto con paletas",
    "tablero de ajedrez o juego de mesa",
]
ESTILOS = ["Windows 98", "BIOS", "Game Boy", "NES", "SNES", "recreativa", "carta de ajuste", "casete",
           "VHS", "synthwave 80s", "hi-fi de madera 70s", "tubos nixie", "calculadora LCD", "reloj Casio",
           "teletexto", "Amstrad/Commodore", "pinball", "gramola", "polaroid", "periodico antiguo", "RPG 8 bits",
           "reloj de paletas", "osciloscopio", "radar", "cabina de avion", "submarino", "laboratorio",
           "acuarela japonesa", "art deco", "bauhaus", "pizarra de tiza", "blueprint", "neon de Tokio",
           "desierto", "aurora boreal", "jardin zen", "metro de Londres", "estacion espacial"]

PEOR = {"hour": "12:59 p. m.", "weekday": "miércoles", "day": "30 sept 2026", "wtemp": "-99°C",
        "wdesc": "Parcialmente nublado", "wfelt": "(-99°C)", "whum": "100%", "cpu_pct": "100%",
        "cpu_temp": "100°C", "gpu_pct": "100%", "gpu_temp": "100°C", "gpu_mem": "100%", "ram_pct": "100%",
        "ram_used": "131072 M", "disk_pct": "100%", "disk_used": "99999 G", "down": "1023.9 MB/s",
        "up": "1023.9 MB/s"}


def rgb(c, defecto=(255, 255, 255)):
    """'#rrggbb', 'r, g, b' o [r, g, b] -> tupla."""
    try:
        if isinstance(c, (list, tuple)):
            return tuple(max(0, min(255, int(v))) for v in c[:3])
        s = str(c).strip()
        if s.startswith("#") and len(s) in (4, 7):
            s = s[1:]
            if len(s) == 3:
                s = "".join(ch * 2 for ch in s)
            return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
        partes = [int(float(p)) for p in re.split(r"[,\s]+", s) if p]
        if len(partes) >= 3:
            return tuple(max(0, min(255, v)) for v in partes[:3])
    except (TypeError, ValueError):
        pass
    return defecto


def col(c) -> str:
    r, g, b = rgb(c)
    return f"{r}, {g}, {b}"


def lum(c) -> float:
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = c
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contraste(a, b) -> float:
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# --------------------------------------------------------------------------
# Herramienta 1: dibujar el fondo a partir de primitivas (como art4/art5.py)
# --------------------------------------------------------------------------
class Taller:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.fonts = self.root / "res" / "fonts"
        self._cache: dict = {}

    def font(self, clave: str, tam: int):
        k = (clave, int(tam))
        if k not in self._cache:
            self._cache[k] = ImageFont.truetype(str(self.fonts / FUENTES[clave]), max(6, int(tam)))
        return self._cache[k]

    def medir(self, texto: str, clave: str, tam: int) -> tuple[int, int]:
        b = self.font(clave, tam).getbbox(texto)
        return b[2] - b[0], b[3] - b[1]

    def tabla_anchos(self, claves=("rb", "rm", "rk", "ri", "mb", "jb", "jx", "rl", "gf", "d7")) -> str:
        """Ancho en px de los textos mas largos a tamano 10 (escala lineal con el tamano)."""
        muestras = ["12:59 p. m.", "miércoles", "30 sept 2026", "Parcialmente nublado", "-99°C",
                    "100%", "100°C", "131072 M", "1023.9 MB/s"]
        filas = []
        for c in claves:
            if not (self.fonts / FUENTES[c]).is_file():
                continue
            anchos = [self.medir(m, c, 10)[0] for m in muestras]
            filas.append(c + ": " + ", ".join(f"{m}={a}" for m, a in zip(muestras, anchos)))
        return "\n".join(filas)

    # ---- primitivas ----
    def fondo(self, escena: list) -> Image.Image:
        im = Image.new("RGBA", (W, H), (12, 12, 16, 255))
        for p in escena if isinstance(escena, list) else []:
            if not isinstance(p, dict):
                continue
            try:
                im = self._primitiva(im, p) or im
            except Exception:  # noqa: BLE001  (una primitiva mal escrita no tumba el tema)
                continue
        return im

    def _primitiva(self, im: Image.Image, p: dict):
        t = str(p.get("t", "")).lower()
        n = lambda k, d=0: int(float(p.get(k, d)))  # noqa: E731
        c = rgb(p.get("color"), (128, 128, 128))
        alfa = max(0, min(255, n("alfa", 255)))
        capa = Image.new("RGBA", im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(capa)
        if t == "degradado":
            a, b = rgb(p.get("arriba"), (20, 20, 40)), rgb(p.get("abajo"), (0, 0, 0))
            for y in range(H):
                k = y / (H - 1)
                d.line((0, y, W, y), fill=tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3)) + (255,))
        elif t == "liso":
            d.rectangle((0, 0, W, H), fill=c + (255,))
        elif t == "estrellas":
            rnd = random.Random(n("semilla", 1))
            for i in range(max(0, min(400, n("n", 60)))):
                x, y = rnd.randrange(W), rnd.randrange(n("hasta_y", H) or H)
                r = 1 + (i % 2)
                d.ellipse((x, y, x + r, y + r), fill=c + (alfa,))
        elif t in ("circulo", "elipse"):
            x, y = n("x"), n("y")
            rx = n("r", 20) if t == "circulo" else n("rx", 20)
            ry = n("r", 20) if t == "circulo" else n("ry", 20)
            borde = p.get("borde")
            d.ellipse((x - rx, y - ry, x + rx, y + ry), fill=None if p.get("hueco") else c + (alfa,),
                      outline=rgb(borde) + (alfa,) if borde else None, width=max(1, n("grosor", 2)))
        elif t in ("rect", "panel"):
            x, y, w, h = n("x"), n("y"), n("w", 10), n("h", 10)
            if t == "panel" and "alfa" not in p:
                alfa = 170
            borde = p.get("borde")
            d.rounded_rectangle((x, y, x + w - 1, y + h - 1), max(0, n("radio", 8 if t == "panel" else 0)),
                                fill=None if p.get("hueco") else c + (alfa,),
                                outline=rgb(borde) + (255,) if borde else None, width=max(1, n("grosor", 1)))
        elif t == "bisel":  # boton/ventana de los 90
            x, y, w, h = n("x"), n("y"), n("w", 10), n("h", 10)
            hundido = bool(p.get("hundido"))
            claro, oscuro = (255, 255, 255, 255), (64, 64, 64, 255)
            d.rectangle((x, y, x + w - 1, y + h - 1), fill=c + (255,))
            a, b = (oscuro, claro) if hundido else (claro, oscuro)
            d.line((x, y, x + w - 1, y), fill=a, width=2)
            d.line((x, y, x, y + h - 1), fill=a, width=2)
            d.line((x, y + h - 1, x + w - 1, y + h - 1), fill=b, width=2)
            d.line((x + w - 1, y, x + w - 1, y + h - 1), fill=b, width=2)
        elif t == "poligono":
            pts = [(int(a), int(b)) for a, b in p.get("puntos", [])][:64]
            if len(pts) >= 3:
                d.polygon(pts, fill=c + (alfa,))
        elif t == "linea":
            pts = [(int(a), int(b)) for a, b in p.get("puntos", [])][:64]
            if len(pts) >= 2:
                d.line(pts, fill=c + (alfa,), width=max(1, n("grosor", 2)))
        elif t == "rejilla":
            x, y, w, h, paso = n("x"), n("y"), n("w", W), n("h", H), max(4, n("paso", 20))
            for gx in range(x, x + w + 1, paso):
                d.line((gx, y, gx, y + h), fill=c + (alfa,))
            for gy in range(y, y + h + 1, paso):
                d.line((x, gy, x + w, gy), fill=c + (alfa,))
        elif t == "suelo":  # suelo en perspectiva tipo synthwave
            hz = n("horizonte", 160)
            for i in range(1, 10):
                y = hz + int((H - hz) * (i / 9) ** 1.8)
                d.line((0, y, W, y), fill=c + (alfa,))
            for i in range(-12, 13):
                d.line((W // 2 + i * 12, hz, W // 2 + i * 70, H), fill=c + (alfa,))
        elif t == "montanas":
            rnd = random.Random(n("semilla", 3))
            base, alto = n("base_y", 220), n("alto", 60)
            pts, x = [(0, H)], 0
            while x <= W:
                pts.append((x, base - rnd.randint(alto // 3, alto)))
                x += rnd.randint(30, 70)
            pts += [(W, base), (W, H)]
            d.polygon(pts, fill=c + (alfa,))
        elif t == "olas":
            y0, amp = n("y", 240), max(2, n("amplitud", 6))
            for k in range(max(1, min(8, n("n", 3)))):
                yy = y0 + k * 3 * amp
                pts = [(x, yy + amp * math.sin(x / 18 + k)) for x in range(0, W + 1, 6)]
                d.line(pts, fill=c + (alfa,), width=2)
        elif t == "rayas":  # lineas de barrido CRT
            for y in range(n("y0", 0), n("y1", H), max(2, n("paso", 3))):
                d.line((0, y, W, y), fill=c + (min(alfa, 90),))
        elif t == "puntos":
            paso = max(3, n("paso", 4))
            for y in range(n("y", 0), n("y", 0) + n("h", H), paso):
                for x in range(n("x", 0), n("x", 0) + n("w", W), paso):
                    d.point((x, y), fill=c + (alfa,))
        elif t == "texto":  # rotulo decorativo (original: nada de marcas ni logotipos)
            clave = p.get("fuente", "rb")
            clave = clave if clave in FUENTES else "rb"
            d.text((n("x"), n("y")), str(p.get("texto", ""))[:40], font=self.font(clave, n("tam", 12)),
                   fill=c + (alfa,))
        elif t == "desenfoque":
            return im.filter(ImageFilter.GaussianBlur(max(1, min(8, n("radio", 2)))))
        else:
            return None
        return Image.alpha_composite(im, capa)


# --------------------------------------------------------------------------
# Herramienta 2: normalizar el JSON de la IA (widgets, etiquetas)
# --------------------------------------------------------------------------
def _i(v, d=0) -> int:
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return d


def normalizar(spec: dict) -> tuple[dict, list, list[str]]:
    """JSON de la IA -> (widgets internos, etiquetas, avisos de formato)."""
    errores: list[str] = []
    ws: dict = {}
    crudo = spec.get("widgets") if isinstance(spec.get("widgets"), dict) else {}
    if isinstance(spec.get("widgets"), list):  # tambien se acepta lista con "clave"
        crudo = {str(w.get("clave")): w for w in spec["widgets"] if isinstance(w, dict) and w.get("clave")}
    for k, w in crudo.items():
        if not isinstance(w, dict):
            continue
        if k in TEXTOS:
            fuente = str(w.get("fuente", "rb"))
            if fuente not in FUENTES:
                errores.append(f"{k}: fuente '{fuente}' no existe; usa una de {list(FUENTES)}")
                fuente = "rb"
            ancla = str(w.get("ancla", "lt"))
            ancla = ancla if ancla in ("lt", "mt", "rt") else "lt"
            ws[k] = {"t": "text", "font": fuente, "sz": max(6, _i(w.get("tam"), 12)), "col": rgb(w.get("color")),
                     "x": _i(w.get("x")), "y": _i(w.get("y")), "w": _i(w.get("w"), 60), "h": _i(w.get("h"), 16),
                     "anch": ancla}
        elif k in BARRAS or k in LINEAS:
            ws[k] = {"t": "bar" if k in BARRAS else "line", "col": rgb(w.get("color")), "x": _i(w.get("x")),
                     "y": _i(w.get("y")), "w": _i(w.get("w"), 80), "h": _i(w.get("h"), 8)}
        elif k in RADIALES:
            fuente = str(w.get("fuente", "rb"))
            ws[k] = {"t": "rad", "cx": _i(w.get("x")), "cy": _i(w.get("y")), "r": _i(w.get("r"), 40),
                     "bw": _i(w.get("grosor"), 8), "col": rgb(w.get("color")),
                     "bg": rgb(w.get("fondo"), (50, 50, 60)), "font": fuente if fuente in FUENTES else "rb",
                     "sz": max(6, _i(w.get("tam"), 14)), "fcol": rgb(w.get("color_texto")),
                     "a0": _i(w.get("inicio"), 135), "a1": _i(w.get("fin"), 45),
                     "steps": max(1, _i(w.get("pasos"), 24)), "sep": max(0, _i(w.get("sep"), 3))}
        else:
            errores.append(f"widget desconocido '{k}' (claves validas: {list(TEXTOS) + BARRAS + LINEAS + RADIALES})")
    etiquetas = []
    for e in spec.get("etiquetas") or []:
        if not isinstance(e, dict) or not str(e.get("texto", "")).strip():
            continue
        fuente = str(e.get("fuente", "rb"))
        etiquetas.append({"texto": str(e["texto"])[:24], "x": _i(e.get("x")), "y": _i(e.get("y")),
                          "font": fuente if fuente in FUENTES and fuente not in SOLO_NUMEROS else "rb",
                          "sz": max(7, _i(e.get("tam"), 10)), "col": rgb(e.get("color"))})
    return ws, etiquetas, errores


def caja(sp) -> tuple[int, int, int, int]:
    if sp["t"] == "rad":
        return (sp["cx"] - sp["r"], sp["cy"] - sp["r"], 2 * sp["r"], 2 * sp["r"])
    return (sp["x"], sp["y"], sp["w"], sp["h"])


def solapan(a, b, hueco=0) -> bool:
    return (a[0] < b[0] + b[2] + hueco and b[0] < a[0] + a[2] + hueco and
            a[1] < b[1] + b[3] + hueco and b[1] < a[1] + a[3] + hueco)


# --------------------------------------------------------------------------
# Herramienta 3: revision (lo mismo que se miraba a mano en cada vista previa)
# --------------------------------------------------------------------------
def tinta(taller: Taller, sp: dict, s: str):
    """Caja de tinta de s dibujado como library/lcd DisplayText (X/Y/WIDTH/HEIGHT + ANCHOR)."""
    f = taller.font(sp["font"], sp["sz"])
    l, t, r = sp["x"], sp["y"], sp["x"] + sp["w"]
    x = (l + r) // 2 if sp["anch"][0] == "m" else (r if sp["anch"][0] == "r" else l)
    m = Image.new("L", (W + 400, H + 400), 0)
    ImageDraw.Draw(m).text((x + 200, t + 200), s, font=f, fill=255, anchor=sp["anch"])
    b = m.getbbox()
    return None if not b else (b[0] - 200, b[1] - 200, b[2] - 200, b[3] - 200)


def cabe(taller: Taller, k: str, sp: dict) -> bool:
    for s in TEXTOS[k][1]:
        b = tinta(taller, sp, s)
        if b and (b[0] < sp["x"] or b[1] < sp["y"] or b[2] > sp["x"] + sp["w"] or b[3] > sp["y"] + sp["h"]):
            return False
    return True


def ajustar_textos(taller: Taller, ws: dict) -> list[str]:
    """Si un texto no cabe, baja la letra hasta un 30 %; si aun asi no cabe, es un error para la IA."""
    errores = []
    for k, sp in ws.items():
        if sp["t"] != "text":
            continue
        original = sp["sz"]
        while not cabe(taller, k, sp) and sp["sz"] > max(7, int(original * 0.7)):
            sp["sz"] -= 1
        if not cabe(taller, k, sp):
            sp["sz"] = original
            a, h = taller.medir(TEXTOS[k][1][0], sp["font"], original)
            errores.append(f"{k}: '{TEXTOS[k][1][0]}' mide {a}x{h} px con {sp['font']} {original} y la caja es "
                           f"{sp['w']}x{sp['h']}; agranda la caja o baja la letra")
    return errores


def revisar(taller: Taller, ws: dict, etiquetas: list, fondo: Image.Image, escena: list) -> list[str]:
    e: list[str] = []
    for k in OBLIGATORIOS:
        if k not in ws:
            e.append(f"falta el widget {k} ({TEXTOS[k][0]})")
    for p, r in PORCENTAJES.items():
        if p not in ws and r not in ws:
            e.append(f"falta {p} (o su radial {r})")
    for k, sp in ws.items():
        if sp["t"] == "text" and sp["font"] in SOLO_NUMEROS and k in ("weekday", "day", "wdesc", "wtemp", "wfelt",
                                                                      "cpu_temp", "gpu_temp"):
            e.append(f"{k}: DIGITAL-7 (d7) no tiene tildes ni el simbolo de grado; usa otra fuente")
        x, y, w, h = caja(sp)
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > W or y + h > H:
            e.append(f"{k}: caja ({x},{y},{w},{h}) fuera de la pantalla {W}x{H}")
        if sp["t"] == "rad":
            if not 0 < sp["bw"] <= sp["r"]:
                e.append(f"{k}: grosor debe estar entre 1 y r")
            if sp["sep"] * sp["steps"] >= 360:
                e.append(f"{k}: pasos*sep debe ser < 360")
            a, hh = taller.medir("100%", sp["font"], sp["sz"])
            hueco = 2 * (sp["r"] - sp["bw"])
            if a > hueco * 0.85 or hh > hueco * 0.7:
                e.append(f"{k}: el texto '100%' ({a}x{hh}) no cabe dentro del anillo (hueco {hueco}px)")
    e += ajustar_textos(taller, ws)
    ks = list(ws)
    for i in range(len(ks)):
        for j in range(i + 1, len(ks)):
            if solapan(caja(ws[ks[i]]), caja(ws[ks[j]])):
                e.append(f"{ks[i]} {caja(ws[ks[i]])} se solapa con {ks[j]} {caja(ws[ks[j]])}")
    rotulos = [(et["texto"], et["x"], et["y"], et["font"], et["sz"]) for et in etiquetas]
    rotulos += [(str(p.get("texto", "")), _i(p.get("x")), _i(p.get("y")),
                 p.get("fuente") if p.get("fuente") in FUENTES else "rb", _i(p.get("tam"), 12))
                for p in escena if isinstance(p, dict) and p.get("t") == "texto"]
    for texto, x, y, fk, sz in rotulos:
        b = taller.font(fk, sz).getbbox(texto)
        rc = (x + b[0], y + b[1], b[2] - b[0], b[3] - b[1])
        if rc[0] < 0 or rc[1] < 0 or rc[0] + rc[2] > W or rc[1] + rc[3] > H:
            e.append(f"etiqueta '{texto}' se sale de la pantalla")
        for k, sp in ws.items():
            if solapan(rc, caja(sp), 2):
                e.append(f"etiqueta '{texto}' en {rc[:2]} pisa o toca el widget {k} {caja(sp)}; "
                         "dejala a 2 px o mas")
    # contraste y fondo cargado debajo de cada texto
    base = fondo.convert("RGB")
    for k, sp in ws.items():
        if sp["t"] != "text":
            continue
        x, y, w, h = caja(sp)
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > W or y + h > H:
            continue
        trozo = base.crop((x, y, x + w, y + h)).resize((max(1, w // 2), max(1, h // 2)))
        crudo = trozo.tobytes()
        px = [tuple(crudo[i:i + 3]) for i in range(0, len(crudo), 3)]
        medio = tuple(sum(c[i] for c in px) // len(px) for i in range(3))
        ls = [lum(c) for c in px]
        media = sum(ls) / len(ls)
        desv = math.sqrt(sum((v - media) ** 2 for v in ls) / len(ls))
        cr = contraste(sp["col"], medio)
        if cr < 3.0:
            e.append(f"{k}: poco contraste ({cr:.1f}:1) entre el texto {col(sp['col'])} y el fondo {col(medio)}; "
                     "cambia el color o pon un panel detras")
        elif desv > 0.16 and cr < 6:
            e.append(f"{k}: el dibujo debajo del texto esta muy cargado; pon un panel liso detras o mueve el texto")
    return e


def huella(nodos: list[tuple[str, tuple]]) -> str:
    """Rejilla 6x4 con el tipo de widget de cada celda: dos temas con la misma huella repiten disposicion."""
    filas = []
    for gy in range(4):
        fila = ""
        for gx in range(6):
            celda = (gx * 80, gy * 80, 80, 80)
            tipos = sorted({t for t, r in nodos if solapan(r, celda)})
            fila += ("".join(tipos) or ".") + "|"
        filas.append(fila)
    return "\n".join(filas)


def nodos_de_yaml(stats: dict) -> list[tuple[str, tuple]]:
    salida = []

    def rec(n, clave):
        if not isinstance(n, dict):
            return
        if n.get("SHOW") is True and "X" in n:
            tipo = {"GRAPH": "b", "LINE_GRAPH": "l", "RADIAL": "r"}.get(clave, "t")
            try:
                if "RADIUS" in n:
                    r = int(n["RADIUS"])
                    salida.append((tipo, (int(n["X"]) - r, int(n["Y"]) - r, 2 * r, 2 * r)))
                elif "WIDTH" in n:
                    salida.append((tipo, (int(n["X"]), int(n["Y"]), int(n["WIDTH"]), int(n["HEIGHT"]))))
            except (TypeError, ValueError, KeyError):
                pass
        for k, v in n.items():
            rec(v, k)

    rec(stats, "")
    return salida


def nodos_de_widgets(ws: dict) -> list[tuple[str, tuple]]:
    return [({"text": "t", "bar": "b", "line": "l", "rad": "r"}[sp["t"]], caja(sp)) for sp in ws.values()]


# --------------------------------------------------------------------------
# Herramienta 4: theme.yaml y vista previa con los valores mas largos
# --------------------------------------------------------------------------
def _ind(bloque: str, n: int) -> str:
    return "\n".join((" " * n + l) if l else l for l in bloque.strip("\n").split("\n"))


def _texto(sp, unidad: bool, extra: str = "") -> str:
    alin = {"l": "left", "m": "center", "r": "right"}[sp["anch"][0]]
    return (extra + f"SHOW: true\nX: {sp['x']}\nY: {sp['y']}\nWIDTH: {sp['w']}\nHEIGHT: {sp['h']}\n"
            f"FONT: {FUENTES[sp['font']]}\nFONT_SIZE: {sp['sz']}\nFONT_COLOR: {col(sp['col'])}\n"
            f"BACKGROUND_IMAGE: background.png\nALIGN: {alin}\nANCHOR: {sp['anch']}\n"
            f"SHOW_UNIT: {'true' if unidad else 'false'}\n")


def _barra(sp) -> str:
    return (f"SHOW: true\nX: {sp['x']}\nY: {sp['y']}\nWIDTH: {sp['w']}\nHEIGHT: {sp['h']}\nMIN_VALUE: 0\n"
            f"MAX_VALUE: 100\nBAR_COLOR: {col(sp['col'])}\nBAR_OUTLINE: false\nBACKGROUND_IMAGE: background.png\n")


def _linea(sp, auto=False) -> str:
    return (f"SHOW: true\nX: {sp['x']}\nY: {sp['y']}\nWIDTH: {sp['w']}\nHEIGHT: {sp['h']}\nMIN_VALUE: 0\n"
            f"MAX_VALUE: 100\nHISTORY_SIZE: 40\nAUTOSCALE: {'true' if auto else 'false'}\n"
            f"LINE_COLOR: {col(sp['col'])}\nLINE_WIDTH: 2\nAXIS: false\nBACKGROUND_IMAGE: background.png\n")


def _radial(sp) -> str:
    return (f"SHOW: true\nX: {sp['cx']}\nY: {sp['cy']}\nRADIUS: {sp['r']}\nWIDTH: {sp['bw']}\nMIN_VALUE: 0\n"
            f"MAX_VALUE: 100\nANGLE_START: {sp['a0']}\nANGLE_END: {sp['a1']}\nANGLE_STEPS: {sp['steps']}\n"
            f"ANGLE_SEP: {sp['sep']}\nCLOCKWISE: true\nBAR_COLOR: {col(sp['col'])}\n"
            f"BAR_BACKGROUND_COLOR: {col(sp['bg'])}\nDRAW_BAR_BACKGROUND: true\nSHOW_TEXT: true\nSHOW_UNIT: true\n"
            f"FONT: {FUENTES[sp['font']]}\nFONT_SIZE: {sp['sz']}\nFONT_COLOR: {col(sp['fcol'])}\n"
            f"BACKGROUND_IMAGE: background.png\n")


def a_yaml(ws: dict, led, cabecera: str) -> str:
    w = ws
    P = [cabecera, "author: Taller IA Centro Turing\ndisplay:\n  DISPLAY_SIZE: 3.5\"\n"
         f"  DISPLAY_ORIENTATION: landscape\n  DISPLAY_RGB_LED: {col(led)}\n",
         "static_images:\n  BACKGROUND:\n    PATH: background.png\n    X: 0\n    Y: 0\n    WIDTH: 480\n"
         "    HEIGHT: 320\nSTATS:\n  DATE:\n    INTERVAL: 1\n",
         "    HOUR:\n      TEXT:\n" + _ind(_texto(w["hour"], False, "FORMAT: HH:mm\nFORMAT_12: h:mm a\nFORMAT_24: HH:mm\n"), 8) + "\n",
         "    WEEKDAY:\n      TEXT:\n" + _ind(_texto(w["weekday"], False, "FORMAT: EEEE\n"), 8) + "\n",
         "    DAY:\n      TEXT:\n" + _ind(_texto(w["day"], False, "FORMAT: d MMM y\n"), 8) + "\n",
         "  WEATHER:\n    INTERVAL: 600\n"]
    for k, nodo in (("wtemp", "TEMPERATURE"), ("wdesc", "WEATHER_DESCRIPTION"), ("wfelt", "TEMPERATURE_FELT"),
                    ("whum", "HUMIDITY")):
        P.append(f"    {nodo}:\n      TEXT:\n" + _ind(_texto(w[k], False), 8) + "\n")

    def bloque(pref, txt_key, txt_nodo, extra_nodos):
        s = ""
        if txt_key in w:
            s += f"      {txt_nodo}:\n" + _ind(_texto(w[txt_key], True), 8) + "\n"
        for clave, nodo, fn in extra_nodos:
            if clave in w:
                s += f"      {nodo}:\n" + _ind(fn(w[clave]), 8) + "\n"
        return s

    P.append("  CPU:\n    PERCENTAGE:\n      INTERVAL: 2\n")
    P.append(bloque("cpu", "cpu_pct", "TEXT", [("cpu_bar", "GRAPH", _barra), ("cpu_line", "LINE_GRAPH", _linea),
                                               ("cpu_rad", "RADIAL", _radial)]))
    P.append("    TEMPERATURE:\n      INTERVAL: 3\n      TEXT:\n" + _ind(_texto(w["cpu_temp"], True), 8) + "\n")
    P.append("  GPU:\n    INTERVAL: 2\n    PERCENTAGE:\n")
    P.append(bloque("gpu", "gpu_pct", "TEXT", [("gpu_bar", "GRAPH", _barra), ("gpu_line", "LINE_GRAPH", _linea),
                                               ("gpu_rad", "RADIAL", _radial)]))
    P.append("    TEMPERATURE:\n      TEXT:\n" + _ind(_texto(w["gpu_temp"], True), 8) + "\n")
    P.append("    MEMORY_PERCENT:\n      TEXT:\n" + _ind(_texto(w["gpu_mem"], True), 8) + "\n")
    if "gpu_mem_bar" in w:
        P.append("      GRAPH:\n" + _ind(_barra(w["gpu_mem_bar"]), 8) + "\n")
    P.append("  MEMORY:\n    INTERVAL: 3\n    VIRTUAL:\n")
    P.append(bloque("ram", "ram_pct", "PERCENT_TEXT", [("ram_bar", "GRAPH", _barra), ("ram_rad", "RADIAL", _radial)]))
    P.append("      TEXT:\n" + _ind(_texto(w["ram_used"], True), 8) + "\n")
    P.append("  DISK:\n    INTERVAL: 10\n    USED:\n")
    P.append(bloque("disk", "disk_pct", "PERCENT_TEXT", [("disk_bar", "GRAPH", _barra), ("disk_rad", "RADIAL", _radial)]))
    P.append("      TEXT:\n" + _ind(_texto(w["disk_used"], True), 8) + "\n")
    P.append("  NET:\n    INTERVAL: 1\n    ETH:\n      DOWNLOAD:\n        TEXT:\n" + _ind(_texto(w["down"], True), 10) + "\n")
    if "down_line" in w:
        P.append("        LINE_GRAPH:\n" + _ind(_linea(w["down_line"], True), 10) + "\n")
    P.append("      UPLOAD:\n        TEXT:\n" + _ind(_texto(w["up"], True), 10) + "\n")
    if "up_line" in w:
        P.append("        LINE_GRAPH:\n" + _ind(_linea(w["up_line"], True), 10) + "\n")
    return "".join(P)


def poner_etiquetas(taller: Taller, fondo: Image.Image, etiquetas: list) -> Image.Image:
    im = fondo.copy()
    d = ImageDraw.Draw(im)
    for e in etiquetas:
        d.text((e["x"], e["y"]), e["texto"], font=taller.font(e["font"], e["sz"]), fill=e["col"] + (255,))
    return im


def vista_previa(taller: Taller, fondo: Image.Image, ws: dict) -> Image.Image:
    """Como lo pinta library/lcd: cada texto recortado a su caja, con los valores mas largos."""
    im = fondo.convert("RGB")
    d = ImageDraw.Draw(im)
    for k, sp in ws.items():
        if sp["t"] == "text":
            capa = im.crop((sp["x"], sp["y"], sp["x"] + sp["w"], sp["y"] + sp["h"]))
            x = sp["w"] // 2 if sp["anch"][0] == "m" else (sp["w"] if sp["anch"][0] == "r" else 0)
            ImageDraw.Draw(capa).text((x, 0), PEOR[k], font=taller.font(sp["font"], sp["sz"]), fill=sp["col"],
                                      anchor=sp["anch"])
            im.paste(capa, (sp["x"], sp["y"]))
        elif sp["t"] == "bar":
            d.rectangle((sp["x"], sp["y"], sp["x"] + int(sp["w"] * 0.75) - 1, sp["y"] + sp["h"] - 1), fill=sp["col"])
        elif sp["t"] == "line":
            pts = [(sp["x"] + i * (sp["w"] - 1) / 39,
                    sp["y"] + sp["h"] * (0.5 - 0.4 * math.sin(i / 3.0) * math.cos(i / 7.0))) for i in range(40)]
            d.line(pts, fill=sp["col"], width=2)
        elif sp["t"] == "rad":
            cx, cy, r, bw = sp["cx"], sp["cy"], sp["r"], sp["bw"]
            total = (sp["a1"] - sp["a0"]) % 360 or 360
            caja_r = (cx - r, cy - r, cx + r, cy + r)
            d.arc(caja_r, sp["a0"], sp["a0"] + total, fill=sp["bg"], width=bw)
            d.arc(caja_r, sp["a0"], sp["a0"] + total * 0.75, fill=sp["col"], width=bw)
            d.text((cx, cy), "100%", font=taller.font(sp["font"], sp["sz"]), fill=sp["fcol"], anchor="mm")
    return im


# --------------------------------------------------------------------------
# Lo que ya existe (para no repetir disposicion ni arquetipo)
# --------------------------------------------------------------------------
def escanear(themes: Path) -> tuple[dict, list[str]]:
    """(huella -> tema) de los temas 3,5" horizontales y arquetipos usados por el taller."""
    huellas: dict = {}
    usados: list[str] = []
    try:
        import yaml  # type: ignore
    except ImportError:
        yaml = None
    for d in sorted(Path(themes).iterdir()) if Path(themes).is_dir() else []:
        f = d / "theme.yaml"
        if not f.is_file():
            continue
        try:
            texto = f.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        m = re.search(r"^# Arquetipo\s*:\s*(.+)$", texto, re.M)
        if m:
            usados.append(m.group(1).strip())
        if yaml is None or not re.search(r'DISPLAY_SIZE:\s*3\.5', texto) or "landscape" not in texto:
            continue
        try:
            datos = yaml.safe_load(texto) or {}
            h = huella(nodos_de_yaml(datos.get("STATS") or {}))
            huellas.setdefault(h, d.name)
        except Exception:  # noqa: BLE001
            continue
    return huellas, usados


# --------------------------------------------------------------------------
# Prompt
# --------------------------------------------------------------------------
SISTEMA = ("Eres disenador de temas para una pantalla de monitorizacion de PC de 3,5 pulgadas (480x320, "
           "horizontal). Dibujas fondos originales con primitivas y colocas cada cifra al pixel. "
           "Respondes SOLO con un objeto JSON valido, sin texto ni comentarios.")


def prompt(taller: Taller, rng: random.Random, descripcion: str, usados: list[str]) -> list[dict]:
    libres = [a for a in ARQUETIPOS if a not in usados] or ARQUETIPOS
    sugerido = rng.choice(libres[-8:] if rng.random() < 0.5 else libres)
    estilo = descripcion.strip() or rng.choice(ESTILOS)
    ejemplo = {
        "nombre": "RadarNocturno", "arquetipo": "un anillo enorme a un lado y columna de texto al otro",
        "estilo": "radar de barco", "led": "#30ff90",
        "escena": [{"t": "degradado", "arriba": "#021a10", "abajo": "#000804"},
                   {"t": "circulo", "x": 130, "y": 160, "r": 120, "color": "#0a3a20"},
                   {"t": "rejilla", "x": 10, "y": 40, "w": 240, "h": 240, "paso": 30, "color": "#14502c", "alfa": 120},
                   {"t": "panel", "x": 270, "y": 12, "w": 200, "h": 296, "color": "#001008", "alfa": 200, "radio": 10}],
        "etiquetas": [{"texto": "CPU", "x": 120, "y": 40, "fuente": "rb", "tam": 11, "color": "#7dffb0"},
                      {"texto": "RAM", "x": 282, "y": 150, "fuente": "rb", "tam": 10, "color": "#7dffb0"}],
        "widgets": {
            "cpu_rad": {"x": 130, "y": 160, "r": 100, "grosor": 14, "color": "#30ff90", "fondo": "#0f3020",
                        "fuente": "rk", "tam": 30, "color_texto": "#e0ffe8", "inicio": 135, "fin": 45, "pasos": 24, "sep": 3},
            "hour": {"x": 282, "y": 20, "w": 180, "h": 34, "fuente": "rk", "tam": 26, "color": "#e0ffe8", "ancla": "lt"},
            "ram_pct": {"x": 282, "y": 164, "w": 60, "h": 18, "fuente": "rb", "tam": 14, "color": "#e0ffe8", "ancla": "lt"},
            "ram_bar": {"x": 282, "y": 186, "w": 176, "h": 6, "color": "#30ff90"},
            "...": "(el resto de widgets obligatorios)"}}
    usuario = f"""Crea UN tema nuevo para Centro Turing. Pantalla 480x320, origen arriba-izquierda.
Estilo/tema: {estilo}. Arquetipo sugerido: "{sugerido}". Semilla {rng.randint(1000, 9999)}.

1) ARQUETIPO: elige uno de esta lista o inventa uno nuevo. NO uses estos, ya existen: {json.dumps(usados[-25:], ensure_ascii=False)}
   Lista: {json.dumps(ARQUETIPOS, ensure_ascii=False)}
   Cada tema debe tener una DISPOSICION distinta (no el mismo diseno con otro color).
2) ESCENA (fondo, se dibuja en orden): lista de primitivas. Tipos y campos:
   degradado(arriba,abajo) | liso(color) | estrellas(n,color,hasta_y,semilla) | circulo(x,y,r,color,borde,hueco)
   | elipse(x,y,rx,ry,color) | rect(x,y,w,h,color,radio,borde,grosor,alfa,hueco) | panel(x,y,w,h,color,alfa,radio)
   | bisel(x,y,w,h,color,hundido) | poligono(puntos:[[x,y],...],color) | linea(puntos,color,grosor)
   | rejilla(x,y,w,h,paso,color,alfa) | suelo(horizonte,color) | montanas(base_y,alto,color,semilla)
   | olas(y,amplitud,n,color) | rayas(y0,y1,paso,color,alfa) | puntos(x,y,w,h,paso,color)
   | texto(x,y,texto,fuente,tam,color) | desenfoque(radio).  Colores "#rrggbb".
   Dibujo ORIGINAL que cuente el estilo (objetos, paisaje, aparato...). Prohibido: personajes, marcas o logotipos
   con copyright. Pon un "panel" liso detras de cada grupo de textos si el dibujo es cargado.
3) WIDGETS (objeto "widgets", clave -> caja). Obligatorios: {", ".join(OBLIGATORIOS)}; y para CPU, GPU, RAM y
   disco su porcentaje como texto (cpu_pct, gpu_pct, ram_pct, disk_pct) o como radial (cpu_rad, gpu_rad, ram_rad, disk_rad).
   Opcionales: barras {BARRAS}, graficas {LINEAS}.
   Texto: {{"x","y","w","h","fuente","tam","color","ancla"}}. ancla "lt" (izquierda), "mt" (centro) o "rt" (derecha);
   y es el borde de arriba. h >= tam*1.25. Barra/grafica: {{"x","y","w","h","color"}}.
   Radial: {{"x","y" (centro), "r","grosor","color","fondo","fuente","tam","color_texto","inicio","fin","pasos","sep"}};
   el cuadrado x-r..x+r, y-r..y+r debe quedar dentro de la pantalla; el texto "100%" va dentro del anillo.
   Angulos en sentido horario: 135->45 (herradura), 180->0 (semicirculo), 225->315 (aguja de vumetro).
   Ninguna caja puede solaparse con otra. Separacion minima 2 px.
   El texto mas largo que puede salir en cada uno: {json.dumps({k: v[1] for k, v in TEXTOS.items()}, ensure_ascii=False)}
   La caja debe caberlo entero. Ancho en px a tamano 10 (multiplica por tam/10):
{taller.tabla_anchos()}
   Fuentes: {json.dumps(FUENTES, ensure_ascii=False)}. d7 (digital) solo para numeros: sin tildes ni simbolo de grado.
   Hora siempre con hueco para "12:59 p. m." (el reloj sigue CLOCK_FORMAT de 12 o 24 h).
4) ETIQUETAS (se pintan en el fondo): en espanol y cortas: CPU, GPU, VRAM, RAM, DISCO, BAJ, SUB, HUM, SENS.,
   TIEMPO... Cada cifra necesita su etiqueta (salvo hora y fecha). A 2 px o mas de cualquier caja, nunca encima.
5) Contraste: texto claro sobre fondo oscuro o al reves (minimo 3:1). Letra minima 9.
6) "nombre": una palabra sin espacios (max 16). "led": color del LED. "estilo": el estilo elegido.

Formato (ejemplo incompleto; no copies su disposicion):
{json.dumps(ejemplo, ensure_ascii=False)}"""
    return [{"role": "system", "content": SISTEMA}, {"role": "user", "content": usuario}]


# --------------------------------------------------------------------------
# Proceso completo: pedir -> dibujar -> revisar -> corregir -> guardar
# --------------------------------------------------------------------------
def construir(taller: Taller, spec: dict, huellas: dict, usados: list[str]):
    """Devuelve (widgets, fondo con etiquetas, vista previa, errores)."""
    ws, etiquetas, errores = normalizar(spec)
    escena = spec.get("escena") if isinstance(spec.get("escena"), list) else []
    if not escena:
        errores.append("falta la escena: dibuja un fondo con primitivas (no lo dejes liso)")
    fondo = taller.fondo(escena)
    errores += revisar(taller, ws, etiquetas, fondo, escena)
    if not errores:
        h = huella(nodos_de_widgets(ws))
        if h in huellas:
            errores.append(f"la disposicion es igual a la del tema {huellas[h]}; mueve los bloques a otro sitio")
        arq = str(spec.get("arquetipo", "")).strip()
        if arq and arq in usados:
            errores.append(f"el arquetipo '{arq}' ya se uso; elige otro distinto")
    fondo = poner_etiquetas(taller, fondo, etiquetas)
    return ws, fondo, vista_previa(taller, fondo, ws), errores


def crear_tema_taller(root: Path, themes: Path, cliente, extraer_json, descripcion: str = "", log=print,
                      rng: random.Random | None = None, nombre: str | None = None, intentos: int = 4):
    """Crea el tema o devuelve None (y el llamador usa el modo anterior)."""
    rng = rng or random.Random()
    taller = Taller(root)
    huellas, usados = escanear(themes)
    base = prompt(taller, rng, descripcion, usados)
    mensajes = list(base)
    for n in range(1, intentos + 1):
        respuesta = cliente.pedir(mensajes, temperatura=0.8 if n == 1 else 0.35, max_tokens=4096, espera=900)
        if not respuesta:
            return None
        spec = extraer_json(respuesta[0])
        if not spec:
            errores = ["la respuesta no era un objeto JSON valido con 'widgets'"]
            ws = None
        else:
            ws, fondo, preview, errores = construir(taller, spec, huellas, usados)
        if not errores:
            limpio = re.sub(r"[^A-Za-z0-9]+", "", str(spec.get("nombre") or ""))[:16] or "Tema"
            destino = Path(themes) / (nombre or _libre(themes, f"GenIA_35H_{limpio}_"))
            if destino.exists():
                raise SystemExit(f'El tema "{destino.name}" ya existe. Usa otro nombre (--nombre).')
            destino.mkdir(parents=True)
            fondo.convert("RGB").save(destino / "background.png")
            preview.save(destino / "preview.png")
            cab = ("# ---------------------------------------------------------------------------\n"
                   "# Tema GENERADO por el taller IA de Centro Turing (tools/taller_ia.py)\n"
                   "# Pantalla : 3.5\" landscape (480x320)\n"
                   f"# Arquetipo: {str(spec.get('arquetipo', '')).strip()[:90]}\n"
                   f"# Estilo   : {str(spec.get('estilo', '')).strip()[:60]}\n"
                   f"# Diseno   : IA ({respuesta[1]}), revisado en {n} intento(s)\n"
                   "# Vista previa con los valores mas largos posibles. Reloj segun CLOCK_FORMAT.\n"
                   "# ---------------------------------------------------------------------------\n")
            (destino / "theme.yaml").write_text(a_yaml(ws, rgb(spec.get("led"), (255, 255, 255)), cab),
                                                encoding="utf-8", newline="\n")
            log(f"  Taller IA: tema listo en el intento {n} ({spec.get('arquetipo', '')})")
            return destino
        log(f"  Taller IA: intento {n}: {len(errores)} fallo(s): " + "; ".join(errores[:4]))
        previo = json.dumps(spec, ensure_ascii=False) if spec else respuesta[0][:6000]
        mensajes = list(base) + [
            {"role": "assistant", "content": previo},
            {"role": "user", "content": "La revision de la vista previa encontro estos fallos:\n- "
             + "\n- ".join(errores[:25]) + "\nCorrigelos y devuelve el JSON COMPLETO otra vez (mismo formato)."}]
    log("  Taller IA: no salio un tema limpio; se usa el generador anterior")
    return None


def _libre(themes: Path, prefijo: str) -> str:
    usados = {c.name.lower() for c in Path(themes).iterdir()} if Path(themes).is_dir() else set()
    for i in range(1, 1000):
        if f"{prefijo}{i:02d}".lower() not in usados:
            return f"{prefijo}{i:02d}"
    return f"{prefijo}{random.randrange(1000, 9999)}"


def activo() -> bool:
    return os.environ.get("CENTRO_TURING_IA_TALLER", "1").strip().lower() not in ("0", "no", "false", "off")


if __name__ == "__main__":  # python tools/taller_ia.py --revisar spec.json [salida.png]
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "--revisar":
        raiz = Path(__file__).resolve().parent.parent
        t = Taller(raiz)
        datos = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        hs, us = escanear(raiz / "res" / "themes")
        _, _, pv, errs = construir(t, datos, hs, us)
        if len(sys.argv) > 3:
            pv.save(sys.argv[3])
        print("\n".join(errs) if errs else "OK")
        raise SystemExit(1 if errs else 0)
    print(__doc__)
