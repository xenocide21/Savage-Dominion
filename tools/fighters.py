#!/usr/bin/env python3
"""Fighter definitions for the SNES arena fighter (ball-jointed 3D).

Everything about a fighter lives here, in plain data:
  * proportions, colours (4 materials x 7 shades), stance, speed
  * the "balls" that make up the body, hair, clothes and accessories
  * the move list (input, speed, damage, hit level, reactions)
Animations are keyframed poses -> forward kinematics -> per-frame joint positions,
written to ROM as int8 (x forward, y up, z left) in half-texel units.

Joint list (20):
  0 pelvis 1 chest 2 neck 3 head
  4 sh_n 5 el_n 6 hand_n   7 sh_f 8 el_f 9 hand_f     (n = near/left side, f = far/right)
  10 hip_n 11 knee_n 12 foot_n   13 hip_f 14 knee_f 15 foot_f
  16 hair1 17 hair2 18 hair3 19 acc (accessory / weapon tip / scarf end)
"""
import math, os, copy, sys
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "build")
PREV = os.path.join(HERE, "..", "preview")
NJ = 20
FPS = 30            # animation frames per second (engine advances one every 2 ticks)

# ------------------------------------------------------------------ vector helpers
def v_add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def v_mul(a, k): return (a[0] * k, a[1] * k, a[2] * k)
def rot_z(v, deg):      # pitch: rotates +y toward +x
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    return (v[0] * c + v[1] * s, -v[0] * s + v[1] * c, v[2])
def rot_y(v, deg):      # yaw/twist: rotates +x toward -z
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    return (v[0] * c + v[2] * s, v[1], -v[0] * s + v[2] * c)
def rot_x(v, deg):      # roll: rotates +y toward +z
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    return (v[0], v[1] * c - v[2] * s, v[1] * s + v[2] * c)

# ------------------------------------------------------------------ pose
POSE_KEYS = ["py", "px", "pz", "lean", "twist", "head",
             "nsh", "nsr", "nel", "fsh", "fsr", "fel",
             "nhp", "nhr", "nkn", "fhp", "fhr", "fkn", "spin"]
def pose(**kw):
    p = {k: 0.0 for k in POSE_KEYS}
    p.update(kw)
    return p
def mix(a, b, t):
    return {k: a[k] + (b[k] - a[k]) * t for k in POSE_KEYS}
def add(a, d):
    r = dict(a)
    for k, v in d.items(): r[k] = r[k] + v
    return r

def fk(ch, p, hairlag=(0, 0, 0)):
    """character proportions + pose -> 20 joint positions (world units, x fwd, y up, z left)"""
    B = ch["body"]
    J = [None] * NJ
    spin = p["spin"]
    def S(v): return rot_y(v, spin)         # whole-body spin (spinning kicks)
    pel = (p["px"], B["leg"] * 2 + p["py"], p["pz"])
    J[0] = pel
    up = rot_y(rot_z((0, 1, 0), p["lean"]), p["twist"])
    J[1] = v_add(pel, S(v_mul(up, B["torso"])))
    J[2] = v_add(J[1], S(v_mul(up, B["neck"])))
    hd = rot_y(rot_z((0, 1, 0), p["lean"] + p["head"]), p["twist"])
    J[3] = v_add(J[2], S(v_mul(hd, B["headr"])))
    side = rot_y((0, 0, 1), p["twist"])
    for s, (sh, sr, el, ji) in ((1, ("nsh", "nsr", "nel", 4)), (-1, ("fsh", "fsr", "fel", 7))):
        shp = v_add(J[1], S(v_mul(side, s * B["shw"])))
        # upper arm: hangs down, pitched forward by sh, rolled out by sr
        ua = rot_y(rot_x(rot_z((0, -1, 0), -p[sh]), s * p[sr]), p["twist"])
        elp = v_add(shp, S(v_mul(ua, B["uarm"])))
        fa = rot_y(rot_x(rot_z((0, -1, 0), -(p[sh] + p[el])), s * p[sr]), p["twist"])
        hnd = v_add(elp, S(v_mul(fa, B["farm"])))
        J[ji], J[ji + 1], J[ji + 2] = shp, elp, hnd
    for s, (hp, hr, kn, ji) in ((1, ("nhp", "nhr", "nkn", 10)), (-1, ("fhp", "fhr", "fkn", 13))):
        hip = v_add(pel, S((0, 0, s * B["hipw"])))
        th = rot_x(rot_z((0, -1, 0), -p[hp]), s * p[hr])
        kne = v_add(hip, S(v_mul(th, B["leg"])))
        sh_ = rot_x(rot_z((0, -1, 0), -(p[hp] - p[kn])), s * p[hr])
        ft = v_add(kne, S(v_mul(sh_, B["leg"])))
        J[ji], J[ji + 1], J[ji + 2] = hip, kne, ft
    # hair / accessory points: offsets in head (or chest) space + a little lag
    for i, (anchor, off) in enumerate(ch["extra"]):
        o = rot_y(rot_z(off, p["lean"] + (p["head"] if anchor == 3 else 0)), p["twist"])
        J[16 + i] = v_add(v_add(J[anchor], S(o)), v_mul(hairlag, 0.6 + 0.4 * i))
    for i in range(len(ch["extra"]), 4):
        J[16 + i] = J[3]
    return J

# ------------------------------------------------------------------ materials / colour
def ramp(base, n=7):
    """dark -> light ramp of a base colour (SNES BGR555)"""
    out = []
    for i in range(n):
        k = 0.30 + 0.85 * i / (n - 1)
        r, g, b = [min(255, int(c * k + (40 * max(0, k - 1.0)))) for c in base]
        out.append(((b >> 3) << 10) | ((g >> 3) << 5) | (r >> 3))
    return out

def bgr(c):
    r, g, b = [max(0, min(255, int(v))) for v in c]
    return ((b >> 3) << 10) | ((g >> 3) << 5) | (r >> 3)

def ramp3(base):
    """Super FX shading: dark rim, mid tone, lit core"""
    return [bgr([c * 0.48 for c in base]), bgr([c * 0.80 for c in base]), bgr([c * 1.06 + 34 for c in base])]

def fxpal(cols):
    """one 16-colour OBJ palette: 0, 4 materials x 3 shades, specular, trail, outline"""
    p = [0]
    for c in cols: p += ramp3(c)
    return p + [bgr((255, 255, 240)), bgr((255, 236, 150)), bgr((12, 10, 16))]

SKIN = {"light": (236, 190, 150), "tan": (206, 150, 104), "brown": (150, 98, 64), "dark": (106, 68, 46)}

# ------------------------------------------------------------------ the roster
# body: leg (thigh = shin length), torso, neck, headr (head centre above neck), shw, hipw, uarm, farm
# balls: (jointA, jointB, t 0..1, radius, material)  material 0 skin, 1 hair/2nd, 2 outfit A, 3 outfit B
# extra: up to 4 extra joints: (anchor joint, offset (x fwd, y up, z left)) in the fighter's frame
def limb(a, b, ra, rb, mat, n=3):
    return [(a, b, i / (n - 1), ra + (rb - ra) * i / (n - 1), mat) for i in range(n)]

def base_body(B, M):
    """joint caps (rendered as shaded octagons); the limbs between them are polygons (base_segs)"""
    balls = []
    balls += [(0, 0, 0, B.get("hipr", 9) * 0.9, M["hip"]), (1, 1, 0, B.get("chestr", 10.5), M["top"])]
    balls += [(3, 3, 0, B.get("headsz", 8.5), 0)]                   # head
    for sh, el, hd in ((4, 5, 6), (7, 8, 9)):
        balls += [(sh, sh, 0, B.get("shr", 6), M.get("shoulder", M["top"]))]
        balls += [(el, el, 0, 4.2, M["farm"])]
        balls += [(hd, hd, 0, 4.2, M["hand"])]
    for hp, kn, ft in ((10, 11, 12), (13, 14, 15)):
        balls += [(kn, kn, 0, 5.2, M["shin"])]
        balls += [(ft, ft, 0, 4.5, M["feet"])]
    return balls

