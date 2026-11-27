#!/usr/bin/env python3
"""SPC700 sound program for the arena fighter: a tiny assembler, a driver
(sound effects + 4-channel music sequencer), synthesized BRR samples and a song.

Output: build/spc.bin (image loaded at $0200 through the IPL boot ROM) and
build/sound.inc (SFX ids, entry point) for the 65816 side.

Ports (65816 -> SPC):  $2140 command counter (bump to play), $2141 sfx id,
                       $2142 song (0 = stop, 1 = fight theme, 2 = title, 3 = victory)
"""
import math, os, random, re, struct

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "build")

# ------------------------------------------------------------------ mini SPC700 assembler
OPS = {
    "mova,#i": 0xE8, "movx,#i": 0xCD, "movy,#i": 0x8D, "mova,d": 0xE4, "movd,a": 0xC4,
    "mova,!w": 0xE5, "mov!w,a": 0xC5, "mova,!w+x": 0xF5, "mova,!w+y": 0xF6,
    "mov!w+x,a": 0xD5, "mov!w+y,a": 0xD6, "movd,#i": 0x8F, "movd,d": 0xFA,
    "movx,a": 0x5D, "mova,x": 0x7D, "movy,a": 0xFD, "mova,y": 0xDD,
    "movd+x,a": 0xD4, "mova,d+x": 0xF4, "mova,[d]+y": 0xF7, "movx,d": 0xF8, "movd,x": 0xD8,
    "movy,d": 0xEB, "movd,y": 0xCB, "movwya,d": 0xBA, "movwd,ya": 0xDA,
    "cmpa,#i": 0x68, "cmpa,d": 0x64, "cmpx,#i": 0xC8, "cmpy,#i": 0xAD,
    "adca,#i": 0x88, "sbca,#i": 0xA8, "adca,d": 0x84, "anda,#i": 0x28, "ora,#i": 0x08,
    "ora,d": 0x04, "eora,#i": 0x48,
    "inca": 0xBC, "deca": 0x9C, "incx": 0x3D, "decx": 0x1D, "incy": 0xFC, "decy": 0xDC,
    "incd": 0xAB, "decd": 0x8B, "asla": 0x1C, "lsra": 0x5C, "xcna": 0x9F,
    "brar": 0x2F, "beqr": 0xF0, "bner": 0xD0, "bcsr": 0xB0, "bccr": 0x90, "bmir": 0x30, "bplr": 0x10,
    "call!w": 0x3F, "ret": 0x6F, "clrc": 0x60, "setc": 0x80, "mulya": 0xCF,
    "pusha": 0x2D, "popa": 0xAE, "pushx": 0x4D, "popx": 0xCE, "pushy": 0x6D, "popy": 0xEE,
    "dbnzy,r": 0xFE, "nop": 0x00, "addwya,d": 0x7A, "incwd": 0x3A,
}

