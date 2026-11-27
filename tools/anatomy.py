#!/usr/bin/env python3
"""Two-layer fighter construction for the Super FX models.

LAYER 1 - ANATOMY.  A per-fighter PHYSIQUE describes the body itself: side-view
width profiles (front / back of the bone, in design units) for the ribcage, pelvis,
thighs, calves, upper arms and forearms, plus joint radii, hand and foot sizes.
Male and female base bodies are scaled region by region (chest, waist, belly, hips,
glutes, arms, legs...) so a heavyweight, a lightweight and a female fighter get
genuinely different bodies, not one template.

LAYER 2 - COSTUME.  Clothing and gear are SLICES of the anatomy profiles (a range
along the bone, a band across it, inflated a little): a boot is the calf profile
from just below the knee to the ankle, puffed out 0.5; a gi sleeve is the arm
profile inflated 0.9; shorts are the pelvis below the waist plus the top half of
the thigh.  So clothes always sit on the body underneath.

Joint construction (how the pieces join without seams):
  * Every limb starts with a DOME around its proximal joint (hip / shoulder / knee /
    elbow socket).  Rotating the limb rotates the dome about the joint, so the
    silhouette stays continuous through the whole range of motion.
  * The ink outline of a limb starts a little BELOW the joint; the dome above it is
    filled without ink (in whatever covers that joint: skin, trousers, trunks),
    covering the cut.  A thigh therefore flows out of the pelvis and a shin out of
    the knee, with no outline ring around the joint.
  * Concave anatomy (lumbar curve, calf-to-Achilles taper) is two convex pieces
    whose union makes the curve; a small BRIDGE fill hides the ink where the second
    piece's border lies inside the first.
Draw order: the depth biases in model.export put the near shin over the near thigh,
forearms over upper arms, and the near limbs over the torso, which is what these
seams are designed for.
"""
import math
import model as Mdl
from model import Part, Bone, MAT, SKIN_D, SKIN, SKIN_L, HAIR_D, HAIR, HAIR_L, A_D, A_M, A_L, B_D, B_M, B_L, WHITE, INK

# ------------------------------------------------------------------ physiques
# profiles: (t along the bone, front, back).  t = 0 at the proximal joint, 1 at the
# distal one.  Torso t runs pelvis joint (0) -> chest/shoulder line (1).

# athletic woman (VALKA): strong legs, narrow waist, full hips and glutes, slimmer
# shoulders and arms than the men, small hands and feet
FEMALE = dict(
    headk=0.86, neckw=2.5,
    pelvis=[(-0.30, 1.6, 4.4), (-0.20, 4.4, 7.6), (-0.06, 5.8, 9.0), (0.10, 6.2, 8.8), (0.26, 5.8, 6.8), (0.36, 5.4, 5.6)],
    ribs=[(0.28, 5.5, 5.3), (0.38, 5.3, 5.0), (0.52, 6.4, 5.5), (0.66, 9.0, 6.4), (0.80, 9.0, 6.8), (0.92, 7.2, 6.8),
          (1.04, 5.6, 6.0), (1.14, 3.2, 3.6)],
    waist_t=0.37,
    thigh=[(0.00, 5.4, 6.4), (0.20, 6.6, 6.2), (0.45, 6.2, 5.0), (0.72, 5.0, 4.0), (0.92, 4.2, 3.6), (1.03, 3.9, 3.4)],
    hipball=(5.6, 6.6),
    calf=[(0.00, 4.0, 3.6), (0.14, 4.0, 4.4), (0.30, 3.7, 5.2), (0.46, 3.3, 4.8), (0.62, 2.9, 3.4)],
    ankle=[(0.54, 3.1, 3.9), (0.70, 2.6, 2.7), (0.86, 2.3, 2.2), (0.98, 2.4, 2.5)],
    knee=(4.2, 3.8),
    uarm=[(0.00, 3.9, 4.2), (0.18, 4.0, 3.9), (0.36, 3.4, 3.4), (0.56, 3.6, 3.3), (0.80, 3.1, 2.8), (1.00, 2.6, 2.6), (1.07, 2.5, 2.4)],
    delt=(4.0, 4.3),
    farm=[(0.00, 2.7, 2.9), (0.16, 3.2, 3.1), (0.40, 2.8, 2.6), (0.70, 2.1, 2.0), (0.90, 1.9, 1.8), (0.96, 1.9, 1.8)],
    elbow=(2.6, 3.0),
    fist=(5.0, 2.2, 1.9),          # length, half-height at the knuckles, at the wrist
    foot=0.86,
)

