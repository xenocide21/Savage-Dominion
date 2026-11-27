#!/usr/bin/env python3
"""Sculpted polygon models for the arena fighters.

Each fighter is a set of PARTS.  A part rides on one bone (joint A -> joint B) and
holds a list of convex polygons drawn in order, each with one palette colour:
outline first, then base, shadow, highlight and details - the way a sprite artist
builds a figure out of shapes.

Polygon points are stored in BONE SPACE as (s, o):
    screen point = A + s * (B - A) + o * scale * perp(B - A) / |B - A|
s is a fraction of the (projected) bone, o is a sideways offset in design units,
perpendicular to the bone (perp = (-dy, dx) in screen space).  Facing the other
way just negates o.  The Super FX evaluates exactly this per point.

Authoring is done in the fighter's side view (x forward, y up, design units) on the
stance pose; to_bone() converts to (s, o).

Palette (one 16-colour OBJ palette per fighter):
    0 transparent | 1-3 skin d/m/l | 4-6 hair d/m/l | 7-9 outfit A | 10-12 outfit B
    13 white (eyes, glints) | 14 trail | 15 outline
"""
import math

SKIN_D, SKIN, SKIN_L = 1, 2, 3
HAIR_D, HAIR, HAIR_L = 4, 5, 6
A_D, A_M, A_L = 7, 8, 9
B_D, B_M, B_L = 10, 11, 12
WHITE, TRAIL, INK = 13, 14, 15
MAT = {"skin": (1, 2, 3), "hair": (4, 5, 6), "a": (7, 8, 9), "b": (10, 11, 12)}

# ------------------------------------------------------------------ geometry
def hull(pts):
    """convex hull (keeps the Super FX filler happy), counter-clockwise"""
    pts = sorted(set((round(x, 3), round(y, 3)) for x, y in pts))
    if len(pts) <= 2: return pts
    def cross(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0: hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]

def grow(pts, d):
    """offset a convex polygon outward by d (for outlines)"""
    h = hull(pts)
    n = len(h)
    if n < 3:
        cx = sum(p[0] for p in h) / n; cy = sum(p[1] for p in h) / n
        return [(cx + d, cy), (cx, cy + d), (cx - d, cy), (cx, cy - d)] if n == 1 else \
               hull([(x + dx, y + dy) for x, y in h for dx, dy in ((d, 0), (-d, 0), (0, d), (0, -d))])
    cx = sum(p[0] for p in h) / n; cy = sum(p[1] for p in h) / n
    out = []
    for i in range(n):
        p0, p1, p2 = h[i - 1], h[i], h[(i + 1) % n]
        # average of the two edge normals
        def nrm(a, b):
            ex, ey = b[0] - a[0], b[1] - a[1]; l = math.hypot(ex, ey) or 1
            return (ey / l, -ex / l)
        n1, n2 = nrm(p0, p1), nrm(p1, p2)
        nx, ny = n1[0] + n2[0], n1[1] + n2[1]
        l = math.hypot(nx, ny) or 1
        # make sure it points away from the centre
        if (p1[0] - cx) * nx + (p1[1] - cy) * ny < 0: nx, ny = -nx, -ny
        k = d / max(0.5, (nx / l) * n1[0] + (ny / l) * n1[1] if False else 1)
        out.append((p1[0] + nx / l * d * 1.15, p1[1] + ny / l * d * 1.15))
    return out

class Bone:
    """stance geometry of one bone in side view"""
    def __init__(self, A, B):
        self.A = A; self.B = B
        self.dx = B[0] - A[0]; self.dy = B[1] - A[1]
        self.L = math.hypot(self.dx, self.dy) or 1e-3
        ux, uy = self.dx / self.L, self.dy / self.L
        # side-view normal pointing to the fighter's front (+x), or up for flat bones
        nx, ny = -uy, ux
        if nx < -1e-3 or (abs(nx) <= 1e-3 and ny < 0): nx, ny = -nx, -ny
        self.front = (nx, ny)

    def along(self, t, across):
        """bone coordinates (t along A->B, across toward the front) -> side view"""
        return (self.A[0] + t * self.dx + across * self.front[0],
                self.A[1] + t * self.dy + across * self.front[1])

    def to_bone(self, p):
        """side-view point -> (s, o) as the Super FX uses them (screen y points down)"""
        px, py = p[0] - self.A[0], p[1] - self.A[1]
        s = (px * self.dx + py * self.dy) / (self.L * self.L)
        o = (px * self.dy - py * self.dx) / self.L
        return s, o

