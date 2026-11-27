#!/usr/bin/env python3
"""Asset generator for the SNES arena fighter.

Produces ../build/assets.s (+ .bin blobs) with:
  * Mode 7 arena floor: 128x128 tile map + up to 256 8bpp tiles, palette entries 64..127
  * perspective HDMA tables for 256 camera yaw angles (M7A/M7B/M7C/M7D per floor line)
  * sky gradient (COLDATA HDMA), distant panorama (BG2, mode 1) + palette
  * shaded ball sprites (OBJ tiles) in 15 sizes x 2 material halves
  * 2bpp font for the HUD (BG3)
  * sin/cos and reciprocal tables for the 3D projection
All sizes/constants shared with the assembly are written to ../build/consts.inc.
"""
import math, os, random
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "build")
PREV = os.path.join(HERE, "..", "preview")
os.makedirs(OUT, exist_ok=True)
os.makedirs(PREV, exist_ok=True)

# ------------------------------------------------------------------ camera / projection constants
HORIZON = 72          # screen line of the horizon
FOG = 10              # lines below the horizon left blank (matrix values would overflow there)
FOCAL = 256           # focal length in pixels
CAMH = 40             # camera height above the floor, world units (= floor texels)
FLOOR0 = HORIZON + FOG
NANG = 256            # camera yaw steps

def c5(r, g, b):
    """8-bit-per-channel rgb -> SNES BGR555 word"""
    return ((b >> 3) << 10) | ((g >> 3) << 5) | (r >> 3)

blobs = []            # (label, bytes, segment)
consts = {}

def blob(label, data, seg=None):
    blobs.append((label, bytes(data), seg))

# ------------------------------------------------------------------ Mode 7 arena floor
MAPW = 1024
CX = CY = 512
ARENA = 168           # half-width of the octagonal ring (world units)
consts.update(ARENA_CX=CX, ARENA_CY=CY, ARENA_R=ARENA)

floor_pal = [
    (24, 40, 72), (30, 52, 92), (40, 66, 112), (60, 96, 140), (110, 150, 190),       # water 0-4
    (70, 64, 60), (92, 86, 78), (116, 108, 98), (140, 132, 120), (168, 160, 146),   # stone 5-9
    (52, 46, 42), (196, 188, 170),                                                  # grout 10, edge light 11
    (150, 110, 60), (190, 150, 80), (230, 196, 110),                                # gold inlay 12-14
    (40, 34, 32),                                                                   # deep edge 15
]

def in_oct(x, y, r):
    """octagon whose diagonal edges run through tile corners (keeps the tile count low)"""
    dx, dy = abs(x - CX), abs(y - CY)
    return dx <= r and dy <= r and dx + dy <= r + 64