def assemble(src, org, syms):
    lines = []
    for raw in src.split("\n"):
        line = raw.split(";")[0].strip()
        if not line: continue
        while ":" in line.split()[0] if line else False:
            lab, line = line.split(":", 1)
            lines.append(("label", lab.strip()))
            line = line.strip()
            if not line: break
        if line: lines.append(("ins", line))

    def val(tok, labels, final):
        tok = tok.strip()
        if tok.startswith("$"): return int(tok[1:], 16)
        if re.match(r"^-?\d+$", tok): return int(tok)
        m = re.match(r"^(\w+)([+-]\d+)?$", tok)
        if m:
            name = m.group(1)
            v = syms.get(name, labels.get(name))
            if v is None:
                if final: raise KeyError(tok)
                return 0
            return v + int(m.group(2) or 0)
        raise ValueError(tok)

    def parse(ins, labels, final):
        mn, _, rest = ins.partition(" ")
        args = [a.strip() for a in rest.split(",")] if rest.strip() else []
        if mn == "call":
            return OPS["call!w"], [("w", val(args[0].lstrip("!"), labels, final))], "call!w"
        pat, vals = [], []
        for a in args:
            al = a.lower()
            if al in ("a", "x", "y", "ya", "(x)", "(x)+"): pat.append(al); continue
            if a.startswith("#"): pat.append("#i"); vals.append(("b", val(a[1:], labels, final))); continue
            if a.startswith("["):
                pat.append("[d]+y"); vals.append(("b", val(a[1:a.index("]")], labels, final))); continue
            suffix = ""
            for s in ("+x", "+y"):
                if al.endswith(s): suffix = s; a = a[:-2]
            if a.startswith("!"): pat.append("!w" + suffix); vals.append(("w", val(a[1:], labels, final))); continue
            if mn in ("bra", "beq", "bne", "bcs", "bcc", "bmi", "bpl", "dbnz") and a == args[-1]:
                pat.append("r"); vals.append(("r", val(a, labels, final))); continue
            pat.append("d" + suffix); vals.append(("b", val(a, labels, final)))
        key = mn + ",".join(pat)
        if mn in ("bra", "beq", "bne", "bcs", "bcc", "bmi", "bpl"): key = mn + "r"
        if mn == "call": key = "call!w"
        if key not in OPS: raise KeyError("bad instruction: " + ins + " (" + key + ")")
        return OPS[key], vals, key

    def emit(final, labels):
        out = bytearray(); pc = org
        for kind, x in lines:
            if kind == "label":
                labels[x] = pc; continue
            if x.startswith(".db"):
                for t in x[3:].split(","): out.append(val(t, labels, final) & 0xFF); pc += 1
                continue
            if x.startswith(".dw"):
                for t in x[3:].split(","): out += struct.pack("<H", val(t, labels, final) & 0xFFFF); pc += 2
                continue
            op, vals, key = parse(x, labels, final)
            ins = bytearray([op])
            size = 1 + sum(2 if k == "w" else 1 for k, _ in vals)
            if key in ("movd,#i",):              # mov dp,#imm -> 8F imm dp
                ins += bytes([vals[1][1] & 0xFF, vals[0][1] & 0xFF])
            elif key == "movd,d":                # mov dst,src -> FA src dst
                ins += bytes([vals[1][1] & 0xFF, vals[0][1] & 0xFF])
            else:
                for k, v in vals:
                    if k == "b": ins.append(v & 0xFF)
                    elif k == "w": ins += struct.pack("<H", v & 0xFFFF)
                    else:
                        rel = v - (pc + size)
                        if final and not -128 <= rel <= 127: raise ValueError("branch range: " + x)
                        ins.append(rel & 0xFF)
            out += ins; pc += len(ins)
        return out
    labels = {}
    emit(False, labels)
    return emit(True, labels), labels

# ------------------------------------------------------------------ BRR
def brr(samples, loop=False):
    """16-bit samples -> BRR (filter 0 / 1, best of each block)"""
    while len(samples) % 16: samples.append(0)
    out = bytearray()
    p1 = p2 = 0
    nblk = len(samples) // 16
    for b in range(nblk):
        blk = samples[b * 16:(b + 1) * 16]
        best = None
        for filt in (0, 1):
            for shift in range(12, -1, -1):
                q1, q2 = p1, p2
                nib = []; err = 0
                for s in blk:
                    pred = 0 if filt == 0 else q1 * 15 // 16
                    d = s - pred
                    n = int(round(d / (1 << shift))) if shift else d
                    n = max(-8, min(7, n))
                    r = (n << shift) >> 1 << 1 if shift else n
                    r = (n << shift) >> 1
                    v = r * 2 + pred
                    v = max(-32768, min(32767, v))
                    err += (v - s) ** 2
                    q2, q1 = q1, v
                    nib.append(n & 15)
                if best is None or err < best[0]:
                    best = (err, filt, shift, nib, q1, q2)
        _, filt, shift, nib, p1, p2 = best
        hdr = (min(12, shift + 1) << 4) | (filt << 2)
        if b == nblk - 1: hdr |= 1 | (2 if loop else 0)
        out.append(hdr)
        for i in range(0, 16, 2): out.append((nib[i] << 4) | nib[i + 1])
    return out

