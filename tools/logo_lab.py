#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Laboratorio de logos de Centro Turing.

Genera las variantes de marca candidatas (256 px y escalera 128/48/32/16) y una
hoja comparativa, para elegir o cambiar de estilo sin tocar el codigo a ciegas.

    python tools/logo_lab.py

Salida en tmp/logo-lab/: <variante>.png y comparativa.png

La variante adoptada (la que dibuja `turing_design.brand_mark`) es la **C,
Monograma neon**: losa oscura, filo cian y "T" en degradado. Para cambiar de
estilo, copia el cuerpo de otra variante sobre `brand_mark()` y regenera iconos
y cartel:

    python tools/logo_lab.py --aplicar C     # deja el .ico y el .png al dia
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

import turing_design as D  # noqa: E402

OUT = ROOT / "tmp" / "logo-lab"
S = 4  # supersampling


def _tile(n: int, c1: str, c2: str, radius_ratio: float = 0.24) -> Image.Image:
    """Losa cuadrada con degradado diagonal y esquinas redondeadas."""
    tile = D.gradient_image((n, n), c1, c2, diagonal=True).convert("RGBA")
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    img.paste(tile, (0, 0), D.rounded_mask((n, n), int(n * radius_ratio)))
    return img


def _gloss(img: Image.Image, alpha: int = 30, blur: float = 0.02) -> None:
    """Brillo de cristal en la mitad superior (se compone sobre img)."""
    n = img.width
    gloss = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(gloss).rounded_rectangle([(0, 0), (n, int(n * 0.55))],
                                            radius=int(n * 0.24), fill=(255, 255, 255, alpha))
    img.alpha_composite(gloss.filter(ImageFilter.GaussianBlur(n * blur)))


# ---------------------------------------------------------------- A: pantalla
def variante_pantalla(size: int = 256) -> Image.Image:
    """Losa con degradado + pantalla blanca con pulso (monitor de datos)."""
    n = size * S
    img = _tile(n, D.lighten(D.C["accent"], 0.06), D.darken(D.C["accent_2"], 0.10))
    _gloss(img, 32)
    d = ImageDraw.Draw(img, "RGBA")

    if size >= 40:
        sw, sh = int(n * 0.56), int(n * 0.42)
        sx, sy = (n - sw) // 2, int(n * 0.245)
        d.rounded_rectangle([(sx, sy), (sx + sw, sy + sh)], radius=int(n * 0.075),
                            fill=(255, 255, 255, 242))
        base_y = sy + int(sh * 0.58)
        pts = [(sx + int(sw * 0.10), base_y),
               (sx + int(sw * 0.30), base_y),
               (sx + int(sw * 0.40), base_y - int(sh * 0.30)),
               (sx + int(sw * 0.52), base_y + int(sh * 0.24)),
               (sx + int(sw * 0.63), base_y),
               (sx + int(sw * 0.90), base_y)]
        d.line(pts, fill=D.rgba(D.C["accent_2"]), width=max(2, int(n * 0.030)), joint="curve")
        r = int(n * 0.032)
        d.ellipse([(pts[-1][0] - r, pts[-1][1] - r), (pts[-1][0] + r, pts[-1][1] + r)],
                  fill=D.rgba(D.C["accent"]))
    else:
        base_y = int(n * 0.56)
        pts = [(int(n * 0.16), base_y), (int(n * 0.34), base_y), (int(n * 0.45), int(n * 0.34)),
               (int(n * 0.58), int(n * 0.74)), (int(n * 0.68), base_y), (int(n * 0.86), base_y)]
        d.line(pts, fill=(255, 255, 255, 245), width=max(2, int(n * 0.085)), joint="curve")
    return img.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------- B: cristal