def base_segs(B, M):
    """flat-shaded limb polygons: (jointA, jointB, half-width at A, at B, material)"""
    s = []
    s += [(0, 1, B.get("waist", 8.5) * 0.95, B.get("chestr", 10.5) * 0.9, M["top"])]      # torso
    s += [(10, 13, B.get("thighr", 6.5), B.get("thighr", 6.5), M["hip"])]                  # pelvis
    s += [(2, 3, 3.6, 3.6, 0)]                                                              # neck
    for sh, el, hd in ((4, 5, 6), (7, 8, 9)):
        s += [(sh, el, 4.8, 4.2, M["uarm"]), (el, hd, 4.2, 3.6, M["farm"])]
    for hp, kn, ft in ((10, 11, 12), (13, 14, 15)):
        s += [(hp, kn, B.get("thighr", 6.5), 5.0, M["thigh"]), (kn, ft, 4.9, 4.0, M["shin"])]
    return s

ROSTER = []

def fighter(**kw):
    ROSTER.append(kw)

# 1 KAZE - karate master: white gi, black belt, red headband tails, spiky black hair
fighter(name="KAZE", styleName="Karate", mats=dict(top=2, hip=2, thigh=2, shin=2, feet=0, uarm=2, farm=0, hand=0), male=True,
        body=dict(leg=21, torso=24, neck=5, headr=8, shw=11, hipw=6.5, uarm=15, farm=14, chestr=10.5, headsz=8.5),
        colors=[SKIN["tan"], (40, 36, 44), (236, 234, 226), (200, 40, 40)],   # skin, hair, gi, red
        extra=[(3, (-2, 8, 0)), (3, (-9, 4, 2)), (3, (-14, -2, 3)), (0, (2, 3, 0))],
        style=dict(hair="spikes", acc="headband"),
        stance=pose(py=-5, lean=8, nsh=55, nel=60, fsh=35, fel=95, nhp=28, nkn=18, fhp=-22, fkn=14, head=-4),
        speed=1.0, power=1.0, weight=1.0)

# 2 LIN - kung fu: red tunic, twin buns, gold trim, light and quick
fighter(name="LIN", styleName="Kung Fu", mats=dict(top=2, hip=2, thigh=2, shin=2, feet=1, uarm=2, farm=0, hand=0), male=False,
        body=dict(leg=19, torso=21, neck=5, headr=7.5, shw=9, hipw=6, uarm=13, farm=12, chestr=9, headsz=7.8, hipr=8.5, waist=7.5),
        colors=[SKIN["light"], (30, 24, 30), (210, 40, 54), (232, 190, 80)],
        extra=[(3, (-1, 5, 5.5)), (3, (-1, 5, -5.5)), (3, (-6, -3, 0)), (0, (3, -6, 0))],
        style=dict(hair="buns", acc="sash"),
        stance=pose(py=-3, lean=4, nsh=80, nel=40, fsh=60, fel=100, nhp=18, nkn=26, fhp=-14, fkn=8, nhr=4, head=-2),
        speed=1.18, power=0.82, weight=0.85)

# 3 BRUTUS - heavyweight wrestler: huge, bald with beard, red trunks, wristbands
fighter(name="BRUTUS", styleName="Pro Wrestling", mats=dict(top=0, hip=2, thigh=0, shin=3, feet=3, uarm=0, farm=0, hand=0), male=True,
        body=dict(leg=22, torso=26, neck=4, headr=8, shw=14, hipw=8, uarm=16, farm=15, chestr=14, headsz=8.8, hipr=12, waist=12.5, shr=8, thighr=8.5),
        colors=[SKIN["brown"], (40, 30, 24), (190, 30, 40), (240, 210, 70)],
        extra=[(3, (4, -5, 0)), (3, (2, -8, 0)), (6, (0, 2, 0)), (9, (0, 2, 0))],
        style=dict(hair="beard", acc="wristbands"),
        stance=pose(py=-8, lean=14, nsh=40, nel=70, fsh=30, fel=80, nhp=24, nkn=24, fhp=-18, fkn=20, nhr=8, fhr=8, head=-8),
        speed=0.78, power=1.32, weight=1.4)

# 4 VALKA - Nordic warrior: long blonde braid, silver shoulder guards, fur boots
fighter(name="VALKA", styleName="Viking Brawler", mats=dict(top=2, hip=2, thigh=2, shin=3, feet=3, uarm=0, farm=0, hand=0, shoulder=3), male=False,
        body=dict(leg=22, torso=23, neck=5, headr=7.8, shw=10.5, hipw=6.5, uarm=15, farm=14, chestr=10, headsz=8, hipr=9.5),
        colors=[SKIN["light"], (240, 206, 110), (70, 110, 180), (200, 206, 214)],
        extra=[(3, (-8, 0, 0)), (3, (-12, -9, 0)), (3, (-14, -19, 0)), (1, (-2, -2, 0))],
        style=dict(hair="braid", acc="shoulders"),
        stance=pose(py=-4, lean=6, nsh=50, nel=55, fsh=70, fel=70, nhp=24, nkn=14, fhp=-20, fkn=16, head=-2),
        speed=0.95, power=1.12, weight=1.1)

# 5 ROCCO - street boxer: green mohawk, big red gloves, tank top, shades
fighter(name="ROCCO", styleName="Boxing / MMA", mats=dict(top=2, hip=3, thigh=0, shin=0, feet=2, uarm=0, farm=0, hand=3), male=True,
        body=dict(leg=20, torso=23, neck=5, headr=8, shw=11.5, hipw=6.5, uarm=14, farm=13, chestr=11, headsz=8.4),
        colors=[SKIN["light"], (60, 210, 90), (60, 64, 76), (220, 40, 40)],
        extra=[(3, (0, 9, 0)), (3, (-6, 8, 0)), (3, (5, 7, 0)), (3, (5, 1, 0))],
        style=dict(hair="mohawk", acc="gloves"),
        stance=pose(py=-6, lean=16, nsh=70, nel=110, fsh=60, fel=120, nhp=20, nkn=22, fhp=-16, fkn=16, head=-10, nhr=4),
        speed=1.08, power=0.95, weight=1.0)

# 6 NOVA - capoeira kickboxer: purple outfit, long ponytail, trailing scarf
fighter(name="NOVA", styleName="Capoeira", mats=dict(top=2, hip=2, thigh=2, shin=2, feet=0, uarm=0, farm=0, hand=0), male=False,
        body=dict(leg=23, torso=21, neck=5, headr=7.5, shw=9.5, hipw=6, uarm=14, farm=13, chestr=9, headsz=7.8, hipr=8.5, waist=7.5),
        colors=[SKIN["brown"], (34, 26, 30), (130, 60, 190), (250, 150, 60)],
        extra=[(3, (-7, 4, 0)), (3, (-12, -3, 0)), (3, (-14, -11, 0)), (2, (-6, -2, 3))],
        style=dict(hair="ponytail", acc="scarf"),
        stance=pose(py=-9, lean=10, nsh=40, nel=40, fsh=20, fel=50, nhp=34, nkn=34, fhp=-26, fkn=30, nhr=6, fhr=6, head=-4),
        speed=1.1, power=0.9, weight=0.9)

def active_window(ch, keys, hj):
    """hit frames = where the striking joint reaches furthest forward (between the
    wind-up keyframe and the recovery keyframe), so every move's reach matches its look"""
    J = bake(ch, expand(ch, keys))
    lo = keys[0][0]; hi = len(J) - keys[-1][0]
    xs = [J[f][hj][0] for f in range(len(J))]
    m = max(range(lo, max(lo + 1, hi)), key=lambda f: xs[f])
    thr = xs[m] - max(4.0, abs(xs[m]) * 0.25)
    a = m
    while a > lo and xs[a - 1] >= thr: a -= 1
    b = m + 1
    while b < hi and xs[b] >= thr: b += 1
    if b - a < 2: b = a + 2
    return a, b