def brr_simple(samples, loop=False):
    """filter-0 BRR (exact decode model: sample = (n << shift) >> 1)"""
    while len(samples) % 16: samples.append(0)
    out = bytearray()
    nblk = len(samples) // 16
    for b in range(nblk):
        blk = samples[b * 16:(b + 1) * 16]
        peak = max(1, max(abs(s) for s in blk))
        rng = 0
        while rng < 12 and (7 << rng) >> 1 < peak: rng += 1
        nib = []
        for s in blk:
            n = int(round(s * 2 / (1 << rng))) if rng else s
            nib.append(max(-8, min(7, n)) & 15)
        hdr = (rng << 4)
        if b == nblk - 1: hdr |= 1 | (2 if loop else 0)
        out.append(hdr)
        for i in range(0, 16, 2): out.append((nib[i] << 4) | nib[i + 1])
    return out

# ------------------------------------------------------------------ samples (16-bit)
random.seed(7)
def clip(v): return max(-32000, min(32000, int(v)))
def env(i, n, a=0.002, rel=1.0):
    t = i / n
    return min(1.0, i / max(1, a * n)) * (1 - t) ** rel

def wave_saw(n=32):    return [clip(30000 * (1 - 2 * i / n) * 0.8) for i in range(n)]
def wave_square(n=32): return [clip(20000 if i < n * 0.25 else -20000) for i in range(n)]
def wave_tri(n=32):    return [clip(30000 * (1 - 4 * abs(i / n - 0.5))) - 0 for i in range(n)]

SR = 16000            # one-shot samples are made at 16 kHz and played at pitch $0800
def kick():
    n = int(SR * 0.22); ph = 0; out = []
    for i in range(n):
        f = 45 + 120 * math.exp(-i / (SR * 0.03))
        ph += 2 * math.pi * f / SR
        out.append(clip(30000 * math.sin(ph) * env(i, n, 0.001, 1.6)))
    return out
def snare():
    n = int(SR * 0.18); out = []; ph = 0; lp = 0
    for i in range(n):
        ph += 2 * math.pi * 190 / SR
        nz = random.uniform(-1, 1); lp = lp * 0.4 + nz * 0.6
        out.append(clip((lp * 22000 + math.sin(ph) * 9000 * math.exp(-i / (SR * 0.03))) * env(i, n, 0.001, 2.2)))
    return out
def hat():
    n = int(SR * 0.05); out = []; prev = 0
    for i in range(n):
        nz = random.uniform(-1, 1); hp = nz - prev; prev = nz
        out.append(clip(hp * 12000 * env(i, n, 0.001, 2.5)))
    return out
def hit(heavy):
    n = int(SR * (0.26 if heavy else 0.13)); out = []; ph = 0; lp = 0
    for i in range(n):
        f = (60 if heavy else 110) + 200 * math.exp(-i / (SR * 0.02))
        ph += 2 * math.pi * f / SR
        nz = random.uniform(-1, 1); lp = lp * (0.75 if heavy else 0.5) + nz * (0.25 if heavy else 0.5)
        v = math.sin(ph) * 20000 * math.exp(-i / (SR * (0.08 if heavy else 0.04))) + lp * 26000 * math.exp(-i / (SR * 0.025))
        out.append(clip(v * env(i, n, 0.0005, 1.0)))
    return out
def block():
    n = int(SR * 0.1); out = []
    for i in range(n):
        t = i / SR
        v = (math.sin(2 * math.pi * 1800 * t) + 0.6 * math.sin(2 * math.pi * 2710 * t) + 0.4 * random.uniform(-1, 1)) * 12000
        out.append(clip(v * math.exp(-i / (SR * 0.02))))
    return out
def swish():
    n = int(SR * 0.16); out = []; lp = 0
    for i in range(n):
        t = i / n
        a = 0.15 + 0.8 * math.sin(math.pi * t)
        nz = random.uniform(-1, 1); lp = lp * (0.85 - 0.5 * t) + nz * (0.15 + 0.5 * t)
        out.append(clip(lp * 26000 * a * (1 - t)))
    return out