def _rombo(n: int, ratio: float, color: str, alpha: int, radius_ratio: float = 0.26) -> Image.Image:
    """Rombo suave (cuadrado redondeado girado 45 grados) centrado en n x n."""
    s = max(6, int(n * ratio))
    tile = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(tile).rounded_rectangle([(0, 0), (s - 1, s - 1)],
                                           radius=int(s * radius_ratio),
                                           fill=D.rgba(color, alpha))
    tile = tile.rotate(45, expand=True, resample=Image.BICUBIC)
    layer = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    layer.alpha_composite(tile, ((n - tile.width) // 2, (n - tile.height) // 2))
    return layer


def variante_cristal(size: int = 256) -> Image.Image:
    """Rombo de cristal por capas (evolucion del rombo original) con resplandor."""
    n = size * S
    img = _tile(n, "#16203a", "#080c16")
    _gloss(img, 26)
    glow = _rombo(n, 0.62, D.C["accent"], 190, 0.30).filter(ImageFilter.GaussianBlur(n * 0.045))
    img.alpha_composite(glow)
    img.alpha_composite(_rombo(n, 0.56, D.C["accent"], 235))
    img.alpha_composite(_rombo(n, 0.40, D.C["accent_2"], 245))
    img.alpha_composite(_rombo(n, 0.22, D.C["accent"], 255))
    d = ImageDraw.Draw(img, "RGBA")
    r2 = int(n * 0.028)
    cx, cy = n // 2, int(n * 0.30)
    d.ellipse([(cx - r2, cy - r2), (cx + r2, cy + r2)], fill=(255, 255, 255, 230))
    return img.resize((size, size), Image.LANCZOS)


# ------------------------------------------------------------- C: monograma
def variante_monograma(size: int = 256) -> Image.Image:
    """Losa oscura con 'T' geometrica en degradado y filo de neon (adoptada)."""
    n = size * S
    img = _tile(n, "#151f33", "#0a0f1a")
    _gloss(img, 20)
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle([(int(n * 0.035), int(n * 0.035)), (int(n * 0.965), int(n * 0.965))],
                        radius=int(n * 0.22), outline=D.rgba(D.C["accent"], 210),
                        width=max(2, int(n * 0.017)))
    bw, bh = int(n * 0.50), int(n * 0.115)
    bar = D.gradient_image((bw, bh), D.C["accent"], D.C["accent_2"]).convert("RGBA")
    img.alpha_composite(bar, (int(n * 0.25), int(n * 0.275)))
    sw, sh = int(n * 0.125), int(n * 0.30)
    stem = D.gradient_image((sw, sh), D.C["accent"], D.darken(D.C["accent_2"], 0.10)).convert("RGBA")
    img.alpha_composite(stem, (int(n * 0.4375), int(n * 0.365)))
    r = int(n * 0.040)
    px, py = int(n * 0.735), int(n * 0.655)
    d.ellipse([(px - r, py - r), (px + r, py + r)], fill=(255, 255, 255, 235))
    return img.resize((size, size), Image.LANCZOS)


VARIANTES = {
    "A - Pantalla con pulso": variante_pantalla,
    "B - Cristal (evolucion)": variante_cristal,
    "C - Monograma neon": variante_monograma,
}


def hoja() -> Path:
    """Comparativa: cada variante a 256, 128, 48, 32 y 16 px."""
    pad, col, row = 28, 300, 320
    sheet = Image.new("RGBA", (pad * 2 + col * len(VARIANTES), pad * 2 + row), D.rgba(D.C["bg"]))
    d = ImageDraw.Draw(sheet)
    for i, (nombre, fn) in enumerate(VARIANTES.items()):
        x = pad + col * i + col // 2
        sheet.alpha_composite(fn(256), (x - 128, pad + 24))
        D.draw_text(sheet, (pad + col * i + 20, pad), nombre, size=24, weight="bold",
                    color=D.C["text"])
        lx, ly = pad + col * i + 20, pad + 24 + 256 + 26
        for s in (128, 48, 32, 16):
            sheet.alpha_composite(fn(s), (lx, ly))
            D.draw_text(sheet, (lx, ly + s + 6), f"{s}px", size=14, color=D.C["faint"])
            lx += s + 18
        d.line([(pad + col * i, pad + 10), (pad + col * i, pad + row - 10)],
               fill=D.rgba(D.C["border"], 160))
    out = OUT / "comparativa.png"
    sheet.convert("RGB").save(out, "PNG")
    return out


def regenerar_iconos() -> list[Path]:
    """Deja al dia el .ico/.png de la app y el cartel del repositorio."""
    escritos = D.save_app_icon(ROOT / "res" / "icons" / "centro-turing.ico",
                               ROOT / "res" / "icons" / "centro-turing.png")
    escritos.append(D.social_banner(ROOT / "res" / "docs" / "centro-turing-banner.png"))
    # Iconos de bandeja (nuestra marca, no el icono de terceros)
    tray = ROOT / "res" / "icons" / "tray"
    tray.mkdir(parents=True, exist_ok=True)
    for s in (16, 24, 32, 48, 64, 128):
        p = tray / f"{s}.png"
        D.brand_mark(s).save(p, "PNG")
        escritos.append(p)
    return escritos


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    if "--aplicar" in sys.argv:
        for p in regenerar_iconos():
            print("escrito", p)
        sys.exit(0)
    for nombre, fn in VARIANTES.items():
        fn(256).save(OUT / (nombre.split(" ")[0] + ".png"), "PNG")
        print("ok", nombre)
    print("hoja:", hoja())
