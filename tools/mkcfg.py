#!/usr/bin/env python3
"""Writes build/snes.cfg: LoROM, NBANKS x 32 KB, FastROM addresses ($80+)."""
import sys, os
n = int(sys.argv[1]) if len(sys.argv) > 1 else 32
out = ["MEMORY {",
       "    ZP:    start = $0000, size = $0100, type = rw;",
       "    RAM:   start = $0100, size = $1D00, type = rw;",
       "    RAM7E: start = $7E2000, size = $E000, type = rw;"]
for b in range(n):
    out.append("    ROM%d: start = $%02X8000, size = $8000, fill = yes, fillval = $FF, file = %%O;" % (b, 0x80 + b))
out += ["}", "SEGMENTS {",
        "    ZEROPAGE: load = ZP, type = zp;",
        "    BSS: load = RAM, type = bss;",
        "    BSS7E: load = RAM7E, type = bss, optional = yes;",
        "    CODE: load = ROM0, start = $808000;",
        "    RODATA: load = ROM0;",
        "    HEADER: load = ROM0, start = $80FFC0;",
        "    VECTORS: load = ROM0, start = $80FFE0;"]
for b in range(1, n):
    out.append("    BANK%d: load = ROM%d, optional = yes;" % (b, b))
out.append("}")
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build", "snes.cfg"), "w").write("\n".join(out) + "\n")