# ------------------------------------------------------------------ a part under construction
class Part:
    def __init__(self, name, a, b, bone, side=None, depth=0):
        self.name, self.a, self.b, self.bone = name, a, b, bone
        self.side = side            # None, 'n' or 'f' (limb sides get near/far shading)
        self.depth = depth          # draw-order bias (+ = drawn later / in front)
        self.polys = []             # (colour, [side-view points])
        self.nearonly = set()       # polygon indices left out of the far-side variant

    def poly(self, col, pts, outline=False, near_only=False):
        h = hull(pts)
        if len(h) < 3: return self          # degenerate slice: nothing to draw
        if near_only: self.nearonly.add(len(self.polys))
        if outline:
            self.polys.append((col | 0x80, grow(h, 1.0)))   # border pixels drawn in ink
        else:
            self.polys.append((col, h))
        return self

    def limb(self, col, stations, t0=None, t1=None, frac=(0.0, 1.0)):
        """polygon from a width profile: stations [(t, front, back)], frac = slice of
        the width from back (0) to front (1) to keep (for shading bands)"""
        pts = []
        for t, f, b in stations:
            if t0 is not None and t < t0: continue
            if t1 is not None and t > t1: continue
            lo = -b + (f + b) * frac[0]
            hi = -b + (f + b) * frac[1]
            pts.append(self.bone.along(t, hi))
            pts.append(self.bone.along(t, lo))
        return pts

# ------------------------------------------------------------------ shading helpers
def shaded_limb(p, mat, st, outline=True, light=True):
    d, m, l = MAT[mat]
    full = p.limb(m, st)
    p.poly(m, full, outline=outline)
    p.poly(d, p.limb(d, st, frac=(0.0, 0.32)))              # back of the limb in shadow
    if light:
        p.poly(l, p.limb(l, st, frac=(0.62, 0.86), t0=st[0][0] + 0.08, t1=st[-1][0] - 0.12))

def shift_far(col):
    """far-side limbs: one shade darker"""
    if col & 0x80: return shift_far(col & 0x7F) | 0x80
    for d, m, l in MAT.values():
        if col == l: return m
        if col == m: return d
    return col