def build_balls(ch):
    B = ch["body"]
    st = ch["style"]
    bl = base_body(B, ch["mats"])
    # hair / accessories (material 1 = hair or second colour)
    h = st["hair"]
    if h == "spikes":
        bl += [(3, 16, 0.6, 4.5, 1), (3, 17, 0.7, 4.2, 1), (3, 3, 0, 8.6, 1)][:2] + [(16, 16, 0, 3.5, 1), (17, 17, 0, 3.2, 1)]
    if h == "buns":
        bl += [(16, 16, 0, 3.8, 1), (17, 17, 0, 3.8, 1), (3, 18, 0.4, 7.0, 1)]
    if h == "beard":
        bl += [(16, 16, 0, 4.2, 1), (17, 17, 0, 3.4, 1)]
    if h == "braid":
        bl += [(3, 16, 0.5, 7.0, 1), (16, 16, 0, 4.5, 1), (16, 17, 0.5, 3.6, 1), (17, 17, 0, 3.4, 1), (17, 18, 0.5, 3.0, 1), (18, 18, 0, 3.4, 1)]
    if h == "mohawk":
        bl += [(16, 16, 0, 3.6, 1), (16, 17, 0.5, 3.4, 1), (17, 17, 0, 3.0, 1), (18, 18, 0, 3.0, 1), (16, 18, 0.5, 3.4, 1)]
    if h == "ponytail":
        bl += [(3, 16, 0.4, 7.0, 1), (16, 16, 0, 3.8, 1), (16, 17, 0.5, 3.4, 1), (17, 17, 0, 3.2, 1), (18, 18, 0, 2.8, 1)]
    a = st["acc"]
    if a == "headband":
        bl += [(3, 18, 0.55, 2.6, 3), (18, 18, 0, 2.4, 3)]          # headband tails
        bl += [(0, 19, 0.5, 4.0, 1)]                                 # black belt knot
    if a == "sash":
        bl += [(0, 19, 0.6, 3.6, 3), (19, 19, 0, 3.2, 3)]
    if a == "wristbands":
        bl += [(5, 6, 0.75, 4.6, 3), (8, 9, 0.75, 4.6, 3)]
    if a == "shoulders":
        bl += [(4, 4, 0, 7.5, 3), (7, 7, 0, 7.5, 3), (19, 19, 0, 4.0, 3)]
    if a == "gloves":
        bl += [(6, 6, 0, 6.2, 3), (9, 9, 0, 6.2, 3), (19, 19, 0, 2.6, 2)]   # shades = small dark ball
    if a == "scarf":
        bl += [(2, 19, 0.5, 3.6, 3), (19, 19, 0, 3.4, 3), (1, 1, 0, 0.1, 3)]
    return bl

# ------------------------------------------------------------------ move sets
# Every fighter has their own move list.  A move:
#   name, inputs, keyframes [(dur, pose delta from stance)], hit joint, level, damage,
#   reaction, block advantage, lunge step
# inputs: "Y" "X" "B" "A" "L" with an optional direction prefix f (toward) b (away)
#   d (down / crouching) or j (in the air); "jab>X" = press X during the jab to chain
#   into this move (a string / combo).  Hit levels: 0 high, 1 mid, 2 low, 9 throw.
# Reactions: 0 stagger, 1 knockdown (as a combo ender, 5+ hits), 2 launch (4+ hits),
#   3 knockdown always (sweeps); otherwise a stagger.  Airborne targets always go down.  Hit joints: 3 head, 6/9 hands,
#   8 far elbow, 11 knee, 12/15 feet.
def P(**kw): return kw

GAME_SPEED = 1.32       # MMA pace: every attack / walk cycle plays this much faster

def M(name, inputs, keys, hj, lvl, dmg, react=0, adv=-4, step=3, label=None):
    return dict(name=name, inputs=inputs.split(), keys=keys, hj=hj, lvl=lvl, dmg=dmg,
                react=react, adv=adv, step=step, label=label or name.upper())