# athletic man (KAZE): deeper chest and broad back (lats), flatter glutes, straight
# waist, thicker arms with a real deltoid, quads and calves
MALE = dict(
    headk=0.88, neckw=3.0,
    pelvis=[(-0.28, 1.8, 4.2), (-0.18, 4.2, 6.4), (-0.04, 5.4, 7.4), (0.12, 5.8, 7.0), (0.28, 5.8, 6.0), (0.38, 5.6, 5.6)],
    ribs=[(0.30, 5.6, 5.6), (0.42, 5.8, 5.5), (0.58, 7.0, 6.6), (0.72, 8.4, 7.4), (0.86, 8.6, 7.6), (0.98, 7.4, 7.2),
          (1.08, 5.2, 5.8), (1.16, 3.4, 3.6)],
    waist_t=0.40,
    thigh=[(0.00, 5.6, 6.4), (0.20, 6.8, 6.0), (0.45, 6.6, 5.2), (0.72, 5.4, 4.4), (0.92, 4.4, 3.9), (1.03, 4.1, 3.6)],
    hipball=(5.8, 6.4),
    calf=[(0.00, 4.2, 3.8), (0.14, 4.2, 4.8), (0.30, 3.9, 5.6), (0.46, 3.5, 5.0), (0.62, 3.0, 3.6)],
    ankle=[(0.54, 3.2, 4.0), (0.70, 2.8, 2.9), (0.86, 2.5, 2.4), (0.98, 2.6, 2.6)],
    knee=(4.4, 4.0),
    uarm=[(0.00, 4.6, 4.8), (0.18, 4.8, 4.4), (0.36, 4.2, 4.0), (0.56, 4.5, 4.0), (0.80, 3.8, 3.4), (1.00, 3.2, 3.1), (1.07, 3.0, 2.9)],
    delt=(4.7, 4.9),
    farm=[(0.00, 3.2, 3.4), (0.16, 3.9, 3.6), (0.40, 3.4, 3.1), (0.70, 2.5, 2.4), (0.90, 2.2, 2.1), (0.96, 2.2, 2.1)],
    elbow=(3.1, 3.5),
    fist=(5.8, 2.6, 2.2),
    foot=1.0,
)

def _scale(st, kf, kb=None, addf=None):
    kb = kf if kb is None else kb
    return [(t, f * (kf(t) if callable(kf) else kf) + (addf(t) if addf else 0.0), b * (kb(t) if callable(kb) else kb)) for t, f, b in st]

def _bell(c, w, a):
    return lambda t: a * max(0.0, 1.0 - abs(t - c) / w)

def body(base, chest=1.0, waist=1.0, belly=0.0, hips=1.0, glute=1.0, bust=1.0, arms=1.0, fore=None, legs=1.0, calf=None,
         neck=1.0, foot=None, fist=None, headk=None):
    """a physique from a base body, scaled region by region"""
    B = dict(base)
    fore = arms if fore is None else fore
    calf = legs if calf is None else calf
    zone = lambda t: waist + (chest - waist) * min(1.0, max(0.0, (t - 0.40) / 0.35))   # waist -> chest
    bustk = lambda t: zone(t) * (1.0 + (bust - 1.0) * max(0.0, 1.0 - abs(t - 0.73) / 0.12))
    B["ribs"] = _scale(base["ribs"], bustk, zone, _bell(0.40, 0.22, belly))
    B["pelvis"] = _scale(base["pelvis"], lambda t: hips if t < 0.2 else waist, lambda t: glute if t < 0.2 else waist,
                         _bell(0.24, 0.20, belly * 0.8))
    B["thigh"] = _scale(base["thigh"], legs); B["hipball"] = tuple(v * legs for v in base["hipball"])
    B["calf"] = _scale(base["calf"], calf); B["ankle"] = _scale(base["ankle"], calf)
    B["knee"] = tuple(v * (legs + calf) / 2 for v in base["knee"])
    B["uarm"] = _scale(base["uarm"], arms); B["delt"] = tuple(v * arms for v in base["delt"])
    B["farm"] = _scale(base["farm"], fore); B["elbow"] = tuple(v * fore for v in base["elbow"])
    B["neckw"] = base["neckw"] * neck
    if fist: B["fist"] = tuple(v * fist for v in base["fist"])
    if foot: B["foot"] = foot
    if headk: B["headk"] = headk
    return B