# ------------------------------------------------------------------ the builder
def build(ch, J, style):
    """ch: fighter dict, J: stance joints (x fwd, y up, z), returns [Part]"""
    B = ch["body"]
    male = ch.get("male", True)
    heavy = B.get("chestr", 10) >= 13
    sv = lambda j: (J[j][0], J[j][1])
    parts = []
    M = style["mats"]              # part -> material name

    # ---------------- torso (pelvis -> chest), side view around the pelvis
    tb = Bone(sv(0), sv(1))
    tor = Part("torso", 0, 1, tb, depth=0)
    P0 = sv(0); C = sv(1); N = sv(2)
    def T(x, y):    # torso-local: x forward from the spine line, y up from the pelvis
        k = (y) / max(1e-3, C[1] - P0[1])
        sx = P0[0] + (C[0] - P0[0]) * k
        return (sx + x, P0[1] + y)
    cw = B.get("chestr", 10.5); ww = B.get("waist", 8.5); hw = B.get("hipr", 9)
    H = C[1] - P0[1]
    if male:
        back = [T(-hw * 0.70, -4), T(-hw * 0.78, 2), T(-ww * 0.66, H * 0.40), T(-cw * 0.62, H * 0.75), T(-cw * 0.58, H * 1.02), T(-3.0, H * 1.18)]
        front = [T(hw * 0.55, -5), T(ww * 0.62, H * 0.25), T(ww * 0.66 + (2.5 if heavy else 0), H * 0.50), T(cw * 0.78, H * 0.72), T(cw * 0.80, H * 0.88), T(cw * 0.55, H * 1.08), T(2.0, H * 1.2)]
    else:
        back = [T(-hw * 0.80, -4), T(-hw * 0.86, 2), T(-ww * 0.60, H * 0.45), T(-cw * 0.58, H * 0.78), T(-cw * 0.52, H * 1.02), T(-2.6, H * 1.18)]
        front = [T(hw * 0.55, -5), T(ww * 0.55, H * 0.30), T(ww * 0.55, H * 0.55), T(cw * 0.86, H * 0.72), T(cw * 0.86, H * 0.84), T(cw * 0.55, H * 1.02), T(1.8, H * 1.18)]
    body = back + front
    tmat = M["torso"]
    d, m, l = MAT[tmat]
    tor.poly(m, body, outline=True)
    tor.poly(d, back + [T(-hw * 0.2, -4), T(-cw * 0.15, H * 1.1)])                 # back in shadow
    tor.poly(l, [T(cw * 0.15, H * 0.66), T(cw * 0.72, H * 0.72), T(cw * 0.74, H * 0.88), T(cw * 0.40, H * 1.0), T(cw * 0.1, H * 0.9)])   # chest light
    deco = style.get("torso", [])
    for kind in deco:
        if kind == "lapel":          # gi / tunic opening: skin V on the chest
            tor.poly(SKIN, [T(cw * 0.40, H * 0.70), T(cw * 0.70, H * 0.86), T(cw * 0.52, H * 1.06), T(1.5, H * 1.18), T(cw * 0.2, H * 1.0)])
            tor.poly(SKIN_L, [T(cw * 0.55, H * 0.86), T(cw * 0.48, H * 1.02), T(cw * 0.32, H * 0.94)])
        if kind == "abs":            # bare muscular torso: pecs and abs
            tor.poly(SKIN_D, [T(cw * 0.30, H * 0.66), T(cw * 0.78, H * 0.70), T(cw * 0.74, H * 0.74), T(cw * 0.30, H * 0.70)])
            for y in (0.30, 0.44):
                tor.poly(SKIN_D, [T(ww * 0.30, H * y), T(ww * 0.62, H * y), T(ww * 0.62, H * y + 1.0), T(ww * 0.30, H * y + 1.0)])
            tor.poly(SKIN_L, [T(cw * 0.35, H * 0.76), T(cw * 0.68, H * 0.80), T(cw * 0.52, H * 0.92)])
        if kind == "belt":           # belt / sash at the waist
            bm = MAT[style.get("beltmat", "hair")]
            tor.poly(bm[1], [T(-ww * 0.74, H * 0.05), T(ww * 0.70, H * 0.03), T(ww * 0.70, H * 0.16), T(-ww * 0.74, H * 0.18)])
        if kind == "tank":           # tank top: shoulders bare (straps)
            tor.poly(SKIN, [T(-cw * 0.40, H * 0.98), T(cw * 0.42, H * 1.0), T(2.0, H * 1.2), T(-3.0, H * 1.18)])
        if kind == "bust":
            tor.poly(l, [T(cw * 0.55, H * 0.70), T(cw * 0.90, H * 0.76), T(cw * 0.84, H * 0.86), T(cw * 0.55, H * 0.84)])
        if kind == "trunks":         # wrestling trunks over the hips (outfit A)
            tor.poly(A_M, [T(-hw * 0.72, -5), T(hw * 0.57, -6), T(ww * 0.62, H * 0.16), T(-ww * 0.70, H * 0.18)])
            tor.poly(A_L, [T(hw * 0.1, -4), T(hw * 0.5, -5), T(ww * 0.56, H * 0.12), T(ww * 0.12, H * 0.13)])
        if kind == "armor":          # silver chest guard (outfit B)
            tor.poly(B_M, [T(-cw * 0.20, H * 0.62), T(cw * 0.84, H * 0.70), T(cw * 0.70, H * 0.96), T(-cw * 0.10, H * 0.96)])
            tor.poly(B_L, [T(cw * 0.30, H * 0.72), T(cw * 0.70, H * 0.76), T(cw * 0.60, H * 0.90)])
    parts.append(tor)

    # ---------------- head (neck -> head centre), side view around the head centre
    hb = Bone(sv(2), sv(3))
    hd = Part("head", 2, 3, hb, depth=2)
    Hc = sv(3); r = B.get("headsz", 8.5) * 0.95 * style.get("headk", 1.0)
    def Hp(x, y): return (Hc[0] + x * r / 8, Hc[1] + y * r / 8)
    # neck
    if style.get("neckblend"):
        # anatomy builder: the neck runs from under the skull into the collar (absolute
        # units, so a smaller head keeps a full-length neck); its lower end has no ink,
        # so it sinks into the torso instead of sitting on it
        nb = B["headr"] + 4.0; nw = style.get("neckw", 2.5 if not male else 3.0)
        def Np(x, y): return (Hc[0] + x, Hc[1] - y)
        hd.poly(SKIN, [Np(-nw, 0.4 * r), Np(nw + 0.2, 0.6 * r), Np(nw + 0.8, nb - 2.0), Np(-nw - 0.2, nb - 2.0)], outline=True)
        hd.poly(SKIN, [Np(-nw + 0.7, nb - 3.4), Np(nw, nb - 3.4), Np(nw + 1.0, nb), Np(-nw + 0.4, nb)])
    else:
        hd.poly(SKIN, [Hp(-2.6, -6), Hp(2.6, -7), Hp(3.0, -13), Hp(-2.8, -13)], outline=True)
    jaw = 1.15 if male else 1.0
    skull = [Hp(-7.6, 1), Hp(-6.6, 5.2), Hp(-3, 8), Hp(1.5, 8.2), Hp(5.2, 6), Hp(6.4, 3), Hp(6.6, 1.5),
             Hp(7.8, -0.4), Hp(6.4, -1.6), Hp(6.4, -3.4), Hp(5.6 * jaw, -6.2), Hp(3.6, -7.6 * jaw), Hp(-0.6, -6.6 * jaw), Hp(-5.8, -3)]
    hd.poly(SKIN, skull, outline=True)
    hd.poly(SKIN_D, [Hp(-7.6, 1), Hp(-5.8, -3), Hp(-0.6, -6.6 * jaw), Hp(1.5, -5), Hp(-2.5, 2)])          # under-jaw / back shade
    hd.poly(SKIN_L, [Hp(2.5, 6.5), Hp(5.2, 5.5), Hp(6.4, 2.6), Hp(4.6, 1.8), Hp(2.0, 4.0)])                # forehead light
    # eyes and brow
    hd.poly(WHITE, [Hp(3.8, 2.3), Hp(6.0, 2.4), Hp(5.9, 0.6), Hp(3.9, 0.7)])
    hd.poly(INK, [Hp(4.8, 2.2), Hp(6.0, 2.3), Hp(5.9, 0.7), Hp(4.8, 0.7)])
    hd.poly(HAIR_D if style.get("brow", "hair") == "hair" else INK, [Hp(3.2, 3.9), Hp(6.6, 3.1), Hp(6.4, 2.3), Hp(3.4, 3.0)])
    hd.poly(SKIN_D, [Hp(5.2, -4.2), Hp(6.3, -4.0), Hp(6.3, -4.6), Hp(5.2, -4.8)])                           # mouth
    if not male:
        hd.poly(B_M if style.get("lips") == "b" else A_D, [Hp(5.4, -4.0), Hp(6.4, -3.8), Hp(6.4, -4.8), Hp(5.4, -5.0)])
    hair = style["hair"]
    HD, HM, HL = MAT["hair"]
    if hair in ("spikes", "buns", "braid", "ponytail"):
        cap = [Hp(-8.1, -1), Hp(-7.4, 5.6), Hp(-3.2, 8.9), Hp(1.8, 9.0), Hp(5.4, 6.8), Hp(6.4, 4.0), Hp(3.0, 5.0), Hp(-1.5, 3.6), Hp(-3.5, 0.0)]
        if hair in ("braid", "ponytail"):
            cap += [Hp(-8.4, -4), Hp(-6.5, -5)]
        hd.poly(HM, cap, outline=True)
        hd.poly(HD, [Hp(-8.1, -1), Hp(-7.4, 5.6), Hp(-4.5, 7.0), Hp(-3.5, 0.0)] + ([Hp(-8.4, -4), Hp(-6.5, -5)] if hair in ("braid", "ponytail") else []))
        hd.poly(HL, [Hp(-1.5, 8.2), Hp(2.4, 8.3), Hp(4.6, 6.6), Hp(0.6, 6.4)])
    if hair == "spikes":
        for (bx, by, tx, ty) in ((-6.5, 5, -10.5, 9.5), (-3, 8, -4.5, 13), (1, 8.6, 2.5, 12.8), (4.5, 6.8, 8.6, 9.0), (-7.8, 1, -12, 2.5)):
            hd.poly(HM, [Hp(bx - 2.2, by - 1.2), Hp(bx + 2.2, by + 0.5), Hp(tx, ty)], outline=True)
            hd.poly(HL, [Hp(bx, by), Hp(bx + 1.6, by + 0.4), Hp(tx, ty)])
    if hair == "beard":
        hd.poly(HM, [Hp(-0.8, -2.2), Hp(4.0, -2.6), Hp(6.6, -3.2), Hp(6.0, -6.8), Hp(3.6, -9.0), Hp(-0.6, -7.4)], outline=True)
        hd.poly(HD, [Hp(-0.8, -2.2), Hp(1.6, -2.4), Hp(2.0, -8.4), Hp(-0.6, -7.4)])
        hd.poly(SKIN_D, [Hp(5.2, -4.4), Hp(6.4, -4.2), Hp(6.4, -4.8), Hp(5.2, -5.0)])
        hd.poly(SKIN_L, [Hp(-3, 8.2), Hp(2, 8.3), Hp(4.4, 6.6), Hp(-0.5, 7.2)])                          # bald shine
        hd.poly(WHITE, [Hp(0.5, 8.0), Hp(2.4, 7.6), Hp(1.6, 7.0)])
    if hair == "mohawk":
        hd.poly(HM, [Hp(-6.8, 4.8), Hp(-3.2, 8.4), Hp(2.4, 8.6), Hp(4.0, 7.2), Hp(2.6, 13.2), Hp(-2.6, 14.0), Hp(-7.6, 10.4), Hp(-9.8, 5.2)], outline=True)
        hd.poly(HL, [Hp(-2.2, 13.2), Hp(1.6, 12.6), Hp(2.6, 9.0), Hp(-2.8, 9.4)])
        hd.poly(HD, [Hp(-9.8, 5.2), Hp(-7.6, 10.4), Hp(-5.8, 8.8), Hp(-6.8, 4.8)])
        hd.poly(SKIN_D, [Hp(-7.4, 4.0), Hp(-3.2, 7.2), Hp(-3.6, 6.0), Hp(-7.0, 2.6)])                     # shaved sides
    if hair == "buns":
        for bx in (-4.0, 1.2):
            hd.poly(HM, [Hp(bx - 3.2, 8.4), Hp(bx + 3.2, 8.4), Hp(bx + 3.4, 12.0), Hp(bx, 14.0), Hp(bx - 3.4, 12.0)], outline=True)
            hd.poly(HL, [Hp(bx - 0.4, 12.6), Hp(bx + 1.8, 11.6), Hp(bx + 0.6, 10.2)])
    acc = style.get("head", [])
    if "headband" in acc:
        hd.poly(B_M, [Hp(-8.3, 2.4), Hp(-4, 6.4), Hp(5.6, 5.4), Hp(6.0, 4.0), Hp(-3.8, 4.6), Hp(-8.1, 0.6)])
        hd.poly(B_L, [Hp(1.0, 5.6), Hp(5.6, 5.0), Hp(5.4, 4.4), Hp(1.0, 4.6)])
    if "shades" in acc:
        hd.poly(INK, [Hp(2.8, 2.6), Hp(7.0, 2.8), Hp(6.8, 0.4), Hp(3.4, 0.4)])
        hd.poly(WHITE, [Hp(5.6, 2.2), Hp(6.6, 2.3), Hp(6.0, 1.4)])
    parts.append(hd)

    # ---------------- limbs
    def arm(sh, el, hn, side):
        ub = Bone(sv(sh), sv(el)); fb = Bone(sv(el), sv(hn))
        ua = Part("uarm" + side, sh, el, ub, side=side, depth=1 if side == "n" else -2)
        big = 1.25 if heavy else (1.0 if male else 0.82)
        st = [(-0.18, 4.6 * big, 5.0 * big), (0.0, 5.6 * big, 5.6 * big), (0.22, 5.2 * big, 4.8 * big), (0.45, 5.8 * big, 4.6 * big),
              (0.75, 4.4 * big, 3.9 * big), (1.0, 3.3 * big, 3.3 * big), (1.1, 2.8 * big, 3.0 * big)]
        sleeve = style.get("sleeve")
        if sleeve in ("long", "short"):
            shaded_limb(ua, M["sleeve"], [(t, f * 1.12, b * 1.12) for t, f, b in st])
        else:
            shaded_limb(ua, "skin", st)
            if heavy or male:   # bicep line
                ua.poly(SKIN_D, ua.limb(SKIN_D, st, t0=0.2, t1=0.6, frac=(0.45, 0.52)))
        if style.get("pads"):   # shoulder guards
            pd = MAT[style["pads"]]
            ua.poly(pd[1], [ub.along(-0.25, 6.4), ub.along(-0.25, -6.6), ub.along(0.32, -6.2), ub.along(0.40, 0), ub.along(0.32, 6.0)], outline=True)
            ua.poly(pd[2], [ub.along(-0.18, 5.4), ub.along(-0.18, 0.5), ub.along(0.25, 1.0), ub.along(0.28, 4.8)])
            ua.poly(pd[0], [ub.along(-0.20, -6.0), ub.along(0.30, -5.6), ub.along(0.34, -2.6), ub.along(-0.20, -2.6)])
        parts.append(ua)
        fa = Part("farm" + side, el, hn, fb, side=side, depth=2 if side == "n" else -1)
        st = [(-0.10, 3.5 * big, 3.5 * big), (0.20, 4.8 * big, 4.0 * big), (0.45, 4.2 * big, 3.5 * big), (0.86, 2.7 * big, 2.6 * big), (0.94, 2.6 * big, 2.5 * big)]
        if sleeve == "long":
            shaded_limb(fa, M["sleeve"], [(t, f * 1.18, b * 1.18) for t, f, b in st if t <= 0.7] + [(0.72, 4.3 * big, 4.1 * big)])
            shaded_limb(fa, "skin", [(0.66, 3.0 * big, 2.9 * big), (0.94, 2.7 * big, 2.6 * big)], light=False)
        else:
            shaded_limb(fa, "skin", st, light=heavy)
        if style.get("wrist"):
            wm = MAT[style["wrist"]]
            fa.poly(wm[1], fa.limb(wm[1], [(0.62, 3.4 * big, 3.2 * big), (0.86, 3.2 * big, 3.0 * big)]), outline=True)
            fa.poly(wm[2], fa.limb(wm[2], [(0.62, 3.4 * big, 3.2 * big), (0.86, 3.2 * big, 3.0 * big)], frac=(0.6, 0.85)))
        # fist
        g = style.get("gloves")
        fm = MAT[g] if g else MAT["skin"]
        gs = 1.55 if g else 1.22
        L = fb.L
        k = 1.0 / L
        fist = [fb.along(0.92, 3.0 * big * gs), fb.along(0.92, -3.0 * big * gs), fb.along(0.92 + 6.6 * k * big * gs, -3.2 * big * gs),
                fb.along(0.92 + 7.4 * k * big * gs, -1.0 * big * gs), fb.along(0.92 + 7.0 * k * big * gs, 3.2 * big * gs)]
        fa.poly(fm[1], fist, outline=True)
        fa.poly(fm[0], [fb.along(0.92, -3.0 * big * gs), fb.along(0.92 + 6.6 * k * big * gs, -3.2 * big * gs), fb.along(0.92 + 6.6 * k * big * gs, -1.2 * big * gs), fb.along(0.92, -1.0 * big * gs)])
        if g: fa.poly(fm[2], [fb.along(0.95 + 2.0 * k * gs, 1.0 * big * gs), fb.along(0.92 + 6.6 * k * big * gs, 1.2 * big * gs), fb.along(0.92 + 6.2 * k * big * gs, 2.8 * big * gs), fb.along(0.95 + 2.0 * k * gs, 2.6 * big * gs)])
        if False:   # knuckle line (sub-pixel at game scale)
            fa.poly(SKIN_D, [fb.along(0.92 + 4.4 * k * big, 3.0 * big), fb.along(0.92 + 4.4 * k * big, -2.6 * big), fb.along(0.92 + 5.0 * k * big, -2.6 * big), fb.along(0.92 + 5.0 * k * big, 3.0 * big)])
        parts.append(fa)

    def leg(hp, kn, ft, side):
        tbn = Bone(sv(hp), sv(kn)); sb = Bone(sv(kn), sv(ft))
        th = Part("thigh" + side, hp, kn, tbn, side=side, depth=0 if side == "n" else -3)
        tw = B.get("thighr", 6.5) * (1.12 if heavy else 1.0)
        st = [(-0.12, tw * 0.95, tw * 1.10), (0.20, tw * 1.12, tw * 1.0), (0.50, tw * 1.05, tw * 0.90), (0.80, tw * 0.84, tw * 0.74), (1.0, tw * 0.66, tw * 0.62), (1.08, tw * 0.6, tw * 0.6)]
        pm = M["legs"]
        if style.get("baggy"):
            st = [(t, f * 1.15, b * 1.15) for t, f, b in st]
        shaded_limb(th, pm, st)
        if style.get("shorts"):
            sm = MAT[style["shorts"]]
            sst = [(t, f * 1.1, b * 1.1) for t, f, b in st if t <= 0.5] + [(0.52, tw * 1.0, tw * 0.95)]
            th.poly(sm[1], th.limb(sm[1], sst), outline=True)
            th.poly(sm[0], th.limb(sm[0], sst, frac=(0, 0.3)))
            th.poly(sm[2], th.limb(sm[2], sst, frac=(0.6, 0.85), t0=0.0, t1=0.4))
        parts.append(th)
        sh_ = Part("shin" + side, kn, ft, sb, side=side, depth=0 if side == "n" else -3)
        st = [(-0.08, tw * 0.66, tw * 0.64), (0.25, tw * 0.62, tw * 0.88), (0.45, tw * 0.58, tw * 0.80), (0.80, tw * 0.42, tw * 0.44), (0.96, tw * 0.40, tw * 0.44)]
        if style.get("baggy"):
            st = [(t, f * 1.2, b * 1.2) for t, f, b in st]
        shaded_limb(sh_, M["shins"], st, light=heavy or not style.get("baggy") is None)
        if style.get("boots"):
            bm = style["boots"]
            bst = [(0.48, tw * 0.62, tw * 0.74), (0.97, tw * 0.52, tw * 0.52)]
            shaded_limb(sh_, bm, bst)
        # foot (side view around the ankle point)
        F = sv(ft)
        fm = MAT[M["feet"]]
        fw = 1.25 if heavy else (1.0 if male else 0.85)
        def Fp(x, y): return (F[0] + x * fw, F[1] + y)
        foot = [Fp(-2.6, -0.6), Fp(7.4, -0.6), Fp(7.6, 0.8), Fp(5.6, 2.6), Fp(1.6, 4.4), Fp(-2.6, 4.2)]
        sh_.poly(fm[1], foot, outline=True)
        sh_.poly(fm[0], [Fp(-2.6, -0.6), Fp(7.4, -0.6), Fp(7.4, 0.6), Fp(-2.6, 0.6)])
        parts.append(sh_)

    arm(4, 5, 6, "n"); arm(7, 8, 9, "f")
    leg(10, 11, 12, "n"); leg(13, 14, 15, "f")

    # ---------------- hair / accessory chains on the extra joints
    for (a, b, w0, w1, mat, dep) in style.get("chains", []):
        cb = Bone(sv(a), sv(b))
        cp = Part("chain%d%d" % (a, b), a, b, cb, depth=dep)
        st = [(-0.05, w0, w0), (1.05, w1, w1)]
        shaded_limb(cp, mat, st, light=w0 >= 2.5)
        parts.append(cp)
    return parts