def thud():
    n = int(SR * 0.3); out = []; ph = 0; lp = 0
    for i in range(n):
        ph += 2 * math.pi * (40 + 50 * math.exp(-i / (SR * 0.05))) / SR
        nz = random.uniform(-1, 1); lp = lp * 0.9 + nz * 0.1
        out.append(clip((math.sin(ph) * 26000 + lp * 30000) * env(i, n, 0.001, 1.8)))
    return out
def splash():
    n = int(SR * 0.6); out = []; lp = 0
    for i in range(n):
        t = i / n
        nz = random.uniform(-1, 1); lp = lp * 0.55 + nz * 0.45
        bub = math.sin(2 * math.pi * (300 + 200 * math.sin(i * 0.002)) * i / SR) * 0.3
        out.append(clip((lp + bub * (t > 0.2)) * 24000 * min(1, i / (SR * 0.01)) * (1 - t) ** 1.5))
    return out
def gong():
    n = int(SR * 0.9); out = []
    parts = [(220, 1.0), (331, 0.6), (467, 0.45), (603, 0.3), (859, 0.2)]
    for i in range(n):
        t = i / SR
        v = sum(a * math.sin(2 * math.pi * f * t) for f, a in parts) * 9000
        out.append(clip(v * min(1, i / (SR * 0.003)) * math.exp(-t * 3.0)))
    return out

SAMPLES = [  # name, data, loop
    ("saw", wave_saw(), True), ("square", wave_square(), True), ("tri", wave_tri(), True),
    ("kick", kick(), False), ("snare", snare(), False), ("hat", hat(), False),
    ("hit", hit(False), False), ("hithv", hit(True), False), ("block", block(), False),
    ("swish", swish(), False), ("thud", thud(), False), ("splash", splash(), False), ("gong", gong(), False),
]
SIDX = {s[0]: i for i, s in enumerate(SAMPLES)}

# sound effects: name -> (sample, pitch, volume, voice)
SFX = [
    ("SWISH", "swish", 0x0800, 70, 4),
    ("HIT", "hit", 0x0800, 100, 5),
    ("HITHV", "hithv", 0x0800, 112, 5),
    ("BLOCK", "block", 0x0800, 90, 6),
    ("THUD", "thud", 0x0800, 100, 6),
    ("SPLASH", "splash", 0x0800, 100, 7),
    ("GONG", "gong", 0x0800, 110, 7),
    ("SELECT", "block", 0x0C00, 70, 7),
    ("CONFIRM", "gong", 0x1000, 80, 7),
    ("COMBO", "gong", 0x1600, 120, 7),
    ("BREAKER", "hithv", 0x0500, 127, 7),
]

# ------------------------------------------------------------------ music (16th-note rows, 4 channels)
NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}
def nn(s):          # "A2" -> note number (C1 = 1)
    name, octv = s[:-1], int(s[-1])
    return (octv - 1) * 12 + NOTE[name] + 1
def pitch_of(n):    # waveforms are 32 samples long: 1000 Hz at $1000
    f = 32.703 * 2 ** ((n - 1) / 12)
    return min(0x3FFF, int(round(f / 1000 * 4096)))