PHYSIQUE = {
    "VALKA": FEMALE,
    "KAZE": MALE,
    # wiry kung-fu woman: smaller, slimmer, light bust, long-line limbs
    "LIN": body(FEMALE, chest=0.90, waist=0.92, hips=0.92, glute=0.90, bust=0.88, arms=0.86, legs=0.88, calf=0.86,
                fist=0.92, foot=0.84, headk=0.92),
    # heavyweight wrestler: barrel chest, belly, thick neck, huge arms and thighs
    "BRUTUS": body(MALE, chest=1.30, waist=1.38, belly=2.4, hips=1.28, glute=1.18, arms=1.40, fore=1.32, legs=1.30,
                   calf=1.30, neck=1.45, fist=1.22, foot=1.22, headk=0.90),
    # lean boxer: built-up shoulders and arms, lighter legs
    "ROCCO": body(MALE, chest=1.04, waist=0.96, arms=1.10, fore=1.04, legs=0.94, calf=0.94, glute=0.92, headk=0.88),
    # capoeirista: long powerful legs and glutes, slim upper body
    "NOVA": body(FEMALE, chest=0.90, waist=0.92, hips=0.96, glute=1.04, bust=0.90, arms=0.88, legs=0.94, calf=0.92,
                 fist=0.94, foot=0.88, headk=0.90),
}

# ------------------------------------------------------------------ profile maths
def W(st, t):
    """front / back half-widths of a profile at t (clamped to its ends)"""
    if t <= st[0][0]: return st[0][1], st[0][2]
    for (t0, f0, b0), (t1, f1, b1) in zip(st, st[1:]):
        if t <= t1:
            k = (t - t0) / max(1e-6, t1 - t0)
            return f0 + (f1 - f0) * k, b0 + (b1 - b0) * k
    return st[-1][1], st[-1][2]

def span(st): return st[0][0], st[-1][0]

def prof(bone, st, t0=None, t1=None, frac=(0.0, 1.0), inflate=0.0, steps=None):
    """polygon points of a profile slice: t0..t1 along, frac = band across (0 back, 1 front)"""
    a, b = span(st)
    t0 = a if t0 is None else max(a, t0); t1 = b if t1 is None else min(b, t1)
    ts = [t0] + [t for t, _, _ in st if t0 < t < t1] + [t1]
    pts = []
    for t in ts:
        f, bk = W(st, t)
        f += inflate; bk += inflate
        lo = -bk + (f + bk) * frac[0]; hi = -bk + (f + bk) * frac[1]
        pts += [bone.along(t, hi), bone.along(t, lo)]
    return pts

def dome(bone, t, rf, rb, inflate=0.0, n=4):
    """half-disc around the joint at t, bulging toward the parent (-t side)"""
    pts = []
    for i in range(n + 1):
        th = math.pi * i / n                       # 0 = front, pi = back
        c, s = math.cos(th), math.sin(th)
        r = (rf if c >= 0 else rb) + inflate
        pts.append(bone.along(t - r * s / bone.L, r * c))
    return pts

def bridge(p, col, bone, profiles, t, h=1.8, inset=0.9):
    """fill over the junction of two convex pieces at t (hides the inner ink line)"""
    hs = h / bone.L
    def wu(tt):
        ws = [W(st, tt) for st in profiles if span(st)[0] - 1e-6 <= tt <= span(st)[1] + 1e-6]
        return (max(w[0] for w in ws), max(w[1] for w in ws)) if ws else (0, 0)
    f = min(wu(tt)[0] for tt in (t - hs, t, t + hs)) - inset
    b = min(wu(tt)[1] for tt in (t - hs, t, t + hs)) - inset
    if f + b > 0.5:
        p.poly(col, [bone.along(t - hs, f), bone.along(t + hs, f), bone.along(t + hs, -b), bone.along(t - hs, -b)])

