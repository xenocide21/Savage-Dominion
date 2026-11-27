#!/bin/bash
# usage: watch.sh script prefix frames "sym[+off] sym ..." -> per-frame values in w.txt
cd "$(dirname "$0")"
W=$(python3 - "$4" <<'PY'
import re,sys
syms={}
for l in open('../build/game.dbg'):
    if l.startswith('sym'):
        m=re.search(r'name="([^"]+)".*val=0x([0-9A-Fa-f]+)',l)
        if m: syms[m.group(1)]=int(m.group(2),16)
out=[]
for t in sys.argv[1].split():
    n,_,o=t.partition('+'); out.append('%X'%((syms[n]+int(o or 0))&0x1FFFF))
print(",".join(out))
PY
)
A=$(python3 -c "
import re
for l in open('../build/game.dbg'):
    if l.startswith('sym') and 'name=\"loopCount\"' in l:
        print('%X' % int(re.search(r'val=0x([0-9A-Fa-f]+)', l).group(1), 16)); break")
SNES_WATCH=$W SNES_WATCHOUT=w.txt SNES_LOOPS=$A ../../tools/snestest ../arena.sfc $1 $2 $3 2>&1 | grep -v Map_
