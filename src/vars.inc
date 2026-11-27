; ---------------------------------------------------------------- direct page
.segment "ZEROPAGE"
tmp0:   .res 2
tmp1:   .res 2
tmp2:   .res 2
tmp3:   .res 2
tmp4:   .res 2
tmp5:   .res 2
tmp6:   .res 2
tmp7:   .res 2
mA:     .res 1          ; signed 8x8 multiply operands
mB:     .res 1
mS:     .res 1
mBw:    .res 2          ; 16-bit operand for smul16x8
muA:    .res 2          ; unsigned 16x16 operands / 32-bit result
muB:    .res 2
mu32:   .res 4
jp:     .res 3          ; long pointer: current fighter's joint frame
bp:     .res 3          ; long pointer: current fighter's ball list
nmiFlag: .res 1
renderReady: .res 1
hudDirty: .res 1
camYaw: .res 2          ; 0..255 (high byte kept 0)
camX:   .res 2          ; camera position, hu relative to arena centre
camZ:   .res 2
camDist: .res 2
m7x:    .res 2
m7y:    .res 2
m7h:    .res 2
m7v:    .res 2
panX:   .res 2
loopCount: .res 2
frameCount: .res 2
pad:    .res 4          ; held  [p1, p2]
padP:   .res 4          ; newly pressed
padOld: .res 4
R0:     .res 2          ; per-fighter camera-space origin (right / forward), hu
F0:     .res 2
cD:     .res 1          ; cos/sin of (facing - camYaw)
sD:     .res 1
cA:     .res 1          ; cos/sin of camYaw
sA:     .res 1
yOff:   .res 2          ; per-fighter height offset (hu)
jIdx:   .res 2          ; joint output index (fighter*20)
nBall:  .res 2
palBase: .res 2
ballsLeft: .res 1
halfSz: .res 2
fastPad: .res 1
fast:   .res 1          ; joint fast path: 0 general, 1 / $FF side-on
sc:     .res 1
mp:     .res 3          ; long pointer: current move record
oi:     .res 2
tickN:  .res 1
npt:    .res 3          ; NMI-only long pointer
ntmp0:  .res 2          ; NMI-only scratch
ntmp1:  .res 2
ntmp2:  .res 2
palDirty: .res 1
dimLvl: .res 1          ; screen dim (0 = full brightness)
sndSeq: .res 1          ; opponent slot (0/2)