# ---- shared keyframe library (fighters re-use these with their own inputs) ----
K = {}
K["jab"]      = [(3, P(nsh=30, nel=-50, lean=4)), (3, P(nsh=40, nel=-70, lean=6)), (5, P())]
K["straight"] = [(5, P(fsh=40, fel=-80, twist=-25, lean=8)), (3, P(fsh=55, fel=-110, twist=-35, lean=10, px=4)), (9, P())]
K["reverse"]  = [(4, P(fsh=40, fel=-80, twist=-30, lean=10, py=-3)), (3, P(fsh=60, fel=-115, twist=-45, lean=14, px=5, py=-4)), (9, P())]
K["frontkick"] = [(5, P(nhp=60, nkn=70)), (4, P(nhp=85, nkn=5, lean=-8, px=2)), (9, P())]
K["highkick"] = [(7, P(nhp=70, nkn=80, nhr=30, twist=20)), (4, P(nhp=100, nkn=0, nhr=45, lean=-18, twist=35)), (12, P())]
K["lowkick"]  = [(5, P(py=-6, nhp=40, nkn=40, lean=12)), (3, P(py=-8, nhp=55, nkn=-5, lean=14)), (8, P(py=-4))]
K["uppercut"] = [(6, P(py=-10, fsh=20, fel=120, lean=22, px=4)), (4, P(py=4, fsh=100, fel=20, lean=4, px=16, twist=-25)), (14, P())]
K["sweep"]    = [(7, P(py=-16, spin=-150, nhp=80, nkn=0, lean=24)), (7, P(py=-16, spin=-360, nhp=85, nkn=0, lean=24)), (14, P(py=-6, spin=-360))]
K["lunge"]    = [(8, P(py=-6, lean=16, fsh=-20, fel=60)), (5, P(px=12, fsh=80, fel=0, lean=20)), (16, P())]
K["flyside"]  = [(10, P(py=12, nhp=40, nkn=100, fhp=-40, fkn=80, lean=-6)), (6, P(py=16, nhp=95, nkn=0, fhp=-40, fkn=90, px=14, lean=-24)), (14, P())]
K["throw"]    = [(4, P(nsh=80, nel=0, fsh=80, fel=0, px=4)), (20, P(nsh=150, fsh=150, nel=20, fel=20, lean=-20, twist=60)), (12, P())]
K["hook"]     = [(4, P(nsh=70, nsr=40, nel=-80, twist=25, lean=6)), (3, P(nsh=88, nsr=-25, nel=-70, twist=-35, lean=10, px=5)), (9, P())]
K["bodyshot"] = [(4, P(py=-8, lean=22, fsh=20, fel=-40)), (3, P(py=-10, lean=26, fsh=60, fel=-70, px=4)), (9, P(py=-2))]
K["superman"] = [(6, P(py=-4, nhp=-30, fhp=40, fsh=-30, lean=-4)), (5, P(py=10, px=14, fsh=95, fel=-120, lean=16, nhp=-20, nkn=60, fkn=80)), (12, P())]
K["legkick"]  = [(5, P(twist=20, fhp=30, fkn=60, fhr=20)), (3, P(twist=40, py=-4, fhp=55, fkn=0, fhr=40, lean=10)), (9, P())]
K["bodykick"] = [(5, P(twist=30, fhp=50, fkn=70, fhr=30)), (3, P(twist=50, fhp=85, fkn=0, fhr=50, lean=-8)), (10, P())]
K["knee"]     = [(4, P(nhp=60, nkn=110, lean=-4, nsh=80, fsh=80, nel=60, fel=60)), (3, P(nhp=100, nkn=125, lean=-12, px=6, nsh=90, fsh=90, nel=70, fel=70)), (10, P())]
K["hammer"]   = [(5, P(nsh=170, nel=20, lean=-6)), (3, P(nsh=70, nel=0, lean=22, py=-4, px=3)), (9, P())]
K["hammer2"]  = [(4, P(fsh=170, fel=20, lean=-6, twist=-15)), (3, P(fsh=70, fel=0, lean=24, py=-5, px=4, twist=-30)), (10, P())]
K["backfist"] = [(5, P(spin=-180, nsh=40, lean=-4)), (4, P(spin=-360, nsh=90, nsr=70, nel=0, px=6)), (12, P(spin=-360))]
K["heeldrop"] = [(7, P(nhp=150, nkn=0, lean=-24)), (4, P(nhp=60, nkn=0, lean=14, px=6)), (12, P())]
K["flyknee"]  = [(6, P(py=-6, lean=6)), (5, P(py=14, px=14, nhp=110, nkn=130, fhp=-10, fkn=60, lean=-14, nsh=60, fsh=60, nel=60, fel=60)), (14, P())]
K["palm"]     = [(2, P(nsh=40, nel=-20, lean=4)), (2, P(nsh=85, nel=-95, lean=8, px=2)), (5, P())]
K["palm2"]    = [(2, P(fsh=40, fel=-20, twist=-15, lean=4)), (2, P(fsh=85, fel=-95, twist=-30, lean=9, px=3)), (6, P())]
K["palm3"]    = [(4, P(nsh=40, fsh=40, nel=60, fel=60, py=-4)), (3, P(nsh=85, fsh=85, nel=-90, fel=-90, lean=14, px=7, py=-6)), (12, P())]
K["crescent"] = [(6, P(nhp=60, nhr=60, nkn=10, twist=30)), (4, P(nhp=110, nhr=-10, nkn=0, twist=-20, lean=-16)), (11, P())]
K["tornado"]  = [(6, P(spin=180, nhp=80, nkn=10, lean=-8, py=6)), (6, P(spin=360, nhp=95, nkn=0, lean=-14, py=8)), (12, P(spin=360))]
K["tiger"]    = [(4, P(py=-6, lean=14, fsh=30, fel=-30)), (3, P(py=-8, lean=18, fsh=70, fel=-100, twist=-30, px=5)), (10, P())]
K["snapkick"] = [(4, P(nhp=55, nkn=80)), (3, P(nhp=95, nkn=10, lean=-10, px=2)), (8, P())]
K["sidekick"] = [(5, P(nhp=70, nkn=110, twist=60, lean=-6)), (4, P(nhp=85, nkn=0, twist=80, lean=-26, px=8)), (12, P())]
K["forearm"]  = [(4, P(nsh=90, nel=-40, nsr=30, twist=20)), (3, P(nsh=95, nel=-60, nsr=-35, twist=-25, lean=12, px=6)), (9, P())]
K["headbutt"] = [(5, P(lean=-18, head=-16, nsh=60, fsh=60, nel=80, fel=80)), (3, P(lean=30, head=20, px=6, nsh=70, fsh=70, nel=60, fel=60)), (12, P())]
K["clothes"]  = [(6, P(fsh=90, fsr=60, fel=0, twist=40)), (4, P(fsh=95, fsr=10, fel=0, twist=-40, lean=8, px=10)), (14, P())]
K["bigboot"]  = [(5, P(nhp=70, nkn=90)), (4, P(nhp=110, nkn=0, lean=-18, px=4)), (11, P())]
K["spear"]    = [(7, P(py=-14, lean=40, nsh=40, fsh=40)), (6, P(py=-16, lean=55, px=18, nsh=80, fsh=80, nel=20, fel=20)), (16, P())]
K["stomp"]    = [(5, P(nhp=80, nkn=100)), (3, P(nhp=40, nkn=10, lean=10, py=-4, px=3)), (10, P())]
K["dropkick"] = [(7, P(py=-6, nhp=30, fhp=30)), (6, P(py=12, lean=-50, nhp=90, fhp=90, nkn=0, fkn=0, px=12)), (16, P())]
K["charge"]   = [(10, P(py=-8, lean=30, nsh=0, fsh=0, nhr=10)), (8, P(px=18, lean=36, nsh=90, fsh=90, nel=0, fel=0)), (18, P())]
K["suplex"]   = [(5, P(nsh=80, fsh=80, nel=20, fel=20, px=4)), (20, P(nsh=170, fsh=170, lean=-60, py=-8)), (14, P())]
K["takedown"] = [(5, P(py=-14, lean=40, nsh=60, fsh=60, px=4)), (18, P(py=-24, lean=60, nsh=90, fsh=90, px=10)), (14, P())]
K["dhammer"]  = [(10, P(py=6, nsh=170, fsh=170, nel=0, fel=0, lean=-12)), (5, P(py=-4, nsh=60, fsh=60, nel=0, fel=0, lean=28, px=6)), (16, P())]
K["rush"]     = [(4, P(nsh=80, nel=-80)), (3, P(fsh=80, fel=-80, twist=-20)), (3, P(nsh=80, nel=-80, twist=10)), (3, P(fsh=85, fel=-90, twist=-30, px=6)), (12, P())]
K["slap"]     = [(3, P(nsh=60, nsr=50, nel=-30, twist=25)), (3, P(nsh=85, nsr=-20, nel=-40, twist=-30, lean=8, px=4)), (7, P())]
K["elbow"]    = [(4, P(fsh=80, fsr=50, fel=140, twist=30)), (3, P(fsh=85, fsr=10, fel=140, twist=-35, px=4, lean=8)), (10, P())]
K["martelo"]  = [(5, P(nhp=60, nkn=90, nhr=50, lean=-6)), (3, P(nhp=100, nkn=0, nhr=60, lean=-24, twist=20)), (10, P())]
K["armada"]   = [(5, P(spin=-180, py=-2, lean=-6)), (5, P(spin=-360, fhp=110, fkn=0, lean=-20)), (12, P(spin=-360))]
K["meialua"]  = [(8, P(py=-6, lean=35, spin=-160, nhp=100, nkn=10, nsh=-30, fsh=-30)), (8, P(py=-4, lean=40, spin=-360, nhp=120, nkn=0, nsh=-40, fsh=-40)), (14, P(spin=-360))]
K["chapa"]    = [(5, P(py=-6, nhp=40, nkn=60, lean=-6)), (3, P(py=-8, nhp=60, nkn=-5, lean=-12, px=3)), (9, P(py=-4))]
K["bencao"]   = [(5, P(nhp=70, nkn=90, lean=-4)), (4, P(nhp=90, nkn=0, lean=-20, px=4)), (12, P())]
K["ponteira"] = [(5, P(py=-10, nhp=40, nkn=60)), (4, P(py=4, nhp=120, nkn=0, lean=-20)), (14, P())]
K["axe"]      = K["heeldrop"]
# air attacks: legs tucked (the jump arc itself comes from the engine's physics)
TUCK = dict(nhp=60, nkn=100, fhp=40, fkn=110)
def air(d): r = dict(TUCK); r.update(d); return r
K["jpunch"]   = [(3, P(**air(dict(nsh=70, nel=60, lean=6)))), (3, P(**air(dict(nsh=60, nel=-30, lean=26, px=4)))), (10, P(**TUCK))]
K["jkick"]    = [(3, P(**TUCK)), (3, P(nhp=95, nkn=0, fhp=30, fkn=110, lean=-20, px=4, nsh=60, fsh=40)), (10, P(**TUCK))]
K["jknee"]    = [(3, P(**TUCK)), (3, P(nhp=110, nkn=130, fhp=10, fkn=100, lean=-6, px=6, nsh=80, fsh=80, nel=60, fel=60)), (10, P(**TUCK))]
K["jstomp"]   = [(3, P(**TUCK)), (3, P(nhp=40, nkn=0, fhp=50, fkn=0, lean=14, py=-6)), (10, P(**TUCK))]