floor = Image.new("P", (MAPW, MAPW), 0)
fp = floor.load()
for y in range(MAPW):
    for x in range(MAPW):
        tx, ty = x % 8, y % 8
        if in_oct(x + 0.5, y + 0.5, ARENA):
            if not in_oct(x + 0.5, y + 0.5, ARENA - 8):
                c = 11 if not in_oct(x + 0.5, y + 0.5, ARENA - 3) else 9      # bright rim
            else:
                sx, sy = (x - CX + 2048) // 32, (y - CY + 2048) // 32
                tone = (sx + sy * 2) % 3
                if (x - CX) % 32 == 0 or (y - CY) % 32 == 0:
                    c = 10
                else:
                    c = 6 + tone
                    if ((tx * 3 + ty * 5) % 11) == 0: c = 5 + tone
                d = math.hypot(x + 0.5 - CX, y + 0.5 - CY)
                if 44 <= d < 48 or 84 <= d < 87:
                    c = 13 if (int(d) % 4) else 14
                if d < 6:
                    c = 14
            fp[x, y] = c
        else:
            if in_oct(x + 0.5, y + 0.5, ARENA + 8):
                fp[x, y] = 15
            else:
                fp[x, y] = 1 + ((x // 4 + y // 4) % 4 > 1) + ((x // 8 + y // 8) % 2)
# tile-ize (deduplicate) -> must fit 256 tiles
tiles, tmap, index = [], [], {}
for ty in range(128):
    for tx in range(128):
        t = floor.crop((tx * 8, ty * 8, tx * 8 + 8, ty * 8 + 8)).tobytes()
        if t not in index:
            index[t] = len(tiles)
            tiles.append(t)
        tmap.append(index[t])
assert len(tiles) <= 256, "mode 7 floor uses %d tiles" % len(tiles)
# VRAM interleave: low byte = map, high byte = tile pixels (64 colours offset by 64)
m7 = bytearray(0x8000)      # 16K VRAM words: low byte map, high byte tile pixels
for i, t in enumerate(tmap):
    m7[i * 2] = t
for ti, t in enumerate(tiles):
    for p in range(64):
        m7[(ti * 64 + p) * 2 + 1] = (t[p] + 64) if True else 0
blob("m7_vram0", m7, 2)
floorpal = [c5(*c) for c in floor_pal]
consts["FLOOR_TILES"] = len(tiles)
prev = Image.new("RGB", (MAPW // 2, MAPW // 2))
pp = prev.load()
for y in range(0, MAPW, 2):
    for x in range(0, MAPW, 2):
        pp[x // 2, y // 2] = floor_pal[fp[x, y]]
prev.save(os.path.join(PREV, "floor.png"))

# ------------------------------------------------------------------ perspective HDMA tables
# floor line y (>= FLOOR0): distance f = CAMH*FOCAL/(y-HORIZON)
#   lateral scale s = CAMH/(y-h), forward step t = CAMH*FOCAL/(y-h)^2
#   A = s*cos, B = t*sin, C = s*sin, D = -t*cos   (8.8 fixed)
# tables: one entry per 2 lines (repeat), HDMA mode 2 (write twice), 4 registers per angle
def fx88(v):
    v = int(round(v * 256))
    v = max(-32768, min(32767, v))
    return v & 0xFFFF

lines = list(range(FLOOR0, 224, 2))
consts["PERSP_ENTRIES"] = len(lines)
tabA, tabB, tabC, tabD = bytearray(), bytearray(), bytearray(), bytearray()
for a in range(NANG):
    ang = a * 2 * math.pi / NANG
    ca, sa = math.cos(ang), math.sin(ang)
    for tab, fn in ((tabA, lambda s, t: s * ca), (tabB, lambda s, t: t * sa),
                    (tabC, lambda s, t: s * sa), (tabD, lambda s, t: -t * ca)):
        tab += bytes([FLOOR0 & 0x7F, 0, 0])                  # lines above the floor: don't care
        for y in lines:
            k = y - HORIZON + 0.5
            s, t = CAMH / k, CAMH * FOCAL / (k * k)
            v = fx88(fn(s, t))
            tab += bytes([2, v & 0xFF, v >> 8])
        tab += bytes([0])
consts["PERSP_TAB_SIZE"] = len(tabA) // NANG
# each register's 256 tables live in their own bank region (size per angle * 256)
HALF = 128 * (len(tabA) // NANG)
for i, (nm, tab) in enumerate((("A", tabA), ("B", tabB), ("C", tabC), ("D", tabD))):
    blob("persp_%s0" % nm, tab[:HALF], 4 + i * 2)          # angles 0..127
    blob("persp_%s1" % nm, tab[HALF:], 5 + i * 2)          # angles 128..255

# ------------------------------------------------------------------ sky gradient + panorama (BG2) + HUD font (BG3)
# COLDATA HDMA (one channel, 1 byte per line, 3 writes via separate R/G/B? -> use the
# combined format: bit7 B, bit6 G, bit5 R + 5-bit value).  Gradient: dusk purple -> orange.
sky = bytearray()
for y in range(HORIZON + FOG + 1):
    k = y / (HORIZON + FOG)
    r = int(4 + 22 * k); g = int(2 + 12 * k); b = int(14 - 6 * k)
    sky += bytes([1, 0x20 | min(31, r)])
    sky += bytes([0, 0x40 | min(31, g)])  # same line: chained writes handled by 3 channels
# HDMA ch7 writes CGADSUB + COLDATA per line (mode 1).  Sky: add a fixed colour to the
# backdrop (R+B channels together; G fixed at init).  Floor: half-add OBJ palettes 4-7 with the
# sub screen (BG1) -> translucent shadows.
sky_r = bytearray()
for y in range(HORIZON + FOG):
    k = y / (HORIZON + FOG)
    sky_r += bytes([1, 0x20, 0xA0 | int(4 + 20 * k)])
sky_r += bytes([1, 0x50, 0xE0])
sky_r += bytes([0])
sky_g = sky_b = b"\0"
blob("sky_r", sky_r)

# panorama: 512 x 40 px silhouette band (mountains + temple columns), 4bpp, palette 1
PW, PH = 512, 48
pan = Image.new("P", (PW, PH), 0)
pp = pan.load()
rr = random.Random(11)
hts = []
h = 26.0
for x in range(PW):
    h += rr.uniform(-1.2, 1.2) + (28 - h) * 0.02
    hts.append(h)
for x in range(PW):
    far = int(PH - hts[x])
    near = int(PH - (hts[(x * 3) % PW] * 0.45 + 6 + 5 * math.sin(x / 23.0)))
    for y in range(PH):
        if y >= near: pp[x, y] = 3
        elif y >= far: pp[x, y] = 2 if (x + y) % 5 else 1
    # temple columns every 128 px
    if x % 128 in range(60, 68) or x % 128 in range(76, 84):
        for y in range(PH - 30, PH): pp[x, y] = 4 if (x % 128) % 8 in (0, 7) else 5
    if x % 128 in range(56, 88):
        for y in range(PH - 33, PH - 30): pp[x, y] = 5
pan_pal = [0, c5(70, 50, 110), c5(56, 40, 92), c5(34, 26, 60), c5(120, 96, 120), c5(160, 128, 140)]
pan_pal += [0] * (16 - len(pan_pal))

def tiles4(img, w, h):
    """img -> list of 4bpp planar 8x8 tiles (row-major), map entries"""
    out, idx, mp = [], {}, []
    px = img.load()
    for ty in range(h // 8):
        for tx in range(w // 8):
            b = bytearray(32)
            for y in range(8):
                for x in range(8):
                    v = px[tx * 8 + x, ty * 8 + y] & 15
                    for p in range(4):
                        if v >> p & 1:
                            b[(p // 2) * 16 + y * 2 + (p & 1)] |= 0x80 >> x
            k = bytes(b)
            if k not in idx:
                idx[k] = len(out); out.append(k)
            mp.append(idx[k])
    return out, mp

pt, pm = tiles4(pan, PW, PH)
consts["PAN_TILES"] = len(pt)
blob("pan_tiles", b"".join(pt), 13)
# BG2 map 64x32: panorama rows placed at tile rows 3..8 (so it sits just above the horizon)
bg2 = bytearray(64 * 32 * 2)
ROW0 = HORIZON // 8 - PH // 8          # bottom of the band touches the horizon
for ty in range(PH // 8):
    for tx in range(64):
        t = pm[ty * 64 + tx]
        e = t | (1 << 10)                    # palette 1
        pos = ((ty + ROW0) * 32 + (tx % 32)) + (0 if tx < 32 else 32 * 32)
        bg2[pos * 2] = e & 0xFF; bg2[pos * 2 + 1] = e >> 8
blob("pan_map", bg2, 13)

# 2bpp font (5x7 in 8x8), ASCII 32..95, palette 0 entries 1..3 (fill, shadow, highlight)
FONT = {}
def glyph(ch, rows): FONT[ch] = rows
import string
G = {
"0": ".###.|#...#|#..##|#.#.#|##..#|#...#|.###.", "1": "..#..|.##..|..#..|..#..|..#..|..#..|.###.",
"2": ".###.|#...#|....#|...#.|..#..|.#...|#####", "3": ".###.|#...#|....#|..##.|....#|#...#|.###.",
"4": "...#.|..##.|.#.#.|#..#.|#####|...#.|...#.", "5": "#####|#....|####.|....#|....#|#...#|.###.",
"6": "..##.|.#...|#....|####.|#...#|#...#|.###.", "7": "#####|....#|...#.|..#..|.#...|.#...|.#...",
"8": ".###.|#...#|#...#|.###.|#...#|#...#|.###.", "9": ".###.|#...#|#...#|.####|....#|...#.|.##..",
"A": ".###.|#...#|#...#|#####|#...#|#...#|#...#", "B": "####.|#...#|#...#|####.|#...#|#...#|####.",
"C": ".###.|#...#|#....|#....|#....|#...#|.###.", "D": "####.|#...#|#...#|#...#|#...#|#...#|####.",
"E": "#####|#....|#....|####.|#....|#....|#####", "F": "#####|#....|#....|####.|#....|#....|#....",
"G": ".###.|#...#|#....|#.###|#...#|#...#|.####", "H": "#...#|#...#|#...#|#####|#...#|#...#|#...#",
"I": ".###.|..#..|..#..|..#..|..#..|..#..|.###.", "J": "..###|...#.|...#.|...#.|...#.|#..#.|.##..",
"K": "#...#|#..#.|#.#..|##...|#.#..|#..#.|#...#", "L": "#....|#....|#....|#....|#....|#....|#####",
"M": "#...#|##.##|#.#.#|#.#.#|#...#|#...#|#...#", "N": "#...#|#...#|##..#|#.#.#|#..##|#...#|#...#",
"O": ".###.|#...#|#...#|#...#|#...#|#...#|.###.", "P": "####.|#...#|#...#|####.|#....|#....|#....",
"Q": ".###.|#...#|#...#|#...#|#.#.#|#..#.|.##.#", "R": "####.|#...#|#...#|####.|#.#..|#..#.|#...#",
"S": ".####|#....|#....|.###.|....#|....#|####.", "T": "#####|..#..|..#..|..#..|..#..|..#..|..#..",
"U": "#...#|#...#|#...#|#...#|#...#|#...#|.###.", "V": "#...#|#...#|#...#|#...#|#...#|.#.#.|..#..",
"W": "#...#|#...#|#...#|#.#.#|#.#.#|#.#.#|.#.#.", "X": "#...#|#...#|.#.#.|..#..|.#.#.|#...#|#...#",
"Y": "#...#|#...#|.#.#.|..#..|..#..|..#..|..#..", "Z": "#####|....#|...#.|..#..|.#...|#....|#####",
"!": "..#..|..#..|..#..|..#..|..#..|.....|..#..", ".": ".....|.....|.....|.....|.....|.....|..#..",
"-": ".....|.....|.....|#####|.....|.....|.....", ":": ".....|..#..|.....|.....|.....|..#..|.....",
"/": "....#|...#.|...#.|..#..|.#...|.#...|#....", "+": ".....|..#..|..#..|#####|..#..|..#..|.....",
"'": "..#..|..#..|.....|.....|.....|.....|.....", "?": ".###.|#...#|....#|...#.|..#..|.....|..#..",
">": "#....|.#...|..#..|...#.|..#..|.#...|#....", "<": "....#|...#.|..#..|.#...|..#..|...#.|....#",
"=": ".....|.....|#####|.....|#####|.....|.....", "*": ".....|#.#.#|.###.|#####|.###.|#.#.#|.....",
"^": "..#..|.#.#.|#...#|.....|.....|.....|.....", ",": ".....|.....|.....|.....|.....|..#..|.#...",
"(": "...#.|..#..|.#...|.#...|.#...|..#..|...#.", ")": ".#...|..#..|...#.|...#.|...#.|..#..|.#...",
"#": ".#.#.|#####|.#.#.|.#.#.|.#.#.|#####|.#.#.",
}
font = bytearray()
for code in range(32, 96):
    ch = chr(code)
    b = bytearray(16)
    if ch in G:
        rows = G[ch].split("|")
        grid = [[c == "#" for c in r] for r in rows]
        for y in range(8):
            for x in range(-1, 7):
                v = 0
                def on(yy, xx): return 0 <= yy < 7 and 0 <= xx < 5 and grid[yy][xx]
                if on(y, x): v = 1
                elif any(on(y + dy, x + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)) or on(y - 1, x - 1): v = 2   # dark outline
                if v & 1: b[y * 2] |= 0x80 >> (x + 1) if x < 7 else 0
                if v & 2: b[y * 2 + 1] |= 0x80 >> (x + 1) if x < 7 else 0
    font += b
blob("font2", font, 13)
# HUD bar tiles (2bpp, indices 64..): empty, full, end caps
bars = bytearray()
for kind in range(9):                           # 0..8 filled pixels (health bar segment)
    b = bytearray(16)
    for y in range(8):
        for x in range(8):
            if y in (0, 7): v = 2
            elif x < kind: v = 3 if y < 3 else 1
            else: v = 2 if y in (1, 6) else 0
            if v & 1: b[y * 2] |= 0x80 >> x
            if v & 2: b[y * 2 + 1] |= 0x80 >> x
    bars += b
blob("bar2", bars, 13)
consts["BAR_TILE0"] = 64

# BG palettes (CGRAM 0..127): 0 backdrop/HUD, 1 panorama
bgpal = [0] * 128
bgpal[0] = c5(8, 4, 24)
bgpal[1] = c5(250, 246, 230); bgpal[2] = c5(20, 16, 30); bgpal[3] = c5(255, 214, 90)   # BG3 pal0: text
bgpal[5] = c5(250, 90, 70); bgpal[6] = c5(20, 16, 30); bgpal[7] = c5(255, 170, 120)   # BG3 pal1: P1 bar
bgpal[9] = c5(90, 170, 250); bgpal[10] = c5(20, 16, 30); bgpal[11] = c5(170, 220, 255) # BG3 pal2: P2 bar
bgpal[13] = c5(255, 196, 40); bgpal[14] = c5(20, 16, 30); bgpal[15] = c5(255, 250, 190) # BG3 pal3: logo
for i in range(16): bgpal[16 + i] = pan_pal[i]
for i, c in enumerate(floorpal): bgpal[64 + i] = c
blob("bg_pal", b"".join(bytes([c & 0xFF, c >> 8]) for c in bgpal))

# ------------------------------------------------------------------ ball sprites
# radii 2..8 in 16x16 cells, 9..16 in 32x32 cells.  Shades 1..7 (variant A) / 8..14 (B), 15 = outline.
SMALL = list(range(2, 9))
LARGE = list(range(9, 17))

def ball_img(r, size, hi):
    im = Image.new("P", (size, size), 0)
    p = im.load()
    c = size / 2.0
    lx, ly, lz = -0.45, -0.55, 0.70
    for y in range(size):
        for x in range(size):
            dx, dy = (x + 0.5 - c) / r, (y + 0.5 - c) / r
            d2 = dx * dx + dy * dy
            if d2 <= 1.0:
                dz = math.sqrt(1 - d2)
                lam = max(0.0, dx * lx + dy * ly + dz * lz)
                spec = lam ** 18
                v = 1 + int(min(6, lam * 5.2 + spec * 3))
                if d2 > 0.80 and r >= 4: v = 1               # dark rim reads as an outline
                p[x, y] = v + (7 if hi else 0)
    return im

def obj_tiles(img):
    """4bpp tiles of an image (row-major 8x8)"""
    t, _ = tiles4(img, img.width, img.height)
    # tiles4 dedups; keep all instead
    out = []
    px = img.load()
    for ty in range(img.height // 8):
        for tx in range(img.width // 8):
            b = bytearray(32)
            for y in range(8):
                for x in range(8):
                    v = px[tx * 8 + x, ty * 8 + y] & 15
                    for pl in range(4):
                        if v >> pl & 1:
                            b[(pl // 2) * 16 + y * 2 + (pl & 1)] |= 0x80 >> x
            out.append(bytes(b))
    return out

# OBJ VRAM: 512 tiles in a 16-wide grid.  Place 32x32 balls first (4x4 blocks), then 16x16.
grid = [[None] * 16 for _ in range(32)]
objtile = {}   # (kind, r, hi) -> top-left tile number
def place(w, imgtiles, key):
    n = w // 8
    for gy in range(0, 32, n):
        for gx in range(0, 16, n):
            if all(grid[gy + j][gx + i] is None for j in range(n) for i in range(n)):
                for j in range(n):
                    for i in range(n):
                        grid[gy + j][gx + i] = imgtiles[j * n + i]
                objtile[key] = gy * 16 + gx
                return
    raise Exception("OBJ VRAM full")

# rows 0..11 of both name tables hold the Super FX-rendered fighters (double-buffered)
for gy in list(range(0, 12)) + list(range(16, 28)):
    for gx in range(16): grid[gy][gx] = b"RESERVED"
# ground shadow: dark ellipse 32x16 (two 16x16 cells), palette 7 with colour math subtract
sh = Image.new("P", (32, 16), 0); sp = sh.load()
for y in range(16):
    for x in range(32):
        if ((x + 0.5 - 16) / 15) ** 2 + ((y + 0.5 - 8) / 6) ** 2 <= 1: sp[x, y] = 1
place(16, obj_tiles(sh.crop((0, 0, 16, 16))), ("SH", 0, 0))
place(16, obj_tiles(sh.crop((16, 0, 32, 16))), ("SH", 1, 0))
# hit spark (16x16) 3 frames
for f in range(3):
    im = Image.new("P", (16, 16), 0); p = im.load()
    rad = 3 + f * 2.5
    for y in range(16):
        for x in range(16):
            dx, dy = x + 0.5 - 8, y + 0.5 - 8
            d = math.hypot(dx, dy)
            ang = math.atan2(dy, dx)
            spike = rad * (1.0 + 0.9 * abs(math.cos(ang * 4)))
            if d < spike: p[x, y] = 3 if d < rad * 0.5 else (2 if d < rad else 1)
    place(16, obj_tiles(im), ("SP", f, 0))
objvram = bytearray()
for gy in range(32):
    for gx in range(16):
        objvram += grid[gy][gx] if grid[gy][gx] and grid[gy][gx] != b"RESERVED" else bytes(32)
blob("obj_tiles", objvram, 12)

def words(v): return b"".join(bytes([x & 0xFF, (x >> 8) & 0xFF]) for x in v)

# ---- Super FX: renderer program and circle half-width table, copied to Game Pak RAM at boot
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gsu as _gsu
_code, _gsyms = _gsu.Asm(0x4000).assemble(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "fx.gsu")).read())
assert _gsyms["psslow"] - 0x4000 <= 512, "GSU scanline code no longer fits the cache: %d" % (_gsyms["psslow"] - 0x4000)
blob("gsu_code", _code, 15)
consts["GSU_SIZE"] = len(_code)
consts["GSU_START"] = _gsyms["start"]
rcp = bytearray()                       # 65536 / dy for edge slopes (GSU has no divide)
for dy in range(256):
    v = 32767 if dy < 2 else min(32767, 65536 // dy)
    rcp += bytes([v & 0xFF, v >> 8])
circ = bytearray()                      # circle half widths, [r][dy]
for r in range(32):
    for dy in range(32):
        circ.append(int(math.sqrt(max(0.0, (r + 0.5) ** 2 - dy * dy))) if dy <= r else 0)
blob("gsu_circ", rcp + circ, 15)        # $2000 reciprocals, $2200 circle table
consts["SHADOW_TILE"] = objtile[("SH", 0, 0)]
consts["SHADOW_TILE2"] = objtile[("SH", 1, 0)]
consts["SPARK_TILE"] = objtile[("SP", 0, 0)]
consts["SPARK_TILE1"] = objtile[("SP", 1, 0)]
consts["SPARK_TILE2"] = objtile[("SP", 2, 0)]

# ------------------------------------------------------------------ math tables
sinT = bytearray(); cosT = bytearray()
for a in range(256):
    sinT.append(int(round(127 * math.sin(a * 2 * math.pi / 256))) & 0xFF)
    cosT.append(int(round(127 * math.cos(a * 2 * math.pi / 256))) & 0xFF)
blob("sin8", sinT); blob("cos8", cosT)
# reciprocal: recip[f] = FOCAL*256/f for f in 0..1023 (f in world units); clamp
rec = [min(65535, (FOCAL * 256) // max(1, f)) for f in range(1024)]
blob("recip", words(rec), 1)
sc8 = [min(255, 65536 // max(1, i * 4 + 2)) for i in range(256)]
blob("scale8", bytes(sc8))
# atan2 helper: angle (0..255) for (dx, dy) with |dx|,|dy| <= 31 (5-bit + sign handled in code) -> 64x64 table
at = bytearray()
for dy in range(-32, 32):
    for dx in range(-32, 32):
        at.append(int(round(math.atan2(dy, dx) * 128 / math.pi)) & 0xFF if (dx or dy) else 0)
blob("atan64", at, 1)

# ------------------------------------------------------------------ emit
consts.update(HORIZON=HORIZON, FOG=FOG, FLOOR0=FLOOR0, FOCAL=FOCAL, CAMH=CAMH)
with open(os.path.join(OUT, "consts.inc"), "w") as f:
    for k, v in consts.items():
        f.write("%s = %d\n" % (k, v))
segs = {}
with open(os.path.join(OUT, "assets.s"), "w") as f:
    f.write("; generated by tools/gen_assets.py\n.include \"consts.inc\"\n")
    for label, data, seg in blobs:
        fn = label + ".bin"
        open(os.path.join(OUT, fn), "wb").write(data)
        f.write('.segment "%s"\n.export %s\n%s: .incbin "%s"\n' %
                ("BANK%d" % seg if seg is not None else "RODATA", label, label, fn))
print("floor tiles %d, pan tiles %d, persp entries %d (%d bytes/angle), OBJ tiles used %d" %
      (len(tiles), len(pt), len(lines), consts["PERSP_TAB_SIZE"], sum(1 for r in grid for c in r if c)))