# ------------------------------------------------------------------ export
def simplify(h, tol):
    """drop convex-hull vertices that sit within tol (design units) of the line through
    their neighbours.  The Super FX pays per vertex (transform + edge setup), not per
    pixel, so near-collinear profile points are pure cost."""
    h = list(h)
    while len(h) > 3:
        best, bi = None, -1
        for i in range(len(h)):
            a, p, c = h[i - 1], h[i], h[(i + 1) % len(h)]
            ex, ey = c[0] - a[0], c[1] - a[1]
            L = math.hypot(ex, ey) or 1e-6
            d = abs((p[0] - a[0]) * ey - (p[1] - a[1]) * ex) / L
            if best is None or d < best: best, bi = d, i
        if best >= tol: break
        h.pop(bi)
    return h

def encode(part, scale_o, tol=None):
    """-> bytes for the Super FX: [npolys] then per polygon [colour, n, (s7, o4) * n]"""
    polys = []
    for col, pts in part.polys:
        q = []
        h = hull(pts)
        if tol: h = simplify(h, tol)
        for p in h:
            s, o = part.bone.to_bone(p)
            q.append((max(-128, min(127, int(round(s * 32)))),       # 1/32 of the bone: -4 .. +4
                      max(-128, min(127, int(round(o * scale_o))))))
        # two-layer models (tol set): re-hull AFTER quantising, so rounding cannot dent a
        # run of nearly collinear profile points (and collinear ones cost no vertices)
        q = hull(q)[:16] if tol is not None else q[:16]
        if len(q) >= 3: polys.append((col, q))
    out = bytearray([len(polys)])
    for col, q in polys:
        out += bytes([col, len(q)])
        for s7, o4 in q: out += bytes([s7 & 0xFF, o4 & 0xFF])
    return out