def socket_cap(p, col, bone, st, ball, t_cut, inflate=0.0):
    """fill (no ink) from the joint dome down past the outline cut: hides the cut"""
    f, b = W(st, t_cut + 0.10)
    pts = dome(bone, st[0][0], ball[0] + inflate, ball[1] + inflate)
    pts += [bone.along(t_cut + 0.10, f + inflate - 0.8), bone.along(t_cut + 0.10, -(b + inflate) + 0.8)]
    p.poly(col, pts)

def shade(p, mat, bone, st, light=True, t0=None, t1=None, inflate=0.0, dark=0.30):
    """form shading: dark band on the back, lit strip on the front.  On limbs both are
    near-side only (the far variant is already a shade darker and mostly hidden)."""
    d, m, l = MAT[mat] if isinstance(mat, str) else mat
    lim = p.side is not None
    p.poly(d, prof(bone, st, t0, t1, frac=(0.0, dark), inflate=inflate), near_only=lim)
    if light:
        a, b = span(st)
        a = max(a, t0 if t0 is not None else a) + 0.06; b = min(b, t1 if t1 is not None else b) - 0.08
        if b > a: p.poly(l, prof(bone, st, a, b, frac=(0.64, 0.86), inflate=inflate), near_only=lim)

def lerp(a, b, k): return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)

# ------------------------------------------------------------------ the builder
def _limb_layer(p, mat, bone, st, ball, t_cut, inflate=0.0, t0=None, t1=None, cap=True, shade_it=True, light=True):
    """one inked layer of a limb (skin or a garment) over a profile, with its socket cap"""
    m = MAT[mat]
    a = t_cut if t0 is None else t0
    p.poly(m[1], prof(bone, st, a, t1, inflate=inflate), outline=True)
    if cap: socket_cap(p, m[1], bone, st, ball, t_cut, inflate=inflate)
    if shade_it: shade(p, mat, bone, st, t0=0.0 if t0 is None else t0, t1=t1, inflate=inflate, light=light)