MOVESETS = {
  "KAZE": [   # Shotokan karate: straight-line power, crisp three-hit strings
    M("jab",        "Y",          K["jab"],       6, 0,  6, 0,  2, 3, "KIZAMI JAB"),
    M("reverse",    "X jab>X frontkick>X", K["reverse"], 9, 0, 14, 0, -4, 5, "GYAKU ZUKI"),
    M("frontkick",  "B jab>B",    K["frontkick"], 12, 1, 12, 0, -3, 4, "MAE GERI"),
    M("roundhouse", "A reverse>A", K["highkick"], 12, 0, 18, 1, -8, 2, "MAWASHI GERI"),
    M("lowkick",    "dB",         K["lowkick"],   12, 2,  9, 0, -2, 2, "GEDAN KICK"),
    M("uppercut",   "dX",         K["uppercut"],  9, 1, 15, 2, -12, 4, "RISING PUNCH"),
    M("sweep",      "dA",         K["sweep"],     12, 2, 14, 3, -14, 0, "ASHI BARAI"),
    M("sidekick",   "fB",         K["sidekick"],  12, 1, 18, 1, -10, 6, "YOKO GERI"),
    M("lunge",      "fX",         K["lunge"],     9, 1, 20, 1, -10, 9, "OI ZUKI"),
    M("flyside",    "fA",         K["flyside"],   12, 0, 22, 1, -12, 8, "FLYING SIDE KICK"),
    M("axe",        "bA",         K["axe"],       12, 1, 20, 1, -12, 4, "KAKATO OTOSHI"),
    M("throw",      "L",          K["throw"],     6, 9, 24, 1, 0, 0, "SHOULDER THROW"),
    M("jpunch",     "jY jX",      K["jpunch"],    6, 1, 12, 0, 0, 0, "AIR PUNCH"),
    M("jkick",      "jB jA",      K["jkick"],     12, 1, 16, 0, 0, 0, "FLYING KICK"),
  ],
  "LIN": [    # Wing chun / long fist: lightning palm flurries, spinning kicks
    M("palm",       "Y",          K["palm"],      6, 0,  5, 0,  3, 2, "CHAIN PALM"),
    M("palm2",      "palm>Y",     K["palm2"],     9, 0,  6, 0,  2, 2, "CHAIN PALM 2"),
    M("palm3",      "palm2>Y",    K["palm3"],     9, 1, 14, 1, -6, 5, "TWIN DRAGON PALM"),
    M("tiger",      "X palm>X",   K["tiger"],     9, 1, 12, 0, -3, 4, "TIGER CLAW"),
    M("snapkick",   "B palm>B palm2>B", K["snapkick"], 12, 1, 10, 0, -2, 3, "SNAP KICK"),
    M("crescent",   "A snapkick>A", K["crescent"], 12, 0, 16, 1, -8, 2, "CRESCENT KICK"),
    M("lowkick",    "dB",         K["lowkick"],   12, 2,  8, 0, -2, 2, "SHIN KICK"),
    M("uppercut",   "dX",         K["uppercut"],  9, 1, 13, 2, -12, 4, "RISING PALM"),
    M("sweep",      "dA",         K["sweep"],     12, 2, 13, 3, -14, 0, "DRAGON SWEEP"),
    M("dragon",     "fX",         K["lunge"],     9, 1, 18, 1, -10, 9, "DRAGON FIST"),
    M("tornado",    "fA",         K["tornado"],   12, 0, 20, 1, -12, 6, "TORNADO KICK"),
    M("throw",      "L",          K["throw"],     6, 9, 22, 1, 0, 0, "WHEEL THROW"),
    M("jpunch",     "jY jX",      K["jpunch"],    6, 1, 11, 0, 0, 0, "AIR PALM"),
    M("jkick",      "jB jA",      K["jkick"],     12, 1, 14, 0, 0, 0, "FLYING KICK"),
  ],
  "BRUTUS": [ # Pro wrestler / grappler: slow, crushing strikes and two big throws
    M("forearm",    "Y",          K["forearm"],   6, 0,  9, 0,  0, 3, "FOREARM SMASH"),
    M("headbutt",   "forearm>Y",  K["headbutt"],  3, 0, 18, 0, -6, 4, "HEADBUTT"),
    M("clothes",    "X forearm>X bigboot>X", K["clothes"], 9, 0, 20, 1, -10, 9, "CLOTHESLINE"),
    M("bigboot",    "B",          K["bigboot"],   12, 1, 15, 0, -6, 4, "BIG BOOT"),
    M("dropkick",   "A",          K["dropkick"],  12, 1, 22, 1, -16, 6, "DROPKICK"),
    M("stomp",      "dB",         K["stomp"],     12, 2, 11, 0, -4, 2, "LEG STOMP"),
    M("uppercut",   "dX",         K["uppercut"],  9, 1, 17, 2, -12, 4, "EURO UPPERCUT"),
    M("spear",      "dA",         K["spear"],     6, 1, 20, 1, -16, 12, "SPEAR"),
    M("charge",     "fX",         K["charge"],    9, 1, 22, 1, -10, 10, "SHOULDER CHARGE"),
    M("heeldrop",   "fA",         K["heeldrop"],  12, 1, 20, 1, -12, 4, "LEG DROP"),
    M("suplex",     "L",          K["suplex"],    6, 9, 30, 1, 0, 0, "SUPLEX"),
    M("takedown",   "fL",         K["takedown"],  6, 9, 22, 1, 0, 0, "DOUBLE LEG"),
    M("jpunch",     "jY jX",      K["jpunch"],    6, 1, 14, 0, 0, 0, "AXE HANDLE"),
    M("jkick",      "jB jA",      K["jstomp"],    12, 1, 18, 0, 0, 0, "BODY DROP"),
  ],
  "VALKA": [  # Viking brawler: hammer fists, spinning backfist, knees and heel drops
    M("hammer",     "Y",          K["hammer"],    6, 1, 10, 0,  0, 3, "HAMMER FIST"),
    M("hammer2",    "hammer>Y",   K["hammer2"],   9, 1, 12, 0, -2, 3, "HAMMER FIST 2"),
    M("straight",   "X",          K["straight"],  9, 0, 14, 0, -4, 5, "STRAIGHT RIGHT"),
    M("knee",       "B straight>B", K["knee"],    11, 1, 15, 0, -3, 4, "KNEE STRIKE"),
    M("roundhouse", "A hammer2>A", K["highkick"], 12, 0, 18, 1, -8, 2, "ROUNDHOUSE"),
    M("lowkick",    "dB",         K["lowkick"],   12, 2, 10, 0, -2, 2, "LOW KICK"),
    M("uppercut",   "dX knee>X",  K["uppercut"],  9, 1, 15, 2, -12, 4, "UPPERCUT"),
    M("sweep",      "dA",         K["sweep"],     12, 2, 14, 3, -14, 0, "SWEEP"),
    M("dhammer",    "fX",         K["dhammer"],   6, 1, 22, 1, -10, 6, "DOUBLE HAMMER"),
    M("flyknee",    "fB",         K["flyknee"],   11, 1, 20, 2, -14, 10, "FLYING KNEE"),
    M("backfist",   "bX",         K["backfist"],  6, 0, 18, 0, -6, 4, "SPIN BACKFIST"),
    M("heeldrop",   "bA",         K["heeldrop"],  12, 1, 20, 1, -12, 4, "HEEL DROP"),
    M("throw",      "L",          K["throw"],     6, 9, 26, 1, 0, 0, "BEAR HUG SLAM"),
    M("jpunch",     "jY jX",      K["jpunch"],    6, 1, 13, 0, 0, 0, "AIR HAMMER"),
    M("jkick",      "jB jA",      K["jknee"],     11, 1, 16, 0, 0, 0, "AIR KNEE"),
  ],
  "ROCCO": [  # Boxer / MMA striker: the jab-cross-hook-uppercut, leg kicks, superman punch
    M("jab",        "Y",          K["jab"],       6, 0,  6, 0,  3, 3, "JAB"),
    M("cross",      "X jab>X",    K["straight"],  9, 0, 13, 0, -2, 5, "CROSS"),
    M("hook",       "cross>Y",    K["hook"],      6, 0, 14, 0, -4, 3, "LEAD HOOK"),
    M("uppercut",   "dX hook>X",  K["uppercut"],  9, 1, 16, 2, -12, 4, "UPPERCUT"),
    M("bodykick",   "B",          K["bodykick"],  15, 1, 14, 0, -4, 2, "BODY KICK"),
    M("headkick",   "A",          K["highkick"],  12, 0, 18, 1, -8, 2, "HEAD KICK"),
    M("legkick",    "dB cross>B", K["legkick"],   15, 2, 10, 0, -2, 2, "CALF KICK"),
    M("bodyshot",   "fY",         K["bodyshot"],  9, 1, 12, 0, -2, 4, "LIVER SHOT"),
    M("superman",   "fX",         K["superman"],  9, 0, 18, 0, -6, 10, "SUPERMAN PUNCH"),
    M("rush",       "fA",         K["rush"],      9, 0, 20, 1, -10, 5, "FLURRY"),
    M("sweep",      "dA",         K["sweep"],     12, 2, 12, 3, -14, 0, "LEG SWEEP"),
    M("throw",      "L",          K["throw"],     6, 9, 22, 1, 0, 0, "CLINCH TOSS"),
    M("jpunch",     "jY jX",      K["jpunch"],    6, 1, 12, 0, 0, 0, "AIR PUNCH"),
    M("jkick",      "jB jA",      K["jknee"],     11, 1, 15, 0, 0, 0, "FLYING KNEE"),
  ],
  "NOVA": [   # Capoeira: flowing spinning kicks, sweeps and low pushes
    M("slap",       "Y",          K["slap"],      6, 0,  6, 0,  2, 2, "GALOPANTE"),
    M("elbow",      "X slap>X",   K["elbow"],     8, 0, 13, 0, -3, 4, "COTOVELADA"),
    M("martelo",    "B slap>B",   K["martelo"],   12, 0, 15, 0, -4, 2, "MARTELO"),
    M("armada",     "A martelo>A", K["armada"],   15, 0, 18, 1, -8, 3, "ARMADA"),
    M("chapa",      "dB",         K["chapa"],     12, 2,  9, 0, -2, 3, "CHAPA BAIXA"),
    M("ponteira",   "dX",         K["ponteira"],  12, 1, 15, 2, -12, 3, "PONTEIRA"),
    M("rasteira",   "dA",         K["sweep"],     12, 2, 14, 3, -14, 0, "RASTEIRA"),
    M("bencao",     "fB elbow>B", K["bencao"],    12, 1, 14, 0, -4, 5, "BENCAO"),
    M("meialua",    "fA bencao>A", K["meialua"],  12, 0, 20, 1, -12, 4, "MEIA LUA"),
    M("queixada",   "bA",         K["crescent"],  12, 0, 17, 1, -8, 2, "QUEIXADA"),
    M("throw",      "L",          K["throw"],     6, 9, 22, 1, 0, 0, "BALAO"),
    M("jpunch",     "jY jX",      K["jpunch"],    6, 1, 11, 0, 0, 0, "AIR STRIKE"),
    M("jkick",      "jB jA",      K["jkick"],     12, 1, 15, 0, 0, 0, "VOO KICK"),
  ],
}
for _n, _ms in MOVESETS.items():
    _names = [m["name"] for m in _ms]
    assert len(set(_names)) == len(_names), _n
    for _m in _ms:
        for _i in _m["inputs"]:
            if ">" in _i: assert _i.split(">")[0] in _names, (_n, _i)

