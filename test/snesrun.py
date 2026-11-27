#!/usr/bin/env python3
"""Headless snes9x (libretro) runner: input scripts, screenshots, RAM pokes and
frame-rate stats.  Env: SNES9X_CORE (path to snes9x_libretro.so), WATCH="sym ..."
(print those variables at the end), SNES9X_LEGACY_GSU=1 (old, optimistic Super FX
timing; needs the patched core), FXDBG=<frame> (Super FX busy time from that frame).
Hold buttons for 8+ frames: the game reads the pad once per main-loop pass.
usage: snesrun.py rom.sfc script.txt outprefix frames
script lines:  "<f0> <f1> <buttons>"  hold buttons (P1) for frames f0..f1
               "<f0> <f1> 2:<buttons>" same for P2
               "shot <f>"             save outprefix_<f>.png
buttons: U D L R (d-pad) a b x y l r (buttons/shoulders) S (start) e (select)
"""
import ctypes as C, sys, os
from PIL import Image

# snes9x libretro core (build: git clone snes9xgit/snes9x; cd snes9x/libretro; make)
CORE = os.environ.get("SNES9X_CORE", os.path.join(os.path.dirname(__file__), "..", "..", "ext", "snes9x", "libretro", "snes9x_libretro.so"))
lib = C.CDLL(os.path.abspath(CORE))

BTN = dict(b=0, y=1, e=2, S=3, U=4, D=5, L=6, R=7, a=8, x=9, l=10, r=11)   # matches the repo test scripts
frame = [None]; held = [0, 0]; nhits = [0]

ENV = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
VID = C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
AUD = C.CFUNCTYPE(None, C.c_int16, C.c_int16)
AUDB = C.CFUNCTYPE(C.c_size_t, C.c_void_p, C.c_size_t)
POLL = C.CFUNCTYPE(None)
STATE = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)

sysdir = C.c_char_p(b"/tmp")
OPTS = {b"snes9x_overclock_superfx": b"100%"}   # libretro core leaves the GSU at 0% otherwise
def env(cmd, data):
    if cmd == 10:   # SET_PIXEL_FORMAT
        return C.cast(data, C.POINTER(C.c_int))[0] == 2   # XRGB8888? accept RGB565
    if cmd in (9, 31):  # system / save dir
        C.cast(data, C.POINTER(C.c_char_p))[0] = sysdir.value; return True
    if cmd == 3: C.cast(data, C.POINTER(C.c_bool))[0] = False; return True
    if cmd == 15:   # GET_VARIABLE
        v = C.cast(data, C.POINTER(C.c_char_p * 2))[0]
        if v[0] in OPTS: v[1] = OPTS[v[0]]; return True
        return False
    return False
def vid(data, w, h, pitch):
    if data: frame[0] = (C.string_at(data, pitch * h), w, h, pitch)
def state(port, dev, idx, i):
    if port > 1 or dev != 1: return 0
    v = 1 if held[port] >> i & 1 else 0
    if v: nhits[0] += 1
    return v
cbs = [ENV(env), VID(vid), AUD(lambda l, r: None), AUDB(lambda d, n: n), POLL(lambda: None), STATE(state)]
lib.retro_set_environment(cbs[0]); lib.retro_set_video_refresh(cbs[1])
lib.retro_set_audio_sample(cbs[2]); lib.retro_set_audio_sample_batch(cbs[3])
lib.retro_set_input_poll(cbs[4]); lib.retro_set_input_state(cbs[5])
lib.retro_init()

class GI(C.Structure):
    _fields_ = [("path", C.c_char_p), ("data", C.c_void_p), ("size", C.c_size_t), ("meta", C.c_char_p)]
rom, script, prefix, nframes = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
blob = open(rom, "rb").read(); buf = C.create_string_buffer(blob, len(blob))
assert lib.retro_load_game(C.byref(GI(rom.encode(), C.cast(buf, C.c_void_p), len(blob), None)))

lib.retro_set_controller_port_device(0, 1); lib.retro_set_controller_port_device(1, 1)   # SNES joypads
holds, shots, pokes = [], set(), []
for ln in open(script):
    p = ln.split()
    if not p: continue
    if p[0] == "shot": shots.add(int(p[1])); continue
    if p[0] == "poke": pokes.append((int(p[1]), int(p[2], 0), int(p[3], 0))); continue
    port = 0; b = p[2] if len(p) > 2 else ""
    if b.startswith("2:"): port, b = 1, b[2:]
    holds.append((int(p[0]), int(p[1]), port, sum(1 << BTN[c] for c in b)))

lib.retro_get_memory_data.restype = C.c_void_p; lib.retro_get_memory_size.restype = C.c_size_t
ram = (C.c_ubyte * lib.retro_get_memory_size(2)).from_address(lib.retro_get_memory_data(2))   # 128 KB WRAM

def save(f):
    data, w, h, pitch = frame[0]
    img = Image.frombuffer("RGB", (w, h), data, "raw", "BGR;16", pitch, 1)   # RGB565
    img.save("%s_%d.png" % (prefix, f))
FXDBG = os.environ.get("FXDBG")           # "frame": dump the Super FX PC histogram from that frame on
for f in range(nframes):
    if FXDBG and f == int(FXDBG) and hasattr(lib, "fxdbg_clear"): lib.fxdbg_clear()
    held[:] = [0, 0]
    for f0, f1, port, m in holds:
        if f0 <= f <= f1: held[port] |= m
    for pf, a, v in pokes:
        if pf == f: ram[a & 0x1FFFF] = v & 0xFF
    lib.retro_run()
    if f in shots: save(f)
print("ran", nframes, "frames; button reads", nhits[0])

# frame-rate stats from the build's debug symbols (dbgUp = tile uploads, dbgBusy = NMIs with the GSU still drawing)
dbg = os.path.join(os.path.dirname(os.path.abspath(rom)), "build", "game.dbg")
if os.path.exists(dbg):
    import re
    syms = {}
    for l in open(dbg):
        m = re.search(r'^sym.*name="([^"]+)".*val=0x([0-9A-Fa-f]+)', l)
        if m: syms[m.group(1)] = int(m.group(2), 16) & 0x1FFFF
    names = ["dbgUp", "dbgBusy", "loopCount"] + os.environ.get("WATCH", "").split()
    vals = {k: ram[syms[k]] | ram[syms[k] + 1] << 8 for k in names if k in syms}
    print("stats", vals)
if FXDBG and hasattr(lib, "fxdbg_count"):    # only in a core patched with test/snes9x_fxdbg.patch
    lib.fxdbg_count.restype = C.c_ulonglong
    print("gsu busy scanline-slices since frame %s: %d" % (FXDBG, lib.fxdbg_count()))
    if os.environ.get("FXDUMP"): sys.stdout.flush(); lib.fxdbg_dump(); lib.fxdbg_regs()
