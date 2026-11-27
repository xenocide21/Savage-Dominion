#!/usr/bin/env python3
"""Menu / splash art for ARENA FIGHTER FX.

Builds (into build/):
  logo2.bin        BG3 2bpp tiles of the ARENA FIGHTER FX logo (tile LOGO_T0..)
  logo_map.bin     28 x 4 BG3 map words (palette + tile) for the logo
  scen_tiles.bin   BG2 4bpp tiles: sunset arena scenery (palette 1)
  scen_map.bin     32 x 32 BG2 map
  line_tiles.bin   BG1 4bpp tiles: the six fighters facing the camera (palettes 2-7)
  line_map.bin     32 x 32 BG1 map
  menu_pal.bin     CGRAM 0..127 for the menu display (BG3 text/logo, scenery, fighters)
  menu_sky.bin     HDMA table: backdrop colour per 2 lines (sunset gradient)
  menu_obj.bin     OBJ tiles: embers
and preview/splash.png.
"""
import os, sys, math, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "build")
PREV = os.path.join(HERE, "..", "preview")
sys.path.insert(0, HERE)
import fighters as F
import model as Mo

LOGO_T0 = 80                    # first BG3 tile of the logo (font 0-63, bars 64-72)
LOGO_W, LOGO_H = 28, 4          # tiles
DARK = (20, 16, 30)