def moves_for(ch): return MOVESETS[ch["name"]]

def move_keys(ch, mv):
    """keyframes at this fighter's speed and the global MMA pace"""
    spd = ch["speed"] * GAME_SPEED
    return [(max(1, round(d / spd)), dl) for d, dl in mv["keys"]]

# reaction / movement animations (deltas from stance)
ANIMS = {
    "idle":     [(15, P(py=-1.5, nsh=4, fsh=4, lean=1)), (15, P(py=0))],
    "walkf":    [(4, P(px=2, nhp=16, nkn=8, fhp=-8, fkn=22, lean=2)), (4, P(px=0, nhp=-8, nkn=22, fhp=16, fkn=8, lean=2))],
    "walkb":    [(5, P(px=-2, nhp=-8, nkn=18, fhp=12, fkn=8)), (5, P(px=0, nhp=14, nkn=8, fhp=-8, fkn=18))],
    "sidestep": [(4, P(py=-4, pz=6, nhr=16, fhr=-10)), (4, P(py=-2, pz=0))],
    "crouch":   [(1, P(py=-14, nhp=40, nkn=70, fhp=10, fkn=80, lean=14))],
    "guard":    [(1, P(nsh=95, nel=95, fsh=90, fel=100, lean=4, head=-6))],
    "cguard":   [(1, P(py=-14, nhp=40, nkn=70, fhp=10, fkn=80, lean=16, nsh=95, nel=95, fsh=90, fel=100))],
    "hit":      [(3, P(lean=-24, head=-20, nsh=-20, fsh=-30, px=-3)), (8, P(lean=-10, px=-2))],
    "hitlow":   [(3, P(py=-6, nhp=-20, nkn=30, lean=20)), (8, P(py=-2))],
    "fall":     [(6, P(py=-10, lean=-50, nhp=40, fhp=50, nsh=120, fsh=130, px=-8)), (8, P(py=-30, lean=-85, nhp=60, fhp=70, nkn=20, fkn=20, nsh=150, fsh=160, px=-14))],
    "down":     [(1, P(py=-36, lean=-90, nhp=80, fhp=85, nkn=30, fkn=10, nsh=170, fsh=160, px=-16))],
    "getup":    [(8, P(py=-26, lean=-40, nhp=60, nkn=90, fhp=30, fkn=60, nsh=60, fsh=80, px=-10)), (8, P(py=-8, lean=10, nhp=30, nkn=40, px=-4)), (4, P())],
    "launched": [(6, P(lean=-40, head=-20, nhp=30, nkn=40, fhp=20, fkn=60, nsh=110, fsh=140)), (10, P(lean=-70, nhp=50, nkn=30, fhp=40, fkn=60, nsh=150, fsh=160))],
    "thrown":   [(8, P(py=10, lean=-60, nsh=140, fsh=140, nhp=40, fhp=20)), (8, P(py=0, lean=-90, spin=-60, nhp=60, fhp=60, nsh=160, fsh=150))],
    "win":      [(10, P(nsh=170, nel=10, fsh=20, fel=60, py=2, head=8)), (10, P(nsh=175, nel=0, fsh=20, fel=60, py=3, head=10))],
    "jump":     [(2, P(py=-8, nhp=40, nkn=60, fhp=10, fkn=60, lean=10)), (5, P(py=4, nhp=60, nkn=100, fhp=40, fkn=110, nsh=70, nel=70, fsh=50, fel=80, lean=4))],
    "dashf":    [(3, P(py=-4, lean=20, px=4, nhp=40, nkn=30, fhp=-30, fkn=40, nsh=70, fsh=60)), (5, P(py=-2, lean=12))],
    "dashb":    [(3, P(py=4, lean=-10, px=-4, nhp=-10, fhp=20, fkn=40)), (5, P(py=-2, lean=2))],
    "dizzy":    [(12, P(py=-5, lean=-12, head=24, twist=18, nsh=-15, fsh=-10, nel=20, fel=15, nkn=24, fkn=18, px=-2)),
                 (12, P(py=-3, lean=-4, head=16, twist=-16, nsh=-5, fsh=-20, nel=10, fel=25, nkn=14, fkn=28, px=1)),
                 (10, P(py=-1))],
    "ko":       [(1, P(py=-36, lean=-90, nhp=80, fhp=85, nkn=30, fkn=10, nsh=170, fsh=160, px=-16, head=10))],
}

def expand(ch, keys, loop=False):
    """keyframes (dur, delta) from the stance -> list of poses at 30 fps (eased)"""
    st = ch["stance"]
    frames = []
    prev = dict(st)
    for dur, d in keys:
        tgt = add(st, d)
        for i in range(1, int(dur) + 1):
            t = i / dur
            t = t * t * (3 - 2 * t)
            frames.append(mix(prev, tgt, t))
        prev = tgt
    return frames

def bake(ch, poses):
    """poses -> joints per frame, with a simple trailing lag for hair / scarves"""
    out = []
    lag = (0, 0, 0)
    prevhead = None
    for p in poses:
        J = fk(ch, p, lag)
        if prevhead is not None:
            vel = (J[3][0] - prevhead[0], J[3][1] - prevhead[1], J[3][2] - prevhead[2])
            lag = v_add(v_mul(lag, 0.6), v_mul(vel, -1.2))
        prevhead = J[3]
        out.append(J)
    return out

SCALE = 0.6     # design units -> floor texels (fighters ~48 texels tall)
def q(v):   # design units -> int8 half-texels
    return max(-127, min(127, int(round(v * 2 * SCALE))))

# ------------------------------------------------------------------ preview
def preview(ch, J, balls, cols, img, ox, oy, scale=2.2, yaw=25):
    pts = []
    for (a, b, t, r, m) in balls:
        pa, pb = J[a], J[b]
        p = (pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t, pa[2] + (pb[2] - pa[2]) * t)
        p = rot_y(p, yaw)
        pts.append((p[2] * -1, p, r, m))        # depth: larger z (toward viewer) drawn last
    d = ImageDraw.Draw(img)
    for _, p, r, m in sorted(pts, key=lambda e: -e[1][2] if False else e[1][2]):
        x, y = ox + p[0] * scale, oy - p[1] * scale
        rr = r * scale
        c = cols[m]
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=tuple(int(k * 0.55) for k in c))
        d.ellipse([x - rr * 0.85, y - rr * 0.92, x + rr * 0.7, y + rr * 0.7], fill=c)
        d.ellipse([x - rr * 0.5, y - rr * 0.6, x - rr * 0.05, y - rr * 0.15], fill=tuple(min(255, int(k * 1.25 + 30)) for k in c))

# ------------------------------------------------------------------ emit

# ------------------------------------------------------------------ finishers
# On the match-deciding KO the loser is left dizzy at a sliver of health ("FINISH THEM!").
# Enter the fighter's code (stick directions are toward / away / down, then a button)
# in close range and the finisher plays itself out.  Script steps:
#   ("anim", name, ticks)  play a move / base anim (the move's strike frame lands a hit)
#   ("wait", t) ("dim", level, t) ("launch", vy, push) ("jump", vy, drift) ("slow", t)
#   ("name",) ("orbit", speed) ("final", vy, push)  -- final: the victim flies off, K.O.
FIN_TOK = {"F": 1, "B": 2, "D": 3, "Y": 4, "X": 5, "Bk": 6, "A": 7, "L": 8}
FIN_ARROW = {"F": "->", "B": "<-", "D": "Down", "Y": "Y", "X": "X", "Bk": "B", "A": "A", "L": "L"}
def flurry(names, t, n):
    return [("anim", names[i % len(names)], t) for i in range(n)]
