#!/bin/bash
# usage: run.sh script prefix frames  -> runs arena.sfc in the snes9x harness; prints frame stats
cd "$(dirname "$0")"
A=$(python3 -c "
import re
for l in open('../build/game.dbg'):
    if l.startswith('sym') and 'name=\"loopCount\"' in l:
        print('%X' % int(re.search(r'val=0x([0-9A-Fa-f]+)', l).group(1), 16)); break")
SNES_LOOPS=$A SNES_TRACE=/tmp/st.txt ../../tools/snestest ../arena.sfc $1 $2 $3 2>&1 | grep -v Map_
