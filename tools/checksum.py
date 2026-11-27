import sys
p = sys.argv[1]
d = bytearray(open(p, "rb").read())
# extended header (needed by Super FX carts): $FFBD = expansion RAM 64 KB
assert all(b == 0xFF for b in d[0x7FB0:0x7FC0]), "code runs into the extended header"
d[0x7FB0:0x7FC0] = b"AF" + b"ARNA" + bytes(7) + bytes([0x06, 0x00, 0x00])
d[0x7FDC:0x7FE0] = b"\xff\xff\x00\x00"
s = sum(d) & 0xFFFF
d[0x7FDC] = (s ^ 0xFFFF) & 0xFF; d[0x7FDD] = (s ^ 0xFFFF) >> 8
d[0x7FDE] = s & 0xFF; d[0x7FDF] = s >> 8
open(p, "wb").write(d)
