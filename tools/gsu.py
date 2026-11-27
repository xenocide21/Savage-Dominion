#!/usr/bin/env python3
"""Minimal Super FX (GSU) assembler.

Syntax (one instruction per line, ';' comments, 'label:' labels, 'NAME = value' constants):
  raw GSU ops:   stop nop cache lsr rol asr div2 ror swap not sex lob hib merge fmult lmult
                 plot rpix color cmode loop sbk getb ramb romb
                 to rN / from rN / with rN
                 add rN | add #n | adc rN | adc #n | sub rN | sub #n | sbc rN | cmp rN
                 and rN | and #n | bic rN | bic #n | or rN | or #n | xor rN | xor #n
                 mult rN | mult #n | umult rN | umult #n
                 inc rN | dec rN | ldw (rN) | ldb (rN) | stw (rN) | stb (rN)
                 ibt rN,#v | iwt rN,#v | lms rN,(addr) | sms (addr),rN | lm rN,(addr) | sm (addr),rN
                 link #n | jmp rN | ljmp rN
                 bra/bge/blt/bne/beq/bpl/bmi/bcc/bcs/bvc/bvs label
  3-operand sugar:  OP rD, rS, rN|#n   ->  [from rS] [to rD] OP rN|#n   (prefix omitted when r0)
  move rD,rS / moves rD,rS
  call label  ->  link #4 / iwt r15,#label / nop          ret -> jmp r11 / nop
  Branches, jmp, ljmp and loop get an automatic 'nop' in their delay slot unless the
  next line starts with '>' (then that instruction is the delay slot).
  .db / .dw data, .org addr, .align n
"""
import re, struct, sys

def reg(t):
    t = t.strip().lower()
    m = re.match(r"^r(\d+)$", t)
    if not m: raise ValueError("register expected: " + t)
    n = int(m.group(1)); assert 0 <= n <= 15
    return n

SIMPLE = {"stop": [0x00], "nop": [0x01], "cache": [0x02], "lsr": [0x03], "rol": [0x04],
          "loop": [0x3C], "plot": [0x4C], "rpix": [0x3D, 0x4C], "swap": [0x4D], "color": [0x4E],
          "cmode": [0x3D, 0x4E], "not": [0x4F], "merge": [0x70], "sbk": [0x90], "sex": [0x95],
          "asr": [0x96], "div2": [0x3D, 0x96], "ror": [0x97], "lob": [0x9E], "fmult": [0x9F],
          "lmult": [0x3D, 0x9F], "hib": [0xC0], "getb": [0xEF], "getc": [0xDF],
          "ramb": [0x3E, 0xDF], "romb": [0x3F, 0xDF]}
BR = {"bra": 0x05, "bge": 0x06, "blt": 0x07, "bne": 0x08, "beq": 0x09, "bpl": 0x0A, "bmi": 0x0B,
      "bcc": 0x0C, "bcs": 0x0D, "bvc": 0x0E, "bvs": 0x0F}
# op: (base, alt for register form, alt for immediate form)
ALU = {"add": (0x50, None, 0x3E), "adc": (0x50, 0x3D, 0x3F), "sub": (0x60, None, 0x3E),
       "sbc": (0x60, 0x3D, None), "cmp": (0x60, 0x3F, None), "and": (0x70, None, 0x3E),
       "bic": (0x70, 0x3D, 0x3F), "or": (0xC0, None, 0x3E), "xor": (0xC0, 0x3D, 0x3F),
       "mult": (0x80, None, 0x3E), "umult": (0x80, 0x3D, 0x3F)}