def c5(r, g, b): return ((b >> 3) << 10) | ((g >> 3) << 5) | (r >> 3)
def rgb(c): return ((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3)

# BG3 2bpp palettes (colours 1..3 of palettes 0..3, shared with the fight HUD)
BG3PAL = {
    0: [(250, 246, 230), DARK, (255, 214, 90)],      # text
    1: [(250, 90, 70), DARK, (255, 170, 120)],       # P1 bar / logo lower half
    2: [(90, 170, 250), DARK, (170, 220, 255)],      # P2 bar / "FX"
    3: [(255, 196, 40), DARK, (255, 250, 190)],      # logo upper half
}

def snes_rgb(t):  # round-trip through 5-bit
    return rgb(c5(*t))

# ------------------------------------------------------------------ logo
def make_logo():
    W, H = LOGO_W * 8, LOGO_H * 8
    fontp = "/usr/share/fonts/truetype/google-fonts/ofl/anton/Anton-Regular.ttf"
    S = 4                                   # supersample
    big = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    f1 = ImageFont.truetype(fontp, 27 * S)
    f2 = ImageFont.truetype(fontp, 34 * S)
    txt = "ARENA FIGHTER"
    tw = f1.getbbox(txt)[2]
    fxw = f2.getbbox("FX")[2]
    gap = 6 * S
    x0 = (W * S - (tw + gap + fxw)) // 2
    # letter mask, then gradient fill + dark outline
    m1 = Image.new("L", big.size, 0)
    ImageDraw.Draw(m1).text((x0, -9 * S), txt, font=f1, fill=255)
    m2 = Image.new("L", big.size, 0)
    # slanted "FX"
    tmp = Image.new("L", (fxw + 20 * S, H * S + 20 * S), 0)
    ImageDraw.Draw(tmp).text((6 * S, -6 * S), "FX", font=f2, fill=255)
    tmp = tmp.transform(tmp.size, Image.AFFINE, (1, 0.28, -4 * S, 0, 1, 0), Image.BILINEAR)
    m2.paste(tmp, (x0 + tw + gap - 6 * S, -2 * S), tmp)
    def grow(m, r):
        return m.filter(ImageFilter.MaxFilter(r * 2 + 1))
    out = Image.new("RGB", (W, H), (0, 0, 0))
    alpha = Image.new("L", (W, H), 0)
    m1s = m1.resize((W, H), Image.LANCZOS); m2s = m2.resize((W, H), Image.LANCZOS)
    o1 = grow(m1s.point(lambda v: 255 if v > 90 else 0), 1)
    o2 = grow(m2s.point(lambda v: 255 if v > 90 else 0), 1)
    px = out.load(); pa = alpha.load()
    a1 = m1s.load(); a2 = m2s.load(); b1 = o1.load(); b2 = o2.load()
    for y in range(H):
        t = y / (H - 1)
        # gold gradient: pale top -> gold -> red-orange
        if t < 0.35: g = BG3PAL[3][2]
        elif t < 0.6: g = BG3PAL[3][0]
        elif t < 0.8: g = BG3PAL[1][2]
        else: g = BG3PAL[1][0]
        fx = BG3PAL[2][2] if t < 0.45 else BG3PAL[2][0]
        for x in range(W):
            if a2[x, y] > 110: px[x, y] = fx; pa[x, y] = 255
            elif a1[x, y] > 110: px[x, y] = g; pa[x, y] = 255
            elif b1[x, y] or b2[x, y]: px[x, y] = DARK; pa[x, y] = 255
    # -> 2bpp tiles, one of palettes 1-3 per tile (best fit)
    tiles = []; tmap = []; seen = {}
    for ty in range(LOGO_H):
        for tx in range(LOGO_W):
            best = None
            for p in (3, 1, 2):
                cols = [snes_rgb(c) for c in BG3PAL[p]]
                err = 0; idx = []
                for y in range(8):
                    for x in range(8):
                        X, Y = tx * 8 + x, ty * 8 + y
                        if pa[X, Y] == 0: idx.append(0); continue
                        c = px[X, Y]
                        k = min(range(3), key=lambda i: sum((c[j] - cols[i][j]) ** 2 for j in range(3)))
                        err += sum((c[j] - cols[k][j]) ** 2 for j in range(3)); idx.append(k + 1)
                if best is None or err < best[0]: best = (err, p, idx)
            _, p, idx = best
            if not any(idx):
                tmap.append(0); continue                    # tile 0 of the font = space
            b = bytearray(16)
            for y in range(8):
                for x in range(8):
                    v = idx[y * 8 + x]
                    if v & 1: b[y * 2] |= 0x80 >> x
                    if v & 2: b[y * 2 + 1] |= 0x80 >> x
            key = bytes(b)
            if key not in seen:
                seen[key] = LOGO_T0 + len(tiles); tiles.append(key)
            tmap.append(seen[key] | (p << 10) | 0x2000)
    assert LOGO_T0 + len(tiles) <= 256, len(tiles)
    prev = Image.new("RGB", (W, H), (8, 4, 24))
    prev.paste(out, (0, 0), alpha)
    return b"".join(tiles), tmap, prev

# ------------------------------------------------------------------ 4bpp tile helpers
def tile4(idx):
    b = bytearray(32)
    for y in range(8):
        for x in range(8):
            v = idx[y * 8 + x]
            for pl in range(4):
                if v & (1 << pl):
                    b[(pl >> 1) * 16 + y * 2 + (pl & 1)] |= 0x80 >> x
    return bytes(b)

def to_tiles(idximg, palimg, tiles, seen, base=0, flip_ok=True):
    """idximg: 256x256 of colour index (0 transparent); palimg: per-tile palette.
    -> 32x32 map words (tiles deduplicated, with h/v flips)."""
    W, H = idximg.size
    mp = []
    pi = idximg.load()
    for ty in range(H // 8):
        for tx in range(W // 8):
            idx = [pi[tx * 8 + x, ty * 8 + y] for y in range(8) for x in range(8)]
            pal = palimg[ty][tx]
            if not any(idx): mp.append(0); continue
            found = None
            for fl, tr in ((0, idx), (0x4000, [idx[y * 8 + 7 - x] for y in range(8) for x in range(8)]),
                           (0x8000, [idx[(7 - y) * 8 + x] for y in range(8) for x in range(8)]),
                           (0xC000, [idx[(7 - y) * 8 + 7 - x] for y in range(8) for x in range(8)])):
                k = tile4(tr)
                if k in seen: found = seen[k] | fl; break
                if not flip_ok: break
            if found is None:
                k = tile4(idx)
                seen[k] = base + len(tiles); tiles.append(k); found = seen[k]
            mp.append(found | (pal << 10))
    return mp

# ------------------------------------------------------------------ scenery (BG2, palette 1)
SCEN = [  # 15 colours: sun / clouds / mountains / arena stone / torch fire
    (255, 236, 150), (255, 170, 80), (236, 96, 70),            # 1-3 sun core / rim / hot cloud
    (180, 70, 110), (110, 44, 100),                             # 4-5 cloud mid / cloud shadow
    (70, 30, 80), (44, 20, 60), (26, 12, 40),                   # 6-8 mountains far / near / darkest
    (120, 96, 110), (84, 66, 84), (56, 44, 60), (34, 26, 40),   # 9-12 stone light..dark
    (255, 120, 30), (255, 220, 90), (200, 180, 170),            # 13-15 fire / fire core / stone highlight
]
CLOUD_Y0, CLOUD_Y1 = 16, 60      # scrolling cloud band (lines)

def make_scenery():
    W, H = 256, 224
    img = Image.new("RGB", (W, H), (0, 0, 0))
    msk = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img); dm = ImageDraw.Draw(msk)
    rnd = random.Random(7)
    # sun, low behind the fighters
    for r, c in ((46, SCEN[1]), (40, SCEN[0])):
        d.ellipse([128 - r, 118 - r, 128 + r, 118 + r], fill=c); dm.ellipse([128 - r, 118 - r, 128 + r, 118 + r], fill=255)
    # sun stripes (retro bands)
    for i, y in enumerate(range(112, 166, 7)):
        h = 1 + i // 2
        d.rectangle([60, y, 196, y + h - 1], fill=(0, 0, 0)); dm.rectangle([60, y, 196, y + h - 1], fill=0)
    # far + near mountains
    def ridge(base, amp, seed, col, step):
        r = random.Random(seed); pts = [(0, H)]
        y = base
        for x in range(0, W + step, step):
            y = max(base - amp, min(base + amp // 3, y + r.randint(-amp // 3, amp // 3)))
            pts.append((x, y))
        pts.append((W, H))
        d.polygon(pts, fill=col); dm.polygon(pts, fill=255)
    ridge(126, 34, 3, SCEN[5], 16)
    ridge(146, 26, 11, SCEN[6], 12)
    ridge(160, 14, 5, SCEN[7], 10)
    # arena platform: stone floor in perspective + front lip
    top = 178
    d.polygon([(0, top + 6), (256, top + 6), (256, 224), (0, 224)], fill=SCEN[10])
    dm.polygon([(0, top + 6), (256, top + 6), (256, 224), (0, 224)], fill=255)
    for i in range(9):
        y = top + 6 + int(40 * (i / 8) ** 1.6)
        d.line([(0, y), (255, y)], fill=SCEN[11])
    for i in range(-10, 11):
        d.line([(128 + i * 14, top + 6), (128 + i * 40, 224)], fill=SCEN[11])
    d.rectangle([0, top + 4, 255, top + 6], fill=SCEN[14]); dm.rectangle([0, top + 4, 255, top + 6], fill=255)
    # stone pillars with torches at both sides
    for px in (10, 222):
        d.rectangle([px, 96, px + 23, top + 4], fill=SCEN[9]); dm.rectangle([px, 96, px + 23, top + 4], fill=255)
        d.rectangle([px + 17, 96, px + 23, top + 4], fill=SCEN[10])
        d.rectangle([px + 2, 96, px + 5, top + 4], fill=SCEN[14])
        for yy in range(104, top, 14): d.line([(px, yy), (px + 23, yy)], fill=SCEN[11])
        d.rectangle([px - 3, 90, px + 26, 97], fill=SCEN[10]); dm.rectangle([px - 3, 90, px + 26, 97], fill=255)
        # brazier + fire
        d.polygon([(px + 2, 90), (px + 21, 90), (px + 17, 84), (px + 6, 84)], fill=SCEN[11]); dm.polygon([(px + 2, 90), (px + 21, 90), (px + 17, 84), (px + 6, 84)], fill=255)
        d.polygon([(px + 4, 85), (px + 12, 62), (px + 19, 85)], fill=SCEN[12]); dm.polygon([(px + 4, 85), (px + 12, 62), (px + 19, 85)], fill=255)
        d.polygon([(px + 8, 85), (px + 12, 70), (px + 15, 85)], fill=SCEN[13])
    # clouds (tileable across 256 px), drawn in the scrolling band
    cl = Image.new("RGB", (W, H), (0, 0, 0)); cm = Image.new("L", (W, H), 0)
    dc = ImageDraw.Draw(cl); dcm = ImageDraw.Draw(cm)
    for i in range(22):
        cx = rnd.randint(0, 255); cy = rnd.randint(CLOUD_Y0 + 8, CLOUD_Y1 - 10); w = rnd.randint(26, 60); h = rnd.randint(5, 10)
        for ox in (-256, 0, 256):
            dc.ellipse([cx + ox - w // 2, cy - h // 2 + 2, cx + ox + w // 2, cy + h // 2 + 2], fill=SCEN[4])
            dc.ellipse([cx + ox - w // 2 + 4, cy - h // 2, cx + ox + w // 2 - 6, cy + h // 2 - 2], fill=SCEN[3] if cy > 60 else SCEN[2])
            dcm.ellipse([cx + ox - w // 2, cy - h // 2, cx + ox + w // 2, cy + h // 2 + 2], fill=255)
    cloud = Image.composite(cl, Image.new("RGB", (W, H)), cm)
    # clouds go behind the sun + mountains
    base = Image.composite(img, cloud, msk)
    bmask = Image.composite(msk, cm, msk)
    # mountains/sun/arena occlude clouds; keep the cloud band free of solid scenery rows? (sun overlaps:
    # the sun rows below CLOUD_Y1 do not scroll)
    return base, bmask

def quant(img, mask, pal, Hpad=256):
    """RGB + mask -> index image (0 transparent, 1..n nearest palette colour)"""
    W, H = img.size
    out = Image.new("L", (256, Hpad), 0)
    pi = img.load(); pm = mask.load(); po = out.load()
    cache = {}
    for y in range(H):
        for x in range(W):
            if pm[x, y] < 128: continue
            c = pi[x, y]
            if c not in cache:
                cache[c] = 1 + min(range(len(pal)), key=lambda i: sum((c[j] - pal[i][j]) ** 2 for j in range(3)))
            po[x, y] = cache[c]
    return out

# ------------------------------------------------------------------ fighters lineup (BG1, palettes 2-7)
LINE_FEET = 196
def lineup_centres():
    return [int(22 + i * 42.4) for i in range(6)]

def make_lineup():
    W, H = 256, 224
    layers = []
    for ci, ch in enumerate(F.ROSTER):
        im = Image.new("RGB", (W, H), (0, 0, 0))
        pal = Mo.palette_rgb(ch, F)
        pal = [(255, 0, 255)] + pal[1:]
        bgk = Image.new("RGB", (W, H), (255, 0, 255))
        # presentation pose: their stance, turned 3/4 toward the camera, a touch more upright
        st = dict(ch["stance"]); st["lean"] = st["lean"] * 0.5; st["head"] = 0
        J = F.fk(ch, st)
        th = math.radians(76)
        J = [(x * math.cos(th) + z * math.sin(th), y, -x * math.sin(th) + z * math.cos(th)) for (x, y, z) in J]
        cx = lineup_centres()[ci]
        flip = ci >= 3                          # the right half faces left (toward the centre)
        Mo.render(ch, F, J, pal, scale=1.08, flip=flip, img=bgk, at=(cx, LINE_FEET))
        layers.append(bgk)
    # combine: per pixel the fighter drawn (later fighters on top), per tile one palette
    idx = Image.new("L", (256, 256), 0); pidx = idx.load()
    owner = [[None] * 32 for _ in range(32)]
    cnt = [[[0] * 6 for _ in range(32)] for _ in range(32)]
    fpal = [Mo.palette_rgb(ch, F) for ch in F.ROSTER]
    px = [l.load() for l in layers]
    for y in range(H):
        for x in range(W):
            for ci in range(6):
                if px[ci][x, y] != (255, 0, 255): cnt[y // 8][x // 8][ci] += 1
    palimg = [[0] * 32 for _ in range(32)]
    for ty in range(28):
        for tx in range(32):
            c = cnt[ty][tx]
            if max(c) == 0: continue
            ci = max(range(6), key=lambda i: c[i])
            palimg[ty][tx] = 2 + ci
            for y in range(8):
                for x in range(8):
                    X, Y = tx * 8 + x, ty * 8 + y
                    v = px[ci][X, Y]
                    if v == (255, 0, 255): continue
                    k = min(range(1, 16), key=lambda i: sum((v[j] - fpal[ci][i][j]) ** 2 for j in range(3)))
                    pidx[X, Y] = k
    return idx, palimg

ML_ROWS = 26
def movelist_text(ch):
    """one fighter's move list as 26 rows of 32 characters"""
    ms = F.moves_for(ch)
    lab = {m["name"]: m["label"] for m in ms}
    nice = {"": "", "f": "->", "b": "<-", "d": "DN+", "j": "AIR "}
    rows = []
    def put(t): rows.append(t[:32].ljust(32))
    title = "%s - %s" % (ch["name"], ch.get("styleName", "").upper())
    put(title.center(32))
    put("")
    put(" MOVE              INPUT")
    for m in ms:
        prim = [i for i in m["inputs"] if ">" not in i]
        chain = [i for i in m["inputs"] if ">" in i]
        inp = ""
        if prim:
            i = prim[0]; inp = nice[i[:-1]] + i[-1]
        if chain:
            fr, bt = chain[0].split(">")
            c = "%s>%s" % (fr.upper()[:8], bt)
            inp = (inp + " " + c).strip() if len(inp) + len(c) < 13 else (inp or c)
        mark = {0: "", 1: "*", 2: "^", 3: "*"}[m["react"]]
        if m["lvl"] == 9: mark = ""
        put(" " + (m["label"][:16] + mark).ljust(18) + inp)
    fin = F.FINISHERS[ch["name"]]
    code = " ".join({"F": "->", "B": "<-", "D": "DN", "Y": "Y", "X": "X", "Bk": "B", "A": "A", "L": "L"}[t] for t in fin["seq"].split())
    while len(rows) < 21: put("")
    put(" FINISHER: " + fin["title"])
    put("   " + code + "  (ON DIZZY FOE)")
    put(" X>Y: PRESS Y DURING X  * DOWN")
    put(" ^ LAUNCH   L: BREAKER WHEN HIT")
    while len(rows) < ML_ROWS: put("")
    assert len(rows) == ML_ROWS, (ch["name"], len(rows))
    out = bytearray()
    for r in rows:
        for c in r.upper():
            o = ord(c)
            out.append(o if 32 <= o < 96 else 32)
    return bytes(out)

def main():
    os.makedirs(OUT, exist_ok=True); os.makedirs(PREV, exist_ok=True)
    # logo
    ltiles, lmap, lprev = make_logo()
    open(os.path.join(OUT, "logo2.bin"), "wb").write(ltiles)
    open(os.path.join(OUT, "logo_map.bin"), "wb").write(b"".join(bytes([w & 0xFF, w >> 8]) for w in lmap))
    # scenery
    sc, sm = make_scenery()
    sidx = quant(sc, sm, SCEN)
    stiles = []; sseen = {tile4([0] * 64): 0}; stiles.append(tile4([0] * 64))
    smap = to_tiles(sidx, [[1] * 32 for _ in range(32)], stiles, sseen)
    assert len(stiles) <= 512, len(stiles)
    open(os.path.join(OUT, "scen_tiles.bin"), "wb").write(b"".join(stiles))
    open(os.path.join(OUT, "scen_map.bin"), "wb").write(b"".join(bytes([w & 0xFF, w >> 8]) for w in smap))
    # lineup
    lidx, lpal = make_lineup()
    ftiles = [tile4([0] * 64)]; fseen = {ftiles[0]: 0}
    fmap = to_tiles(lidx, lpal, ftiles, fseen)
    assert len(ftiles) <= 768, len(ftiles)
    open(os.path.join(OUT, "line_tiles.bin"), "wb").write(b"".join(ftiles))
    open(os.path.join(OUT, "line_map.bin"), "wb").write(b"".join(bytes([w & 0xFF, w >> 8]) for w in fmap))
    # palettes
    cg = [0] * 128
    cg[0] = c5(30, 12, 50)
    for p, cols in BG3PAL.items():
        for i, c in enumerate(cols): cg[p * 4 + 1 + i] = c5(*c)
    for i, c in enumerate(SCEN): cg[16 + 1 + i] = c5(*c)
    for ci, ch in enumerate(F.ROSTER):
        fp = F.fxpal(ch["colors"])
        for i in range(1, 16): cg[(2 + ci) * 16 + i] = fp[i]
    open(os.path.join(OUT, "menu_pal.bin"), "wb").write(b"".join(bytes([c & 0xFF, c >> 8]) for c in cg))
    # sky gradient: HDMA mode 3 to CGADD (CGADD, CGADD, CGDATA, CGDATA), 2 lines per entry
    sky = bytearray(); skyc = []
    for y in range(0, 224, 2):
        t = y / 224
        if t < 0.5:
            k = t / 0.5; c = (int(24 + 120 * k), int(10 + 20 * k), int(60 + 30 * k))
        else:
            k = (t - 0.5) / 0.5; c = (int(144 + 110 * k), int(30 + 90 * k), int(90 - 50 * k))
        v = c5(*c); skyc.append(c)
        sky += bytes([2, 0, 0, v & 0xFF, v >> 8])
    sky += bytes([0])
    open(os.path.join(OUT, "menu_sky.bin"), "wb").write(sky)
    # OBJ: ember (16x16, 4bpp, palette 0 of OBJ): small glowing dot
    em = [0] * 256
    for y in range(16):
        for x in range(16):
            r = math.hypot(x - 7.5, y - 7.5)
            em[y * 16 + x] = 3 if r < 1.3 else 2 if r < 2.4 else 1 if r < 3.4 else 0
    obj = bytearray()
    for ty in range(2):
        for tx in range(2):
            obj += tile4([em[(ty * 8 + y) * 16 + tx * 8 + x] for y in range(8) for x in range(8)])
    # OBJ tiles go to name rows: tile 0,1 (row 0) and 16,17 (row 1)
    objv = bytearray(32 * 32)
    objv[0:64] = obj[0:64]; objv[16 * 32:16 * 32 + 64] = obj[64:128]
    open(os.path.join(OUT, "menu_obj.bin"), "wb").write(bytes(objv))
    # preview composite
    prev = Image.new("RGB", (256, 224))
    pp = prev.load()
    for y in range(224):
        for x in range(256): pp[x, y] = skyc[y // 2]
    scol = [(0, 0, 0)] + SCEN
    si = sidx.load(); li = lidx.load()
    for y in range(224):
        for x in range(256):
            if si[x, y]: pp[x, y] = scol[si[x, y]]
    fpal = [Mo.palette_rgb(ch, F) for ch in F.ROSTER]
    for y in range(224):
        for x in range(256):
            if li[x, y]: pp[x, y] = fpal[lpal[y // 8][x // 8] - 2][li[x, y]]
    prev.paste(lprev, (16, 8))
    d = ImageDraw.Draw(prev)
    for ci, ch in enumerate(F.ROSTER):
        d.text((lineup_centres()[ci] - 14, 84 if ci % 2 == 0 else 74), ch["name"], fill=(250, 246, 230))
    prev.resize((768, 672), Image.NEAREST).save(os.path.join(PREV, "splash.png"))
    with open(os.path.join(OUT, "menu.inc"), "w") as f:
        f.write("LOGO_T0 = %d\nLOGO_NT = %d\nSCEN_NT = %d\nLINE_NT = %d\nCLOUD_Y0 = %d\nCLOUD_Y1 = %d\n" % (
            LOGO_T0, len(ltiles) // 16, len(stiles), len(ftiles), CLOUD_Y0, CLOUD_Y1))
        f.write(".define LINE_X %s\n" % ", ".join(str(c) for c in lineup_centres()))
        f.write("LOGO_H = %d\n" % LOGO_H)
    # move list screens: 26 rows x 32 chars per fighter (ASCII 32..95)
    ml = bytearray()
    for ch in F.ROSTER:
        ml += movelist_text(ch)
    open(os.path.join(OUT, "movelist.bin"), "wb").write(ml)
    # assembly wrapper
    asm = ['; generated by tools/menu_art.py', '.segment "BANK29"',
           '.export line_tiles, scen_tiles', 'line_tiles: .incbin "line_tiles.bin"', 'scen_tiles: .incbin "scen_tiles.bin"',
           '.segment "BANK30"',
           '.export line_map, scen_map, logo2, logo_map, menu_pal, menu_sky, menu_obj, movelists',
           'line_map: .incbin "line_map.bin"', 'scen_map: .incbin "scen_map.bin"', 'logo2: .incbin "logo2.bin"',
           'logo_map: .incbin "logo_map.bin"', 'menu_pal: .incbin "menu_pal.bin"',
           '    .word %s' % ", ".join(str(c5(*c)) for c in [(0, 0, 0), (200, 60, 20), (255, 150, 40), (255, 240, 160)] + [(0, 0, 0)] * 12),
           'menu_sky: .incbin "menu_sky.bin"', 'menu_obj: .incbin "menu_obj.bin"', 'movelists: .incbin "movelist.bin"',
           '.segment "RODATA"', '.export fadeTab', 'fadeTab:']
    for lv in range(33):
        row = []
        for v in range(32):
            if lv <= 16: row.append(v * lv // 16)
            else: row.append(v + (31 - v) * (lv - 16) // 16)
        asm.append('    .byte ' + ", ".join(str(x) for x in row))
    open(os.path.join(OUT, "menu_art.s"), "w").write("\n".join(asm) + "\n")
    print("menu art: logo %d tiles, scenery %d tiles, lineup %d tiles" % (len(ltiles) // 16, len(stiles), len(ftiles)))

if __name__ == "__main__":
    main()