def far_variant(part):
    q = Part(part.name, part.a, part.b, part.bone, part.side, part.depth)
    q.polys = [(shift_far(c), pts) for i, (c, pts) in enumerate(part.polys) if i not in getattr(part, "nearonly", ())]
    return q

# ------------------------------------------------------------------ the six fighters
STYLES = {
    # every fighter uses the two-layer builder (anatomy.py): v2=True; the costume dict
    # describes the clothing layer over that fighter's PHYSIQUE.  The legacy keys
    # (torso / sleeve / baggy ...) still drive the head, hair and accessory chains.
    "KAZE": dict(v2=True, simplify=0.8, mats=dict(torso="a", sleeve="a", legs="a", shins="a", feet="skin"),
                 costume=dict(top_inflate=0.7, lapel=True, belt="hair", belt_inflate=0.6, sleeve="a", sleeve_inflate=1.0, cuff=0.70,
                              pants="a", pants_inflate=1.2, hem=0.86),
                 torso=["lapel", "belt"], beltmat="hair", hair="spikes", head=["headband"], sleeve="long", baggy=True,
                 chains=[(17, 18, 1.5, 1.1, "b", -2), (0, 19, 1.4, 1.2, "hair", 1)]),
    "LIN": dict(v2=True, simplify=0.8, mats=dict(torso="a", sleeve="a", legs="hair", shins="hair", feet="hair"),
                costume=dict(top_inflate=0.4, belt="b", sleeve="a", sleeve_inflate=0.7, cuff=0.72,
                             pants="hair", pants_inflate=1.3, hem=0.90, gathered=True),
                torso=["bust", "belt"], beltmat="b", hair="buns", sleeve="long", lips="a", baggy=True,
                chains=[(0, 19, 1.8, 1.4, "b", 1)]),
    "BRUTUS": dict(v2=True, simplify=0.8, mats=dict(torso="skin", legs="skin", shins="skin", feet="b"),
                   costume=dict(abs=True, trunks="a", wrist="b", wrist_t0=0.60, boots="b", boot_top=0.45),
                   torso=["abs", "trunks"], hair="beard", wrist="b", boots="b", brow="hair",
                   chains=[]),
    # VALKA was the reference character for the two-layer builder
    "VALKA": dict(v2=True, simplify=0.8, mats=dict(torso="a", legs="a", shins="b", feet="b"),
                  costume=dict(guard="b", neckline=True, belt="hair", pads="b", wrist="b", boots="b", boot_top=0.10, fur="hair", pants="a"),
                  torso=["bust", "armor", "belt"], beltmat="hair", hair="braid", pads="b", wrist="b", lips="a",
                  chains=[(3, 16, 2.8, 2.6, "hair", -2), (16, 17, 2.6, 2.0, "hair", -2), (17, 18, 2.0, 1.2, "hair", -2)]),
    "ROCCO": dict(v2=True, simplify=0.8, mats=dict(torso="a", legs="skin", shins="skin", feet="a"),
                  costume=dict(tank=True, shorts="b", gloves="b"),
                  torso=["tank", "abs"], hair="mohawk", head=["shades"], gloves="b", shorts="b", chains=[]),
    "NOVA": dict(v2=True, simplify=0.8, mats=dict(torso="a", legs="a", shins="a", feet="skin"),
                 costume=dict(top_inflate=0.3, belt="b", pants="a", pants_inflate=1.4, hem=0.88, gathered=True),
                 torso=["bust", "belt"], beltmat="b", hair="ponytail", lips="a", baggy=True,
                 chains=[(3, 16, 2.6, 2.4, "hair", -2), (16, 17, 2.4, 1.8, "hair", -2), (17, 18, 1.8, 1.0, "hair", -2), (2, 19, 2.2, 1.6, "b", 1)]),
}

