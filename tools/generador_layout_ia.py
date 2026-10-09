#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generador de temas con DISENO NUEVO (no solo colores) para Centro Turing.

Cada llamada crea un tema completamente distinto, adaptado al tamano y a la
orientacion de la pantalla seleccionada:

  * distribucion de los widgets (donde va cada cosa y de que tamano),
  * que datos se muestran (CPU, GPU, RAM, disco, red, reloj, ping...),
  * tipo de widget (texto, barra, grafica de linea, indicador circular),
  * fuentes, paleta y fondo (degradados, rejilla, circuito, puntos, ondas...).

Primero se pide el diseno a una IA (servidor compatible con OpenAI: el que ya
este abierto en el equipo -Jan, LM Studio, Ollama, llama.cpp-, DeepSeek si hay
DEEPSEEK_API_KEY, o el llama-server de Jan arrancado un momento). La respuesta
se VALIDA (coordenadas dentro de la pantalla, sin solapes, tamanos minimos,
fuentes existentes). Si la IA no esta disponible o su diseno no sirve, se usa
un generador procedural que tambien cambia la distribucion en cada llamada.

Configuracion opcional (variables de entorno o tools/generador_ia.json):
  CENTRO_TURING_IA_URL      p. ej. http://127.0.0.1:1337/v1  (o .../chat/completions)
  CENTRO_TURING_IA_MODELO   nombre del modelo
  CENTRO_TURING_IA_CLAVE    clave (si el servidor la pide)
  CENTRO_TURING_IA_AUTOARRANQUE=0   no arrancar el llama-server de Jan
  CENTRO_TURING_IA=0        no usar IA (solo procedural)
  CENTRO_TURING_IA_ESPERA   segundos maximos por respuesta (por defecto 300; el taller usa 900)
  CENTRO_TURING_IA_TALLER=0 no usar el taller (tools/taller_ia.py) en 3,5" horizontal
