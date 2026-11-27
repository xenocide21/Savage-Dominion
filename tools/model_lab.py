#!/usr/bin/env python3
"""Model lab: renders one or more fighters across a pose sheet (and camera yaws) with
exactly the Super FX maths (model.render), for anatomy work.

usage: python3 tools/model_lab.py [NAME ...] [--yaw 0,35] [--scale 1.0] [--zoom 3] [-o out.png]
"""
import sys, os, math, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fighters as F
import model as M
from PIL import Image, ImageDraw

POSES = ["stance", "idle", "walkf", "crouch", "guard", "jump", "hit", "fall", "down", "getup",
         "m0", "m2", "m3", "m4", "m5", "m7", "m9", "m11"]

def pose_joints(ch, name):
    if name == "stance": return F.fk(ch, ch["stance"]), "stance"
    if name.startswith("m"):
        ms = F.moves_for(ch); mv = ms[min(len(ms) - 1, int(name[1:]))]
        keys = F.move_keys(ch, mv); fr = F.bake(ch, F.expand(ch, keys))
        a, b = F.active_window(ch, keys, mv["hj"]) if mv["lvl"] != 9 else (keys[0][0], keys[0][0] + 1)
        return fr[min(len(fr) - 1, (a + b) // 2)], mv["name"]
    fr = F.bake(ch, F.expand(ch, F.ANIMS[name]))
    return fr[min(len(fr) - 1, len(fr) // 2 if name not in ("fall", "jump") else len(fr) - 1)], name

def yawed(J, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [(x * c - z * s, y, x * s + z * c) for x, y, z in J]

def quant(J):
    """the ROM stores joints as int8 half-texels: match that"""
    k = 2 * F.SCALE
    return [tuple(round(v * k) / k for v in p) for p in J]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", default=["VALKA"])
    ap.add_argument("--yaw", default="0")
    ap.add_argument("--poses", default=",".join(POSES))
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--zoom", type=int, default=3)
    ap.add_argument("--flip", action="store_true")
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("-o", default=os.path.join(os.path.dirname(__file__), "..", "preview", "lab.png"))
    a = ap.parse_args()
    chars = [c for c in F.ROSTER if c["name"] in [n.upper() for n in a.names]] if a.names != ["ALL"] else F.ROSTER
    yaws = [float(y) for y in a.yaw.split(",")]
    poses = a.poses.split(",")
    W, H = int(130 * a.scale), int(118 * a.scale)
    rows = [(c, y) for c in chars for y in yaws]
    cols = min(a.cols, len(poses)); per = -(-len(poses) // cols)
    img = Image.new("RGB", (W * cols, H * len(rows) * per), (60, 64, 80))
    d = ImageDraw.Draw(img)
    for ri, (ch, yaw) in enumerate(rows):
        pal = M.palette_rgb(ch, F)
        for pj, pn in enumerate(poses):
            pi = pj % cols; rr = ri * per + pj // cols
            J, label = pose_joints(ch, pn)
            J = quant(yawed(J, yaw))
            # ground line
            gy = H * rr + H - int(8 * a.scale)
            d.line([(W * pi + 6, gy), (W * pi + W - 6, gy)], fill=(80, 86, 104))
            M.render(ch, F, J, pal, scale=a.scale, flip=a.flip, img=img, at=(W * pi + W // 2 - int(10 * a.scale), gy))
            d.text((W * pi + 3, H * rr + 2), "%s %s%s" % (ch["name"][:5], label[:10], " y%d" % yaw if yaw else ""), fill=(200, 200, 210))
    img = img.resize((img.width * a.zoom, img.height * a.zoom), Image.NEAREST)
    img.save(a.o)
    print(a.o, img.size)

if __name__ == "__main__":
    main()
