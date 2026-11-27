#!/bin/bash
# Build the SNES arena fighter.  Requires ca65/ld65 (cc65 suite), python3 + Pillow.
set -e
cd "$(dirname "$0")"
mkdir -p build preview
python3 tools/gen_assets.py
python3 tools/fighters.py
python3 tools/menu_art.py
python3 tools/spc.py
python3 tools/mkcfg.py 32                       # 1 MB LoROM
cd build
for f in ../src/main.s assets.s fighters.s menu_art.s; do
  ca65 --cpu 65816 -I . -I ../src --bin-include-dir . -g -o $(basename $f .s).o $f
done
ld65 -C snes.cfg --dbgfile game.dbg -m game.map -o ../arena.sfc *.o
cd ..
python3 tools/checksum.py arena.sfc
ls -la arena.sfc