"""
from __future__ import annotations

import colorsys
import json
import math
import os
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# --------------------------------------------------------------------------
# Pantallas
# --------------------------------------------------------------------------
# (ancho, alto) en VERTICAL, igual que library/display.py::_get_theme_size
TAMANOS: dict[str, tuple[int, int]] = {
    '0.96"': (80, 160), '2.1"': (480, 480), '2.8"': (480, 480), '3.5"': (320, 480),
    '4.6"': (320, 960), '5"': (480, 800), '5.2"': (720, 1280), '8"': (800, 1280),
    '8.8"': (480, 1920), '9.2"': (480, 1920), '12.3"': (720, 1920),
}
# Revisiones con un unico tamano. C, TUR_USB y SIMU dependen del modelo: se usa el del tema actual.
REVISION_TAMANO = {"A": '3.5"', "B": '3.5"', "D": '3.5"', "WEACT_A": '3.5"', "WEACT_B": '0.96"'}


def _norm_tamano(valor) -> str:
    s = str(valor or "").strip().replace("'", "").replace('"', "").replace(" ", "").lower()
    s = s.replace("pulgadas", "").replace("inch", "").replace(",", ".")
    return f'{s}"' if f'{s}"' in TAMANOS else ""


def _norm_orientacion(valor) -> str:
    s = str(valor or "").strip().lower()
    if s in ("landscape", "horizontal", "h", "apaisado"):
        return "landscape"
    if s in ("portrait", "vertical", "v"):
        return "portrait"
    return ""


def _leer_yaml_simple(ruta: Path) -> dict:
    try:
        import yaml  # type: ignore
        with open(ruta, encoding="utf-8-sig") as f:
            datos = yaml.safe_load(f)
        return datos if isinstance(datos, dict) else {}
    except Exception:  # noqa: BLE001
        pass
    # Respaldo sin PyYAML: solo claves "CLAVE: valor"
    datos: dict = {}
    try:
        for linea in ruta.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            m = re.match(r"^\s*([A-Z_]+):\s*(.*?)\s*$", linea)
            if m and m.group(1) not in datos:
                datos[m.group(1)] = m.group(2).strip("'")
    except OSError:
        pass
    return {"_plano": datos}


def _clave(datos: dict, seccion: str, clave: str):
    if "_plano" in datos:
        return datos["_plano"].get(clave)
    return (datos.get(seccion) or {}).get(clave)


def detectar_pantalla(root: Path, tamano: str | None = None, orientacion: str | None = None) -> dict:
    """Tamano/orientacion seleccionados: config.yaml (REVISION) + tema actual."""
    cfg = _leer_yaml_simple(root / "config.yaml")
    revision = str(_clave(cfg, "display", "REVISION") or "A").strip().upper()
    tema = str(_clave(cfg, "config", "THEME") or "").strip()
    clave_tiempo = str(_clave(cfg, "config", "WEATHER_API_KEY") or "").strip()

    tam_tema, ori_tema = "", ""
    if tema:
        td = _leer_yaml_simple(root / "res" / "themes" / tema / "theme.yaml")
        tam_tema = _norm_tamano(_clave(td, "display", "DISPLAY_SIZE"))
        ori_tema = _norm_orientacion(_clave(td, "display", "DISPLAY_ORIENTATION"))

    tam_rev = REVISION_TAMANO.get(revision, "")
    tam = _norm_tamano(tamano) or tam_rev or tam_tema or '3.5"'
    ori = _norm_orientacion(orientacion)
    if not ori:
        ori = ori_tema if (ori_tema and tam_tema == tam) else ("landscape" if tam != '0.96"' else "portrait")
    w, h = TAMANOS[tam]
    if ori == "landscape":
        w, h = h, w
    return {"tamano": tam, "orientacion": ori, "ancho": w, "alto": h, "revision": revision,
            "tema_actual": tema, "tiempo": bool(clave_tiempo) and clave_tiempo != "YOUR_OPENWEATHERMAP_API_KEY"}


# --------------------------------------------------------------------------
# Catalogo de datos (ruta en STATS, nodo de texto, tipos de widget permitidos)
# --------------------------------------------------------------------------
TODOS = ("texto", "barra", "linea", "radial")
DATOS: dict[str, dict] = {
    "cpu_uso":    dict(ruta=("CPU", "PERCENTAGE"), txt="TEXT", tipos=TODOS, etq="CPU", ej="100%", demo=37, max=100),
    "cpu_temp":   dict(ruta=("CPU", "TEMPERATURE"), txt="TEXT", tipos=TODOS, etq="TEMP CPU", ej="100°C", demo=54, max=100),
    "cpu_frec":   dict(ruta=("CPU", "FREQUENCY"), txt="TEXT", tipos=("texto", "linea"), etq="FREC CPU", ej="5.20 GHz", demo=None, auto=True),
    "gpu_uso":    dict(ruta=("GPU", "PERCENTAGE"), txt="TEXT", tipos=TODOS, etq="GPU", ej="100%", demo=62, max=100),
    "gpu_temp":   dict(ruta=("GPU", "TEMPERATURE"), txt="TEXT", tipos=TODOS, etq="TEMP GPU", ej="100°C", demo=48, max=100),
    "gpu_mem":    dict(ruta=("GPU", "MEMORY_PERCENT"), txt="TEXT", tipos=TODOS, etq="VRAM", ej="100%", demo=41, max=100),
    "gpu_frec":   dict(ruta=("GPU", "FREQUENCY"), txt="TEXT", tipos=("texto", "linea"), etq="FREC GPU", ej="2.10 GHz", demo=None, auto=True),
    "ram_uso":    dict(ruta=("MEMORY", "VIRTUAL"), txt="PERCENT_TEXT", tipos=TODOS, etq="RAM", ej="100%", demo=58, max=100),
    "ram_usada":  dict(ruta=("MEMORY", "VIRTUAL", "USED"), txt=None, tipos=("texto",), etq="RAM USADA", ej="131072 M", demo=None),
    "disco_uso":  dict(ruta=("DISK", "USED"), txt="PERCENT_TEXT", tipos=("texto", "barra", "radial"), etq="DISCO", ej="100%", demo=71, max=100),
    "disco_libre": dict(ruta=("DISK", "FREE"), txt="TEXT", tipos=("texto",), etq="DISCO LIBRE", ej="99999 G", demo=None),
    "red_bajada": dict(ruta=("NET", "ETH", "DOWNLOAD"), txt="TEXT", tipos=("texto", "linea"), etq="BAJADA", ej="1023.9 MB/s", demo=None, auto=True),
    "red_subida": dict(ruta=("NET", "ETH", "UPLOAD"), txt="TEXT", tipos=("texto", "linea"), etq="SUBIDA", ej="1023.9 MB/s", demo=None, auto=True),
    "uptime":     dict(ruta=("UPTIME", "FORMATTED"), txt="TEXT", tipos=("texto",), etq="ENCENDIDO", ej="9 days, 23:59:59", demo=None),
    "ping":       dict(ruta=("PING",), txt="TEXT", tipos=("texto", "linea", "barra"), etq="PING", ej="9999ms", demo=18, max=200, auto=True),
    "reloj":      dict(ruta=("DATE",), txt=None, tipos=("texto",), etq="", ej="12:59 p. m.", demo=None),
    "tiempo":     dict(ruta=("WEATHER",), txt=None, tipos=("texto",), etq="TIEMPO", ej="-99°C", demo=None, tiempo=True),
}
DEMO_TEXTO = {"cpu_frec": "3.85 GHz", "gpu_frec": "1.74 GHz", "ram_usada": "18422 M", "disco_libre": "512 G",
              "red_bajada": "2.4 M/s", "red_subida": "310.0 K/s", "uptime": "2 days, 4:12:09",
              "cpu_temp": "54°C", "gpu_temp": "48°C", "ping": "18ms"}
INTERVALO_GRUPO = {"GPU": 1, "MEMORY": 3, "DISK": 10, "NET": 1, "DATE": 1, "UPTIME": 5, "PING": 5, "WEATHER": 600}
INTERVALO_CPU = {"PERCENTAGE": 1, "TEMPERATURE": 3, "FREQUENCY": 3}

FUENTES_VALOR = [
    "jetbrains-mono/JetBrainsMono-Bold.ttf", "jetbrains-mono/JetBrainsMono-ExtraBold.ttf",
    "jetbrains-mono/JetBrainsMono-Light.ttf", "roboto/Roboto-Black.ttf", "roboto/Roboto-Bold.ttf",
    "roboto/Roboto-Light.ttf", "roboto-mono/RobotoMono-Bold.ttf", "roboto-mono/RobotoMono-Light.ttf",
    "geforce/GeForce-Bold.ttf", "generale-mono/GeneraleMonoA.ttf", "digital/DIGITAL-7.TTF",
]
FUENTES_ETIQUETA = [
    "roboto/Roboto-Medium.ttf", "roboto/Roboto-Bold.ttf", "roboto/Roboto-Regular.ttf",
    "jetbrains-mono/JetBrainsMono-Medium.ttf", "jetbrains-mono/JetBrainsMono-SemiBold.ttf",
    "roboto-mono/RobotoMono-Medium.ttf", "geforce/GeForce-Light.ttf",
]
ESTILOS_FONDO = ["degradado", "radial", "rejilla", "lineas", "circuito", "puntos", "diagonal", "bokeh",
                 "ondas", "estrellas", "liso"]
DISTRIBUCIONES = ["reloj grande arriba y mosaico debajo", "columna lateral con reloj y rejilla de indicadores",
                  "un indicador circular enorme en el centro rodeado de datos pequenos",
                  "tres columnas", "dos filas de tarjetas", "reloj abajo y graficas de linea arriba",
                  "asimetrica tipo revista", "cuatro cuadrantes", "barras horizontales apiladas"]
PANELES = ["redondeado", "contorno", "esquinas", "cristal", "lateral", "subrayado", "ninguno"]
INSPIRACION = ["cyberpunk", "minimalista suizo", "cabina de avion", "terminal retro", "vaporwave", "nordico",
               "oceano profundo", "volcan", "bosque nocturno", "neon de Tokio", "art deco", "laboratorio",
               "galaxia", "papel japones", "industrial", "arcade 80s", "aurora boreal", "desierto", "hielo",
               "carbono y rojo", "pastel suave", "matrix", "sintetizador", "submarino", "estacion espacial"]


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------
def _rgb(valor, defecto=(255, 255, 255)) -> tuple[int, int, int]:
    if isinstance(valor, (list, tuple)) and len(valor) >= 3:
        try:
            return tuple(max(0, min(255, int(v))) for v in valor[:3])  # type: ignore[return-value]
        except (TypeError, ValueError):
            return defecto
    s = str(valor or "").strip()
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", s)
    if m:
        h = m.group(1)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    m = re.fullmatch(r"#?([0-9a-fA-F]{3})", s)
    if m:
        h = m.group(1)
        return int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16)
    m = re.findall(r"\d{1,3}", s)
    if len(m) >= 3:
        return tuple(max(0, min(255, int(v))) for v in m[:3])  # type: ignore[return-value]
    return defecto


def _col(c) -> str:
    return f"{c[0]}, {c[1]}, {c[2]}"


def _hsv(h: float, s: float, v: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0, min(1, s)), max(0, min(1, v)))
    return int(r * 255), int(g * 255), int(b * 255)


def _lum(c) -> float:
    return (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255.0


def _mezcla(a, b, t: float):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _contraste(texto, fondo, minimo=0.45):
    """Si el texto no contrasta con el fondo, lo aclara u oscurece."""
    if abs(_lum(texto) - _lum(fondo)) >= minimo:
        return texto
    return _mezcla(texto, (255, 255, 255) if _lum(fondo) < 0.5 else (0, 0, 0), 0.75)


class Fuentes:
    def __init__(self, root: Path):
        self.dir = root / "res" / "fonts"
        self._cache: dict = {}
        self._ok: dict = {}

    def existe(self, rel: str) -> bool:
        return (self.dir / rel).is_file()

    def get(self, rel: str, size: int):
        clave = (rel, int(size))
        if clave not in self._cache:
            try:
                self._cache[clave] = ImageFont.truetype(str(self.dir / rel), max(6, int(size)))
            except Exception:  # noqa: BLE001
                self._cache[clave] = ImageFont.load_default()
        return self._cache[clave]

    def soporta(self, rel: str, texto: str) -> bool:
        """True si la fuente tiene todos los glifos (compara con un caracter inexistente)."""
        clave = (rel, texto)
        if clave in self._ok:
            return self._ok[clave]
        ok = self.existe(rel)
        if ok:
            f = self.get(rel, 24)
            try:
                falta = (f.getmask("\U0010FFFD").getbbox(), f.getlength("\U0010FFFD"))
                for ch in set(texto) - {" "}:
                    if (f.getmask(ch).getbbox(), f.getlength(ch)) == falta:
                        ok = False
                        break
            except Exception:  # noqa: BLE001
                ok = True
        self._ok[clave] = ok
        return ok

    def ajustar(self, rel: str, texto: str, ancho: int, alto: int, maximo: int = 200) -> int:
        """Mayor tamano de letra con el que 'texto' cabe en ancho x alto."""
        size = max(7, min(maximo, int(alto / 1.22)))
        while size > 7:
            f = self.get(rel, size)
            _, t, _, b = f.getbbox(texto)
            if f.getlength(texto) <= ancho and (b - min(0, t)) * 1.08 <= alto:
                break
            size -= 1
        return size


def _demo_fecha() -> tuple[str, str]:
    """Textos de ejemplo largos (en espanol) para dimensionar dia y fecha."""
    try:
        import datetime
        import babel.dates  # type: ignore
        d = datetime.date(2026, 9, 30)
        return (babel.dates.format_date(d, format="EEEE", locale="es"),
                babel.dates.format_date(d, format="d MMM yyyy", locale="es"))
    except Exception:  # noqa: BLE001
        return "miércoles", "30 sept 2026"


# --------------------------------------------------------------------------
# Paleta y fondo
# --------------------------------------------------------------------------
def paleta_aleatoria(rng: random.Random, tono: float | None = None) -> dict:
    h = rng.random() if tono is None else tono
    esquema = rng.choice(["analogo", "complementario", "triada", "mono", "split"])
    h2 = {"analogo": h + 0.08, "complementario": h + 0.5, "triada": h + 0.333, "mono": h,
          "split": h + 0.42}[esquema]
    if rng.random() < 0.12:  # tema claro
        f1, f2 = _hsv(h, rng.uniform(0.05, 0.18), 0.96), _hsv(h2, rng.uniform(0.08, 0.25), 0.86)
        texto, tenue = _hsv(h, 0.6, 0.18), _hsv(h, 0.35, 0.42)
        acento, acento2 = _hsv(h, rng.uniform(0.75, 1), 0.72), _hsv(h2, rng.uniform(0.7, 1), 0.65)
    else:
        f1 = _hsv(h, rng.uniform(0.35, 0.9), rng.uniform(0.03, 0.12))
        f2 = _hsv(h2 + rng.uniform(-0.04, 0.04), rng.uniform(0.4, 0.95), rng.uniform(0.12, 0.30))
        acento = _hsv(h, rng.uniform(0.6, 1.0), rng.uniform(0.85, 1.0))
        acento2 = _hsv(h2, rng.uniform(0.5, 1.0), rng.uniform(0.85, 1.0))
        texto = _hsv(h, rng.uniform(0.0, 0.12), rng.uniform(0.92, 1.0))
        tenue = _hsv(h, rng.uniform(0.15, 0.4), rng.uniform(0.55, 0.75))
    return {"fondo1": f1, "fondo2": f2, "acento": acento, "acento2": acento2, "texto": texto, "tenue": tenue}


def _degradado(w: int, h: int, c1, c2, angulo: float) -> Image.Image:
    ca, sa = math.cos(angulo), math.sin(angulo)
    proy = [x * ca + y * sa for x, y in ((0, 0), (w, 0), (0, h), (w, h))]
    lo, hi = min(proy), max(proy)
    rango = (hi - lo) or 1
    datos = []
    for y in range(h):
        for x in range(w):
            t = ((x * ca + y * sa) - lo) / rango
            datos.append((int(c1[0] + (c2[0] - c1[0]) * t), int(c1[1] + (c2[1] - c1[1]) * t),
                          int(c1[2] + (c2[2] - c1[2]) * t)))
    img = Image.new("RGB", (w, h))
    img.putdata(datos)
    return img


def generar_fondo(w: int, h: int, pal: dict, estilo: str, rng: random.Random) -> Image.Image:
    f1, f2, ac, ac2 = pal["fondo1"], pal["fondo2"], pal["acento"], pal["acento2"]
    if estilo == "liso":
        img = Image.new("RGB", (w, h), f1)
    elif estilo == "radial":
        img = Image.new("RGB", (w, h), f1)
        d = ImageDraw.Draw(img)
        cx, cy = rng.uniform(0, w), rng.uniform(0, h)
        rmax = int(max(w, h) * rng.uniform(0.6, 1.1))
        for i in range(rmax, 0, -6):
            d.ellipse((cx - i, cy - i, cx + i, cy + i), fill=_mezcla(f1, f2, 1 - i / rmax))
        img = img.filter(ImageFilter.GaussianBlur(6))
    else:
        img = _degradado(w, h, f1, f2, rng.uniform(0, math.pi * 2))

    capa = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    a = rng.randint(18, 42)
    if estilo == "rejilla":
        paso = rng.choice([16, 20, 24, 32])
        for x in range(0, w, paso):
            d.line((x, 0, x, h), fill=ac + (a,))
        for y in range(0, h, paso):
            d.line((0, y, w, y), fill=ac + (a,))
    elif estilo == "lineas":
        paso = rng.choice([2, 3, 4])
        for y in range(0, h, paso):
            d.line((0, y, w, y), fill=(0, 0, 0, rng.randint(40, 70)))
    elif estilo == "circuito":
        for _ in range(int(w * h / 2500)):
            x, y = rng.randrange(0, w, 8), rng.randrange(0, h, 8)
            for _ in range(rng.randint(2, 5)):
                if rng.random() < 0.5:
                    nx, ny = x + rng.choice([-1, 1]) * rng.randrange(16, 80, 8), y
                else:
                    nx, ny = x, y + rng.choice([-1, 1]) * rng.randrange(16, 60, 8)
                d.line((x, y, nx, ny), fill=ac + (a + 10,), width=1)
                x, y = nx, ny
            d.ellipse((x - 2, y - 2, x + 2, y + 2), outline=ac + (a + 40,))
    elif estilo == "puntos":
        paso = rng.choice([8, 10, 12, 16])
        r = rng.choice([1, 1, 2])
        for y in range(paso // 2, h, paso):
            for x in range(paso // 2, w, paso):
                d.ellipse((x - r, y - r, x + r, y + r), fill=ac + (a,))
    elif estilo == "diagonal":
        paso = rng.choice([10, 14, 20, 28])
        grosor = rng.choice([1, 2, 4])
        for k in range(-h, w + h, paso):
            d.line((k, 0, k + h, h), fill=ac + (a // 2 + 6,), width=grosor)
    elif estilo == "bokeh":
        for _ in range(rng.randint(10, 26)):
            r = rng.randint(int(min(w, h) * 0.04), int(min(w, h) * 0.22))
            x, y = rng.randint(0, w), rng.randint(0, h)
            d.ellipse((x - r, y - r, x + r, y + r), fill=rng.choice([ac, ac2]) + (rng.randint(14, 40),))
        capa = capa.filter(ImageFilter.GaussianBlur(4))
    elif estilo == "ondas":
        for _ in range(rng.randint(3, 7)):
            amp, fase = rng.uniform(6, h * 0.12), rng.uniform(0, 6.3)
            frec, base_y = rng.uniform(1, 3.5), rng.uniform(0.15, 0.95) * h
            pts = [(x, base_y + amp * math.sin(fase + frec * x / w * 2 * math.pi)) for x in range(0, w + 4, 4)]
            d.line(pts, fill=rng.choice([ac, ac2]) + (a + 8,), width=rng.choice([1, 2, 3]))
    elif estilo == "estrellas":
        for _ in range(int(w * h / 600)):
            d.point((rng.randint(0, w - 1), rng.randint(0, h - 1)), fill=(255, 255, 255, rng.randint(40, 200)))
        for _ in range(4):
            x, y, r = rng.randint(0, w), rng.randint(0, h), rng.randint(20, 80)
            d.ellipse((x - r, y - r, x + r, y + r), fill=ac2 + (12,))
    if rng.random() < 0.6:  # vineta suave
        m = int(min(w, h) * 0.08)
        vin = Image.new("L", (w, h), 0)
        ImageDraw.Draw(vin).rectangle((m, m, w - m, h - m), fill=255)
        vin = vin.filter(ImageFilter.GaussianBlur(m))
        oscuro = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        oscuro.putalpha(vin.point(lambda v: int((255 - v) * 0.35)))
        capa = Image.alpha_composite(capa, oscuro)
    return Image.alpha_composite(img.convert("RGBA"), capa).convert("RGB")


# --------------------------------------------------------------------------
# Diseno: validacion de lo que devuelve la IA y distribucion procedural
# --------------------------------------------------------------------------
MIN_TAM = {"texto": (44, 22), "barra": (70, 34), "linea": (80, 44), "radial": (60, 60)}


def _area(r) -> int:
    return max(0, r[2]) * max(0, r[3])


def _interseccion(a, b) -> int:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    return max(0, x2 - x1) * max(0, y2 - y1)


def _mejor_tipo(dato: str, w: int, h: int, pedido: str | None, rng: random.Random) -> str | None:
    validos = [t for t in DATOS[dato]["tipos"] if w >= MIN_TAM[t][0] and h >= MIN_TAM[t][1]]
    if not validos:
        return None
    if pedido in validos:
        return pedido
    ar = w / max(1, h)
    pesos = [{"texto": 1.0, "barra": 1.6 if ar > 1.8 else 0.6, "linea": 2.0 if ar > 1.6 and h >= 50 else 0.4,
              "radial": 2.5 if 0.65 < ar < 1.6 else 0.15}[t] for t in validos]
    return rng.choices(validos, pesos)[0]


def _fuentes_ok(fuentes, lista):
    return [f for f in lista if fuentes.existe(f)] or ["roboto/Roboto-Bold.ttf"]


def validar_diseno(spec: dict, pant: dict, fuentes: Fuentes, rng: random.Random) -> dict:
    """Limpia lo que devuelve la IA: datos/tipos validos, coordenadas, solapes, fuentes, contraste."""
    W, H = pant["ancho"], pant["alto"]
    salida: dict = {"nombre": re.sub(r"[^A-Za-z0-9]+", "", str(spec.get("nombre") or ""))[:16]}
    estilo = str(spec.get("estilo_fondo") or "").lower()
    salida["estilo_fondo"] = estilo if estilo in ESTILOS_FONDO else rng.choice(ESTILOS_FONDO)
    panel = str(spec.get("panel") or "").lower()
    salida["panel"] = panel if panel in PANELES else rng.choice(PANELES)
    base = paleta_aleatoria(rng)
    cols = spec.get("colores") if isinstance(spec.get("colores"), dict) else {}
    pal = {k: _rgb(cols.get(k), base[k]) for k in base}
    if abs(_lum(pal["fondo1"]) - _lum(pal["fondo2"])) > 0.3:  # degradado de oscuro a claro: ilegible
        pal["fondo2"] = _mezcla(pal["fondo1"], pal["fondo2"], 0.3)
    pal["texto"] = _contraste(pal["texto"], pal["fondo1"])
    for k, m in (("acento", 0.25), ("acento2", 0.25), ("tenue", 0.22)):
        pal[k] = _contraste(pal[k], pal["fondo1"], m)
    salida["colores"] = pal
    fv, fe = str(spec.get("fuente_valores") or ""), str(spec.get("fuente_etiquetas") or "")
    salida["fuente_valores"] = fv if fv in FUENTES_VALOR and fuentes.existe(fv) else rng.choice(_fuentes_ok(fuentes, FUENTES_VALOR))
    salida["fuente_etiquetas"] = fe if fe in FUENTES_ETIQUETA and fuentes.existe(fe) else rng.choice(_fuentes_ok(fuentes, FUENTES_ETIQUETA))

    aceptados: list[dict] = []
    usados: set[str] = set()
    for wd in spec.get("widgets") or []:
        if not isinstance(wd, dict):
            continue
        dato = str(wd.get("dato") or "").strip().lower()
        if dato not in DATOS or dato in usados:
            continue
        if DATOS[dato].get("tiempo") and not pant.get("tiempo"):
            continue
        try:
            x, y = int(float(wd.get("x"))), int(float(wd.get("y")))
            w, h = int(float(wd.get("ancho"))), int(float(wd.get("alto")))
        except (TypeError, ValueError):
            continue
        x, y = max(0, min(W - 10, x)), max(0, min(H - 10, y))
        w, h = max(1, min(W - x, w)), max(1, min(H - y, h))
        tipo = _mejor_tipo(dato, w, h, str(wd.get("tipo") or "").lower(), rng)
        if tipo is None:
            continue
        r = (x, y, w, h)
        if any(_interseccion(r, a["rect"]) > 0.25 * min(_area(r), _area(a["rect"])) for a in aceptados):
            continue
        for a in aceptados:  # solape pequeno: se recorta el rectangulo nuevo
            if _interseccion(r, a["rect"]):
                r = _recortar(r, a["rect"])
        if any(_interseccion(r, a["rect"]) for a in aceptados) or _mejor_tipo(dato, r[2], r[3], None, rng) is None:
            continue
        tipo = _mejor_tipo(dato, r[2], r[3], str(wd.get("tipo") or "").lower(), rng) or tipo
        etq = wd.get("etiqueta")
        etq = DATOS[dato]["etq"] if etq is None else str(etq)
        etq = re.sub(r"[^\w %°/.:+-]", "", etq).strip()[:14]
        color = str(wd.get("color") or "acento").lower()
        aceptados.append({"dato": dato, "tipo": tipo, "rect": r, "etiqueta": etq,
                          "color": color if color in ("acento", "acento2", "texto") else "acento",
                          "alineacion": str(wd.get("alineacion") or "").lower()})
        usados.add(dato)
    if aceptados:  # la IA suele dejar huecos: se agrandan los widgets hasta ocupar la pantalla
        margen = max(4, int(min(W, H) * 0.02))
        nuevos = _expandir([a["rect"] for a in aceptados], W, H, margen, max(4, margen))
        for a, r in zip(aceptados, nuevos):
            a["rect"] = r
            a["tipo"] = _mejor_tipo(a["dato"], r[2], r[3], a["tipo"], rng) or a["tipo"]
    salida["widgets"] = aceptados
    return salida


def _recortar(r, otro):
    """Quita a r la parte que pisa a 'otro' (por el lado que menos area pierde)."""
    x, y, w, h = r
    ox, oy, ow, oh = otro
    opciones = []
    if ox + ow > x and ox + ow < x + w:   # cortar por la izquierda
        opciones.append((ox + ow, y, x + w - (ox + ow), h))
    if ox > x and ox < x + w:             # cortar por la derecha
        opciones.append((x, y, ox - x, h))
    if oy + oh > y and oy + oh < y + h:   # cortar por arriba
        opciones.append((x, oy + oh, w, y + h - (oy + oh)))
    if oy > y and oy < y + h:             # cortar por abajo
        opciones.append((x, y, w, oy - y))
    opciones = [o for o in opciones if o[2] > 0 and o[3] > 0 and not _interseccion(o, otro)]
    return max(opciones, key=_area) if opciones else (x, y, 0, 0)


def _expandir(rects, W, H, margen, hueco):
    """Agranda cada rectangulo (por turnos, 2 px por lado) sin pisar a los demas ni salirse."""
    rs = [[r[0], r[1], r[0] + r[2], r[1] + r[3]] for r in rects]
    paso = 2

    def sep(a, b) -> int:
        return max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3])

    def libre(i, c):
        if c[0] < margen or c[1] < margen or c[2] > W - margen or c[3] > H - margen:
            return False
        for j, o in enumerate(rs):
            # no acercarse a otro por debajo del hueco (ni mas de lo que ya estaba)
            if j != i and sep(c, o) < min(hueco, sep(rs[i], o)):
                return False
        return True

    for i, c in enumerate(rs):  # primero, meter dentro del margen lo que ya estaba pegado al borde
        c[0], c[1] = max(c[0], margen), max(c[1], margen)
        c[2], c[3] = min(c[2], W - margen), min(c[3], H - margen)
    cambiado = True
    vueltas = 0
    while cambiado and vueltas < 1000:
        cambiado = False
        vueltas += 1
        for i, c in enumerate(rs):
            for lado, delta in ((0, -paso), (1, -paso), (2, paso), (3, paso)):
                prueba = list(c)
                prueba[lado] += delta
                if libre(i, prueba):
                    rs[i] = c = prueba
                    cambiado = True
    return [(c[0], c[1], c[2] - c[0], c[3] - c[1]) for c in rs]


def _partir(rng: random.Random, rect, n: int, minw: int, minh: int) -> list:
    """Particion recursiva (guillotina) con cortes al azar: cada vez una distribucion distinta."""
    rects = [rect]
    intentos = 0
    while len(rects) < n and intentos < 200:
        intentos += 1
        rects.sort(key=_area, reverse=True)
        idx = 0 if rng.random() < 0.7 else rng.randrange(len(rects))
        x, y, w, h = rects[idx]
        vertical = w > h * 1.25 or (h <= w * 1.25 and rng.random() < 0.5)
        t = rng.uniform(0.32, 0.68)
        if vertical:
            a = int(w * t)
            if a < minw or w - a < minw:
                continue
            nuevos = [(x, y, a, h), (x + a, y, w - a, h)]
        else:
            a = int(h * t)
            if a < minh or h - a < minh:
                continue
            nuevos = [(x, y, w, a), (x, y + a, w, h - a)]
        rects.pop(idx)
        rects += nuevos
    return rects


def diseno_procedural(pant: dict, fuentes: Fuentes, rng: random.Random, preferencia: dict | None = None,
                      tono: float | None = None) -> dict:
    """Distribucion nueva al azar (particion recursiva + cabecera/pie/lateral opcional)."""
    W, H = pant["ancho"], pant["alto"]
    escala = math.sqrt(W * H / (480 * 320))
    margen = rng.choice([4, 6, 8, 10, 12])
    hueco = rng.choice([4, 6, 8, 10])
    zona = (margen, margen, W - 2 * margen, H - 2 * margen)
    widgets: list[dict] = []
    forma = rng.choice(["cabecera", "cabecera", "lateral", "pie", "libre", "libre"])
    if W < H and forma == "lateral":
        forma = "cabecera"
    x, y, w, h = zona
    if forma == "cabecera":
        alto = int(h * rng.uniform(0.17, 0.27))
        widgets.append({"dato": "reloj", "rect": (x, y, w, alto)})
        zona = (x, y + alto + hueco, w, h - alto - hueco)
    elif forma == "pie":
        alto = int(h * rng.uniform(0.15, 0.22))
        widgets.append({"dato": "reloj", "rect": (x, y + h - alto, w, alto)})
        zona = (x, y, w, h - alto - hueco)
    elif forma == "lateral":
        ancho = int(w * rng.uniform(0.26, 0.36))
        izquierda = rng.random() < 0.5
        widgets.append({"dato": "reloj", "rect": (x if izquierda else x + w - ancho, y, ancho, h)})
        zona = (x + ancho + hueco if izquierda else x, y, w - ancho - hueco, h)

    pref = [d for d in (preferencia or {}).get("datos", []) if d in DATOS and d != "reloj"]
    n = (rng.randint(3, 6) if escala < 1.3 else rng.randint(5, 9)) + (1 if forma == "libre" else 0)
    huecos = _partir(rng, zona, n, int(78 * escala), int(50 * escala))
    pool = ["cpu_uso", "gpu_uso", "ram_uso", "cpu_temp", "gpu_temp", "disco_uso", "red_bajada", "red_subida",
            "gpu_mem", "cpu_frec", "gpu_frec", "uptime", "ping", "disco_libre", "ram_usada"]
    if pant.get("tiempo"):
        pool.append("tiempo")
    if forma == "libre":
        pool.append("reloj")
    pesos = {"cpu_uso": 9, "gpu_uso": 8, "ram_uso": 8, "cpu_temp": 6, "gpu_temp": 6, "disco_uso": 4,
             "red_bajada": 4, "red_subida": 3, "gpu_mem": 3, "reloj": 10}
    pref = [d for d in pref if not DATOS[d].get("tiempo") or pant.get("tiempo")]
    restantes = list(dict.fromkeys(pref + pool))
    for rx, ry, rw, rh in sorted(huecos, key=_area, reverse=True):
        r = (rx + hueco // 2, ry + hueco // 2, rw - hueco, rh - hueco)
        candidatos = [d for d in restantes if _mejor_tipo(d, r[2], r[3], None, rng)]
        if not candidatos:
            continue
        dato = candidatos[0] if candidatos[0] in pref else rng.choices(candidatos, [pesos.get(d, 2) for d in candidatos])[0]
        restantes.remove(dato)
        widgets.append({"dato": dato, "rect": r})

    tipos_pref = (preferencia or {}).get("tipos", {})
    for wd in widgets:
        wd["tipo"] = _mejor_tipo(wd["dato"], wd["rect"][2], wd["rect"][3], tipos_pref.get(wd["dato"]), rng) or "texto"
        wd["etiqueta"] = DATOS[wd["dato"]]["etq"]
        wd["color"] = rng.choice(["acento", "acento", "acento2", "texto"])
        wd["alineacion"] = rng.choice(["izquierda", "centro", "derecha", "izquierda"])
    spec = {"nombre": "", "estilo_fondo": rng.choice(ESTILOS_FONDO), "panel": rng.choice(PANELES),
            "colores": paleta_aleatoria(rng, tono), "widgets": widgets,
            "fuente_valores": rng.choice(_fuentes_ok(fuentes, FUENTES_VALOR)),
            "fuente_etiquetas": rng.choice(_fuentes_ok(fuentes, FUENTES_ETIQUETA))}
    for k in ("estilo_fondo", "panel", "colores", "fuente_valores", "fuente_etiquetas", "nombre"):
        if preferencia and preferencia.get(k):
            spec[k] = preferencia[k]
    return spec


# --------------------------------------------------------------------------
# Construccion: especificacion -> theme.yaml + fondo + vista previa
# --------------------------------------------------------------------------
def _ruta_set(arbol: dict, ruta: tuple, valor: dict) -> None:
    nodo = arbol
    for k in ruta[:-1]:
        nodo = nodo.setdefault(k, {})
    nodo.setdefault(ruta[-1], {}).update(valor)


def construir(spec: dict, pant: dict, fuentes: Fuentes, rng: random.Random):
    """Devuelve (theme_dict, fondo PIL, vista previa PIL)."""
    W, H = pant["ancho"], pant["alto"]
    pal = spec["colores"]
    fv, fe = spec["fuente_valores"], spec["fuente_etiquetas"]
    fondo = generar_fondo(W, H, pal, spec["estilo_fondo"], rng)
    deco = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(deco)
    stats: dict = {}
    vista: list = []
    escala = math.sqrt(W * H / (480 * 320))
    pad = max(3, int(rng.choice([5, 6, 8]) * escala))
    radio_panel = rng.choice([4, 8, 12, 16])
    dia_ej, fecha_ej = _demo_fecha()

    def txt_nodo(rect, fuente, muestra, color, alin, maximo=200):
        x, y, w, h = [int(v) for v in rect]
        w, h = max(8, min(w, W - x)), max(8, min(h, H - y))
        if not fuentes.soporta(fuente, muestra):
            fuente = "roboto/Roboto-Bold.ttf"
        size = fuentes.ajustar(fuente, muestra, w, h, min(maximo, int(min(W, H) * 0.3)))
        alto = min(h, int(size * 1.25) + 2)
        anchor, align = {"centro": ("mt", "center"), "derecha": ("rt", "right")}.get(alin, ("lt", "left"))
        # Con WIDTH/HEIGHT, library/lcd usa X como borde izquierdo del recuadro y alinea dentro.
        return {"SHOW": True, "SHOW_UNIT": True, "X": x, "Y": y, "WIDTH": w, "HEIGHT": alto, "FONT": fuente,
                "FONT_SIZE": size, "FONT_COLOR": _col(color), "BACKGROUND_IMAGE": "background.png",
                "ALIGN": align, "ANCHOR": anchor, "MIN_SIZE": 0}

    def panel(rect, color):
        x, y, w, h = rect
        estilo = spec["panel"]
        if estilo == "redondeado":
            dd.rounded_rectangle((x, y, x + w - 1, y + h - 1), radio_panel, fill=pal["fondo2"] + (150,),
                                 outline=color + (110,), width=1)
        elif estilo == "contorno":
            dd.rounded_rectangle((x, y, x + w - 1, y + h - 1), min(radio_panel, 6), outline=color + (170,), width=1)
        elif estilo == "esquinas":
            L = max(6, min(w, h) // 5)
            for cx, cy, sx, sy in ((x, y, 1, 1), (x + w - 1, y, -1, 1), (x, y + h - 1, 1, -1),
                                   (x + w - 1, y + h - 1, -1, -1)):
                dd.line((cx, cy, cx + sx * L, cy), fill=color + (230,), width=2)
                dd.line((cx, cy, cx, cy + sy * L), fill=color + (230,), width=2)
        elif estilo == "cristal":
            dd.rounded_rectangle((x, y, x + w - 1, y + h - 1), radio_panel, fill=(255, 255, 255, 22),
                                 outline=(255, 255, 255, 50), width=1)
        elif estilo == "lateral":
            dd.rectangle((x, y, x + w - 1, y + h - 1), fill=(0, 0, 0, 70))
            dd.rectangle((x, y, x + 3, y + h - 1), fill=color + (255,))
        elif estilo == "subrayado":
            dd.line((x, y + h - 1, x + w - 1, y + h - 1), fill=color + (160,), width=1)

    def etiqueta(texto, x, y, w, size, color, alin) -> int:
        """Dibuja la etiqueta fija en el fondo; devuelve el alto ocupado."""
        if not texto:
            return 0
        f = fuentes.get(fe, size)
        while size > 7 and f.getlength(texto) > w:
            size -= 1
            f = fuentes.get(fe, size)
        largo = f.getlength(texto)
        tx = {"centro": x + (w - largo) / 2, "derecha": x + w - largo}.get(alin, x)
        dd.text((tx, y), texto, font=f, fill=color + (255,))
        return int(size * 1.3) + 2

    for wd in spec["widgets"]:
        dato, tipo = wd["dato"], wd["tipo"]
        info = DATOS[dato]
        x, y, w, h = [int(v) for v in wd["rect"]]
        color = pal.get(wd.get("color", "acento"), pal["acento"])
        alin = {"izquierda": "izquierda", "left": "izquierda", "centro": "centro", "center": "centro",
                "derecha": "derecha", "right": "derecha"}.get(wd.get("alineacion", ""), "izquierda")
        panel((x, y, w, h), color)
        ix, iy, iw, ih = x + pad, y + pad, w - 2 * pad, h - 2 * pad
        etq_size = max(8, min(int(15 * escala), int(ih * 0.2)))
        ruta = info["ruta"]

        if dato == "reloj":
            fmt_fecha = rng.choice(["d MMM yyyy", "EEE d MMM", "dd/MM/yyyy", "d MMM"])
            apilado = iw / max(1, ih) < 2.2
            if apilado:
                hora_r = (ix, iy, iw, int(ih * 0.62))
                resto = (ix, iy + int(ih * 0.62), iw, ih - int(ih * 0.62))
            else:
                ancho_hora = int(iw * 0.6)
                hora_r = (ix, iy, ancho_hora, ih)
                resto = (ix + ancho_hora + pad, iy, iw - ancho_hora - pad, ih)
            nodo = txt_nodo(hora_r, fv, "12:59 p. m.", pal["texto"], alin if apilado else "izquierda")
            nodo.update({"FORMAT": "HH:mm", "FORMAT_12": "h:mm a", "FORMAT_24": "HH:mm"})
            if not apilado:
                nodo["Y"] = iy + max(0, (ih - nodo["HEIGHT"]) // 2)
            _ruta_set(stats, ("DATE", "HOUR", "TEXT"), nodo)
            vista.append(("texto", nodo, "10:42 p. m."))
            al_r = alin if apilado else "derecha"
            mitad = resto[3] // 2
            n1 = txt_nodo((resto[0], resto[1], resto[2], mitad), fe, dia_ej, color, al_r, 40)
            n1["FORMAT"] = "EEEE"
            n2 = txt_nodo((resto[0], resto[1] + mitad, resto[2], resto[3] - mitad), fe,
                          "30/09/2026" if fmt_fecha == "dd/MM/yyyy" else fecha_ej, pal["tenue"], al_r, 40)
            n2["FORMAT"] = fmt_fecha
            _ruta_set(stats, ("DATE", "WEEKDAY", "TEXT"), n1)
            _ruta_set(stats, ("DATE", "DAY", "TEXT"), n2)
            vista += [("texto", n1, "jueves"), ("texto", n2, "1 oct 2026")]
            continue

        if dato == "tiempo":
            lh = etiqueta(wd.get("etiqueta", ""), ix, iy, iw, etq_size, pal["tenue"], alin)
            alto1 = int((ih - lh) * 0.6)
            n1 = txt_nodo((ix, iy + lh, iw, alto1), fv, "-99°C", pal["texto"], alin)
            n1["SHOW_UNIT"] = False
            n2 = txt_nodo((ix, iy + lh + alto1, iw, ih - lh - alto1), fe, "Parcialmente nublado", color, alin, 30)
            _ruta_set(stats, ("WEATHER", "TEMPERATURE", "TEXT"), n1)
            _ruta_set(stats, ("WEATHER", "WEATHER_DESCRIPTION", "TEXT"), n2)
            vista += [("texto", n1, "24°C"), ("texto", n2, "cielo claro")]
            continue

        ruta_txt = ruta + ((info["txt"],) if info["txt"] else ())
        demo_v = info.get("demo")
        demo_txt = DEMO_TEXTO.get(dato, f"{demo_v}%" if demo_v is not None else info["ej"])
        maxv = info.get("max", 100)

        if tipo == "radial":
            lh = etiqueta(wd.get("etiqueta", ""), ix, iy, iw, etq_size, pal["tenue"], "centro")
            aw, ah = iw, ih - lh
            xc, yc = ix + iw // 2, iy + lh + ah // 2
            r = max(10, min(aw, ah) // 2 - 1)
            r = min(r, xc, yc, W - xc, H - yc)
            bw = max(3, min(r - 4, int(r * rng.uniform(0.12, 0.3))))
            a0, a1, cw = rng.choice([(135, 45, True), (270, 270, True), (180, 0, True), (90, 90, False),
                                     (150, 30, True)])
            pasos, sep = rng.choice([(1, 0), (1, 0), (20, 4), (12, 6), (30, 3)])
            fuente = fv if fuentes.soporta(fv, info["ej"]) else "roboto/Roboto-Bold.ttf"
            size = fuentes.ajustar(fuente, info["ej"], int(2 * (r - bw) * 0.82), int((r - bw) * 0.9), 120)
            nodo = {"SHOW": True, "X": xc, "Y": yc, "RADIUS": r, "WIDTH": bw, "MIN_VALUE": 0, "MAX_VALUE": maxv,
                    "ANGLE_START": a0, "ANGLE_END": a1, "ANGLE_STEPS": pasos, "ANGLE_SEP": sep,
                    "CLOCKWISE": cw, "BAR_COLOR": _col(color), "SHOW_TEXT": True, "SHOW_UNIT": True,
                    "FONT": fuente, "FONT_SIZE": size, "FONT_COLOR": _col(pal["texto"]),
                    "BACKGROUND_IMAGE": "background.png"}
            _ruta_set(stats, ruta + ("RADIAL",), nodo)
            pista = _mezcla(pal["fondo1"], pal["tenue"], 0.35)
            ini, fin = (a0, a1) if cw else (a1, a0)
            if fin <= ini:
                fin += 360
            dd.arc((xc - r, yc - r, xc + r, yc + r), ini, fin, fill=pista + (200,), width=bw)
            vista.append(("radial", nodo, demo_v if demo_v is not None else 50, demo_txt))
            continue

        if tipo == "texto":
            lh = etiqueta(wd.get("etiqueta", ""), ix, iy, iw, etq_size, pal["tenue"], alin)
            nodo = txt_nodo((ix, iy + lh, iw, ih - lh), fv, info["ej"], color, alin)
            nodo["Y"] = iy + lh + max(0, (ih - lh - nodo["HEIGHT"]) // 2)
            _ruta_set(stats, ruta_txt, nodo)
            vista.append(("texto", nodo, demo_txt))
            continue

        if tipo == "barra":
            lh = etiqueta(wd.get("etiqueta", ""), ix, iy, iw, etq_size, pal["tenue"], "izquierda")
            bh = max(4, min(int(18 * escala), int((ih - lh) * rng.uniform(0.18, 0.32))))
            vr = (ix, iy + lh, iw, ih - lh - bh - 3)
            if vr[3] < 12:  # sin sitio debajo: valor a la derecha de la etiqueta
                vr = (ix + iw // 2, iy, iw - iw // 2, max(12, lh))
            nodo = txt_nodo(vr, fv, info["ej"], pal["texto"], "centro" if alin == "centro" else "derecha")
            _ruta_set(stats, ruta_txt, nodo)
            vista.append(("texto", nodo, demo_txt))
            by = iy + ih - bh
            barra = {"SHOW": True, "X": ix, "Y": by, "WIDTH": iw, "HEIGHT": bh, "MIN_VALUE": 0, "MAX_VALUE": maxv,
                     "BAR_COLOR": _col(color), "BAR_OUTLINE": rng.random() < 0.3,
                     "BACKGROUND_IMAGE": "background.png"}
            _ruta_set(stats, ruta + ("GRAPH",), barra)
            dd.rectangle((ix, by, ix + iw - 1, by + bh - 1), fill=_mezcla(pal["fondo1"], pal["tenue"], 0.25) + (200,))
            vista.append(("barra", barra, demo_v if demo_v is not None else 40))
            continue

        # tipo == "linea": etiqueta + valor en una fila y la grafica debajo
        fila = max(int(16 * escala), min(int(ih * 0.34), int(30 * escala)))
        etiqueta(wd.get("etiqueta", ""), ix, iy + max(0, int((fila - etq_size * 1.3) // 2)), iw // 2, etq_size,
                 pal["tenue"], "izquierda")
        nodo = txt_nodo((ix + iw // 2, iy, iw - iw // 2, fila), fv, info["ej"], pal["texto"], "derecha")
        _ruta_set(stats, ruta_txt, nodo)
        vista.append(("texto", nodo, demo_txt))
        gy = iy + fila + 2
        auto = bool(info.get("auto"))
        linea = {"SHOW": True, "X": ix, "Y": gy, "WIDTH": iw, "HEIGHT": max(8, ih - fila - 2), "MIN_VALUE": 0,
                 "MAX_VALUE": 1 if dato.startswith("red") else maxv, "HISTORY_SIZE": rng.choice([20, 30, 45, 60]),
                 "AUTOSCALE": auto, "LINE_COLOR": _col(color), "LINE_WIDTH": rng.choice([1, 2, 2, 3]),
                 "AXIS": rng.random() < 0.35, "AXIS_COLOR": _col(pal["tenue"]),
                 "BACKGROUND_IMAGE": "background.png"}
        _ruta_set(stats, ruta + ("LINE_GRAPH",), linea)
        vista.append(("linea", linea))

    # INTERVAL: sin el, el planificador (library/scheduler.py) no refresca ese grupo
    for grupo in list(stats):
        sub = stats[grupo]
        if grupo == "CPU":
            for k in sub:
                sub[k] = {"INTERVAL": INTERVALO_CPU.get(k, 2), **sub[k]}
        else:
            stats[grupo] = {"INTERVAL": INTERVALO_GRUPO.get(grupo, 2), **sub}

    fondo = Image.alpha_composite(fondo.convert("RGBA"), deco).convert("RGB")
    tema = {
        "author": "Generador IA Centro Turing",
        "display": {"DISPLAY_SIZE": pant["tamano"], "DISPLAY_ORIENTATION": pant["orientacion"],
                    "DISPLAY_RGB_LED": _col(pal["acento"])},
        "static_images": {"BACKGROUND": {"PATH": "background.png", "X": 0, "Y": 0, "WIDTH": W, "HEIGHT": H}},
        "STATS": stats,
    }
    return tema, fondo, _vista_previa(fondo, vista, fuentes, rng)


def _vista_previa(fondo: Image.Image, vista: list, fuentes: Fuentes, rng: random.Random) -> Image.Image:
    img = fondo.copy()
    d = ImageDraw.Draw(img)
    for el in vista:
        tipo, n = el[0], el[1]
        if tipo == "texto":
            f = fuentes.get(n["FONT"], n["FONT_SIZE"])
            x, y, w = n["X"], n["Y"], n["WIDTH"]
            pos = {"rt": (x + w, y), "mt": (x + w // 2, y)}.get(n["ANCHOR"], (x, y))
            d.text(pos, el[2], font=f, fill=_rgb(n["FONT_COLOR"]), anchor=n["ANCHOR"])
        elif tipo == "barra":
            v = max(0.0, min(1.0, el[2] / max(1, n["MAX_VALUE"])))
            d.rectangle((n["X"], n["Y"], n["X"] + int(n["WIDTH"] * v), n["Y"] + n["HEIGHT"] - 1),
                        fill=_rgb(n["BAR_COLOR"]))
        elif tipo == "linea":
            fase = rng.uniform(0, 6)
            pts = [(n["X"] + n["WIDTH"] * i / 30,
                    n["Y"] + n["HEIGHT"] * (1 - (0.5 + 0.35 * math.sin(fase + i / 4) * math.cos(i / 9))))
                   for i in range(31)]
            d.line(pts, fill=_rgb(n["LINE_COLOR"]), width=n["LINE_WIDTH"])
        elif tipo == "radial":
            xc, yc, r, bw = n["X"], n["Y"], n["RADIUS"], n["WIDTH"]
            v = max(0.0, min(1.0, el[2] / max(1, n["MAX_VALUE"])))
            a0, a1 = n["ANGLE_START"], n["ANGLE_END"]
            total = ((a1 - a0) % 360 or 360) if n["CLOCKWISE"] else ((a0 - a1) % 360 or 360)
            caja = (xc - r, yc - r, xc + r, yc + r)
            if n["CLOCKWISE"]:
                d.arc(caja, a0, a0 + total * v, fill=_rgb(n["BAR_COLOR"]), width=bw)
            else:
                d.arc(caja, a0 - total * v, a0, fill=_rgb(n["BAR_COLOR"]), width=bw)
            d.text((xc, yc), el[3], font=fuentes.get(n["FONT"], n["FONT_SIZE"]), fill=_rgb(n["FONT_COLOR"]),
                   anchor="mm")
    return img


# --------------------------------------------------------------------------
# YAML (emisor propio: no depende de PyYAML y deja DISPLAY_SIZE: 3.5" sin comillas)
# --------------------------------------------------------------------------
def _escalar(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if re.fullmatch(r"\d{1,3}, \d{1,3}, \d{1,3}", s) or re.fullmatch(r"\d+(\.\d+)?\"", s):
        return s
    if (not s or s[0] in "!&*-?{}[],#|>@`'\"%" or ": " in s or " #" in s or s != s.strip()
            or s.lower() in ("true", "false", "yes", "no", "on", "off", "null", "~")
            or re.fullmatch(r"[-+]?\d+(\.\d*)?", s)):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def a_yaml(d: dict, sangria: int = 0) -> str:
    lineas = []
    for k, v in d.items():
        if isinstance(v, dict):
            lineas.append(" " * sangria + f"{k}:")
            lineas.append(a_yaml(v, sangria + 2))
        else:
            lineas.append(" " * sangria + f"{k}: {_escalar(v)}")
    return "\n".join(l for l in lineas if l != "")


def comprobar_tema(tema: dict, pant: dict) -> list[str]:
    """Comprobacion de limites equivalente a los assert de library/lcd (DisplayText / Radial)."""
    W, H = pant["ancho"], pant["alto"]
    errores: list[str] = []

    def rec(n, ruta):
        if not isinstance(n, dict):
            return
        if n.get("SHOW") is True:
            x, y = n.get("X", 0), n.get("Y", 0)
            if "RADIUS" in n:
                r = n["RADIUS"]
                if x - r < 0 or x + r > W or y - r < 0 or y + r > H or not (0 < n["WIDTH"] <= r):
                    errores.append(f"{ruta}: radial fuera de pantalla")
                if n.get("ANGLE_SEP", 0) * n.get("ANGLE_STEPS", 1) >= 360:
                    errores.append(f"{ruta}: ANGLE_SEP*ANGLE_STEPS >= 360")
            else:
                w, h = n.get("WIDTH", 0), n.get("HEIGHT", 0)
                if x < 0 or y < 0 or x + w > W or y + h > H or w <= 0 or h <= 0:
                    errores.append(f"{ruta}: ({x},{y},{w},{h}) fuera de {W}x{H}")
            if "FONT_SIZE" in n and n["FONT_SIZE"] <= 0:
                errores.append(f"{ruta}: FONT_SIZE invalido")
        for k, v in n.items():
            rec(v, f"{ruta}/{k}")

    rec(tema.get("STATS", {}), "STATS")
    return errores


# --------------------------------------------------------------------------
# IA (API compatible con OpenAI: Jan, LM Studio, Ollama, llama.cpp, DeepSeek...)
# --------------------------------------------------------------------------
def _cfg_ia(root: Path) -> dict:
    cfg: dict = {}
    ruta = root / "tools" / "generador_ia.json"
    if ruta.is_file():
        try:
            cfg = json.loads(ruta.read_text(encoding="utf-8-sig"))
        except Exception:  # noqa: BLE001
            cfg = {}
    for clave, env in (("url", "CENTRO_TURING_IA_URL"), ("modelo", "CENTRO_TURING_IA_MODELO"),
                       ("clave", "CENTRO_TURING_IA_CLAVE"), ("autoarranque", "CENTRO_TURING_IA_AUTOARRANQUE"),
                       ("activa", "CENTRO_TURING_IA"), ("timeout", "CENTRO_TURING_IA_ESPERA")):
        if os.environ.get(env):
            cfg[clave] = os.environ[env]
    return cfg


def _no(valor) -> bool:
    return str(valor).strip().lower() in ("0", "no", "false", "off")


def _base(url: str) -> str:
    url = url.strip().rstrip("/")
    for sufijo in ("/chat/completions", "/v1"):
        if url.endswith(sufijo):
            url = url[: -len(sufijo)]
    return url.rstrip("/")


def _http_json(url: str, datos: dict | None = None, clave: str = "", timeout: float = 5.0) -> dict:
    cabeceras = {"Content-Type": "application/json", "Accept": "application/json"}
    if clave:
        cabeceras["Authorization"] = "Bearer " + clave
    cuerpo = json.dumps(datos).encode("utf-8") if datos is not None else None
    req = urllib.request.Request(url, data=cuerpo, headers=cabeceras, method="POST" if cuerpo else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (URL local o configurada)
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _modelos(base: str, clave: str) -> list[str]:
    try:
        datos = _http_json(base + "/v1/models", clave=clave, timeout=1.5)
    except Exception:  # noqa: BLE001
        return []
    ids = [str(m.get("id")) for m in datos.get("data", []) if isinstance(m, dict) and m.get("id")]
    return [i for i in ids if not re.search(r"embed|sentence|whisper|tts|rerank", i, re.I)] or ids


def _mejor_modelo(modelos: list[str]) -> str:
    """Modelo LOCAL para disenar JSON: instruct/coder de 7-14B (cabe en 12 GB de VRAM).

    Se descartan los que Jan reenvia a servicios de fuera (ids con "/", ":free",
    deepseek-chat/reasoner, gpt, claude-3...) para no gastar una API de pago sin querer.
    """
    def remoto(m: str) -> bool:
        s = m.lower()
        return "/" in s or ":free" in s or s in ("deepseek-chat", "deepseek-reasoner") or s.startswith(("gpt-", "o1", "o3"))

    def nota(m: str) -> float:
        s = m.lower()
        n = 0.0
        if re.search(r"coder|instruct", s):
            n += 3
        if re.search(r"r1|think|reason|abliterated|uncensored|uncnr|heretic|dolphin", s):
            n -= 2
        tam = re.search(r"(\d+(?:\.\d+)?)b", s)
        if tam:
            b = float(tam.group(1))
            n += min(b, 14) / 7 - (1.5 if b > 16 else 0)
        return n
    locales = [m for m in modelos if not remoto(m)]
    return max(locales, key=nota) if locales else (modelos[0] if modelos else "default")


def _es_local(url: str) -> bool:
    return bool(re.match(r"https?://(127\.0\.0\.1|localhost|\[::1\])(:\d+)?(/|$)", url or ""))


def _llama_server_jan() -> tuple[Path, Path] | None:
    """llama-server.exe y el modelo .gguf mas grande que trae Jan (si esta instalado)."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    raiz = Path(appdata) / "Jan" / "data" / "llamacpp"
    if not raiz.is_dir():
        return None
    try:
        servidores = sorted(raiz.glob("backends/*/*/build/bin/llama-server.exe"),
                            key=lambda p: ("cuda" not in str(p).lower(), -p.stat().st_mtime))
        modelos = sorted((p for p in raiz.glob("models/*/model.gguf")
                          if not re.search(r"embed|sentence", p.parent.name, re.I)),
                         key=lambda p: -p.stat().st_size)
    except OSError:
        return None
    return (servidores[0], modelos[0]) if servidores and modelos else None


