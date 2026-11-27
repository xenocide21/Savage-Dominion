"""Stage art: THE PIT, an underground fight club.  Drawn procedurally, original art.

draw(w, h, floor_top, feet_y) -> far image, far palette, near image, near palette,
floor palette.  Images are palette-index images; index 0 is transparent.  The far
layer repeats every 256 px and the near layer every 128 px, which keeps the tile
count small and lets the scroll wrap at any speed.
"""
import math, random
from PIL import Image, ImageDraw

FAR_PAL = [(0, 0, 0),
    (14, 10, 14), (24, 16, 18), (46, 28, 26), (62, 38, 32), (80, 50, 38),     # 1-5 shadow, mortar, brick x3
    (14, 12, 22), (30, 22, 34),                                               # 6-7 crowd dark / lit
    (150, 96, 56), (110, 26, 30), (190, 170, 140),                            # 8 rim light, 9 banner red, 10 banner mark
    (100, 66, 46), (36, 26, 40), (0, 0, 0), (0, 0, 0), (0, 0, 0)]

NEAR_PAL = [(0, 0, 0),
    (12, 10, 14), (52, 48, 56), (96, 90, 98), (156, 146, 146),                # 1-4 ink, iron dark/mid/light
    (110, 60, 30), (160, 92, 40),                                             # 5-6 rust
    (255, 236, 170), (240, 180, 80), (120, 80, 44),                           # 7-9 lamp light
    (120, 24, 28), (176, 40, 40),                                             # 10-11 rope red
    (60, 40, 30), (0, 0, 0), (0, 0, 0), (0, 0, 0)]

FLOOR_PAL = [(0, 0, 0),
    (24, 20, 24), (46, 40, 42), (60, 52, 50), (74, 64, 58), (90, 78, 68),     # 1 seam, 2-5 concrete far -> near
    (108, 94, 80), (126, 112, 94),                                            # 6-7 light grit
    (80, 12, 16), (116, 20, 22),                                              # 8-9 old blood
    (170, 156, 128), (130, 110, 86),                                          # 10-11 worn paint
    (36, 30, 32), (0, 0, 0), (0, 0, 0), (0, 0, 0)]