; ---------------------------------------------------------------- low WRAM
.segment "BSS"
oamBuf: .res 544
hudBuf: .res 256
; per fighter (index 0 / 2)
fX:     .res 4          ; position, hu relative to arena centre
fZ:     .res 4
fY:     .res 4          ; height above floor (hu), for launches/jumps
fFace:  .res 4          ; facing angle (byte, word slots)
fChar:  .res 4
fAnim:  .res 4
fFrame: .res 4          ; frame within animation
fTick:  .res 4
fPtr:   .res 6          ; 24-bit pointer to the current joint frame (3 bytes each)
fPal:   .res 4          ; palette set (0 normal, 1 alt costume)
; projected joints: 40 (2 fighters x 20)
jSX:    .res 80
jSY:    .res 80
jFW:    .res 80
; ball records (max 80): key, sx, sy, size, tile/attr
bKey:   .res 80
bSX:    .res 160
bSY:    .res 160
bSz:    .res 80
bAttr:  .res 160        ; tile (low 9 bits) | palette<<9
bucketN: .res 130
bucketS: .res 130
order:  .res 80
; ---- fighting engine (per fighter, word slots 0 / 2)
fState: .res 4
fTimer: .res 4
fMove:  .res 4
fLevel: .res 4
fHP:    .res 4
fVY:    .res 4
fYF:    .res 4
fXF:    .res 4
fZF:    .res 4
fPush:  .res 4
fPushA: .res 4
fHitDone: .res 4
fCrouch: .res 4
fGuard: .res 4
fWins:  .res 4
fVin:   .res 4
fVinP:  .res 4
fVinO:  .res 4
fBuf:   .res 4
fBufT:  .res 4
fSideD: .res 4
fDownT: .res 4
fAnimEnd: .res 4
fOldX:  .res 4
fOldZ:  .res 4
fAirHits: .res 4
aiT:    .res 4
aiHold: .res 4
aiPress: .res 4
demo:   .res 2
; ---- match / round
phase:  .res 2
phaseT: .res 2
roundNum: .res 2
timeSec: .res 2
secTick: .res 2
rng:    .res 2
hitStop: .res 2
sparkJ: .res 2
sparkT: .res 2
lastNmi: .res 2
lineAng: .res 2
dist:   .res 2
hudChg: .res 2
p2Human: .res 2
endKind: .res 2
winner: .res 2
msgBuf: .res 20
scene:  .res 2          ; 0 fight, 1 title (attract), 2 character select
gmode:  .res 2          ; 0 arcade (1P), 1 versus (2P)
ladder: .res 2          ; arcade: opponents beaten
selDone: .res 4
selT:   .res 2
msgBuf2: .res 20
; ---- Super FX frame pipeline
nB0:    .res 2
oamN:   .res 2
dlN:    .res 4
boxOX:  .res 4
boxOY:  .res 4
boxX0:  .res 4
boxX1:  .res 4
boxY0:  .res 4
boxY1:  .res 4
boxBW:  .res 4
boxW:   .res 4
boxH:   .res 4
fFlash: .res 4
backSetBit: .res 2
upState: .res 1
dl0:    .res 14 + 48 * 12
dl1:    .res 14 + 48 * 12
nM7x:   .res 2
nM7y:   .res 2
nM7h:   .res 2
nM7v:   .res 2
nPanX:  .res 2
nYaw:   .res 2
pYaw:   .res 2
dbgBusy: .res 2
curMinX: .res 2
curMaxX: .res 2
curMinY: .res 2
curMaxY: .res 2
trX:    .res 16
trY:    .res 16
trN:    .res 4
trI:    .res 4
slowmo: .res 2
bSX2:   .res 160
bSY2:   .res 160
bSz2:   .res 80
dbgUp:  .res 2
bShp:   .res 160
fFlip:  .res 4
shapeDirty: .res 1
; ---- jump / dash / strings
fAir:   .res 4          ; 1 while airborne from a jump
fJumpV: .res 4          ; horizontal jump drift (signed, along facing)
fAirAtk: .res 4         ; air attack used this jump
fTapT:  .res 4          ; double-tap window
fTapD:  .res 4          ; direction of the first tap
fDashV: .res 4          ; dash speed (signed)
fCombo: .res 4          ; hits in the current combo (attacker)
chainFrom: .res 2
comboT: .res 2
fUsed1: .res 4          ; moves used once in the current combo (bit per move)
fUsed2: .res 4          ; ... used twice (no more cancels into them)
fBreak: .res 4          ; combo breakers left this round
comboBuf: .res 32
aiLv:   .res 2
; ---- dizzy / finishers
fHist:  .res 4          ; last 4 input tokens (newest in the low byte of fHist)
fHist2: .res 4
fHistT: .res 4
finPhase: .res 2        ; 0 none, 1 dizzy, 2 finisher running, 3 finished
finSlot: .res 2         ; finishing fighter
finPtr: .res 2
finWait: .res 2
finHitF: .res 2
finHitOK: .res 2
camOrbit: .res 2
dimT:   .res 2
aiSeqI: .res 4
aiSeqT: .res 4
aiFinGo: .res 4
finOrb: .res 2
finP1: .res 2
finP2: .res 2
finP3: .res 2
fUsed3: .res 4
fBufV: .res 4          ; stick when the buffered button was pressed
; ---- menus / presentation
dispMode: .res 2        ; 0 fight display (Mode 7 + Super FX), 1 menu display
bright: .res 2          ; menu display brightness (0..15)
fadeLv: .res 24
fadeChg: .res 2
cgBuf:  .res 288
cgDirty: .res 2
scrDirty: .res 2
scrAttr: .res 2
cloudTab: .res 16
cl1:    .res 2
cl2:    .res 2
emX:    .res 24
emY:    .res 24
emV:    .res 24
emberOn: .res 2
mT:     .res 2
mSel:   .res 2
musLv:  .res 2
sfxLv:  .res 2
recs:   .res 32
recNew: .res 2
tTime:  .res 2
tCombos: .res 2
mlChar: .res 2
numBuf: .res 8
nameBuf: .res 16
paused: .res 2
pauseSel: .res 2
pauseSlot: .res 2
bandDirty: .res 2
.segment "BSS7E"
scrBuf: .res 32 * 28 * 2
bandBuf: .res 5 * 32 * 2
.segment "BSS"
