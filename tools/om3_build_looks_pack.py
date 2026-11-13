#!/usr/bin/env python3
"""Build OM3MOD LOOKS.BIN + NAMES.BIN from Caduceus film library.

Default pack mirrors the blog COLOR-1 set:
  Classic Neg, Kodachrome 64, Portra 400, Gold 200, Kodak 2383
and Caduceus Control Panel defaults on COLOR 2–4.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
CAD = ROOT / "third_party/caduceus-om3"
FILMS_JSON = CAD / "webapp/src/data/om3films.json"
LIBRARY_JSON = CAD / "webapp/src/data/library.json"
FONT_DIR = ROOT / "toolchains/fonts"
MKPROFILES = CAD / "card/mkprofiles.py"

# Current ship pack:
# COLOR1: two films + three Empty slots for in-camera HSL/Extras DIY
# COLOR4 slot5: Vision3 500T (Kodak 5219) migrated from old library.json
COLOR1 = ["Classic Neg", "Kodachrome 64", None, None, None]
DEFAULT_ROWS = [
    COLOR1,
    ["Velvia 50", "Kodachrome 64", "Ektachrome E100", "Provia 100F", "Astia 100F"],
    ["Portra 400", "Portra 160", "Ektar 100", "Gold 200", "Fuji 400H"],
    ["CineStill 800T", "Kodak 2383", "Vision3 250D", "FP-100C", "lib:Vision3 500T"],
]

NM_W, NM_H, NM_GROUP_MAX = 175, 50, 16384
FONTS = [
    str(FONT_DIR / "DejaVuSansCondensed.ttf"),
    str(FONT_DIR / "dejavu-fonts-ttf-2.37/ttf/DejaVuSansCondensed.ttf"),
]


def load_films() -> dict[str, dict]:
    data = json.loads(FILMS_JSON.read_text(encoding="utf-8"))
    by = {f["name"]: f for f in data["films"]}
    for alias, canon in (data.get("aliases") or {}).items():
        if canon in by:
            by[alias] = by[canon]
    return by


def load_library_looks() -> dict[str, dict]:
    raw = json.loads(LIBRARY_JSON.read_text(encoding="utf-8"))
    looks = raw["looks"] if isinstance(raw, dict) and "looks" in raw else raw
    return {look["name"]: look for look in looks if look.get("kind") == "colour"}


def film_to_profile(film: dict, display_name: str | None = None) -> dict:
    wb = film.get("wb")
    tone = film.get("tone") or {}
    return {
        "name": (display_name or film["name"])[:15],
        "hue": list(film["hue"]),
        "light": list(film["light"]),
        "sat": list(film["sat"]),
        "wb": bool(wb),
        "ab": (wb or {}).get("a_b", 0),
        "gm": (wb or {}).get("g_m", 0),
        "blacks": tone.get("blacks", 0),
        "whites": tone.get("whites", 0),
        "contrast": film.get("contrast", 0),
        "sharp": 0,  # v0.22 keeps +42 at 0
        "sharp22": film.get("sharp", 0),
        "shading": 0,
        "sh": tone.get("shadows", 0),
        "mid": tone.get("midtones", 0),
        "hi": tone.get("highlights", 0),
        "fx": 0,
        "art": 0,
        "nr": 0,
        "vig": 0,
        "grain": 0,
    }


def library_to_profile(look: dict, display_name: str | None = None) -> dict:
    """Migrate an old Look Lab library colour entry into a LOOKS record (no Glow/Art/Grain)."""
    wb = look.get("wb")
    tone = look.get("tone") or {}
    advice = look.get("advice") or {}
    return {
        "name": (display_name or look["name"])[:15],
        "hue": list(look["hue"]),
        "light": list(look["light"]),
        "sat": list(look["sat"]),
        "wb": bool(wb and ((wb or {}).get("a_b") or (wb or {}).get("g_m"))),
        "ab": (wb or {}).get("a_b", 0) if wb else 0,
        "gm": (wb or {}).get("g_m", 0) if wb else 0,
        "blacks": tone.get("blacks", 0),
        "whites": tone.get("whites", 0),
        "contrast": advice.get("contrast", 0),
        "sharp": 0,
        "sharp22": advice.get("sharpness", 0),
        "shading": int(look.get("vignette") or 0),
        "sh": tone.get("shadows", 0),
        "mid": tone.get("midtones", 0),
        "hi": tone.get("highlights", 0),
        "fx": 0,
        "art": 0,
        "nr": 0,
        "vig": 0,
        "grain": 0,
    }


def build_bank_json(
    by: dict[str, dict],
    lib: dict[str, dict],
    rows: list[list[str | None]],
) -> dict:
    prof = []
    for row in rows:
        slots = []
        for name in row:
            if not name:
                slots.append(None)
                continue
            if name.startswith("lib:"):
                key = name[4:]
                look = lib.get(key)
                if not look:
                    raise SystemExit(f"look not found in library.json: {key!r}")
                slots.append(library_to_profile(look, display_name=key))
                continue
            film = by.get(name)
            if not film:
                raise SystemExit(f"film not found in om3films.json: {name!r}")
            slots.append(film_to_profile(film, display_name=name))
        while len(slots) < 5:
            slots.append(None)
        prof.append(slots[:5])
    while len(prof) < 4:
        prof.append([None] * 5)
    return {"sel": [0, 0, 0, 0], "prof": prof[:4]}


def build_looks_bin(bank: dict) -> bytes:
    sys.path.insert(0, str(MKPROFILES.parent))
    import mkprofiles  # type: ignore

    return mkprofiles.build(bank)


def font(size: int):
    for p in FONTS:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    raise SystemExit(f"no usable font; place DejaVuSansCondensed.ttf under {FONT_DIR}")


def raster(txt: str, fs: int, sq: float) -> np.ndarray:
    S = 4
    f = font(fs * S)
    im = Image.new("L", (fs * S * max(1, len(txt)) + 200, fs * S * 2), 0)
    ImageDraw.Draw(im).text((50, 20), txt, font=f, fill=255)
    a = np.array(im)
    ys, xs = np.nonzero(a > 0)
    if len(xs) == 0:
        return np.zeros((max(1, round(im.height / S)), 1), dtype=int)
    im = im.crop((int(xs.min()), 0, int(xs.max()) + 1, a.shape[0]))
    return np.array(
        im.resize((max(1, round(im.width / S * sq)), round(im.height / S)), Image.LANCZOS)
    ).astype(int)


def name_indices(text: str, shrink: int = 0) -> np.ndarray:
    """Camera label-style 175x50 palette indices (ported from om3names.ts / mkguides)."""
    fs = 20
    for fs in range(20, 60):
        rows = np.nonzero((raster("H", fs, 1.0) > 128).any(axis=1))[0]
        if len(rows) and rows.max() - rows.min() + 1 >= 31:
            break
    sq = 0.6
    for k in range(60, 111):
        sq = k / 100
        cols = np.nonzero((raster("o", fs, sq) > 128).any(axis=0))[0]
        if len(cols) and cols.max() - cols.min() + 1 >= 15:
            break
    fs = max(16, fs - shrink)
    a = raster(text, fs, sq)
    while a.shape[1] > 167 and sq > 0.6:
        sq = round(sq - 0.02, 2)
        a = raster(text, fs, sq)
    while a.shape[1] > 167 and fs > 16:
        fs -= 1
        a = raster(text, fs, sq)

    a0 = raster(text[0], fs, sq)
    base_rows = np.nonzero((a0 > 128).any(axis=1))[0]
    base = int(base_rows.max()) if len(base_rows) else 30
    ink = np.nonzero((a > 40).any(axis=1))[0]
    rows = [a[yy] for yy in range(a.shape[0])]
    DESC = 6
    if len(ink) and ink[-1] - base > DESC:
        tail = rows[base + 1 : ink[-1] + 1]
        n = len(tail)
        sq2 = []
        for k in range(DESC):
            lo, hi = k * n / DESC, (k + 1) * n / DESC
            row = np.zeros(a.shape[1], dtype=int)
            for xx in range(a.shape[1]):
                s = wsum = 0.0
                for t in range(int(np.floor(lo)), int(np.ceil(hi))):
                    wgt = min(hi, t + 1) - max(lo, t)
                    s += float(tail[t][xx]) * wgt
                    wsum += wgt
                row[xx] = int(round(s / wsum)) if wsum else 0
            sq2.append(row)
        rows = rows[: base + 1] + sq2 + [np.zeros(a.shape[1], dtype=int) for _ in rows[ink[-1] + 1 :]]

    lay = np.zeros((NM_H, NM_W), dtype=np.uint8)
    x0 = (NM_W - a.shape[1]) // 2
    shift = 40 - base
    for yy, row in enumerate(rows):
        y2 = yy + shift
        if y2 < 0 or y2 >= NM_H:
            continue
        for xx, v in enumerate(row):
            X = x0 + xx
            if X < 0 or X >= NM_W:
                continue
            if v > 128:
                lay[y2, X] = 10
            elif v > 40:
                lay[y2, X] = 11

    fillm = lay == 10
    soft = lay == 11
    e = ndimage.distance_transform_edt(~fillm)
    out = np.zeros((NM_H, NM_W), dtype=np.uint8)
    out[(e > 0) & (e <= 1.0)] = 7
    out[(e > 0) & (e <= 1.0) & soft] = 11
    out[(e > 1.0) & (e < 1.5)] = 12
    out[(e >= 1.5) & (e <= 2.0)] = 7
    out[(e > 2.0) & (e <= 2.9)] = 9
    out[fillm] = 10
    return out


def encode11(px: np.ndarray, w: int = NM_W, h: int = NM_H) -> bytes:
    flat = px.reshape(-1)
    toks = []
    i = 0
    while i < len(flat):
        v = int(flat[i])
        r = 1
        while r < 16 and i + r < len(flat) and int(flat[i + r]) == v:
            r += 1
        toks.append((v << 4) | (r - 1))
        i += r
    out = bytearray(4 + 8 * ((len(toks) + 4) // 5))
    out[0] = (h - 1) & 255
    out[1] = ((h - 1) >> 8 & 3) | (((w - 1) & 15) << 4)
    out[2] = ((w - 1) >> 4) & 63
    out[3] = 11
    for k in range(0, len(toks), 5):
        lo = hi = 0
        for s in range(5):
            if k + s >= len(toks):
                break
            t = toks[k + s] << (12 * s)
            lo |= t & 0xFFFFFFFF
            hi |= t >> 32
        struct.pack_into("<II", out, 4 + 8 * (k // 5), lo & 0xFFFFFFFF, hi & 0xFFFFFFFF)
    return bytes(out)


def name_text(prof_row: list[dict | None], j: int) -> str:
    p = prof_row[j] if j < len(prof_row) else None
    if not p:
        return "Empty"
    return (p.get("name") or f"Look {j + 1}")[:15]


def build_names_bin(bank: dict) -> bytes:
    groups = []
    for k in range(4):
        row = bank["prof"][k]
        shrink = 0
        while True:
            pics = [encode11(name_indices(name_text(row, j), shrink)) for j in range(5)]
            tot = sum((len(p) + 3) & ~3 for p in pics)
            if tot <= NM_GROUP_MAX or shrink >= 16:
                break
            shrink += 2
        groups.append(pics)
    glen = [sum((len(p) + 3) & ~3 for p in pics) for pics in groups]
    total = 144 + sum(glen)
    b = bytearray(total)
    b[0:4] = b"OM3N"
    struct.pack_into("<I", b, 4, total)
    struct.pack_into("<HHHH", b, 12, 1, 20, NM_W, NM_H)
    at = 144
    for k, pics in enumerate(groups):
        struct.pack_into("<II", b, 32 + 8 * k, at, glen[k])
        off = 0
        for j, pic in enumerate(pics):
            struct.pack_into("<HH", b, 64 + 4 * (5 * k + j), off, len(pic))
            b[at + off : at + off + len(pic)] = pic
            off += (len(pic) + 3) & ~3
        at += glen[k]
    struct.pack_into("<I", b, 8, zlib.crc32(b[12:]) & 0xFFFFFFFF)
    return bytes(b)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True, help="OM3MOD output directory")
    ap.add_argument(
        "--pack",
        choices=("blog-color1", "caduceus-default"),
        default="blog-color1",
        help="blog-color1: COLOR1 = Classic Neg + Kodachrome 64 + 3 Empty; COLOR4-5 = Vision3 500T",
    )
    args = ap.parse_args()
    by = load_films()
    lib = load_library_looks()
    rows = [list(r) for r in DEFAULT_ROWS]
    if args.pack == "caduceus-default":
        rows[0] = ["Classic Chrome", "Classic Neg", "Reala Ace", "Eterna", "Pro Neg Std"]
        rows[3][4] = "lib:Vision3 500T"
    bank = build_bank_json(by, lib, rows)
    looks = build_looks_bin(bank)
    names = build_names_bin(bank)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "LOOKS.BIN").write_bytes(looks)
    (args.out / "NAMES.BIN").write_bytes(names)
    (args.out / "looks_bank.json").write_text(json.dumps(bank, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(args.out),
                "pack": args.pack,
                "LOOKS.BIN": {"bytes": len(looks), "sha256": __import__("hashlib").sha256(looks).hexdigest()},
                "NAMES.BIN": {"bytes": len(names), "sha256": __import__("hashlib").sha256(names).hexdigest()},
                "color1": [p["name"] if p else None for p in bank["prof"][0]],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
