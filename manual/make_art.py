#!/usr/bin/env python3
"""Generates the print art for ARENA FIGHTER FX: front cover, back insert, disc label.
Run from anywhere: python3 make_art.py  (outputs to ./art/)"""
import math, os, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
SNES = os.path.dirname(HERE)
OUT = os.path.join(HERE, "art"); os.makedirs(OUT, exist_ok=True)
ANTON = "/usr/share/fonts/truetype/google-fonts/ofl/anton/Anton-Regular.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf"
SANSB = "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"
DPI = 300
GOLD_T, GOLD_B = (255, 240, 130), (255, 150, 40)
BLUE_T, BLUE_B = (150, 215, 255), (50, 110, 235)

def font(p, s): return ImageFont.truetype(p, s)

# ---------- fighter sprites (from the renderer's own model sheet) ----------
def load_fighters():
    sheet = Image.open(os.path.join(SNES, "preview/models.png")).convert("RGB")
    bg = sheet.getpixel((5, 5))
    out = []
    for r in range(6):
        row = []
        for c in range(2):   # col 0 faces right, col 1 faces left
            box = (c * 330, r * 360, c * 330 + 330, r * 360 + 360)
            tile = sheet.crop(box)
            a = Image.new("L", tile.size, 0)
            px, ap = tile.load(), a.load()
            for y in range(tile.height):
                for x in range(tile.width):
                    p = px[x, y]
                    if max(abs(p[i] - bg[i]) for i in range(3)) > 6: ap[x, y] = 255
            tile.putalpha(a)
            tile = tile.crop(tile.getbbox())
            # the sheet is 3x pixel art: sample back to native, then integer upscale
            nat = tile.resize((max(1, tile.width // 3), max(1, tile.height // 3)), Image.NEAREST)
            row.append(nat)
        out.append(row)
    return out

def up(im, k): return im.resize((im.width * k, im.height * k), Image.NEAREST)

# ---------- scenery ----------
def lerp(a, b, t): return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

def scenery(w, h, horizon, seed=7):
    rnd = random.Random(seed)
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    stops = [(0, (14, 6, 46)), (0.35, (70, 16, 100)), (0.65, (176, 44, 110)), (0.85, (255, 112, 70)), (1, (255, 190, 90))]
    for y in range(horizon):
        t = y / horizon
        for i in range(len(stops) - 1):
            if stops[i][0] <= t <= stops[i + 1][0]:
                tt = (t - stops[i][0]) / (stops[i + 1][0] - stops[i][0])
                d.line([(0, y), (w, y)], fill=lerp(stops[i][1], stops[i + 1][1], tt)); break
    # stars
    for _ in range(int(w * horizon / 9000)):
        x, y = rnd.randrange(w), rnd.randrange(int(horizon * .5))
        d.point((x, y), fill=(255, 230, 255))
    # sun with slits
    cx, r = w // 2, int(w * .24)
    cy = horizon - int(r * .25)
    sun = Image.new("RGB", (w, h)); sd = ImageDraw.Draw(sun)
    for y in range(cy - r, cy + r):
        t = (y - (cy - r)) / (2 * r)
        sd.line([(0, y), (w, y)], fill=lerp((255, 245, 150), (255, 90, 120), t))
    m = Image.new("L", (w, h), 0); md = ImageDraw.Draw(m)
    md.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    k = 0
    for y in range(cy + int(r * .1), cy + r, 1):
        k = (y - cy) / r
        if int(y / (4 + k * 6)) % 2 == 0 and k > 0.1: md.line([(0, y), (w, y)], fill=0)
    im.paste(sun, (0, 0), m)
    # clouds (soft stripes)
    cl = Image.new("RGBA", (w, h), (0, 0, 0, 0)); cd = ImageDraw.Draw(cl)
    for _ in range(14):
        y = rnd.randrange(int(horizon * .25), int(horizon * .8)); x = rnd.randrange(-100, w)
        cd.rounded_rectangle([x, y, x + rnd.randrange(200, 520), y + rnd.randrange(8, 22)], 10, fill=(255, 140, 110, 150))
    im.paste(cl.filter(ImageFilter.GaussianBlur(3)), (0, 0), cl.filter(ImageFilter.GaussianBlur(3)))
    # mountains
    for layer, (col, amp, base) in enumerate([((70, 24, 96), .13, .0), ((38, 12, 62), .09, .04)]):
        pts = [(0, horizon)]; ph = rnd.random() * 9
        for x in range(0, w + 20, 20):
            pts.append((x, horizon - amp * horizon * (0.5 + 0.5 * math.sin(x / (w / 5) + ph + layer * 2) * math.cos(x / (w / 11) + ph)) - base * horizon))
        pts.append((w, horizon)); d.polygon(pts, fill=col)
    # floor
    for y in range(horizon, h):
        t = (y - horizon) / (h - horizon)
        d.line([(0, y), (w, y)], fill=lerp((60, 24, 84), (20, 10, 38), t))
    gc = (150, 70, 170)
    for i in range(-14, 15):
        d.line([(cx, horizon), (cx + i * w * .16, h)], fill=lerp(gc, (40, 16, 60), .3), width=2)
    y, step = horizon, 6
    while y < h:
        d.line([(0, int(y)), (w, int(y))], fill=gc, width=2); step *= 1.32; y += step
    d.line([(0, horizon), (w, horizon)], fill=(255, 200, 120), width=3)
    return im, horizon

def torch(im, x, base_y, s):
    d = ImageDraw.Draw(im)
    d.rectangle([x - 26 * s, base_y - 150 * s, x + 26 * s, base_y], fill=(52, 30, 70), outline=(20, 8, 30), width=3)
    d.rectangle([x - 34 * s, base_y - 170 * s, x + 34 * s, base_y - 148 * s], fill=(78, 46, 98), outline=(20, 8, 30), width=3)
    fl = Image.new("RGBA", im.size, (0, 0, 0, 0)); fd = ImageDraw.Draw(fl)
    fy = base_y - 170 * s
    fd.polygon([(x - 26 * s, fy), (x, fy - 120 * s), (x + 26 * s, fy)], fill=(255, 120, 30, 255))
    fd.polygon([(x - 14 * s, fy), (x, fy - 70 * s), (x + 14 * s, fy)], fill=(255, 235, 120, 255))
    glow = fl.filter(ImageFilter.GaussianBlur(18 * s))
    im.paste(glow, (0, 0), glow); im.paste(fl, (0, 0), fl)

def embers(im, n, seed=3):
    rnd = random.Random(seed); d = ImageDraw.Draw(im)
    for _ in range(n):
        x, y, r = rnd.randrange(im.width), rnd.randrange(im.height), rnd.choice([2, 3, 4])
        d.rectangle([x, y, x + r, y + r], fill=rnd.choice([(255, 170, 60), (255, 210, 110), (255, 120, 50)]))

# ---------- text helpers ----------
def grad_text(im, xy, text, fnt, top, bot, stroke=8, shadow=10, anchor="la", shear=0.0, outline=(22, 8, 40)):
    d = ImageDraw.Draw(im)
    bb = d.textbbox((0, 0), text, font=fnt, stroke_width=stroke)
    pad = 40
    w, h = bb[2] - bb[0] + pad * 2, bb[3] - bb[1] + pad * 2
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((pad - bb[0], pad - bb[1]), text, font=fnt, fill=255)
    full = Image.new("L", (w, h), 0)
    ImageDraw.Draw(full).text((pad - bb[0], pad - bb[1]), text, font=fnt, fill=255, stroke_width=stroke)
    g = Image.new("RGB", (w, h)); gd = ImageDraw.Draw(g)
    for y in range(h): gd.line([(0, y), (w, y)], fill=lerp(top, bot, min(1, max(0, (y - pad) / max(1, bb[3] - bb[1])))))
    if shear:
        sh = lambda i, rs: i.transform((w + int(abs(shear) * h), h), Image.AFFINE, (1, shear, -shear * h if shear > 0 else 0, 0, 1, 0), Image.BICUBIC)
        mask, full, g = sh(mask, 0), sh(full, 0), sh(g, 0); w += int(abs(shear) * h)
    x, y = xy
    if anchor[0] == "m": x -= w // 2
    if anchor[0] == "r": x -= w
    if anchor[1] == "m": y -= h // 2
    # drop shadow, outline, fill
    shd = Image.new("L", (w, h), 0); shd.paste(full, (0, shadow)); 
    black = Image.new("RGB", (w, h), (0, 0, 0)); im.paste(black, (int(x), int(y)), shd.point(lambda v: v * 190 // 255))
    im.paste(Image.new("RGB", (w, h), outline), (int(x), int(y)), full)
    im.paste(g, (int(x), int(y)), mask)
    return w, h

def text_c(im, cx, y, s, fnt, fill, shadow=True):
    d = ImageDraw.Draw(im)
    w = d.textlength(s, font=fnt)
    if shadow: d.text((cx - w / 2 + 2, y + 2), s, font=fnt, fill=(0, 0, 0))
    d.text((cx - w / 2, y), s, font=fnt, fill=fill)

def logo(im, cx, y, size, fx=True):
    f = font(ANTON, size)
    d = ImageDraw.Draw(im)
    tw = d.textlength("ARENA FIGHTER", font=f)
    w, h = grad_text(im, (cx, y), "ARENA FIGHTER", f, GOLD_T, GOLD_B, stroke=max(4, size // 22), shadow=size // 14, anchor="ma")
    if fx:
        ff = font(ANTON, int(size * 1.75))
        grad_text(im, (cx + int(tw * .30), y + int(size * .92)), "FX", ff, BLUE_T, BLUE_B, stroke=max(5, size // 16), shadow=size // 12, anchor="ma", shear=-0.2)
    return w, h

def vignette(im, strength=.55):
    w, h = im.size
    m = Image.new("L", (w, h), 0); d = ImageDraw.Draw(m)
    d.ellipse([-w * .25, -h * .25, w * 1.25, h * 1.25], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(w / 6))
    dark = Image.new("RGB", (w, h), (8, 2, 20))
    inv = m.point(lambda v: int((255 - v) * strength))
    im.paste(dark, (0, 0), inv)

FIGH = None
def fighters_line(im, base_y, centre_x, k=4, names=False):
    """six fighters, three face right on the left, three face left on the right"""
    global FIGH
    if FIGH is None: FIGH = load_fighters()
    order = [(0, 0), (1, 0), (2, 0), (3, 1), (4, 1), (5, 1)]  # (fighter, facing col)
    spr = [up(FIGH[f][c], k) for f, c in order]
    total = sum(s.width for s in spr)
    span = im.width * .96
    gap = (span - total) / 5
    x = (im.width - span) / 2
    pos = []
    d = ImageDraw.Draw(im)
    for s in spr:
        # shadow
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
        sd.ellipse([x + s.width * .05, base_y - 14, x + s.width * .95, base_y + 22], fill=(0, 0, 0, 150))
        sh = sh.filter(ImageFilter.GaussianBlur(6)); im.paste(sh, (0, 0), sh)
        im.paste(s, (int(x), int(base_y - s.height)), s)
        pos.append((int(x), s.width)); x += s.width + gap
    return pos

# ---------- front cover (4.75 in square, plus bleed handled by the full-bleed art) ----------
def cover():
    W = int(4.75 * DPI)
    im, hz = scenery(W, W, int(W * .66))
    torch(im, int(W * .07), int(W * .70), 1.7); torch(im, int(W * .93), int(W * .70), 1.7)
    embers(im, 60)
    fighters_line(im, int(W * .90), W // 2, k=4)
    vignette(im, .5)
    logo(im, W // 2, int(W * .045), int(W * .125))
    d = ImageDraw.Draw(im)
    text_c(im, W // 2, int(W * .445), "FOR THE SUPER FX CHIP", font(SANSB, int(W * .026)), (255, 235, 200))
    # footer strip
    d.rectangle([0, W - 62, W, W], fill=(14, 6, 34)); d.line([(0, W - 62), (W, W - 62)], fill=(255, 190, 80), width=4)
    text_c(im, W // 2, W - 50, "1-2 PLAYERS   -   6 FIGHTERS   -   SNES / SUPER FAMICOM HOMEBREW   -   NOT FOR SALE", font(SANSB, 22), (255, 214, 140), shadow=False)
    im.save(os.path.join(OUT, "cover_front.png"), dpi=(DPI, DPI))
    return im

# ---------- back insert / tray card: 150 x 118 mm incl. two 6.5 mm spines ----------
def mm(v): return int(round(v / 25.4 * DPI))
def back():
    W, H = mm(150), mm(118); SP = mm(6.5)
    im, hz = scenery(W, H, int(H * .60), seed=11)
    vignette(im, .65)
    d = ImageDraw.Draw(im)
    # content panel
    px0, px1 = SP + 28, W - SP - 28
    logo(im, (px0 + px1) // 2, 26, 104)
    text_c(im, (px0 + px1) // 2, 338, "A 3D ARENA FIGHTER FOR THE SUPER FX CHIP", font(SANSB, 30), (255, 232, 190))
    panel = Image.new("RGBA", im.size, (0, 0, 0, 0)); ImageDraw.Draw(panel).rounded_rectangle([px0 - 22, 392, px1 - 360, 846], 18, fill=(12, 4, 30, 205))
    im.paste(panel, (0, 0), panel)
    # screenshots
    sheet = Image.open(os.path.join(SNES, "preview", "screens.png")).convert("RGB")
    crops = [sheet.crop((0, 0, 512, 448)), sheet.crop((520, 0, 1032, 448)), sheet.crop((1040, 0, 1552, 448))]
    sw = 322; sh_ = int(sw * 448 / 512)
    sx = px1 - sw
    for i, c in enumerate([crops[1], crops[0]]):
        c = c.resize((sw, sh_), Image.NEAREST)
        y = 392 + i * (sh_ + 18)
        d.rectangle([sx - 5, y - 5, sx + sw + 4, y + sh_ + 4], fill=(255, 200, 90))
        im.paste(c, (sx, y))
    # features
    f = font(SANS, 26); fb = font(SANSB, 26)
    feats = ["Mode 7 rotating arena, drawn live by the Super FX chip",
             "6 fighters, each with their own style and move set",
             "Killer Instinct style combos, up to ULTRA (21+ hits)",
             "Dizzy-and-FINISH-THEM cinematic finishing moves",
             "Tournament, Practice and 2 Player modes",
             "Tournament records saved to battery RAM"]
    y = 412; x = px0
    for t in feats:
        d.rectangle([x, y + 11, x + 11, y + 22], fill=(255, 190, 80))
        words = t.split(); line = ""; 
        maxw = sx - 30 - (x + 26)
        lines = []
        for wd in words:
            if d.textlength(line + " " + wd, font=f) > maxw: lines.append(line.strip()); line = wd
            else: line += " " + wd
        lines.append(line.strip())
        for ln in lines:
            d.text((x + 26 + 2, y + 2), ln, font=f, fill=(0, 0, 0)); d.text((x + 26, y), ln, font=f, fill=(255, 244, 225)); y += 33
        y += 10
    # roster
    d.rectangle([px0, y + 6, sx - 22, y + 8], fill=(255, 190, 80))
    y += 22
    names = [("KAZE", "Karate"), ("LIN", "Kung Fu"), ("BRUTUS", "Pro Wrestling"), ("VALKA", "Viking Brawler"), ("ROCCO", "Boxing / MMA"), ("NOVA", "Capoeira")]
    rf = font(ANTON, 30); rs = font(SANS, 20)
    for i, (n, s) in enumerate(names):
        cx0 = px0 + (i % 3) * ((sx - 22 - px0) // 3); cy0 = y + (i // 3) * 64
        d.text((cx0 + 2, cy0 + 2), n, font=rf, fill=(0, 0, 0)); d.text((cx0, cy0), n, font=rf, fill=(255, 214, 110))
        d.text((cx0, cy0 + 36), s, font=rs, fill=(235, 225, 245))
    # quick controls strip
    d.rounded_rectangle([px0 - 22, 1000, px1 + 22, H - 175], 18, fill=(12, 4, 30))
    d.text((px0, 1010), "QUICK CONTROLS", font=font(ANTON, 34), fill=(255, 214, 110))
    ctl = [("D-PAD", "walk / guard away"), ("UP", "jump"), ("DOWN", "crouch"), ("R", "guard (+Up/Down sidestep)"),
           ("Y  X", "punch  /  power punch"), ("B  A", "kick  /  power kick"), ("L", "throw (also COMBO BREAKER)"), ("START", "pause: move list / forfeit")]
    cf, cs = font(SANSB, 24), font(SANS, 24)
    colw = (px1 + 22 - px0 + 22) // 2
    for i, (k, v) in enumerate(ctl):
        cx0 = px0 + (i // 4) * colw; cy0 = 1064 + (i % 4) * 34
        d.text((cx0, cy0), k, font=cf, fill=(255, 190, 80)); d.text((cx0 + 120, cy0), v, font=cs, fill=(240, 232, 250))
    # fine print
    d.rectangle([SP, H - 150, W - SP, H], fill=(14, 6, 34)); d.line([(SP, H - 150), (W - SP, H - 150)], fill=(255, 190, 80), width=4)
    fp = font(SANS, 19); fy = H - 138
    lines = ["Requires a Super FX (GSU-2) capable SNES / Super Famicom cartridge setup or emulator (snes9x, bsnes, Mesen-S, ares). 1 MB LoROM / FastROM, 64 KB battery RAM.",
             "(c) 2026 Xenocide21. Free and open source under the MIT License: you may use, copy, modify and share it. See LICENSE.",
             "Designed by Xenocide21. Programmed and illustrated with Claude, an AI model made by Anthropic. Logo font: Anton (SIL OFL 1.1).",
             "A fan-made homebrew. Not affiliated with, endorsed or sponsored by Nintendo. Super Nintendo, SNES and Super Famicom are trademarks of their owners."]
    for ln in lines:
        words = ln.split(); line = ""
        for wd in words:
            if d.textlength(line + " " + wd, font=fp) > W - 2 * SP - 60: d.text((SP + 30, fy), line.strip(), font=fp, fill=(225, 215, 240)); fy += 24; line = wd
            else: line += " " + wd
        d.text((SP + 30, fy), line.strip(), font=fp, fill=(225, 215, 240)); fy += 28
    # spines
    for x0 in (0, W - SP):
        d.rectangle([x0, 0, x0 + SP, H], fill=(14, 6, 34))
        d.line([(x0 + (SP if x0 == 0 else 0), 0), (x0 + (SP if x0 == 0 else 0), H)], fill=(255, 190, 80), width=3)
        t = Image.new("RGBA", (H, SP), (0, 0, 0, 0)); td = ImageDraw.Draw(t)
        sf = font(ANTON, SP - 24)
        tw = td.textlength("ARENA FIGHTER FX", font=sf)
        td.text((40, 10), "ARENA FIGHTER", font=sf, fill=GOLD_T); 
        td.text((40 + td.textlength("ARENA FIGHTER ", font=sf), 10), "FX", font=sf, fill=BLUE_T)
        td.text((H - 40 - td.textlength("SUPER FX  -  SNES HOMEBREW", font=font(SANSB, SP - 34)), 14), "SUPER FX  -  SNES HOMEBREW", font=font(SANSB, SP - 34), fill=(255, 214, 140))
        t = t.rotate(-90, expand=True)
        im.paste(t, (x0, 0), t)
    im.save(os.path.join(OUT, "cover_back.png"), dpi=(DPI, DPI))

# ---------- disc label: 120 mm disc, 15 mm hole ----------
def label():
    D = mm(120); hole = mm(15); hub = mm(41)
    im, hz = scenery(D, D, int(D * .56), seed=5)
    torch(im, int(D * .13), int(D * .60), 1.3); torch(im, int(D * .87), int(D * .60), 1.3)
    embers(im, 40, seed=9)
    fighters_line(im, int(D * .78), D // 2, k=3) if False else None
    global FIGH
    if FIGH is None: FIGH = load_fighters()
    sk = 3
    left, right = up(FIGH[0][0], sk), up(FIGH[3][1], sk)
    for s, x in ((left, int(D * .17)), (right, int(D * .83) - right.width)):
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).ellipse([x + 10, int(D * .83) - 12, x + s.width - 10, int(D * .83) + 16], fill=(0, 0, 0, 160))
        sh = sh.filter(ImageFilter.GaussianBlur(6)); im.paste(sh, (0, 0), sh)
        im.paste(s, (x, int(D * .83) - s.height), s)
    vignette(im, .6)
    d = ImageDraw.Draw(im)
    logo(im, D // 2, int(D * .075), int(D * .085))
    # hub ring
    d.ellipse([D // 2 - hub // 2, D // 2 - hub // 2, D // 2 + hub // 2, D // 2 + hub // 2], outline=(255, 190, 80), width=5)
    text_c(im, D // 2, int(D * .72), "FOR THE SUPER FX CHIP", font(SANSB, int(D * .026)), (255, 232, 190))
    text_c(im, D // 2, int(D * .79), "KAZE  -  LIN  -  BRUTUS  -  VALKA  -  ROCCO  -  NOVA", font(SANSB, int(D * .024)), (255, 214, 140))
    text_c(im, D // 2, int(D * .87), "1-2 PLAYERS  -  TOURNAMENT  -  PRACTICE  -  VERSUS", font(SANS, int(D * .021)), (235, 225, 245))
    text_c(im, D // 2, int(D * .915), "(c) 2026 Xenocide21  -  MIT License  -  Made with Claude (AI)", font(SANS, int(D * .0185)), (210, 200, 230))
    # circular mask with hole
    mask = Image.new("L", (D, D), 0); md = ImageDraw.Draw(mask)
    md.ellipse([0, 0, D - 1, D - 1], fill=255); md.ellipse([D // 2 - hole // 2, D // 2 - hole // 2, D // 2 + hole // 2, D // 2 + hole // 2], fill=0)
    # keep a flat copy with a bleed too (for printers that want a square): full-bleed square
    im.save(os.path.join(OUT, "disc_label_square.png"), dpi=(DPI, DPI))
    out = im.convert("RGBA"); out.putalpha(mask)
    ring = ImageDraw.Draw(out)
    out.save(os.path.join(OUT, "disc_label.png"), dpi=(DPI, DPI))

if __name__ == "__main__":
    cover(); back(); label(); print("ok")