def parts_for(ch, F):
    J = F.fk(ch, ch["stance"])
    st = STYLES[ch["name"]]
    if st.get("v2"):
        import anatomy
        return anatomy.build(ch, J, st)
    return build(ch, J, st)

# ------------------------------------------------------------------ preview (same maths as the Super FX)
def render(ch, F, J, pal, scale=0.93, flip=False, img=None, at=(0, 0)):
    from PIL import ImageDraw
    parts = parts_for(ch, F)
    so = 4 * F.SCALE
    d = ImageDraw.Draw(img)
    def scr(j):
        x, y = J[j][0], J[j][1]
        if flip: x = -x
        return (at[0] + x * scale, at[1] - y * scale)
    # same order as the 65816: depth = mean of the bone ends, minus bias * 8 half-texels
    # (one design unit = 2 * SCALE half-texels); the camera looks from +z here
    nearN = J[4][2] >= J[7][2]
    hu = 2 * F.SCALE
    order = []
    for p in parts:
        z = (J[p.a][2] + J[p.b][2]) / 2
        q = p
        bn, bf = part_bias(ch, p)
        bias = bn
        if p.side:
            far = (p.side == "n") != nearN
            if far: q = far_variant(p); bias = bf
        order.append((z + bias * 8 / hu, q))
    order.sort(key=lambda t: t[0])
    for _, p in order:
        data = encode(p, so, STYLES[ch["name"]].get("simplify"))
        A = scr(p.a); Bp = scr(p.b)
        dx, dy = Bp[0] - A[0], Bp[1] - A[1]
        L = math.hypot(dx, dy) or 1
        ux, uy = -dy / L, dx / L
        if flip: ux, uy = -ux, -uy
        i = 1
        for _ in range(data[0]):
            col, n = data[i], data[i + 1]; i += 2
            pts = []
            for _ in range(n):
                s7 = data[i] - 256 if data[i] > 127 else data[i]
                o4 = data[i + 1] - 256 if data[i + 1] > 127 else data[i + 1]
                i += 2
                o_px = o4 / so * scale
                pts.append((A[0] + s7 / 32 * dx + o_px * ux, A[1] + s7 / 32 * dy + o_px * uy))
            if col & 0x80:
                d.polygon(pts, fill=pal[col & 0x7F], outline=pal[INK])
            elif len(pts) >= 3: d.polygon(pts, fill=pal[col])
            else: d.point(pts, fill=pal[col])

