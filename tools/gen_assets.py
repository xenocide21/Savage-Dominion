#!/usr/bin/env python3
"""Asset generator for the SNES arena fighter.

Produces ../build/assets.s (+ .bin blobs) with:
  * the side-view stage (stage_pit.py): BG1 / BG2 tiles, maps, palettes, floor scroll factors
  * colour-math HDMA tables (translucent floor shadows, title band)
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
# Side view: the camera looks straight at the fighting plane from CAMDIST away.
HORIZON = 124         # screen line of the horizon
FOCAL = 256           # focal length in pixels
CAMH = 40             # camera height above the floor, world units (= floor texels)
CAMDIST = 330         # hu from the camera to the fighting plane
STAGE_SC = 201        # screen pixels per 256 hu at the fighting plane (scale8 at CAMDIST)
FEET_Y = HORIZON + ((CAMH * 2 * STAGE_SC) >> 8)   # where standing feet meet the floor
FLOORTOP = 152        # screen line of the floor's far edge (a tile boundary)
STAGE_HALF = 300      # walls, hu either side of the stage centre
CAMX_MAX = 160        # the camera stops this far from the centre
MAXSEP = 250          # fighters can't separate further than the screen shows

def c5(r, g, b):
    """8-bit-per-channel rgb -> SNES BGR555 word"""
    return ((b >> 3) << 10) | ((g >> 3) << 5) | (r >> 3)

blobs = []            # (label, bytes, segment)
consts = {}

def blob(label, data, seg=None):
    blobs.append((label, bytes(data), seg))

consts.update(HORIZON=HORIZON, FOCAL=FOCAL, CAMH=CAMH, CAMDIST=CAMDIST, STAGE_SC=STAGE_SC, FEET_Y=FEET_Y,
              FLOORTOP=FLOORTOP, STAGE_HALF=STAGE_HALF, CAMX_MAX=CAMX_MAX, MAXSEP=MAXSEP)

# ------------------------------------------------------------------ 4bpp tile helper
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

# ------------------------------------------------------------------ stage 1: THE PIT (underground fight club)
# BG2 = far brick wall and crowd (slow parallax); BG1 = lamps, cage barrier and the
# concrete floor.  Both maps are 512 x 256 and repeat every 128 px (BG1) / 256 px (BG2).
# The floor's pseudo-perspective comes from a per-line BG1 scroll table (HDMA).
import stage_pit
far_img, far_pal, near_img, near_pal, floor_pal = stage_pit.draw(512, 256, FLOORTOP, FEET_Y)

def stage_layer(img, name, pal_of_row, limit):
    t, m = tiles4(img, 512, 256)
    blank = bytes(32)
    if t[0] != blank:                       # tile 0 stays empty (transparent)
        t = [blank] + t
        m = [i + 1 for i in m]
    assert len(t) <= limit, "%s uses %d tiles (limit %d)" % (name, len(t), limit)
    mp = bytearray(64 * 32 * 2)
    for ty in range(32):
        for tx in range(64):
            e = m[ty * 64 + tx] | (pal_of_row(ty) << 10)
            pos = (ty * 32 + (tx % 32)) + (0 if tx < 32 else 32 * 32)
            mp[pos * 2] = e & 0xFF; mp[pos * 2 + 1] = e >> 8
    consts[name.upper() + "_TILES"] = len(t)
    blob(name + "_tiles", b"".join(t), 2 if name == "near" else 13)
    blob(name + "_map", mp, 4)
    return len(t)

n_near = stage_layer(near_img, "near", lambda ty: 4 if ty * 8 >= FLOORTOP else 3, 512)
n_far = stage_layer(far_img, "far", lambda ty: 2, 256)

# per 2-line floor band: horizontal scroll factor * 128 (1.0 at the feet line)
bands = list(range(FLOORTOP, 224, 2))
floor_k = [max(1, min(255, int(round(128 * (y + 1 - HORIZON) / (FEET_Y - HORIZON))))) for y in bands]
blob("floor_k", bytes(floor_k))
consts["FLOOR_BANDS"] = len(bands)
# CGADSUB + COLDATA (HDMA mode 1): translucent shadows only on the floor lines
def runs(n, a, b):
    out = bytearray()
    while n > 0:
        k = min(127, n); out += bytes([k, a, b]); n -= k
    return out
blob("math_fight", runs(FLOORTOP, 0x00, 0xE0) + runs(1, 0x50, 0xE0) + b"\0")
BAND = 176
blob("math_title", runs(FLOORTOP, 0x00, 0xE0) + runs(BAND - FLOORTOP, 0x50, 0xE0) +
     runs(2, 0x20, 0x60 | 22) + runs(2, 0x20, 0x60 | 9) + runs(1, 0x00, 0xE0) + b"\0")
blob("tm_title", bytes([127, 0x17, BAND - 127, 0x17, 1, 0x14, 0]))

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
for base, pal in ((32, far_pal), (48, near_pal), (64, floor_pal)):
    for i, c in enumerate(pal): bgpal[base + i] = c5(*c)
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
            spike = rad * (0.6 + 1.0 * abs(math.cos(ang * 2)) ** 6)
            if d < min(spike, 7.8): p[x, y] = 3 if d < rad * 0.5 else (2 if d < rad else 1)
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
_hot = _gsyms["hotEnd"] - _gsyms["hot"]
assert _gsyms["hot"] % 16 == 0 and _hot <= 560, "GSU hot code has outgrown the cache window: %d bytes" % _hot
print("gsu: hot code %d bytes (512 cached)" % _hot)
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
print("stage tiles: near %d, far %d; OBJ tiles used %d" %
      (n_near, n_far, sum(1 for r in grid for c in r if c)))