INTRO = [("name",), ("orbit", 1), ("dim", 7, 50), ("anim", "win", 34)]
FINISHERS = {
  "KAZE":   dict(title="THOUSAND FISTS", seq="B F F X", steps=INTRO +
             flurry(["jab", "reverse"], 9, 10) + [("anim", "lunge", 16), ("anim", "uppercut", 16), ("launch", 1700, 200),
             ("jump", 1500, 30), ("wait", 12), ("anim", "jkick", 14), ("slow", 60), ("dim", 4, 30), ("final", 600, 2600)]),
  "LIN":    dict(title="DRAGON TEMPEST", seq="D D F A", steps=INTRO +
             flurry(["palm", "palm2"], 7, 12) + [("anim", "crescent", 14), ("anim", "tornado", 18), ("anim", "uppercut", 16),
             ("launch", 1700, 200), ("jump", 1500, 30), ("wait", 12), ("anim", "jkick", 14), ("slow", 60), ("dim", 4, 30), ("final", 500, 2600)]),
  "BRUTUS": dict(title="TITAN BOMB", seq="F B F L", steps=INTRO +
             flurry(["forearm", "headbutt"], 12, 6) + [("anim", "clothes", 18), ("anim", "uppercut", 16), ("launch", 2000, 100),
             ("jump", 1800, 20), ("wait", 16), ("anim", "jpunch", 14), ("slow", 70), ("dim", 3, 40), ("final", 100, 2800)]),
  "VALKA":  dict(title="VALHALLA FALLS", seq="D B D X", steps=INTRO +
             flurry(["hammer", "hammer2"], 9, 8) + [("anim", "backfist", 16), ("anim", "knee", 14), ("anim", "flyknee", 18),
             ("launch", 1800, 200), ("jump", 1600, 30), ("wait", 12), ("anim", "jkick", 14), ("slow", 60), ("dim", 4, 30), ("final", 300, 2700)]),
  "ROCCO":  dict(title="KNOCKOUT KING", seq="F F F Y", steps=INTRO +
             flurry(["jab", "cross", "hook"], 8, 12) + [("anim", "bodyshot", 12), ("anim", "rush", 22), ("anim", "superman", 16),
             ("anim", "uppercut", 16), ("launch", 1700, 200), ("jump", 1500, 30), ("wait", 12), ("anim", "jpunch", 14),
             ("slow", 60), ("dim", 4, 30), ("final", 600, 2600)]),
  "NOVA":   dict(title="CARNAVAL STORM", seq="B D F A", steps=INTRO +
             flurry(["martelo", "armada"], 13, 6) + [("anim", "meialua", 20), ("anim", "meialua", 20), ("anim", "ponteira", 16),
             ("launch", 1700, 200), ("jump", 1500, 30), ("wait", 12), ("anim", "jkick", 14), ("slow", 60), ("dim", 4, 30), ("final", 600, 2600)]),
}
FIN_OPS = {"anim": 1, "wait": 2, "dim": 3, "launch": 4, "jump": 5, "slow": 6, "name": 7, "final": 8, "orbit": 9}

def fin_seq_words(ch):
    toks = []
    for t in FINISHERS[ch["name"]]["seq"].split():
        toks.append(FIN_TOK["Bk" if t == "Bk" else t])
    assert len(toks) == 4
    hi = (toks[0] << 8) | toks[1]; lo = (toks[2] << 8) | toks[3]
    return lo, hi

def fin_legend(ch):
    return " ".join(FIN_ARROW[t] for t in FINISHERS[ch["name"]]["seq"].split())