def draw(w, h, floor_top, feet_y):
    rr = random.Random(7)
    # ---------------- far: brick wall, banners, a crowd in the half dark
    far = Image.new("P", (256, h), 0)
    d = ImageDraw.Draw(far)
    d.rectangle([0, 0, 255, h - 1], fill=2)
    tone = {}
    for y in range(0, floor_top + 8, 8):
        off = 8 if (y // 8) % 2 else 0
        for bx in range(-1, 17):
            x = bx * 16 + off
            key = ((x % 64) // 16, (y // 8) % 4)
            if key not in tone:
                tone[key] = rr.choice((0, 0, 1, 1, 2))
            dark = 1 if y < 40 else 0          # the ceiling falls into shadow
            c = max(2, 3 + tone[key] - dark * 2)
            for dx in (0, 256, -256):
                d.rectangle([x + dx + 1, y + 1, x + dx + 15, y + 7], fill=c)
    d.rectangle([0, 0, 255, 15], fill=1)
    for x0 in (40,):                            # hanging banner with a claw mark
        d.polygon([(x0, 40), (x0 + 40, 40), (x0 + 40, 96), (x0 + 20, 88), (x0, 96)], fill=9)
        for k in range(3):
            d.line([(x0 + 10 + k * 9, 50), (x0 + 4 + k * 9, 76)], fill=10, width=3)
    # crowd: two rows of heads and shoulders, back row darker, repeating every 64 px
    for row, (base, col, rim) in enumerate(((floor_top - 22, 12, 11), (floor_top - 8, 6, 8))):
        heads = [(4 + i * 16 + rr.randrange(-3, 4) + row * 7, rr.randrange(-4, 3), rr.randrange(5, 7)) for i in range(4)]
        d.rectangle([0, base + 6, 255, floor_top + 8], fill=col)
        for k in range(-1, 5):
            for i, (hx, hy, r) in enumerate(heads):
                x, y = k * 64 + hx, base + hy
                d.ellipse([x - r - 4, y + r - 1, x + r + 4, y + r + 14], fill=col)
                d.ellipse([x - r, y - r, x + r, y + r], fill=col)
                d.arc([x - r, y - r, x + r, y + r], 200, 320, fill=rim)
                if row == 1 and i == 1:          # a raised fist
                    d.line([(x + 7, y + 8), (x + 11, y - 9)], fill=col, width=4)
                    d.ellipse([x + 8, y - 14, x + 14, y - 8], fill=col)
    far_full = Image.new("P", (w, h), 0)
    far_full.paste(far, (0, 0)); far_full.paste(far, (256, 0))

    # ---------------- near: lamps, barrier, floor (128 px repeat)
    near = Image.new("P", (128, h), 0)
    d = ImageDraw.Draw(near)
    # hanging lamp on a chain
    for y in range(0, 50, 6):
        d.ellipse([62, y, 66, y + 7], outline=3)
    d.polygon([(54, 50), (74, 50), (84, 62), (44, 62)], fill=2, outline=1)
    d.line([(55, 52), (73, 52)], fill=4)
    d.rectangle([48, 63, 80, 64], fill=8)
    d.rectangle([56, 63, 72, 66], fill=7)
    # barrier: iron posts, two sagging ropes, a low kick board
    for y0, sag in ((floor_top - 30, 4), (floor_top - 17, 3)):
        pts = [(x, y0 + round(sag * math.sin(math.pi * ((x - 8) % 128) / 128))) for x in range(128)]
        for x, y in pts:
            near.putpixel((x, y - 1), 11); near.putpixel((x, y), 10); near.putpixel((x, y + 1), 1)
    d.rectangle([4, floor_top - 40, 13, floor_top - 1], fill=2, outline=1)
    d.line([(6, floor_top - 38), (6, floor_top - 2)], fill=4)
    d.rectangle([2, floor_top - 43, 15, floor_top - 39], fill=3, outline=1)
    for y in (floor_top - 30, floor_top - 17):
        d.rectangle([3, y - 3, 14, y + 3], fill=5, outline=1)
    d.rectangle([0, floor_top - 6, 127, floor_top - 1], fill=12)
    d.line([(0, floor_top - 6), (127, floor_top - 6)], fill=5)
    d.line([(0, floor_top - 1), (127, floor_top - 1)], fill=1)
    # floor: concrete slabs whose rows deepen toward the camera
    edges, y, step = [floor_top], floor_top, 4.0
    while y < h:
        y += int(step); step *= 1.55; edges.append(min(y, h))
    for i, (y0, y1) in enumerate(zip(edges, edges[1:])):
        c = min(5, 2 + i)
        d.rectangle([0, y0, 127, y1 - 1], fill=c)
        d.line([(0, y0), (127, y0)], fill=1)
        for x in ((20 + i * 37) % 128, (84 + i * 37) % 128):       # staggered joints
            d.line([(x, y0), (x, y1 - 1)], fill=1)
        for _ in range(26 + i * 8):                                # grit
            x, gy = rr.randrange(128), rr.randrange(y0 + 1, max(y0 + 2, y1))
            if gy < h: near.putpixel((x, gy), min(7, c + rr.choice((-1, 1, 1))))
    # a worn painted ring line just behind the feet, scuffed in places
    py = feet_y - 12
    for x in range(128):
        if (x * 7) % 31 > 3:
            near.putpixel((x, py), 10); near.putpixel((x, py + 1), 11)
    # old blood
    for cx, cy, rx, ry in ((38, feet_y + 12, 13, 4), (104, feet_y - 2, 7, 2)):
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=8)
        d.ellipse([cx - rx // 2, cy - ry // 2, cx + rx // 3, cy + ry // 2], fill=9)
        for _ in range(9):
            near.putpixel((max(0, min(127, cx + rr.randrange(-rx - 7, rx + 8))), min(h - 1, cy + rr.randrange(-ry - 2, ry + 3))), 8)
    near_full = Image.new("P", (w, h), 0)
    for x in range(0, w, 128):
        near_full.paste(near, (x, 0))
    _preview(far_full, near_full, floor_top)
    return far_full, FAR_PAL, near_full, NEAR_PAL, FLOOR_PAL

def _preview(far, near, floor_top):
    import os
    out = Image.new("RGB", (256, 224))
    for y in range(224):
        for x in range(256):
            n = near.getpixel((x + 128, y))
            if n: c = (FLOOR_PAL if y >= floor_top else NEAR_PAL)[n]
            else: c = FAR_PAL[far.getpixel((x + 128, y))]
            out.putpixel((x, y), c)
    out.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "preview", "stage_pit.png"))