class Asm:
    def __init__(self, org):
        self.org = org

    def value(self, t, final):
        t = t.strip()
        try:
            v = eval(re.sub(r"\$([0-9A-Fa-f]+)", r"0x\1", t), {"__builtins__": {}}, self.syms)
            return int(v)
        except (NameError, TypeError):
            if final: raise
            return 0

    def expand(self, lines):
        """sugar -> plain ops; returns list of (kind, text, lineno)"""
        out = []
        for ln, line in lines:
            low = line.lower()
            m = re.match(r"^(\w+)\s+(r\d+)\s*,\s*(r\d+)\s*,\s*(.+)$", low)
            if m and m.group(1) in ALU:
                op, d, s, n = m.groups()
                if reg(s) != 0: out.append((ln, "from " + s))
                if reg(d) != 0: out.append((ln, "to " + d))
                out.append((ln, op + " " + n))
                continue
            m = re.match(r"^(\w+)\s+(r\d+)\s*,\s*(r\d+)$", low)
            if m and m.group(1) in ("lsr", "asr", "rol", "ror", "not", "sex", "lob", "hib", "swap", "div2"):
                op, d, s = m.groups()
                if reg(s) != 0: out.append((ln, "from " + s))
                if reg(d) != 0: out.append((ln, "to " + d))
                out.append((ln, op))
                continue
            if low.startswith("call "):
                out += [(ln, "link #4"), (ln, "iwt r15,#" + line.split(None, 1)[1]), (ln, ">nop")]
                continue
            m = re.match(r"^l(bge|blt|beq|bne|bpl|bmi|bcc|bcs|bvc|bvs)\s+(\w+)$", low)
            if m:
                inv = {"bge": "blt", "blt": "bge", "beq": "bne", "bne": "beq", "bpl": "bmi", "bmi": "bpl",
                       "bcc": "bcs", "bcs": "bcc", "bvc": "bvs", "bvs": "bvc"}[m.group(1)]
                self.lb = getattr(self, "lb", 0) + 1
                skip = "__lb%d" % self.lb
                tgt = line.split()[1]
                out += [(ln, inv + " " + skip), (ln, ">nop"), (ln, "iwt r15,#" + tgt), (ln, "nop"), (ln, "@" + skip)]
                continue
            if low == "ret":
                out += [(ln, "jmp r11"), (ln, ">nop")]
                continue
            out.append((ln, line))
        # delay slots
        res = []
        for i, (ln, line) in enumerate(out):
            res.append((ln, line.lstrip(">").strip()))
            op = line.lstrip(">").split()[0].lower() if line.strip() else ""
            if (op in BR or op in ("jmp", "ljmp", "loop")) and not line.startswith(">"):
                nxt = out[i + 1][1] if i + 1 < len(out) else ""
                if not nxt.startswith(">"):
                    res.append((ln, "nop"))
        return res

    def encode(self, line, pc, final):
        p = line.split(None, 1)
        op = p[0].lower(); arg = p[1].strip() if len(p) > 1 else ""
        if op in SIMPLE: return bytes(SIMPLE[op])
        if op == ".db": return bytes(self.value(x, final) & 0xFF for x in arg.split(","))
        if op == ".dw": return b"".join(struct.pack("<H", self.value(x, final) & 0xFFFF) for x in arg.split(","))
        if op in ("to", "from", "with"):
            return bytes([{"to": 0x10, "from": 0xB0, "with": 0x20}[op] | reg(arg)])
        if op in ("move", "moves"):
            d, s = [x.strip() for x in arg.split(",")]
            if op == "move": return bytes([0x20 | reg(s), 0x10 | reg(d)])
            return bytes([0x20 | reg(d), 0xB0 | reg(s)])
        if op in BR:
            tgt = self.value(arg, final)
            rel = tgt - (pc + 2)
            if final and not -128 <= rel <= 127: raise ValueError("branch out of range: " + line)
            return bytes([BR[op], rel & 0xFF])
        if op in ALU:
            base, altr, alti = ALU[op]
            if arg.startswith("#"):
                n = self.value(arg[1:], final)
                assert 0 <= n <= 15 or not final, line
                return bytes([alti, base | (n & 15)])
            n = reg(arg)
            if op in ("and", "or", "bic", "xor") : assert n != 0, line
            return bytes(([altr] if altr else []) + [base | n])
        if op in ("inc", "dec"):
            n = reg(arg); assert n <= 14
            return bytes([(0xD0 if op == "inc" else 0xE0) | n])
        if op in ("ldw", "ldb", "stw", "stb"):
            n = reg(arg.strip("() ")); assert n <= 11
            b = (0x40 if op[0] == "l" else 0x30) | n
            return bytes(([0x3D] if op[2] == "b" else []) + [b])
        if op in ("ibt", "iwt"):
            r, v = [x.strip() for x in arg.split(",", 1)]
            v = self.value(v.lstrip("#"), final)
            if op == "ibt":
                assert -128 <= v <= 255 or not final, line
                return bytes([0xA0 | reg(r), v & 0xFF])
            return bytes([0xF0 | reg(r)]) + struct.pack("<H", v & 0xFFFF)
        if op in ("lms", "lm"):
            r, a = [x.strip() for x in arg.split(",", 1)]
            a = self.value(a.strip("()"), final)
            if op == "lms":
                assert a % 2 == 0 and a < 0x200 or not final, line
                return bytes([0x3D, 0xA0 | reg(r), (a >> 1) & 0xFF])
            return bytes([0x3D, 0xF0 | reg(r)]) + struct.pack("<H", a & 0xFFFF)
        if op in ("sms", "sm"):
            a, r = [x.strip() for x in arg.split(",", 1)]
            a = self.value(a.strip("()"), final)
            if op == "sms":
                assert a % 2 == 0 and a < 0x200 or not final, line
                return bytes([0x3E, 0xA0 | reg(r), (a >> 1) & 0xFF])
            return bytes([0x3E, 0xF0 | reg(r)]) + struct.pack("<H", a & 0xFFFF)
        if op == "link":
            n = self.value(arg.lstrip("#"), final); assert 1 <= n <= 4
            return bytes([0x90 + n])
        if op in ("jmp", "ljmp"):
            n = reg(arg); assert 8 <= n <= 13
            return bytes(([0x3D] if op == "ljmp" else []) + [0x90 + n])
        raise ValueError("unknown instruction: " + line)

    def assemble(self, src, syms=None):
        self.syms = dict(syms or {})
        lines = []
        for i, raw in enumerate(src.split("\n")):
            line = raw.split(";")[0].rstrip()
            s = line.strip()
            if not s: continue
            m = re.match(r"^(\w+)\s*=\s*(.+)$", s)
            if m:
                self.syms[m.group(1)] = None; lines.append((i + 1, "=" + s)); continue
            while True:
                m = re.match(r"^(\w+):\s*(.*)$", s)
                if not m: break
                lines.append((i + 1, "@" + m.group(1))); s = m.group(2).strip()
            if s: lines.append((i + 1, s))
        body = []
        for ln, l in lines:
            if l[0] in "=@": body.append((ln, l))
        exp = self.expand([(ln, l) for ln, l in lines if l[0] not in "=@"])
        # re-merge labels/constants in order: expand() keeps relative order, so redo per line
        merged = []
        ei = 0
        for ln, l in lines:
            if l[0] in "=@":
                merged.append((ln, l))
            else:
                # take all expanded entries with this line number in order
                while ei < len(exp) and exp[ei][0] == ln:
                    merged.append(exp[ei]); ei += 1
        for final in (False, False, True):
            pc = self.org; out = bytearray()
            for ln, l in merged:
                try:
                    if l.startswith("="):
                        n, v = l[1:].split("=", 1); self.syms[n.strip()] = self.value(v, final); continue
                    if l.startswith("@"):
                        self.syms[l[1:]] = pc; continue
                    if l.startswith(".org"):
                        pc = self.value(l[4:], final); continue
                    if l.startswith(".align"):
                        a = self.value(l[6:], final)
                        while pc % a: out.append(0x01); pc += 1
                        continue
                    b = self.encode(l, pc, final)
                except Exception as e:
                    raise SystemExit("gsu asm line %d: %s: %s" % (ln, l, e))
                out += b; pc += len(b)
        return bytes(out), self.syms

if __name__ == "__main__":
    src = open(sys.argv[1]).read()
    org = int(sys.argv[2], 0)
    code, syms = Asm(org).assemble(src)
    open(sys.argv[3], "wb").write(code)
    print("gsu: %d bytes" % len(code))