def fin_script(ch, base, ms):
    out = []
    names = {m["name"]: i for i, m in enumerate(ms)}
    for st in FINISHERS[ch["name"]]["steps"]:
        op = FIN_OPS[st[0]]
        if st[0] == "anim":
            nm, t = st[1], st[2]
            if nm in names:
                mv = ms[names[nm]]; kk = move_keys(ch, mv)
                a0 = active_window(ch, kk, mv["hj"])[0] if mv["lvl"] != 9 else kk[0][0]
                t = max(t, (a0 + 1) * 2 + 1)
                out += [op, base + names[nm], a0, t]
            else:
                out += [op, list(ANIMS.keys()).index(nm), 255, t]
        elif st[0] in ("launch", "jump", "final"):
            out += [op, st[1] // 16, (st[2] // 16 if st[0] != "jump" else st[2]) & 0xFF, 0]
        elif st[0] in ("wait", "slow", "orbit"):
            out += [op, st[1], 0, 0]
        elif st[0] == "dim":
            out += [op, st[1], st[2], 0]
        else:
            out += [op, 0, 0, 0]
    return out + [0, 0, 0, 0]

LOOPING = {"idle", "walkf", "walkb", "sidestep", "win", "dizzy"}
BTN = {"Y": 1, "X": 2, "B": 3, "A": 4, "L": 5}
DIRC = {"": 0, "f": 1, "b": 2, "d": 3, "j": 4}
BTNPAD = {"Y": "PAD_Y", "X": "PAD_X", "B": "PAD_B", "A": "PAD_A", "L": "PAD_L"}
DIRPAD = {"": "0", "f": "PAD_RIGHT", "b": "PAD_LEFT", "d": "PAD_DOWN"}
MAXMOVES = 16

def move_table(ch):
    """-> list of (button, dir, from-move or 255, move) input entries; chains first"""
    ms = moves_for(ch)
    ids = {m["name"]: i for i, m in enumerate(ms)}
    chains, plain = [], []
    for i, m in enumerate(ms):
        for inp in m["inputs"]:
            if ">" in inp:
                fr, bt = inp.split(">")
                chains.append((BTN[bt], 0, ids[fr], i))
            else:
                plain.append((BTN[inp[-1]], DIRC[inp[:-1]], 255, i))
    return chains + plain

def legend_inputs(m, ms):
    lab = {x["name"]: x["label"].title() for x in ms}
    nice = {"f": "->", "b": "<-", "d": "Down+", "j": "Air "}
    out = []
    for inp in m["inputs"]:
        if ">" in inp:
            fr, bt = inp.split(">"); out.append("after %s: %s" % (lab[fr], bt))
        else:
            d = inp[:-1]; out.append((nice[d] if d else "") + inp[-1])
    return out

def main():
    os.makedirs(OUT, exist_ok=True); os.makedirs(PREV, exist_ok=True)
    asm = ['; generated by tools/fighters.py', '.include "consts.inc"', '.include "regs.inc"']
    sheet = Image.new("RGB", (6 * 150, 2 * 240), (30, 26, 40))
    base = list(ANIMS.keys())
    consts = {"NJOINT": NJ, "NFIGHTER": len(ROSTER), "NBASEANIM": len(base)}
    for i, n in enumerate(base): consts["AN_" + n.upper()] = i
    legend = ["# Move lists", "", "Controls: D-pad moves; Up jumps (Up+toward / Up+away jump in / out);",
              "Down crouches; R guards; R+Up / R+Down sidestep (hold to keep circling);",
              "double-tap toward / away dashes in / backdashes.  Y punch, X power punch,",
              "B kick, A power kick, L throw.  'after Jab: X' = press X while the jab is",
              "still out to chain into the next hit of the string.", "",
              "Combos: when a hit connects, ANY ground move can cancel into any other",
              "(each move up to 3 times per combo), so mix strings and cancels for long",
              "combos.  Damage grows with every hit: single hits are weak, big combos",
              "are devastating.  Knockdowns only happen as combo enders (5+ hits),",
              "launchers (4+ hits), sweeps, throws, or when the target is in the air.",
              "COMBO BREAKER: press L while being hit (3rd hit onward), once per round.", "",
              "FINISHERS: when the KO would decide the match, the loser is left dizzy at a",
              "sliver of health for 5 seconds (FINISH THEM!).  Get close and enter your",
              "fighter's finisher code (one press each, in order, quickly) for a cinematic",
              "finishing move.  Any normal hit just knocks them out.", ""]
    for ci, ch in enumerate(ROSTER):
        name = "ch%d" % ci
        ms = moves_for(ch)
        assert len(ms) <= MAXMOVES
        base_frames = bytearray(); move_frames = bytearray()
        atab = []
        for an in base:
            J = bake(ch, expand(ch, ANIMS[an]))
            atab.append(("%s_frames" % name, len(base_frames), len(J)))
            for fr in J:
                for (x, y, z) in fr: base_frames += bytes([q(x) & 0xFF, q(y) & 0xFF, q(z) & 0xFF])
        rec = []
        for mi, mv in enumerate(ms):
            kk = move_keys(ch, mv)
            J = bake(ch, expand(ch, kk))
            atab.append(("%s_mframes" % name, len(move_frames), len(J)))
            for fr in J:
                for (x, y, z) in fr: move_frames += bytes([q(x) & 0xFF, q(y) & 0xFF, q(z) & 0xFF])
            total = sum(d for d, _ in kk)
            if mv["lvl"] == 9:
                a0s = kk[0][0]; a1s = a0s + 2
            else:
                a0s, a1s = active_window(ch, kk, mv["hj"])
            air = any(i.startswith("j") for i in mv["inputs"])
            rec.append((len(base) + mi, a0s, a1s, mv["lvl"], min(60, int(mv["dmg"] * ch["power"])), mv["react"],
                        1 if air else 0, mv["adv"] & 0xFF, mv["step"], mv["hj"] * 3, total))
        assert len(base_frames) < 0x8000 - 9000, (ch["name"], len(base_frames))
        assert len(move_frames) < 0x8000, (ch["name"], len(move_frames))
        open(os.path.join(OUT, name + "_frames.bin"), "wb").write(base_frames)
        open(os.path.join(OUT, name + "_mframes.bin"), "wb").write(move_frames)
        asm.append('.segment "BANK%d"' % (16 + ci))
        asm.append('.export %s_frames, %s_anim, %s_balls, %s_nballs, %s_pal, %s_move, %s_segs' % ((name,) * 7))
        import model as _M
        blob, table = _M.export(ch, sys.modules[__name__])
        asm.append('.export %s_shapes, %s_parts' % (name, name))
        asm.append('%s_shapes: .word %d' % (name, len(blob)))
        for i in range(0, len(blob), 24):
            asm.append('    .byte ' + ", ".join(str(b) for b in blob[i:i + 24]))
        asm.append('%s_parts: .byte %d' % (name, len(table)))
        for (a, b, side, bn, bf, on, of) in table:
            asm.append('    .byte %d, %d, %d, %d, %d, 0' % (a * 2, b * 2, side, bn & 0xFF, bf & 0xFF))
            asm.append('    .word %d, %d' % (on, of))
        segs = base_segs(ch["body"], ch["mats"])
        asm.append('%s_segs:' % name)
        for (a, b, wa, wb, m) in segs:
            asm.append('    .byte %d, %d, %d, %d, %d' % (a * 2, b * 2, int(wa * 4 * SCALE), int(wb * 4 * SCALE), m))
        asm.append('%s_frames: .incbin "%s_frames.bin"' % (name, name))
        # anim table: frame data address (lo word), frame count, bank
        asm.append('%s_anim:' % name)
        for (lab, off, n) in atab:
            asm.append('    .word .loword(%s + %d)\n    .byte %d, ^%s' % (lab, off, n, lab))
        balls = build_balls(ch)
        asm.append('%s_nballs: .byte %d' % (name, len(balls)))
        asm.append('%s_balls:' % name)
        for (a, b, t, r, m) in balls:
            asm.append('    .byte %d, %d, %d, %d, %d' % (a * 2, b * 2, min(255, int(t * 256)), int(r * 4 * SCALE), m))
        cols = ch["colors"]
        alt = [tuple(int(c * 0.6) for c in cols[3]), tuple(min(255, int(c * 0.9 + 40)) for c in cols[2])]
        asm.append('%s_pal: .word %s' % (name, ", ".join(str(c) for c in fxpal(cols) + fxpal([cols[0], cols[1], alt[0], alt[1]]))))
        # moves: anim, active start/end, level, damage, reaction, air flag, block adv, step, hit joint*3, total
        asm.append('%s_move:' % name)
        for r in rec: asm.append('    .byte ' + ", ".join(str(v) for v in r))
        asm.append('.segment "BANK%d"' % (22 + ci))
        asm.append('%s_mframes: .incbin "%s_mframes.bin"' % (name, name))
        # inputs / CPU tables (bank 0)
        asm.append('.segment "RODATA"')
        asm.append('.export %s_inputs, %s_ai, %s_aichain' % (name, name, name))
        asm.append('%s_inputs:' % name)
        tab = move_table(ch)
        for e in tab: asm.append('    .byte %d, %d, %d, %d' % e)
        asm.append('    .byte 0, 0, 0, 0')
        ground = [(m, inp) for m in ms for inp in m["inputs"] if ">" not in inp and not inp.startswith("j")]
        pool = [ground[i % len(ground)] for i in range(16)]
        asm.append('%s_ai: .word ' % name + ", ".join("%s|%s" % (BTNPAD[inp[-1]], DIRPAD[inp[:-1]]) for _, inp in pool))
        chainbtn = []
        for i in range(MAXMOVES):
            c = [e for e in tab if e[2] == i]
            chainbtn.append(["0", "PAD_Y", "PAD_X", "PAD_B", "PAD_A", "PAD_L"][c[0][0]] if c else "0")
        asm.append('%s_aichain: .word ' % name + ", ".join(chainbtn))
        canc = 0
        for i, m in enumerate(ms):
            if m["lvl"] != 9 and not any(x.startswith("j") for x in m["inputs"]): canc |= 1 << i
        consts["%s_CANC" % name.upper()] = canc
        # finisher: script, title, input code
        asm.append('.export %s_fin, %s_finName' % (name, name))
        asm.append('%s_fin: .byte ' % name + ", ".join(str(b) for b in fin_script(ch, len(base), ms)))
        asm.append('%s_finName: .byte "%s", 0' % (name, FINISHERS[ch["name"]]["title"]))
        flo, fhi = fin_seq_words(ch)
        consts["%s_FINLO" % name.upper()] = flo; consts["%s_FINHI" % name.upper()] = fhi
        # legend
        legend.append("## %s - %s" % (ch["name"], ch.get("styleName", "")))
        legend.append("")
        legend.append("| Move | Input | Hits | Notes |")
        legend.append("|---|---|---|---|")
        for m in ms:
            note = {0: "", 1: "knockdown as a combo ender (5+ hits)", 2: "launcher in combos (4+ hits)", 3: "knockdown"}[m["react"]]
            if m["lvl"] == 9: note = "throw (unblockable, close)"
            legend.append("| %s | %s | %s | %s |" % (m["label"].title(), " / ".join(legend_inputs(m, ms)),
                          {0: "high", 1: "mid", 2: "low", 9: "throw"}[m["lvl"]], note))
        legend.append("| **FINISHER: %s** | %s | - | only on a dizzy opponent, close range |" % (FINISHERS[ch["name"]]["title"].title(), fin_legend(ch)))
        legend.append("")
        # preview: stance + a kick
        J = fk(ch, ch["stance"])
        preview(ch, J, balls, cols, sheet, ci * 150 + 75, 200)
        kk = expand(ch, move_keys(ch, ms[3]))
        J2 = bake(ch, kk)[min(len(kk) - 1, 8)]
        preview(ch, J2, balls, cols, sheet, ci * 150 + 75, 440)
        ImageDraw.Draw(sheet).text((ci * 150 + 50, 8), ch["name"] + (" (M)" if ch["male"] else " (F)"), fill=(255, 255, 255))
        print("%-7s base %5d  moves %5d  (%d moves, %d input entries)" % (ch["name"], len(base_frames), len(move_frames), len(ms), len(tab)))
    sheet.save(os.path.join(PREV, "roster.png"))
    asm.append('.segment "RODATA"\n.export fighterNames, animLoop')
    asm.append('fighterNames: ' + "\n".join('    .byte "%-7s"' % c["name"] for c in ROSTER))
    asm.append('animLoop: .byte ' + ", ".join("1" if n in LOOPING else "0" for n in base))
    asm.append('.export ballCount\nballCount: .byte ' + ", ".join(str(len(build_balls(c))) for c in ROSTER))
    asm.append('.export segCount\nsegCount: .byte ' + ", ".join(str(len(base_segs(c["body"], c["mats"]))) for c in ROSTER))
    open(os.path.join(OUT, "fighters.s"), "w").write("\n".join(asm) + "\n")
    open(os.path.join(OUT, "movelist.md"), "w").write("\n".join(legend) + "\n")
    with open(os.path.join(OUT, "fighters.inc"), "w") as f:
        for k, v in consts.items(): f.write("%s = %d\n" % (k, v))

if __name__ == "__main__":
    main()