def fight_song():
    rows = []
    prog = ["A", "F", "G", "E"]           # Am F G Em
    lead = [  # one bar each, 16 steps: (step, note) ; 0 = key off
        [(0, "E5"), (3, "D5"), (6, "C5"), (8, "D5"), (10, "E5"), (12, "A4"), (15, 0)],
        [(0, "F5"), (3, "E5"), (6, "C5"), (8, "A4"), (12, "C5"), (14, "D5")],
        [(0, "D5"), (3, "B4"), (6, "G4"), (8, "B4"), (10, "D5"), (12, "G5"), (15, 0)],
        [(0, "E5"), (2, "B4"), (4, "G#4"), (6, "B4"), (8, "E5"), (10, "G#5"), (12, "B5"), (14, 0)],
    ]
    lead2 = [
        [(0, "A5"), (2, "G5"), (4, "E5"), (6, "G5"), (8, "A5"), (11, "C6"), (14, "B5")],
        [(0, "A5"), (4, "F5"), (6, "A5"), (8, "C6"), (12, "A5"), (14, "F5")],
        [(0, "G5"), (2, "D5"), (4, "B4"), (6, "D5"), (8, "G5"), (12, "B5"), (14, "D6")],
        [(0, "B5"), (4, "G#5"), (8, "E5"), (12, "B4"), (15, 0)],
    ]
    for part in range(4):
        L = lead if part % 2 == 0 else lead2
        for bar in range(4):
            root = prog[bar]
            low = root + "2"
            for st in range(16):
                r = [0, 0, 0, 0]
                # bass: driving 8ths with octave jumps
                if st % 2 == 0:
                    r[0] = nn(low) + (12 if st in (6, 14) else 0)
                # lead (silent on the first pass of part 0 for an intro feel)
                for s, note in L[bar]:
                    if s == st and not (part == 0 and bar < 2):
                        r[1] = 0x80 if note == 0 else nn(note)
                # drums: 1 kick, 2 snare, 3 hat
                if st in (0, 6, 8, 11) or (part == 3 and bar == 3 and st in (12, 13, 14, 15)): r[2] = 1
                elif st in (4, 12): r[2] = 2
                elif st % 2 == 0: r[2] = 3
                if part == 3 and bar == 3 and st >= 12: r[2] = 2
                # pad / arpeggio (triangle): chord tones on 8ths
                chord = {"A": ["A3", "C4", "E4"], "F": ["F3", "A3", "C4"], "G": ["G3", "B3", "D4"], "E": ["E3", "G3", "B3"]}[root]
                if part >= 1 and st % 4 == 2:
                    r[3] = nn(chord[(st // 4) % 3])
                rows.append(r)
    return rows

def title_song():
    rows = []
    prog = [("A", ["A3", "C4", "E4"]), ("F", ["F3", "A3", "C4"]), ("C", ["C4", "E4", "G4"]), ("G", ["G3", "B3", "D4"])]
    for rep in range(2):
        for root, ch in prog:
            for st in range(16):
                r = [0, 0, 0, 0]
                if st == 0: r[0] = nn(root + "2")
                if st == 8: r[0] = nn(root + "2") + 7 if root != "A" else nn("E2")
                arp = ch + [ch[1]]
                if st % 2 == 0: r[3] = nn(arp[(st // 2) % 4])
                if rep == 1:
                    if st in (0, 8): r[2] = 1
                    elif st == 12: r[2] = 2
                    elif st % 4 == 2: r[2] = 3
                rows.append(r)
    return rows

def victory_song():
    rows = []
    seq = [("A4", 2), ("C5", 2), ("E5", 2), ("A5", 6), ("G5", 2), ("A5", 10), (0, 8)]
    for note, ln in seq:
        for i in range(ln):
            r = [0, 0, 0, 0]
            if i == 0:
                r[1] = 0x80 if note == 0 else nn(note)
                if note: r[0] = nn("A2")
                r[2] = 1 if note else 0
            rows.append(r)
    rows.append([0xFF, 0, 0, 0])      # stop (no loop)
    return rows

# ------------------------------------------------------------------ driver
DRIVER = """
; zero page
cmd     .equ $00
song    .equ $01
rowl    .equ $02        ; current row pointer
rowh    .equ $03
loopl   .equ $04
looph   .equ $05
tick    .equ $06
speed   .equ $07
kon     .equ $08
koff    .equ $09
tmp     .equ $0A
playing .equ $0B
chn     .equ $0C
dspv    .equ $0D
vol     .equ $0E        ; CPU port 3: music level << 4 | effects level (0..10)
t2      .equ $0F
t3      .equ $10

start:
        mov x,#0
        mov a,#0
clr:    mov $00+x,a
        inc x
        cmp x,#$20
        bne clr
        ; DSP init
        mov $F2,#$6C
        mov $F3,#$20        ; FLG: unmute, no echo writes
        mov $F2,#$0C
        mov $F3,#$40        ; MVOL L
        mov $F2,#$1C
        mov $F3,#$40        ; MVOL R
        mov $F2,#$2C
        mov $F3,#$00
        mov $F2,#$3C
        mov $F3,#$00        ; EVOL
        mov $F2,#$4D
        mov $F3,#$00        ; EON
        mov $F2,#$3D
        mov $F3,#$00        ; NON
        mov $F2,#$2D
        mov $F3,#$00        ; PMON
        mov $F2,#$5D
        mov $F3,#DIRPAGE    ; sample directory
        mov $F2,#$5C
        mov $F3,#$00        ; KOFF
        ; timer 0: 8 kHz / 80 = 100 Hz
        mov $FA,#80
        mov $F1,#$01
        mov a,$F4
        mov cmd,a
        mov speed,#6

main:   mov a,$F7
        mov vol,a
        mov a,$F4
        cmp a,cmd
        beq nocmd
        mov cmd,a
        mov a,$F5
        call sfx
nocmd:  mov a,$F6
        cmp a,song
        beq nosong
        mov song,a
        call newsong
nosong: mov a,$FD
        beq main
        call music
        bra main

; ---- sound effect: A = id (0..)
sfx:    mov x,a
        asl a
        asl a
        asl a
        mov y,a                 ; y = id * 8
        mov a,!sfxtab+y         ; voice (0..7)
        xcn a                   ; * 16 -> DSP voice base
        mov dspv,a
        mov $F2,a               ; VOL L
        mov a,!sfxtab+1+y
        call sscale
        mov $F3,a
        inc $F2                 ; VOL R
        mov $F3,a
        inc $F2                 ; PITCH L
        mov a,!sfxtab+2+y
        mov $F3,a
        inc $F2                 ; PITCH H
        mov a,!sfxtab+3+y
        mov $F3,a
        inc $F2                 ; SRCN
        mov a,!sfxtab+4+y
        mov $F3,a
        inc $F2                 ; ADSR1 = 0 -> GAIN
        mov $F3,#$00
        inc $F2
        inc $F2                 ; GAIN
        mov $F3,#$7F
        mov $F2,#$5C
        mov $F3,#$00            ; clear KOFF
        mov $F2,#$4C            ; KON
        mov a,!sfxtab+5+y
        mov $F3,a
        ret

; ---- start a song: A = song id (0 stops)
newsong:
        mov playing,#0
        mov $F2,#$5C
        mov $F3,#$0F            ; key off music voices
        cmp a,#0
        beq ns_done
        asl a
        mov y,a
        mov a,!songtab-2+y
        mov rowl,a
        mov loopl,a
        mov a,!songtab-1+y
        mov rowh,a
        mov looph,a
        mov a,!speedtab-1+y     ; (y = id*2: use odd slots)
        mov speed,a
        mov tick,#0
        mov playing,#1
ns_done:
        ret

; ---- sequencer: one row every 'speed' timer ticks
music:  mov a,playing
        beq mu_done
        mov a,tick
        beq mu_row
        dec tick
mu_done:
        ret
mu_row: mov tick,speed
        dec tick
        mov kon,#0
        mov koff,#0
        mov $F2,#$5C
        mov $F3,#$00            ; release last row's key-offs
        mov y,#0
        mov a,[rowl]+y
        cmp a,#$FF
        bne mu_go
        mov playing,#0          ; end (no loop)
        mov $F2,#$5C
        mov $F3,#$0F
        ret
mu_go:  mov chn,#0
mu_ch:  mov y,chn
        mov a,[rowl]+y
        beq mu_next
        cmp a,#$80
        bne mu_note
        mov a,chn
        call bitof
        or a,koff
        mov koff,a
        bra mu_next
mu_note:
        call note
mu_next:
        inc chn
        mov a,chn
        cmp a,#4
        bne mu_ch
        mov $F2,#$5C
        mov a,koff
        mov $F3,a
        mov $F2,#$4C
        mov a,kon
        mov $F3,a
        ; advance (4 bytes per row), loop at the $FE marker
        clrc
        mov a,rowl
        adc a,#4
        mov rowl,a
        mov a,rowh
        adc a,#0
        mov rowh,a
        mov y,#0
        mov a,[rowl]+y
        cmp a,#$FE
        bne mu_ok
        mov rowl,loopl
        mov rowh,looph
mu_ok:  ret

; A = 1 << chn
bitof:  mov x,a
        mov a,#1
        cmp x,#0
        beq bo_done
bo_lp:  asl a
        dec x
        bne bo_lp
bo_done:
        ret

; key on note A for channel chn (0 bass, 1 lead, 2 drums, 3 arp)
note:   mov tmp,a
        mov a,chn
        xcn a
        mov dspv,a
        mov x,chn
        mov a,chn
        cmp a,#2
        bne nt_tone
        ; drums: A = 1 kick / 2 snare / 3 hat
        mov a,tmp
        clrc
        adc a,#SKICKM1
        mov tmp,a               ; sample number
        mov a,dspv
        or a,#4
        mov $F2,a
        mov a,tmp
        mov $F3,a               ; SRCN
        mov a,dspv
        or a,#2
        mov $F2,a
        mov $F3,#$00
        inc $F2
        mov $F3,#$08            ; pitch $0800
        mov a,dspv
        mov $F2,a
        mov a,#DRUMVOL
        call mscale
        mov $F3,a
        inc $F2
        mov $F3,a
        mov a,dspv
        or a,#5
        mov $F2,a
        mov $F3,#$00            ; GAIN mode
        inc $F2
        inc $F2
        mov $F3,#$7F
        bra nt_kon
nt_tone:
        mov a,dspv
        or a,#2
        mov $F2,a
        mov a,tmp
        asl a
        mov y,a
        mov a,!pitchtab-2+y
        mov $F3,a
        inc $F2
        mov a,!pitchtab-1+y
        mov $F3,a
        inc $F2                 ; SRCN
        mov a,!chsrc+x
        mov $F3,a
        inc $F2                 ; ADSR1
        mov a,!chadsr1+x
        mov $F3,a
        inc $F2                 ; ADSR2
        mov a,!chadsr2+x
        mov $F3,a
        mov a,dspv
        mov $F2,a
        mov a,!chvol+x
        call mscale
        mov $F3,a
        inc $F2
        mov $F3,a
nt_kon: mov a,chn
        call bitof
        or a,kon
        mov kon,a
        ret

; volume scaling: A = volume -> A * level / 16 (keeps Y)
sscale: push y
        mov t2,a
        mov a,vol
        and a,#$0F
        bra scl
mscale: push y
        mov t2,a
        mov a,vol
        xcn a
        and a,#$0F
scl:    mov x,a
        mov a,!voltab+x
        mov y,a
        mov a,t2
        mul ya
        mov t2,a
        mov a,y
        xcn a
        and a,#$F0
        mov t3,a
        mov a,t2
        xcn a
        and a,#$0F
        or a,t3
        pop y
        ret
voltab:  .db 0, 2, 3, 5, 6, 8, 10, 11, 13, 14, 16, 16, 16, 16, 16, 16
chsrc:   .db SSAW, SSQUARE, 0, STRI
chadsr1: .db $DF, $CE, 0, $DF
chadsr2: .db $70, $B0, 0, $60
chvol:   .db 58, 40, 0, 30
"""

def build():
    os.makedirs(OUT, exist_ok=True)
    ORG = 0x0200
    DIRADDR = 0x0800
    syms = {"DIRPAGE": DIRADDR >> 8, "SSAW": SIDX["saw"], "SSQUARE": SIDX["square"], "STRI": SIDX["tri"],
            "SKICKM1": SIDX["kick"] - 1, "DRUMVOL": 60}
    # resolve .equ
    src = []
    for line in DRIVER.split("\n"):
        m = re.match(r"^\s*(\w+)\s+\.equ\s+\$([0-9A-Fa-f]+)", line)
        if m: syms[m.group(1)] = int(m.group(2), 16); continue
        src.append(line)
    src = "\n".join(src)
    # data placed after the driver: tables, then samples, then songs
    pitch = [pitch_of(n) for n in range(1, 97)]
    songs = [fight_song(), title_song(), victory_song()]
    speeds = [6, 9, 7]
    # first pass to size the code
    code, labels = assemble(src + "\nsfxtab:\nsongtab:\nspeedtab:\npitchtab:\n", ORG, dict(syms, **{"sfxtab": 0, "songtab": 0, "speedtab": 0, "pitchtab": 0}))
    tab_at = ORG + len(code) - 0
    # tables
    sfx_bytes = bytearray()
    for name, smp, p, vol, v in SFX:
        sfx_bytes += bytes([v, vol, p & 0xFF, p >> 8, SIDX[smp], 1 << v, 0, 0])
    pitch_bytes = b"".join(struct.pack("<H", p) for p in pitch)
    assert DIRADDR >= tab_at + len(sfx_bytes) + len(pitch_bytes) + 16, "driver overlaps the sample directory"
    # sample data after the directory
    dirbytes = bytearray(); sdata = bytearray()
    sbase = DIRADDR + 4 * len(SAMPLES)
    for name, data, loop in SAMPLES:
        b = brr_simple(list(data), loop)
        addr = sbase + len(sdata)
        dirbytes += struct.pack("<HH", addr, addr)
        sdata += b
    song_base = sbase + len(sdata)
    song_bytes = bytearray(); song_addrs = []
    for rows in songs:
        song_addrs.append(song_base + len(song_bytes))
        for r in rows: song_bytes += bytes(r)
        if rows[-1][0] != 0xFF: song_bytes += bytes([0xFE, 0, 0, 0])
    songtab = b"".join(struct.pack("<H", a) for a in song_addrs)
    speedtab = b"".join(bytes([s, s]) for s in speeds)
    # place tables right after code (before the directory at $0300 if they fit, else after songs)
    tables = bytearray()
    t_sfx = tab_at; tables += sfx_bytes
    t_song = tab_at + len(tables); tables += songtab
    t_speed = tab_at + len(tables); tables += speedtab
    t_pitch = tab_at + len(tables); tables += pitch_bytes
    if tab_at + len(tables) > DIRADDR:
        # move tables after the song data
        base = song_base + len(song_bytes)
        t_sfx = base; t_song = base + len(sfx_bytes); t_speed = t_song + len(songtab); t_pitch = t_speed + len(speedtab)
        after = True
    else:
        after = False
    code, labels = assemble(src, ORG, dict(syms, sfxtab=t_sfx, songtab=t_song, speedtab=t_speed, pitchtab=t_pitch))
    img = bytearray(0x10000)
    img[ORG:ORG + len(code)] = code
    if not after:
        img[tab_at:tab_at + len(tables)] = tables
    img[DIRADDR:DIRADDR + len(dirbytes)] = dirbytes
    img[sbase:sbase + len(sdata)] = sdata
    img[song_base:song_base + len(song_bytes)] = song_bytes
    end = song_base + len(song_bytes)
    if after:
        img[t_sfx:t_sfx + len(tables)] = tables
        end = t_sfx + len(tables)
    assert end < 0xFF00
    open(os.path.join(OUT, "spc.bin"), "wb").write(img[ORG:end])
    with open(os.path.join(OUT, "sound.inc"), "w") as f:
        f.write("SPC_LOAD = $%04X\nSPC_ENTRY = $%04X\nSPC_SIZE = %d\n" % (ORG, labels["start"], end - ORG))
        for i, s in enumerate(SFX): f.write("SFX_%s = %d\n" % (s[0], i))
        f.write("SONG_FIGHT = 1\nSONG_TITLE = 2\nSONG_WIN = 3\n")
    print("spc: driver %d bytes, samples %d bytes, songs %d bytes, image %d bytes" % (len(code), len(sdata), len(song_bytes), end - ORG))
    # preview wav of the fight song mix (rough) for sanity
    return labels

if __name__ == "__main__":
    build()