def build(ch, J, style):
    """anatomy + costume parts; head and hair chains come from the legacy builder"""
    PH = PHYSIQUE[ch["name"]]
    male = ch.get("male", True)
    legacy = Mdl.build(ch, J, dict(style, headk=PH.get("headk", 1.0), neckblend=True, neckw=PH["neckw"]))
    keep = {p.name: p for p in legacy}
    sv = lambda j: (J[j][0], J[j][1])
    M = style["mats"]
    cos = style.get("costume", {})
    parts = []

    # ================= torso: pelvis + ribcage (anatomy) in the top's material, then costume
    tb = Bone(sv(0), sv(1))
    tor = Part("torso", 0, 1, tb, depth=0)
    top = M["torso"]; tm = MAT[top]; ti = cos.get("top_inflate", 0.0)
    pel, rib = PH["pelvis"], PH["ribs"]
    tor.poly(tm[1], prof(tb, pel, inflate=ti), outline=True)
    tor.poly(tm[1], prof(tb, rib, inflate=ti), outline=True)
    bridge(tor, tm[1], tb, [_scale(pel, 1, 1, lambda t: ti), _scale(rib, 1, 1, lambda t: ti)], (pel[-1][0] + rib[0][0]) / 2, h=2.6)
    # form shading: back in shadow (glutes, lumbar, upper back), chest lit
    tor.poly(tm[0], prof(tb, pel, frac=(0.0, 0.34), inflate=ti))
    tor.poly(tm[0], prof(tb, rib, t0=0.30, t1=1.06, frac=(0.0, 0.26), inflate=ti))
    tor.poly(tm[2], prof(tb, rib, t0=0.58, t1=0.92, frac=(0.58, 0.84), inflate=ti))
    wt = PH["waist_t"]
    allp = sorted(pel + rib)
    if cos.get("abs"):          # bare torso: pec line, two ab grooves, pec light
        tor.poly(SKIN_D, prof(tb, rib, 0.64, 0.68, frac=(0.46, 1.0)))
        for t in (wt + 0.02, wt + 0.12):
            tor.poly(SKIN_D, prof(tb, allp, t, t + 0.035, frac=(0.66, 0.94)))
        tor.poly(SKIN_L, prof(tb, rib, 0.70, 0.84, frac=(0.70, 0.92)))
    if cos.get("tank"):         # tank top: bare shoulders and upper chest
        tor.poly(SKIN, prof(tb, rib, 1.00, 1.16, frac=(0.0, 1.0)))
        tor.poly(SKIN, prof(tb, rib, 0.94, 1.02, frac=(0.66, 0.92)))
    if cos.get("lapel"):        # gi: skin V of the chest between the lapels, open to the sternum
        fw = lambda t: W(rib, t)[0] + ti
        tor.poly(SKIN, [tb.along(0.58, fw(0.58) - 0.5), tb.along(0.74, fw(0.74) - 0.2), tb.along(0.94, fw(0.94) - 0.2),
                        tb.along(1.06, fw(1.06) - 0.8), tb.along(0.96, fw(0.96) * 0.45)])
        tor.poly(SKIN_L, [tb.along(0.74, fw(0.74) - 0.6), tb.along(0.90, fw(0.90) - 0.6), tb.along(0.90, fw(0.90) * 0.62)])
        tor.poly(tm[0], [tb.along(0.58, fw(0.58) - 0.5), tb.along(0.56, fw(0.56) - 1.4), tb.along(0.96, fw(0.96) * 0.38), tb.along(0.96, fw(0.96) * 0.45)])  # lapel edge
    if "guard" in cos:          # chest guard: a plate on the ribcage profile, bust shaped
        gm = MAT[cos["guard"]]
        tor.poly(gm[1], prof(tb, rib, 0.60, 0.98, frac=(0.18, 1.0), inflate=0.5), outline=True)
        tor.poly(gm[0], prof(tb, rib, 0.60, 0.98, frac=(0.18, 0.40), inflate=0.5))
        tor.poly(gm[2], prof(tb, rib, 0.68, 0.86, frac=(0.62, 0.92), inflate=0.5))
    if cos.get("neckline"):     # skin at the collar (the neck sits in it)
        tor.poly(SKIN, prof(tb, rib, 0.97, 1.14, frac=(0.40, 0.92)))
    for key, hi in (("trunks", 0.14), ("shorts", wt - 0.14)):   # briefs / shorts over the pelvis
        if key in cos:
            sm = MAT[cos[key]]
            tor.poly(sm[1], prof(tb, pel, None, hi, inflate=ti + 0.5), outline=True)
            tor.poly(sm[0], prof(tb, pel, None, hi, frac=(0.0, 0.36), inflate=ti + 0.5))
            tor.poly(sm[2], prof(tb, pel, hi - 0.08, hi, inflate=ti + 0.5))        # waistband
    if "belt" in cos:           # belt / sash at the natural waist
        bm = MAT[cos["belt"]]; bi = cos.get("belt_inflate", 0.4) + ti
        tor.poly(bm[1], prof(tb, allp, wt - 0.07, wt + 0.04, inflate=bi))
    parts.append(tor)
    parts.append(keep["head"])

    # ================= arms
    sleeve = cos.get("sleeve")                   # long sleeves: (material); cuff on the forearm
    si = cos.get("sleeve_inflate", 0.8); cuff = cos.get("cuff", 0.70)
    for sh, el, hn, side in ((4, 5, 6, "n"), (7, 8, 9, "f")):
        ub = Bone(sv(sh), sv(el)); fb = Bone(sv(el), sv(hn))
        ua = Part("uarm" + side, sh, el, ub, side=side)
        st = PH["uarm"]
        if sleeve:
            _limb_layer(ua, sleeve, ub, st, PH["delt"], 0.10, inflate=si, cap="pads" not in cos)
        else:
            _limb_layer(ua, "skin", ub, st, PH["delt"], 0.10, cap="pads" not in cos)
            if male: ua.poly(SKIN_D, prof(ub, st, 0.30, 0.66, frac=(0.50, 0.57)), near_only=True)     # biceps / triceps split
        if "pads" in cos:       # shoulder guard: follows the deltoid dome
            pm = MAT[cos["pads"]]
            df, db = PH["delt"]
            pad = dome(ub, 0.0, df, db, inflate=1.4, n=6) + prof(ub, st, 0.34, 0.34, inflate=1.6)
            ua.poly(pm[1], pad, outline=True)
            ua.poly(pm[0], [ub.along(0.0, -db - 1.4)] + prof(ub, st, 0.10, 0.34, frac=(0.0, 0.36), inflate=1.6))
            k = 1.0 / ub.L        # specular crescent on the front-top of the dome
            ua.poly(pm[2], [ub.along(-(db + 0.6) * 0.55 * k, (df + 0.6) * 0.30), ub.along(-(db + 0.9) * 0.82 * k, (df + 0.9) * 0.62),
                            ub.along(-0.2 * k, df + 1.2), ub.along(0.10, df + 0.4), ub.along(0.02, df * 0.45)], near_only=True)
        parts.append(ua)

        fa = Part("farm" + side, el, hn, fb, side=side)
        st = PH["farm"]
        if sleeve:              # skin wrist under the sleeve, then the sleeve with its cuff
            fa.poly(SKIN, prof(fb, st, cuff - 0.08), outline=True)
            _limb_layer(fa, sleeve, fb, st, PH["elbow"], 0.08, inflate=si, t1=cuff)
            fa.poly(MAT[sleeve][0], prof(fb, st, cuff - 0.06, cuff, inflate=si + 0.2))          # cuff hem
        else:
            _limb_layer(fa, "skin", fb, st, PH["elbow"], 0.08)
        if "wrist" in cos:      # bracer / wristband on the forearm profile
            wm = MAT[cos["wrist"]]; w0 = cos.get("wrist_t0", 0.56)
            fa.poly(wm[1], prof(fb, st, w0, 0.90, inflate=0.6), outline=True)
            fa.poly(wm[0], prof(fb, st, w0, 0.90, frac=(0.0, 0.34), inflate=0.6), near_only=True)
        k = 1.0 / fb.L; t0 = 0.93
        g = cos.get("gloves")
        if g:                   # boxing glove: a padded mitt with a cuff, thumb ridge on top
            gm = MAT[g]; ln, hk, hw = PH["fist"]; ln *= 1.45; hk *= 1.55; hw *= 1.3
            fa.poly(gm[1], prof(fb, st, 0.74, 0.95, inflate=1.0), outline=True)                    # cuff
            glove = [fb.along(t0 - 0.02, hw), fb.along(t0 + 1.8 * k, hk + 0.4), fb.along(t0 + (ln - 1.4) * k, hk + 0.2), fb.along(t0 + ln * k, hk - 1.6),
                     fb.along(t0 + ln * k, -hk + 1.4), fb.along(t0 + (ln - 1.6) * k, -hk), fb.along(t0 + 1.6 * k, -hk + 0.2), fb.along(t0 - 0.02, -hw)]
            fa.poly(gm[1], glove, outline=True)
            fa.poly(gm[0], [fb.along(t0, -hw), fb.along(t0 + 1.6 * k, -hk + 0.2), fb.along(t0 + (ln - 1.6) * k, -hk), fb.along(t0 + ln * k, -hk + 1.4),
                            fb.along(t0 + ln * k, -hk + 2.6), fb.along(t0, -hw + 1.4)])
            fa.poly(gm[2], [fb.along(t0 + 2.2 * k, hk - 0.4), fb.along(t0 + (ln - 1.8) * k, hk - 0.2), fb.along(t0 + (ln - 2.2) * k, hk - 1.6),
                            fb.along(t0 + 2.4 * k, hk - 1.4)], near_only=True)
        else:                   # fist: proportioned to the head, knuckles forward, fingers curled on the palm side
            ln, hk, hw = PH["fist"]
            fist = [fb.along(t0, hw), fb.along(t0 + 1.6 * k, hk + 0.3), fb.along(t0 + (ln - 0.6) * k, hk), fb.along(t0 + ln * k, hk - 1.0),
                    fb.along(t0 + ln * k, -hk + 0.6), fb.along(t0 + (ln - 0.8) * k, -hk), fb.along(t0 + 1.4 * k, -hk), fb.along(t0, -hw)]
            fa.poly(SKIN, fist, outline=True)
            fa.poly(SKIN_D, [fb.along(t0 + 1.6 * k, -hk + 1.6), fb.along(t0 + (ln - 0.4) * k, -hk + 1.2),
                             fb.along(t0 + (ln - 0.8) * k, -hk), fb.along(t0 + 1.4 * k, -hk)])          # curled fingers
            fa.poly(SKIN_L, [fb.along(t0 + 2.0 * k, hk - 0.2), fb.along(t0 + (ln - 0.8) * k, hk - 0.2), fb.along(t0 + (ln - 1.0) * k, hk - 1.2)], near_only=True)
        parts.append(fa)

    # ================= legs
    pants = cos.get("pants")                     # trousers over thigh and shin (None = bare legs)
    pi = cos.get("pants_inflate", 0.0); hem = cos.get("hem", 0.90)
    for hp, kn, ft, side in ((10, 11, 12, "n"), (13, 14, 15, "f")):
        tbn = Bone(sv(hp), sv(kn)); sb = Bone(sv(kn), sv(ft))
        th = Part("thigh" + side, hp, kn, tbn, side=side)
        st = PH["thigh"]
        if pants:
            _limb_layer(th, pants, tbn, st, PH["hipball"], 0.14, inflate=pi)
            th.poly(MAT[pants][0], prof(tbn, st, 0.62, 0.86, frac=(0.62, 0.70), inflate=pi), near_only=True)   # crease
        else:
            _limb_layer(th, "skin", tbn, st, PH["hipball"], 0.14, cap=False)
            for key, hi in (("trunks", 0.10), ("shorts", 0.50)):
                if key in cos:          # the garment continues from the pelvis down the thigh
                    sm = MAT[cos[key]]
                    socket_cap(th, sm[1], tbn, st, PH["hipball"], hi - 0.12 if key == "shorts" else hi - 0.04, inflate=0.5)
                    if key == "shorts":
                        th.poly(sm[1], prof(tbn, st, 0.0, hi, inflate=0.9), outline=True)
                        th.poly(sm[0], prof(tbn, st, 0.0, hi, frac=(0.0, 0.32), inflate=0.9), near_only=True)
                        th.poly(sm[2], prof(tbn, st, 0.06, hi - 0.1, frac=(0.64, 0.86), inflate=0.9), near_only=True)
                    else:
                        th.poly(sm[0], prof(tbn, st, hi - 0.05, hi, inflate=0.5))               # leg band
            if not (cos.get("trunks") or cos.get("shorts")):
                socket_cap(th, SKIN, tbn, st, PH["hipball"], 0.14)
            th.poly(SKIN_D, prof(tbn, st, 0.56, 0.86, frac=(0.62, 0.69)), near_only=True)       # quad line
        parts.append(th)

        sh_ = Part("shin" + side, kn, ft, sb, side=side)
        calf, ank = PH["calf"], PH["ankle"]
        boot = cos.get("boots")
        lm = MAT[pants or "skin"]
        if not boot and not pants:
            sh_.poly(lm[1], prof(sb, calf, 0.06, 0.30), outline=True)
        socket_cap(sh_, lm[1], sb, calf, PH["knee"], 0.06, inflate=pi if pants else 0.0)
        if boot:                # boots: the calf and ankle profiles, inflated, from below the knee
            bm = MAT[boot]; bt = cos.get("boot_top", 0.18)
            if bt > 0.3:        # mid-calf boots: bare shin above them
                sh_.poly(lm[1], prof(sb, calf, 0.06), outline=True)
                shade(sh_, "skin", sb, calf, t0=0.0, t1=bt)
            sh_.poly(bm[1], prof(sb, calf, bt, inflate=0.5), outline=True)
            sh_.poly(bm[1], prof(sb, ank, max(bt, ank[0][0]), inflate=0.5), outline=True)
            bridge(sh_, bm[1], sb, [calf, ank], (calf[-1][0] + ank[0][0]) / 2, inset=1.3)
            if bt < 0.5: shade(sh_, boot, sb, calf, t0=bt + 0.06, inflate=0.5)
            else: shade(sh_, boot, sb, ank, t0=bt + 0.04, inflate=0.5)
            if "fur" in cos:    # fur cuff at the boot top
                fm = MAT[cos["fur"]]
                sh_.poly(fm[1], prof(sb, calf, bt - 0.05, bt + 0.09, inflate=1.2), outline=True)
            elif bt > 0.3:      # boot top rim
                sh_.poly(bm[2], prof(sb, calf if bt < calf[-1][0] else ank, bt, bt + 0.05, inflate=0.6))
            fmat = bm
        elif pants:             # trousers: the calf profile inflated, hemmed above the ankle
            pm = MAT[pants]
            sh_.poly(SKIN if M["feet"] == "skin" else MAT[M["feet"]][1], prof(sb, ank, hem - 0.06), outline=True)   # ankle below the hem
            sh_.poly(pm[1], prof(sb, calf, 0.0, inflate=pi), outline=True)
            sh_.poly(pm[1], prof(sb, ank, None, hem, inflate=pi), outline=True)
            bridge(sh_, pm[1], sb, [_scale(calf, 1, 1, lambda t: pi), _scale(ank, 1, 1, lambda t: pi)], (calf[-1][0] + ank[0][0]) / 2, inset=1.2)
            shade(sh_, pants, sb, calf, t0=0.06, inflate=pi)
            if cos.get("gathered"):   # gathered cuff (kung fu / capoeira trousers)
                sh_.poly(pm[0], prof(sb, ank, hem - 0.08, hem, inflate=pi * 0.5 + 0.3))
            fmat = MAT[M["feet"]]
        else:                   # bare shin
            sh_.poly(lm[1], prof(sb, calf, 0.2), outline=True)
            sh_.poly(lm[1], prof(sb, ank), outline=True)
            bridge(sh_, lm[1], sb, [calf, ank], (calf[-1][0] + ank[0][0]) / 2)
            shade(sh_, "skin", sb, calf, t0=0.2)
            fmat = MAT[M["feet"]]
        # foot: heel behind the ankle, instep, ball, toe
        F = sv(ft); fw = PH["foot"]
        def Fp(x, y): return (F[0] + x * fw, F[1] + y)
        if M["feet"] == "skin" and not boot:     # bare foot: lower, with the toes
            sh_.poly(SKIN, [Fp(-2.4, -0.6), Fp(7.0, -0.6), Fp(7.4, 0.4), Fp(6.0, 1.4), Fp(3.0, 2.8), Fp(0.6, 4.4), Fp(-2.0, 4.0), Fp(-2.8, 1.4)], outline=True)
            sh_.poly(SKIN_D, [Fp(-2.4, -0.6), Fp(7.0, -0.6), Fp(7.2, 0.2), Fp(-2.6, 0.4)])              # sole
            sh_.poly(SKIN_D, [Fp(5.0, -0.6), Fp(5.4, -0.6), Fp(5.4, 1.4), Fp(5.0, 1.6)], near_only=True)  # toe line
        else:
            sh_.poly(fmat[1], [Fp(-2.6, -0.6), Fp(7.2, -0.6), Fp(7.6, 0.6), Fp(6.4, 1.8), Fp(3.4, 3.4), Fp(0.6, 4.8), Fp(-2.2, 4.4), Fp(-3.0, 1.6)], outline=True)
            sh_.poly(fmat[0], [Fp(-2.6, -0.6), Fp(7.2, -0.6), Fp(7.4, 0.4), Fp(-2.9, 0.6)])       # sole
            sh_.poly(fmat[2], [Fp(1.0, 4.0), Fp(3.4, 3.0), Fp(5.8, 1.8), Fp(3.0, 2.2)], near_only=True)  # instep light
        parts.append(sh_)

    parts += [p for p in legacy if p.name.startswith("chain")]
    return parts