class ClienteIA:
    PUERTO_PROPIO = 39281

    def __init__(self, root: Path, log=print):
        self.root, self.log = root, log
        self.cfg = _cfg_ia(root)
        self._proceso: subprocess.Popen | None = None

    def activa(self) -> bool:
        return not _no(self.cfg.get("activa", "1"))

    def candidatos(self):
        """(base, modelo, clave, descripcion) por orden de preferencia."""
        vistos = set()
        if self.cfg.get("url"):
            base = _base(self.cfg["url"])
            vistos.add(base)
            clave = self.cfg.get("clave", "")
            modelo = self.cfg.get("modelo") or _mejor_modelo(_modelos(base, clave))
            yield base, modelo, clave, "IA configurada"
        token_local = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
        locales = []
        if os.environ.get("AYIS_API") and _es_local(os.environ["AYIS_API"]):
            locales.append((_base(os.environ["AYIS_API"]), ""))
        if _es_local(os.environ.get("ANTHROPIC_BASE_URL", "")):
            locales.append((_base(os.environ["ANTHROPIC_BASE_URL"]), token_local))
        locales += [("http://127.0.0.1:1337", token_local), ("http://127.0.0.1:1234", ""),
                    ("http://127.0.0.1:11434", ""), ("http://127.0.0.1:8080", ""),
                    (f"http://127.0.0.1:{self.PUERTO_PROPIO}", "")]
        for base, clave in locales:
            if base in vistos:
                continue
            vistos.add(base)
            modelos = _modelos(base, clave)
            if modelos:
                pref = [os.environ.get(v, "") for v in ("ANTHROPIC_DEFAULT_SONNET_MODEL", "AYIS_MODEL")]
                modelo = next((m for m in pref if m and m in modelos), None) or _mejor_modelo(modelos)
                yield base, modelo, clave, f"servidor local {base}"
        if os.environ.get("DEEPSEEK_API_KEY"):
            self.log("  IA: no hay IA local; se usa DeepSeek (API de pago, DEEPSEEK_API_KEY)")
            yield "https://api.deepseek.com", "deepseek-chat", os.environ["DEEPSEEK_API_KEY"], "DeepSeek"
        if not _no(self.cfg.get("autoarranque", "1")):
            arrancado = self._arrancar_jan()
            if arrancado:
                yield arrancado

    def _arrancar_jan(self):
        encontrado = _llama_server_jan()
        if not encontrado:
            return None
        exe, modelo = encontrado
        self.log(f"  IA: arrancando un momento el motor local de Jan ({modelo.parent.name})...")
        flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
        try:
            self._proceso = subprocess.Popen(
                [str(exe), "-m", str(modelo), "-ngl", "99", "-c", "8192", "--host", "127.0.0.1",
                 "--port", str(self.PUERTO_PROPIO)], cwd=str(exe.parent), stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
        except OSError as error:
            self.log(f"  IA: no se pudo arrancar llama-server ({error})")
            return None
        base = f"http://127.0.0.1:{self.PUERTO_PROPIO}"
        limite = time.time() + 150
        while time.time() < limite:
            if self._proceso.poll() is not None:
                self.log("  IA: el motor local se cerro al arrancar")
                return None
            try:
                if _http_json(base + "/health", timeout=2).get("status") == "ok":
                    return base, modelo.parent.name, "", "llama-server de Jan"
            except Exception:  # noqa: BLE001
                pass
            time.sleep(1.5)
        self.log("  IA: el motor local tardo demasiado en arrancar")
        self.cerrar()
        return None

    def cerrar(self) -> None:
        """Para el llama-server SOLO si lo arranco este generador (libera la VRAM)."""
        if self._proceso and self._proceso.poll() is None:
            self._proceso.terminate()
            try:
                self._proceso.wait(timeout=10)
            except Exception:  # noqa: BLE001
                self._proceso.kill()
        self._proceso = None

    def pedir(self, mensajes: list[dict], temperatura: float = 0.95, max_tokens: int = 3000,
              espera: float = 300) -> tuple[str, str] | None:
        """Devuelve (texto, descripcion del servidor) o None si ninguna IA responde."""
        if not self.activa():
            return None
        for base, modelo, clave, desc in self.candidatos():
            for formato in (True, False):
                datos = {"model": modelo, "messages": mensajes, "temperature": temperatura,
                         "max_tokens": max_tokens, "stream": False}
                if formato:
                    datos["response_format"] = {"type": "json_object"}
                try:
                    r = _http_json(base + "/v1/chat/completions", datos, clave, timeout=float(self.cfg.get("timeout") or espera))
                    msg = (r.get("choices") or [{}])[0].get("message") or {}
                    texto = msg.get("content") or ""
                    if _extraer_json(texto):
                        return texto, f"{desc} | {modelo}"
                    self.log(f"  IA: {desc} no devolvio JSON valido" + (" (reintento sin json_object)" if formato else ""))
                except urllib.error.HTTPError as error:
                    if formato and error.code in (400, 404, 422, 500, 501):
                        continue
                    self.log(f"  IA: {desc} respondio HTTP {error.code}")
                    break
                except Exception as error:  # noqa: BLE001
                    self.log(f"  IA: {desc} no responde ({type(error).__name__})")
                    break
        return None


def _extraer_json(texto: str) -> dict | None:
    texto = re.sub(r"<think>.*?</think>", "", texto or "", flags=re.S)
    texto = re.sub(r"```(?:json)?", "", texto)
    ini = texto.find("{")
    while ini != -1:
        nivel = 0
        for i in range(ini, len(texto)):
            if texto[i] == "{":
                nivel += 1
            elif texto[i] == "}":
                nivel -= 1
                if nivel == 0:
                    trozo = texto[ini:i + 1]
                    for intento in (trozo, re.sub(r",\s*([}\]])", r"\1", trozo)):
                        try:
                            d = json.loads(intento)
                            if isinstance(d, dict) and d.get("widgets"):
                                return d
                        except json.JSONDecodeError:
                            pass
                    break
        ini = texto.find("{", ini + 1)
    return None


def _prompt(pant: dict, rng: random.Random, descripcion: str = "") -> list[dict]:
    W, H = pant["ancho"], pant["alto"]
    datos = {k: list(v["tipos"]) for k, v in DATOS.items() if not v.get("tiempo") or pant.get("tiempo")}
    n_min, n_max = (4, 8) if W * H <= 480 * 480 else (6, 12)
    inspiracion = descripcion.strip() or ", ".join(rng.sample(INSPIRACION, 2))
    ejemplo = {
        "nombre": "NeonCabina", "estilo_fondo": "rejilla", "panel": "esquinas",
        "colores": {"fondo1": "#05070f", "fondo2": "#14213d", "acento": "#00e5ff", "acento2": "#ff2e88",
                    "texto": "#f1f5ff", "tenue": "#7f8fb0"},
        "fuente_valores": "jetbrains-mono/JetBrainsMono-Bold.ttf", "fuente_etiquetas": "roboto/Roboto-Medium.ttf",
        "widgets": [{"dato": "reloj", "tipo": "texto", "x": 8, "y": 8, "ancho": W - 16, "alto": int(H * 0.2),
                     "etiqueta": "", "color": "texto", "alineacion": "centro"},
                    {"dato": "cpu_uso", "tipo": "radial", "x": 8, "y": int(H * 0.2) + 16, "ancho": 120,
                     "alto": 130, "etiqueta": "CPU", "color": "acento", "alineacion": "centro"}],
    }
    sistema = ("Eres un disenador de interfaces para pantallas pequenas de monitorizacion de PC. "
               "Respondes SOLO con un objeto JSON valido, sin texto adicional.")
    usuario = f"""Disena un tema COMPLETAMENTE NUEVO para una pantalla de {pant['tamano']} en orientacion
{'horizontal' if pant['orientacion'] == 'landscape' else 'vertical'}: {W}x{H} pixeles (origen arriba-izquierda).
Inspiracion/estilo: {inspiracion}.  Semilla de variedad: {rng.randint(1000, 9999)}.
Sugerencia para esta vez (puedes cambiarla si no encaja): estilo_fondo "{rng.choice(ESTILOS_FONDO)}",
panel "{rng.choice(PANELES)}", distribucion "{rng.choice(DISTRIBUCIONES)}".

Reglas:
- Entre {n_min} y {n_max} widgets. Cada widget es un rectangulo (x, y, ancho, alto) en pixeles enteros.
- Todos dentro de la pantalla: x>=0, y>=0, x+ancho<={W}, y+alto<={H}. Los rectangulos NO se solapan.
  Deja 4-10 px de separacion. Ocupa casi toda la pantalla con una distribucion original
  (asimetrica, columnas, mosaico, gran indicador central, barra lateral... pero distinta cada vez).
- Tamanos minimos: texto 50x24, barra 80x36, linea 90x48, radial 70x70 (radial mejor casi cuadrado).
- "dato" debe ser una clave de esta lista y "tipo" uno de los permitidos para ese dato (no repitas datos):
  {json.dumps(datos, ensure_ascii=False)}
  ("reloj" = hora + dia + fecha juntos; conviene un rectangulo ancho.)
- estilo_fondo: uno de {ESTILOS_FONDO}
- panel (decoracion de cada widget): uno de {PANELES}
- fuente_valores: una de {FUENTES_VALOR}
- fuente_etiquetas: una de {FUENTES_ETIQUETA}
- colores en #rrggbb; fondo1/fondo2 = fondo, texto con buen contraste. "color" de cada widget:
  "acento", "acento2" o "texto". alineacion: "izquierda", "centro" o "derecha".
- etiqueta: texto corto en espanol en MAYUSCULAS (max 12 letras) o "" para ninguna.
- Deja sitio para los textos MAS LARGOS: hora "12:59 p. m.", tiempo "Parcialmente nublado" y "-99°C",
  "100°C", "131072 M", "99999 G", "1023.9 MB/s". Un texto no puede pisar a otro ni a una etiqueta.
- Estilo original: nada de personajes, marcas ni logotipos con copyright.
- nombre: una palabra creativa sin espacios (max 16 letras).

Ejemplo SOLO del formato (no copies esta distribucion):
{json.dumps(ejemplo, ensure_ascii=False)}"""
    return [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]


# --------------------------------------------------------------------------
# API principal
# --------------------------------------------------------------------------
def _slug_tamano(pant: dict) -> str:
    return pant["tamano"].replace('"', "").replace(".", "") + ("H" if pant["orientacion"] == "landscape" else "V")


def _nombre_libre(themes: Path, prefijo: str) -> str:
    usados = {c.name.lower() for c in themes.iterdir()} if themes.is_dir() else set()
    for i in range(1, 1000):
        candidato = f"{prefijo}{i:02d}"
        if candidato.lower() not in usados:
            return candidato
    return f"{prefijo}{random.randrange(1000, 9999)}"


def crear_tema(root: Path, themes: Path, nombre: str | None = None, tamano: str | None = None,
               orientacion: str | None = None, usar_ia: bool = True, descripcion: str = "",
               tono: float | None = None, log=print, semilla: int | None = None) -> Path:
    """Crea res/themes/<nombre> con theme.yaml, background.png y preview.png. Devuelve la carpeta."""
    rng = random.Random(semilla if semilla is not None else (time.time_ns() ^ os.getpid()))
    pant = detectar_pantalla(root, tamano, orientacion)
    fuentes = Fuentes(root)
    log(f"  Pantalla: {pant['tamano']} {('horizontal' if pant['orientacion'] == 'landscape' else 'vertical')} "
        f"({pant['ancho']}x{pant['alto']}) | revision {pant['revision']}")

    spec, origen = None, "procedural"
    if usar_ia and pant["tamano"] == '3.5"' and pant["orientacion"] == "landscape":
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import taller_ia
        except Exception as error:  # noqa: BLE001
            taller_ia = None
            log(f"  Taller IA no disponible ({error})")
        if taller_ia is not None and taller_ia.activo():
            log("  Taller IA: arquetipo nuevo + fondo dibujado + revision de la vista previa con reintentos")
            cliente = ClienteIA(root, log)
            try:
                hecho = taller_ia.crear_tema_taller(root, themes, cliente, _extraer_json, descripcion, log, rng, nombre)
            finally:
                cliente.cerrar()
            if hecho:
                return hecho
    if usar_ia:
        cliente = ClienteIA(root, log)
        try:
            respuesta = cliente.pedir(_prompt(pant, rng, descripcion))
        finally:
            cliente.cerrar()
        if respuesta:
            bruto = _extraer_json(respuesta[0]) or {}
            spec = validar_diseno(bruto, pant, fuentes, rng)
            n = len(spec["widgets"])
            if n >= 3:
                origen = f"IA ({respuesta[1]})"
            else:
                log(f"  IA: su diseno solo tenia {n} widget(s) validos; se usa su estilo con otra distribucion")
                widgets_ia = [w for w in bruto.get("widgets") or [] if isinstance(w, dict)]
                pref = {"datos": [str(w.get("dato")) for w in widgets_ia],
                        "tipos": {str(w.get("dato")): str(w.get("tipo")) for w in widgets_ia},
                        **{k: spec[k] for k in ("estilo_fondo", "panel", "colores", "fuente_valores",
                                                "fuente_etiquetas", "nombre")}}
                spec = diseno_procedural(pant, fuentes, rng, pref)
                origen = f"IA (estilo) + distribucion procedural ({respuesta[1]})"
        else:
            log("  IA: no hay ninguna IA disponible; se usa el generador procedural (tambien cambia el diseno)")
    if spec is None:
        spec = diseno_procedural(pant, fuentes, rng, tono=tono)

    tema, fondo, preview = construir(spec, pant, fuentes, rng)
    errores = comprobar_tema(tema, pant)
    if errores:  # no deberia pasar; por si acaso, otro diseno procedural
        log("  aviso: diseno con errores de limites, se rehace: " + "; ".join(errores[:3]))
        spec = diseno_procedural(pant, fuentes, rng, tono=tono)
        origen += " -> procedural"
        tema, fondo, preview = construir(spec, pant, fuentes, rng)

    prefijo = ("GenIA_" if origen.startswith("IA") else "GenRnd_") + _slug_tamano(pant) + "_"
    if spec.get("nombre"):
        prefijo += spec["nombre"][:14] + "_"
    nombre = nombre or _nombre_libre(themes, prefijo)
    destino = themes / nombre
    if destino.exists():
        raise SystemExit(f'El tema "{nombre}" ya existe. Usa otro nombre (--nombre).')
    destino.mkdir(parents=True)
    fondo.save(destino / "background.png")
    preview.save(destino / "preview.png")
    lista = ", ".join(w["dato"] + ":" + w["tipo"] for w in spec["widgets"])
    cabecera = (
        "# ---------------------------------------------------------------------------\n"
        "# Tema GENERADO por Centro Turing (tools/generador_layout_ia.py)\n"
        f"# Pantalla : {pant['tamano']} {pant['orientacion']} ({pant['ancho']}x{pant['alto']})\n"
        f"# Diseno   : {origen}\n"
        f"# Fondo    : {spec['estilo_fondo']} | paneles {spec['panel']}\n"
        f"# Fuentes  : {spec['fuente_valores']} / {spec['fuente_etiquetas']}\n"
        f"# Widgets  : {lista}\n"
        "# Es YAML normal: puedes editarlo a mano para ajustar posiciones o colores.\n"
        "# ---------------------------------------------------------------------------\n"
    )
    (destino / "theme.yaml").write_text(cabecera + a_yaml(tema) + "\n", encoding="utf-8")
    log(f"  Diseno: {origen} | {len(spec['widgets'])} widgets | fondo {spec['estilo_fondo']} | paneles {spec['panel']}")
    return destino