def palette_rgb(ch, F):
    out = []
    for c in F.fxpal(ch["colors"]):
        r, g, b = (c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3
        out.append((r, g, b))
    return out

def part_bias(ch, p):
    """(near, far) depth bias of a part, as written to the part table"""
    if not p.side: return p.depth, p.depth
    bn = {"uarm": 1, "farm": 2, "thigh": 0, "shin": 0}[p.name[:-1]]
    if p.name.startswith("shin") and STYLES[ch["name"]].get("v2"): bn = 1   # knee: shin dome over the thigh end
    return bn, bn - 3

def export(ch, F):
    """-> (shape blob, part table entries [(a, b, side, biasNear, biasFar, offNear, offFar)])"""
    so = 4 * F.SCALE
    blob = bytearray(); table = []
    for p in parts_for(ch, F):
        tol = STYLES[ch["name"]].get("simplify")
        offN = len(blob); blob += encode(p, so, tol)
        side = {None: 0, "n": 1, "f": 2}[p.side]
        if p.side:
            offF = len(blob); blob += encode(far_variant(p), so, tol)
            # depth bias by role, not by joint name: near limbs in front of the torso, far limbs behind
            bn, bf = part_bias(ch, p)
        else:
            offF = offN; bn = bf = p.depth
        table.append((p.a, p.b, side, bn, bf, offN, offF))
    return blob, table

if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import fighters as F
    from PIL import Image
    poses = ["stance", "jab", "highkick"]
    W, H = 110, 120
    img = Image.new("RGB", (W * len(poses) * 2, H * len(F.ROSTER)), (60, 64, 80))
    for ci, ch in enumerate(F.ROSTER):
        pal = palette_rgb(ch, F)
        for pi, pn in enumerate(poses):
            if pn == "stance": Jp = F.fk(ch, ch["stance"])
            else:
                mv = F.moves_for(ch)[{"jab": 0, "highkick": 3}[pn]]
                keys = F.move_keys(ch, mv)
                fr = F.bake(ch, F.expand(ch, keys))
                Jp = fr[min(len(fr) - 1, keys[0][0] + keys[1][0] - 1)]
            for fl in (0, 1):
                render(ch, F, Jp, pal, scale=1.0, flip=bool(fl), img=img, at=(W * (pi * 2 + fl) + W // 2, H * ci + H - 8))
    img = img.resize((img.width * 3, img.height * 3), Image.NEAREST)
    img.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "preview", "models.png"))
    print("preview/models.png")
