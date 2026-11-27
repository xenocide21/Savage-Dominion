; =============================================================================
; fighting engine: 60 Hz state machine per fighter, hit detection, rounds, AI
; Conventions: routines are entered with A 8-bit (like the rest of the code) unless
; marked .a16; X = fighter slot (0 / 2) for per-fighter routines.
; Virtual input (fVin): PAD_RIGHT = forward (toward opponent), PAD_LEFT = back,
; PAD_UP = jump, PAD_DOWN = crouch, R = guard, R+Up / R+Down = sidestep,
; double-tap forward / back = dash / backdash.
; =============================================================================
.macro MA16
        rep     #$20
        .a16
.endmacro
.macro MA8
        sep     #$20
        .a8
.endmacro

ST_NEUTRAL = 0
ST_SIDE    = 1
ST_ATTACK  = 2
ST_HIT     = 3
ST_BLOCK   = 4
ST_FALL    = 5
ST_AIR     = 6
ST_DOWN    = 7
ST_GETUP   = 8
ST_THROWN  = 9
ST_KO      = 10
ST_WIN     = 11
ST_RINGOUT = 12
ST_JUMP    = 13
ST_LAND    = 14
ST_DASH    = 15
ST_DIZZY   = 16
ST_FINISH  = 17         ; performing a finisher (scripted)
ST_FINISHED = 18        ; on the receiving end
JUMPV      = 1180       ; jump launch speed (1/256 hu per tick)
WALKF      = 440
WALKB      = 330
SIDEV      = 600

SC_FIGHT  = 0
SC_TITLE  = 1
SC_SELECT = 2

PH_INTRO = 0
PH_FIGHT = 1
PH_END   = 2
PH_MATCH = 3

HPMAX   = 208
GRAV    = 80            ; 1/256 hu per tick^2
FWD     = PAD_RIGHT
BACK    = PAD_LEFT
BUTTONS = PAD_Y | PAD_X | PAD_B | PAD_A | PAD_L

; move record (11 bytes, from fighters.py)
MR_ANIM = 0
MR_A0   = 1
MR_A1   = 2
MR_LVL  = 3
MR_DMG  = 4
MR_REACT = 5
MR_ADV  = 7
MR_AIR  = 6             ; 1 = air attack
MR_STEP = 8
MR_HJ   = 9
MR_TOTAL = 10

; ---------------------------------------------------------------- match setup
gameInit:
        .a8
        ldx     #0
        stx     fChar
        ldx     #3
        stx     fChar+2
        MA16
        lda     #$ACE1
        sta     rng
        stz     p2Human
        lda     #330
        sta     camDist
        lda     #10
        sta     musLv
        sta     sfxLv
        jsr     writeVol
        lda     #$FF
        sta     recNew
        jsr     toSplash
        MA8
        rts

newMatch:
        .a8
        lda     #1
        sta     palDirty
        sta     shapeDirty
        MA16
        lda     scene
        bne     :+
        lda     #SONG_FIGHT
        jsr     playSong
:       MA8
        MA16
        stz     fWins
        stz     fWins+2
        lda     #1
        sta     roundNum
        MA8
        ; fall through
newRound:
        .a8
        MA16
        lda     #.loword(-52)
        sta     fX
        lda     #52
        sta     fX+2
        ldx     #0
@f:     stz     fZ,x
        stz     fY,x
        stz     fXF,x
        stz     fZF,x
        stz     fYF,x
        stz     fVY,x
        stz     fPush,x
        stz     fState,x
        stz     fCrouch,x
        stz     fGuard,x
        stz     fBufT,x
        stz     fDownT,x
        stz     fVinO,x
        stz     fAir,x
        stz     fAirAtk,x
        stz     fJumpV,x
        stz     fTapT,x
        stz     fTapD,x
        stz     fCombo,x
        stz     fUsed1,x
        stz     fUsed2,x
        stz     fUsed3,x
        lda     #1
        sta     fBreak,x
        lda     #HPMAX
        sta     fHP,x
        lda     #AN_IDLE
        jsr     setAnim
        inx
        inx
        cpx     #4
        bne     @f
        stz     fFace
        lda     #128
        sta     fFace+2
        lda     #3
        sta     fFrame+2                ; desync the idle bob
        stz     phase
        stz     phaseT
        stz     hitStop
        stz     sparkT
        stz     comboT
        stz     comboBuf
        stz     finPhase
        stz     finOrb
        stz     camOrbit
        stz     dimT
        stz     aiSeqI
        stz     aiSeqI+2
        stz     aiFinGo
        stz     aiFinGo+2
        MA8
        stz     dimLvl
        MA16
        lda     #60
        sta     timeSec
        stz     secTick
        stz     camYaw
        lda     #1
        sta     hudChg
        MA8
        jsr     facing
        lda     lineAng
        sta     camYaw
        ldx     #2
        jsr     framePtr
        rts

; ---------------------------------------------------------------- per tick
gameTick:
        .a8
        MA16
        inc     frameCount
        jsr     rngStep
        lda     scene
        cmp     #SC_SPLASH
        bcc     :+
        jsr     menuSceneTick
        MA8
        rts
        .a16
:       lda     paused
        beq     :+
        jsr     pauseTick
        MA8
        rts
        .a16
:       lda     scene
        cmp     #SC_SELECT
        bne     :+
        jsr     selectTick
        bra     @anims
:       cmp     #SC_TITLE
        bne     :+
        lda     frameCount
        and     #$1F
        bne     :+
        inc     hudChg                  ; blink PRESS START
:       jsr     buildInputs
        lda     hitStop
        beq     :+
        dec     hitStop
        jmp     @cam
:       lda     slowmo
        beq     :+
        dec     slowmo
        lsr     a
        bcc     :+
        jmp     @cam                ; KO slow motion: every other tick
:       jsr     phaseLogic
        ldx     #0
        jsr     fighterTick
        ldx     #2
        jsr     fighterTick
        jsr     collide
        ldx     #0
        jsr     bounds
        ldx     #2
        jsr     bounds
        ldx     #0
        jsr     hitCheck
        ldx     #2
        jsr     hitCheck
        jsr     comboTick
        lda     finPhase
        cmp     #2
        bcc     :+
        lda     camOrbit
        clc
        adc     finOrb
        and     #$00FF
        sta     camOrbit
:       lda     dimT
        beq     @anims
        dec     dimT
        bne     @anims
        MA8
        stz     dimLvl
        MA16
@anims: ldx     #0
        jsr     animStep
        ldx     #2
        jsr     animStep
        lda     fFlash
        beq     :+
        dec     fFlash
:       lda     fFlash+2
        beq     :+
        dec     fFlash+2
:       lda     sparkT
        beq     @cam
        dec     sparkT
@cam:   MA8
        jsr     facing
        jsr     cameraFollow
        rts

rngStep:
        .a16
        lda     rng
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        eor     rng
        sta     rng
        lsr     a
        lsr     a
        lsr     a
        lsr     a
        lsr     a
        lsr     a
        lsr     a
        lsr     a
        lsr     a
        eor     rng
        sta     rng
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        eor     rng
        sta     rng
        rts

; ---------------------------------------------------------------- inputs
buildInputs:
        .a16
        lda     scene
        cmp     #SC_TITLE
        bne     @fight
        lda     padP
        ora     padP+2
        and     #PAD_START
        beq     @in
        lda     #SFX_CONFIRM
        jsr     playSfx
        stz     mSel
        jmp     toMenu
@fight: ; START: pause (P1; in 2 player either pad)
        lda     scene
        bne     @in
        lda     phase
        cmp     #PH_FIGHT
        bne     @in
        ldx     #0
        lda     padP
        and     #PAD_START
        bne     @pause
        lda     gmode
        cmp     #GM_VS
        bne     @in
        ldx     #2
        lda     padP+2
        and     #PAD_START
        beq     @in
@pause: stx     pauseSlot
        lda     #1
        sta     paused
        stz     pauseSel
        sta     hudChg
        lda     #SFX_SELECT
        jmp     playSfx
@in:    ; practice: SELECT leaves the dummy dizzy (finisher practice)
        lda     gmode
        cmp     #GM_PRACT
        bne     @in2
        lda     scene
        bne     @in2
        lda     padP
        and     #PAD_SEL
        beq     @in2
        lda     finPhase
        bne     @in2
        lda     fState+2
        bne     @in2
        ldx     #2
        jsr     tryDizzy
@in2:   ; slot 0: P1 pad (or the CPU in demo mode)
        lda     demo
        beq     :+
        ldx     #0
        jsr     aiThink
        bra     @p1
:       lda     pad
@p1:    ldx     phase
        cpx     #PH_FIGHT
        beq     :+
        lda     #0
:       ldx     #0
        jsr     setVin
        ; slot 2: P2 pad (left/right swapped: P2 stands on the right) or the CPU
        lda     p2Human
        beq     @cpu
        lda     pad+2
        sta     tmp0
        and     #.loword(~(PAD_LEFT | PAD_RIGHT))
        sta     tmp1
        lda     tmp0
        and     #PAD_RIGHT
        asl     a
        ora     tmp1
        sta     tmp1
        lda     tmp0
        and     #PAD_LEFT
        lsr     a
        ora     tmp1
        bra     @p2
@cpu:   lda     gmode
        cmp     #GM_PRACT
        bne     :+
        lda     scene
        bne     :+
        lda     #0                      ; practice dummy: never fights back
        bra     @p2
:       ldx     #2
        jsr     aiThink
@p2:    ldx     phase
        cpx     #PH_FIGHT
        beq     :+
        lda     #0
:       ldx     #2
        ; fall through
setVin:
        .a16
        sta     fVin,x
        eor     fVinO,x
        and     fVin,x
        sta     fVinP,x
        lda     fVin,x
        sta     fVinO,x
        jsr     histPush
        ; buffer attack presses
        lda     fVinP,x
        and     #BUTTONS
        beq     :+
        sta     fBuf,x
        lda     fVin,x
        sta     fBufV,x
        lda     #12
        sta     fBufT,x
:       rts

; ---------------------------------------------------------------- fighter state machine
fighterTick:
        .a16
        lda     fX,x
        sta     fOldX,x
        lda     fZ,x
        sta     fOldZ,x
        lda     fBufT,x
        beq     :+
        dec     fBufT,x
:       lda     fTapT,x
        beq     :+
        dec     fTapT,x
:       ; knockback slide along fPushA
        lda     fPush,x
        beq     :++
        ldy     fPushA,x
        jsr     addPos
        lda     fPush,x
        sec
        sbc     #22
        bpl     :+
        lda     #0
:       sta     fPush,x
:       lda     finPhase
        cmp     #1
        bne     :+
        jsr     finCheck
        bcc     :+
        rts
:       lda     fState,x
        asl     a
        tay
        lda     stateTab,y
        sta     tmp6
        jmp     (tmp6)

stateTab:
        .word   .loword(stNeutral), .loword(stSide), .loword(stAttack), .loword(stHit), .loword(stBlock), .loword(stFall), .loword(stAir)
        .word   .loword(stDown), .loword(stGetup), .loword(stThrown), .loword(stKO), .loword(stWin), .loword(stRingout)
        .word   .loword(stJump), .loword(stHit), .loword(stDash)
        .word   .loword(stDizzy), .loword(stFinish), .loword(stFinished)

stNeutral:
        .a16
        stz     fGuard,x
        jsr     turnToward
        jsr     tryAttack
        bcc     :+
        rts
:       ; R + Up / Down: sidestep in / out
        lda     fVin,x
        and     #PAD_R
        beq     @noR
        lda     fVinP,x
        and     #PAD_UP
        beq     :+
        lda     #1
        jmp     startSide
:       lda     fVinP,x
        and     #PAD_DOWN
        beq     @noR
        lda     #.loword(-1)
        jmp     startSide
@noR:   ; Up: jump (with the forward / back held as drift)
        lda     fVinP,x
        and     #PAD_UP
        beq     :+
        jmp     startJump
:       ; double-tap forward / back: dash
        lda     fVinP,x
        and     #(FWD | BACK)
        beq     @noTap
        cmp     fTapD,x
        bne     :+
        ldy     fTapT,x
        beq     :+
        stz     fTapT,x
        stz     fTapD,x
        jmp     startDash
:       sta     fTapD,x
        lda     #14
        sta     fTapT,x
@noTap: lda     fVin,x
        and     #PAD_DOWN
        beq     @stand
        lda     #1
        sta     fCrouch,x
        lda     fVin,x
        and     #(BACK | PAD_R)
        beq     :+
        lda     #1
        sta     fGuard,x
        lda     #AN_CGUARD
        jmp     wantAnim
:       lda     #AN_CROUCH
        jmp     wantAnim
@stand: stz     fCrouch,x
        lda     fVin,x
        and     #PAD_R
        beq     :+
        lda     #1
        sta     fGuard,x
        lda     #AN_GUARD
        jmp     wantAnim
:       lda     fVin,x
        and     #BACK
        beq     :+
        lda     #1
        sta     fGuard,x
        lda     #.loword(-WALKB)
        jsr     walkSelf
        lda     #AN_WALKB
        jmp     wantAnim
:       lda     fVin,x
        and     #FWD
        beq     :+
        lda     #WALKF
        jsr     walkSelf
        lda     #AN_WALKF
        jmp     wantAnim
:       lda     #AN_IDLE
        ; fall through
wantAnim:
        .a16
        cmp     fAnim,x
        beq     :+
        jmp     setAnim
:       rts

; A = +1 (into the screen) / -1 (out of the screen)
startSide:
        .a16
        sta     fSideD,x
        lda     #ST_SIDE
        sta     fState,x
        lda     #13
        sta     fTimer,x
        stz     fCrouch,x
        lda     #AN_SIDESTEP
        jmp     setAnim

stSide:
        .a16
        jsr     turnToward
        jsr     tryAttack
        bcc     :+
        rts
:       ; local +z = into the screen for the left fighter; flip for the right one
        lda     fSideD,x
        cpx     #0
        beq     :+
        eor     #$FFFF
        inc     a
:       sta     tmp0
        lda     fFace,x
        sec
        sbc     #64
        and     #$00FF
        tay
        lda     #SIDEV
        bit     tmp0
        bpl     :+
        lda     #.loword(-SIDEV)
:       jsr     addPos
        dec     fTimer,x
        bne     @done
        lda     fVin,x                  ; holding R + the direction keeps circling
        and     #PAD_R
        beq     :+
        lda     #PAD_UP
        ldy     fSideD,x
        bpl     @hd
        lda     #PAD_DOWN
@hd:    and     fVin,x
        beq     :+
        lda     #13
        sta     fTimer,x
        rts
:       stz     fState,x
@done:  rts

; carry set if an attack started (from the input buffer).
; tryChain: same, but only string follow-ups of the current move (fMove)
tryChain:
        .a16
        lda     fMove,x
        jsr     pickMove
        bcs     startBuf
        rts
tryAttack:
        .a16
        lda     #$FF
        jsr     pickMove
        bcs     startBuf
        rts
startBuf:
        .a16
        stz     fBufT,x
        jsr     startAttack
        sec
        rts
; after a connecting hit: a string follow-up, or ANY ground move this combo
; hasn't used twice yet
tryCancel:
        .a16
        jsr     tryChain
        bcc     :+
        rts
:       lda     #$FF
        jsr     pickMove
        bcc     @no
        sta     tmp4
        asl     a
        tay
        lda     bitTab,y
        sta     tmp5
        lda     fChar,x
        and     #$00FF
        asl     a
        tay
        lda     cancTab,y
        and     tmp5
        beq     @no
        lda     fUsed3,x
        and     tmp5
        bne     @no
        lda     tmp4
        bra     startBuf
@no:    clc
        rts
bitTab: .word   1, 2, 4, 8, $10, $20, $40, $80, $100, $200, $400, $800, $1000, $2000, $4000, $8000
cancTab: .word  CH0_CANC, CH1_CANC, CH2_CANC, CH3_CANC, CH4_CANC, CH5_CANC

; A = chain-from move ($FF none) -> carry set, A = move id (from the input buffer)
pickMove:
        .a16
        sta     chainFrom
        lda     fBufT,x
        bne     :+
        clc
        rts
:       ; button code: L 5, Y 1, X 2, B 3, A 4
        lda     fBuf,x
        ldy     #5
        bit     #PAD_L
        bne     @dir
        ldy     #1
        bit     #PAD_Y
        bne     @dir
        ldy     #2
        bit     #PAD_X
        bne     @dir
        ldy     #3
        bit     #PAD_B
        bne     @dir
        ldy     #4
@dir:   sty     tmp0
        ; direction: air 4, d 3 (down held or crouching), f 1, b 2, none 0
        ldy     #0
        lda     chainFrom
        cmp     #$FF
        bne     @have                   ; strings ignore the stick
        ldy     #4
        lda     fAir,x
        bne     @have
        ldy     #3
        lda     fCrouch,x
        bne     @have
        lda     fBufV,x                 ; the stick as it was when the button went in
        ora     fVin,x
        bit     #PAD_DOWN
        bne     @have
        ldy     #1
        bit     #FWD
        bne     @have
        ldy     #2
        bit     #BACK
        bne     @have
        ldy     #0
@have:  sty     tmp1
        jsr     findMove
        bcs     @go
        lda     tmp1
        beq     @none
        cmp     #4
        beq     @none                   ; nothing in the air for this button
        stz     tmp1
        jsr     findMove
        bcs     @go
@none:  clc
        rts
@go:    sec
        rts

; tmp0 = button code, tmp1 = dir, chainFrom -> carry set, A = move id
; (per-character input table: button, dir, from-move ($FF = none), move; 0 ends)
findMove:
        .a16
        lda     fChar,x
        and     #$00FF
        asl     a
        tay
        lda     inTab,y
        sta     tmp2
        ldy     #0
@lp:    lda     (tmp2),y                ; lo = button, hi = dir
        and     #$00FF
        beq     @no
        cmp     tmp0
        bne     @next
        iny
        lda     (tmp2),y
        dey
        and     #$00FF
        cmp     tmp1
        bne     @next
        iny
        iny
        lda     (tmp2),y
        dey
        dey
        and     #$00FF
        cmp     chainFrom
        bne     @next
        iny
        iny
        iny
        lda     (tmp2),y
        and     #$00FF
        sec
        rts
@next:  iny
        iny
        iny
        iny
        bra     @lp
@no:    clc
        rts
inTab:  .word   .loword(ch0_inputs), .loword(ch1_inputs), .loword(ch2_inputs)
        .word   .loword(ch3_inputs), .loword(ch4_inputs), .loword(ch5_inputs)

; A = move id
startAttack:
        .a16
        sta     fMove,x
        jsr     setMovePtr
        ldy     #MR_LVL
        lda     [mp],y
        and     #$00FF
        sta     fLevel,x
        ldy     #MR_ANIM
        lda     [mp],y
        and     #$00FF
        jsr     setAnim
        lda     #ST_ATTACK
        sta     fState,x
        stz     fHitDone,x
        stz     fTimer,x
        stz     fDownT,x
        stz     fGuard,x
        stz     fCrouch,x
        lda     #SFX_SWISH
        jmp     playSfx

; mp = this fighter's move record
setMovePtr:
        .a16
        lda     fMove,x
        sta     tmp0
        asl     a
        asl     a
        asl     a
        clc
        adc     tmp0
        adc     tmp0
        adc     tmp0                    ; *11
        sta     tmp0
        lda     fChar,x
        and     #$00FF
        asl     a
        asl     a
        tay
        lda     moveTab,y
        clc
        adc     tmp0
        sta     mp
        MA8
        lda     moveTab+2,y
        sta     mp+2
        MA16
        rts
moveTab: .faraddr ch0_move
        .byte   0
        .faraddr ch1_move
        .byte   0
        .faraddr ch2_move
        .byte   0
        .faraddr ch3_move
        .byte   0
        .faraddr ch4_move
        .byte   0
        .faraddr ch5_move
        .byte   0

stAttack:
        .a16
        inc     fTimer,x
        jsr     setMovePtr
        lda     fAir,x
        beq     @ground
        ; air attack: keep flying
        jsr     jumpPhys
        bcc     :+
        lda     #10                     ; landing recovery after an air attack
        jmp     toLand
:       lda     fAnimEnd,x
        beq     :+
        lda     #ST_JUMP
        sta     fState,x
        lda     #AN_JUMP
        jmp     setAnim
:       rts
@ground:
        lda     fHitDone,x
        cmp     #2
        bne     :+
        jsr     tryCancel               ; it connected: cancel into the next hit
        bcc     :+
        rts
:       ; lunge forward until the active window ends
        ldy     #MR_A1
        lda     [mp],y
        and     #$00FF
        cmp     fFrame,x
        bcc     @late
        beq     @late
        ldy     #MR_STEP
        lda     [mp],y
        and     #$00FF
        beq     @end
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        jsr     walkSelf
        bra     @end
@late:  ; strings: from the end of the active window the next hit can cancel in
        jsr     tryChain
        bcc     @end
        rts
@end:   lda     fAnimEnd,x
        beq     :+
        stz     fState,x
        jsr     tryAttack               ; buffered follow-up
:       rts

; ---------------------------------------------------------------- jump / dash
startJump:
        .a16
        lda     #ST_JUMP
        sta     fState,x
        lda     #1
        sta     fAir,x
        stz     fAirAtk,x
        stz     fCrouch,x
        stz     fGuard,x
        stz     fTapT,x
        lda     #JUMPV
        sta     fVY,x
        lda     fVin,x
        ldy     #0
        bit     #FWD
        beq     :+
        ldy     #420
:       bit     #BACK
        beq     :+
        ldy     #.loword(-330)
:       tya
        sta     fJumpV,x
        lda     #SFX_SWISH
        jsr     playSfx
        lda     #AN_JUMP
        jmp     setAnim

stJump:
        .a16
        jsr     turnToward
        lda     fAirAtk,x
        bne     :+
        jsr     tryAttack
        bcc     :+
        lda     #1
        sta     fAirAtk,x
        rts
:       jsr     jumpPhys
        bcc     :+
        lda     #4
        jmp     toLand
:       rts

; drift + gravity; carry set on landing
jumpPhys:
        .a16
        lda     fJumpV,x
        beq     :+
        jsr     walkSelf
:       jmp     airPhys

; A = landing recovery ticks
toLand:
        .a16
        sta     fTimer,x
        stz     fAir,x
        stz     fY,x
        stz     fVY,x
        lda     #ST_LAND
        sta     fState,x
        lda     #AN_CROUCH
        jmp     setAnim


; ---------------------------------------------------------------- dizzy / finishers
; input history: each newly pressed direction / button becomes a token (F 1, B 2,
; D 3, Y 4, X 5, B 6, A 7, L 8) shifted into fHist2:fHist; 40 idle ticks clear it
histPush:
        .a16
        lda     fHistT,x
        inc     a
        sta     fHistT,x
        cmp     #40
        bcc     :+
        stz     fHist,x
        stz     fHist2,x
:       lda     fVinP,x
        bne     :+
        rts
:       sta     tmp0
        ldy     #0
@lp:    lda     tmp0
        and     histBits,y
        beq     @n
        tya
        lsr     a
        inc     a
        sta     tmp1
        lda     fHist2,x
        xba
        and     #$FF00
        sta     fHist2,x
        lda     fHist,x
        xba
        and     #$00FF
        ora     fHist2,x
        sta     fHist2,x
        lda     fHist,x
        xba
        and     #$FF00
        ora     tmp1
        sta     fHist,x
        stz     fHistT,x
@n:     iny
        iny
        cpy     #16
        bne     @lp
        rts
histBits: .word FWD, BACK, PAD_DOWN, PAD_Y, PAD_X, PAD_B, PAD_A, PAD_L

; X = fighter whose HP just hit 0.  Match-deciding KO -> dizzy at a sliver of health.
tryDizzy:
        .a16
        lda     finPhase
        bne     @no
        lda     phase
        cmp     #PH_FIGHT
        bne     @no
        txa
        eor     #2
        tay
        lda     gmode
        cmp     #GM_PRACT
        beq     :+                      ; practice: finishers any time
        lda     fWins,y
        cmp     #1
        bne     @no
:       lda     #0
        sta     fBufT,y                 ; the attacker's queued follow-ups are dropped
        lda     #1
        sta     fHP,x
        sta     finPhase
        lda     #ST_DIZZY
        sta     fState,x
        lda     #300
        sta     fTimer,x
        stz     fY,x
        stz     fVY,x
        stz     fAir,x
        stz     fPush,x
        stz     fCrouch,x
        stz     fGuard,x
        lda     #AN_DIZZY
        jsr     setAnim
        lda     #14
        sta     hitStop
        lda     #8
        sta     fFlash,x
        lda     #SFX_GONG
        jsr     playSfx
        phx
        ldy     #.loword(txtFinish)
        jsr     setMsg
        plx
        sec
        rts
@no:    clc
        rts

stDizzy:
        .a16
        dec     fTimer,x
        bne     :+
        stz     fHP,x                   ; nobody finished them: they drop
        ldy     #0
        phx
        jsr     setMsg
        plx
        jmp     toDown
:       rts

; X = fighter (finPhase 1): finisher code entered in range? -> carry set, started
finCheck:
        .a16
        txa
        eor     #2
        tay
        lda     fState,y
        cmp     #ST_DIZZY
        bne     @no
        lda     fState,x
        cmp     #ST_NEUTRAL
        beq     @ok
        cmp     #ST_SIDE
        beq     @ok
        cmp     #ST_DASH
        beq     @ok
        cmp     #ST_ATTACK
        bne     @no
@ok:    lda     dist
        bpl     :+
        eor     #$FFFF
        inc     a
:       cmp     #90
        bcs     @no
        lda     fChar,x
        and     #$00FF
        asl     a
        tay
        lda     finLoTab,y
        cmp     fHist,x
        bne     @no
        lda     finHiTab,y
        cmp     fHist2,x
        bne     @no
        jsr     startFinisher
        sec
        rts
@no:    clc
        rts

startFinisher:
        .a16
        stx     finSlot
        lda     #2
        sta     finPhase
        stz     fHist,x
        stz     fHist2,x
        stz     fBufT,x
        stz     fCombo,x
        stz     fCrouch,x
        stz     fGuard,x
        stz     fAir,x
        stz     fY,x
        stz     fVY,x
        lda     #ST_FINISH
        sta     fState,x
        txa
        eor     #2
        tay
        lda     #ST_FINISHED
        sta     fState,y
        lda     #0
        sta     fAir,y
        lda     fChar,x
        and     #$00FF
        asl     a
        tay
        lda     finTab,y
        sta     finPtr
        stz     finWait
        lda     #$FF
        sta     finHitF
        lda     #SFX_CONFIRM
        jmp     playSfx

stFinish:
        .a16
        jsr     turnToward
        lda     fAir,x
        beq     @gnd
        jsr     jumpPhys
        bcc     @act
        stz     fAir,x
        lda     #AN_IDLE
        jsr     setAnim
        bra     @act
@gnd:   lda     dist                    ; stay on top of the victim
        bpl     :+
        eor     #$FFFF
        inc     a
:       cmp     #44
        bcc     @act
        lda     #520
        jsr     walkSelf
@act:   lda     finHitF
        cmp     fFrame,x
        bne     :+
        lda     finHitOK
        bne     :+
        inc     finHitOK
        jsr     finHit
:       lda     finWait
        beq     finStep
        dec     finWait
        beq     finStep
        rts

; run script steps until one takes time.  X = finisher
finStep:
        .a16
        ldy     finPtr
        lda     a:1,y
        and     #$00FF
        sta     finP1
        lda     a:2,y
        and     #$00FF
        sta     finP2
        lda     a:3,y
        and     #$00FF
        sta     finP3
        lda     a:0,y
        and     #$00FF
        cmp     #10
        bcc     :+
        lda     #0
:       asl     a
        tay
        lda     finOps,y
        sta     tmp6
        lda     finPtr
        clc
        adc     #4
        sta     finPtr
        txa
        eor     #2
        tay                             ; Y = victim
        jmp     (tmp6)
finOps: .word   .loword(fopEnd), .loword(fopAnim), .loword(fopWait), .loword(fopDim), .loword(fopLaunch)
        .word   .loword(fopJump), .loword(fopSlow), .loword(fopName), .loword(fopFinal), .loword(fopOrbit)

fopEnd: lda     finPtr
        sec
        sbc     #4
        sta     finPtr
        lda     #60
        sta     finWait
        rts
fopAnim:
        lda     finP1
        jsr     setAnim
        lda     finP2
        sta     finHitF
        stz     finHitOK
        lda     finP3
        sta     finWait
        lda     #SFX_SWISH
        jmp     playSfx
fopWait:
        lda     finP1
        sta     finWait
        rts
fopDim: MA8
        lda     finP1
        sta     dimLvl
        MA16
        lda     finP2
        sta     dimT
        jmp     finStep
fopLaunch:
        lda     finP1
        asl     a
        asl     a
        asl     a
        asl     a
        sta     fVY,y
        lda     finP2
        asl     a
        asl     a
        asl     a
        asl     a
        sta     fPush,y
        lda     fFace,x
        and     #$00FF
        sta     fPushA,y
        lda     #1
        sta     fAir,y
        phx
        tyx
        lda     #AN_LAUNCHED
        jsr     setAnim
        plx
        jmp     finStep
fopJump:
        lda     #1
        sta     fAir,x
        lda     finP1
        asl     a
        asl     a
        asl     a
        asl     a
        sta     fVY,x
        lda     finP2
        bit     #$0080
        beq     :+
        ora     #$FF00
:       asl     a
        asl     a
        asl     a
        sta     fJumpV,x
        lda     #AN_JUMP
        jsr     setAnim
        lda     #SFX_SWISH
        jsr     playSfx
        jmp     finStep
fopSlow:
        lda     finP1
        sta     slowmo
        jmp     finStep
fopName:
        phx
        lda     fChar,x
        and     #$00FF
        asl     a
        tay
        lda     finNameTab,y
        tay
        jsr     setMsg
        plx
        jmp     finStep
fopOrbit:
        lda     finP1
        sta     finOrb
        jmp     finStep
fopFinal:
        ; the last blow: K.O., and the victim goes flying (often right out of the ring)
        jsr     finHit
        ldy     finSlot
        tya
        eor     #2
        tay
        lda     #0
        sta     fHP,y
        sta     fAir,y
        lda     #9
        sta     fAirHits,y
        lda     finP1
        asl     a
        asl     a
        asl     a
        asl     a
        sta     fVY,y
        lda     finP2
        asl     a
        asl     a
        asl     a
        asl     a
        sta     fPush,y
        lda     #ST_AIR
        sta     fState,y
        lda     #12
        sta     fFlash,y
        sta     hitStop
        phx
        tyx
        lda     #AN_LAUNCHED
        jsr     setAnim
        plx
        lda     #3
        sta     finPhase
        stz     fState,x
        lda     #AN_IDLE
        jsr     setAnim
        lda     #SFX_HITHV
        jmp     playSfx

; a scripted blow lands on the victim.  X = finisher
finHit:
        .a16
        inc     fCombo,x
        lda     fCombo,x
        jsr     showCombo
        txa
        eor     #2
        tay
        lda     #5
        sta     fFlash,y
        lda     #160
        sta     fPush,y
        lda     fFace,x
        and     #$00FF
        sta     fPushA,y
        lda     #2                      ; spark on the victim's chest
        cpy     #0
        beq     :+
        lda     #42
:       sta     sparkJ
        lda     #12
        sta     sparkT
        lda     #3
        sta     hitStop
        lda     fCombo,x
        lsr     a
        lda     #SFX_HIT
        bcc     :+
        lda     #SFX_HITHV
:       jsr     playSfx
        txa
        eor     #2
        tay
        phx
        tyx
        lda     fAir,x
        beq     :+
        lda     #520                    ; airborne: keep them up there
        sta     fVY,x
        lda     #AN_LAUNCHED
        bra     :++
:       lda     #AN_HIT
:       jsr     setAnim
        plx
        rts

stFinished:
        .a16
        lda     fAir,x
        beq     :+
        jsr     airPhys
        bcc     :+
        stz     fAir,x
        lda     #SFX_THUD
        jsr     playSfx
        lda     #AN_DOWN
        jmp     setAnim
:       rts

finTab: .word   .loword(ch0_fin), .loword(ch1_fin), .loword(ch2_fin), .loword(ch3_fin), .loword(ch4_fin), .loword(ch5_fin)
finNameTab: .word .loword(ch0_finName), .loword(ch1_finName), .loword(ch2_finName)
        .word   .loword(ch3_finName), .loword(ch4_finName), .loword(ch5_finName)
finLoTab: .word CH0_FINLO, CH1_FINLO, CH2_FINLO, CH3_FINLO, CH4_FINLO, CH5_FINLO
finHiTab: .word CH0_FINHI, CH1_FINHI, CH2_FINHI, CH3_FINHI, CH4_FINHI, CH5_FINHI
finSeqTab: .byte >CH0_FINHI, <CH0_FINHI, >CH0_FINLO, <CH0_FINLO
        .byte   >CH1_FINHI, <CH1_FINHI, >CH1_FINLO, <CH1_FINLO
        .byte   >CH2_FINHI, <CH2_FINHI, >CH2_FINLO, <CH2_FINLO
        .byte   >CH3_FINHI, <CH3_FINHI, >CH3_FINLO, <CH3_FINLO
        .byte   >CH4_FINHI, <CH4_FINHI, >CH4_FINLO, <CH4_FINLO
        .byte   >CH5_FINHI, <CH5_FINHI, >CH5_FINLO, <CH5_FINLO

; A = FWD (dash in) or BACK (backdash)
startDash:
        .a16
        cmp     #FWD
        bne     @back
        lda     #900
        sta     fDashV,x
        lda     #12
        sta     fTimer,x
        lda     #AN_DASHF
        bra     @go
@back:  lda     #.loword(-780)
        sta     fDashV,x
        lda     #11
        sta     fTimer,x
        lda     #AN_DASHB
@go:    pha
        lda     #ST_DASH
        sta     fState,x
        stz     fCrouch,x
        stz     fGuard,x
        pla
        jmp     setAnim

stDash:
        .a16
        jsr     turnToward
        lda     fDashV,x
        bmi     :+
        jsr     tryAttack               ; dash-in strikes
        bcc     :+
        rts
:       lda     fDashV,x
        jsr     walkSelf
        dec     fTimer,x
        bne     :+
        stz     fState,x
:       rts

stHit:
stBlock:
        .a16
        dec     fTimer,x
        bne     :+
        lda     fHP,x
        beq     @ko                     ; the combo that emptied the bar is over
        stz     fState,x
:       rts
@ko:    jmp     toDown

stFall:
        .a16
        dec     fTimer,x
        bne     :+
        jmp     toDown
:       rts

stThrown:
        .a16
        dec     fTimer,x
        bne     :+
        jmp     toDown
:       rts

stAir:
        .a16
        jsr     airPhys
        bcc     :+
        jmp     toDown
:       rts

stRingout:
        .a16
        jsr     airPhys
        lda     fY,x
        bpl     :+
        cmp     #.loword(-300)
        bcs     :+
        lda     #.loword(-300)
        sta     fY,x
        stz     fVY,x
:       rts

; gravity; carry set when landing on the floor (ring-out falls through)
airPhys:
        .a16
        lda     fVY,x
        sec
        sbc     #GRAV
        sta     fVY,x
        MA8
        clc
        lda     fYF,x
        adc     fVY,x
        sta     fYF,x
        MA16
        lda     fVY,x
        xba
        and     #$00FF
        bit     #$0080
        beq     :+
        ora     #$FF00
:       adc     fY,x
        sta     fY,x
        lda     fState,x
        cmp     #ST_RINGOUT
        beq     @no
        lda     fY,x
        bpl     @no
        stz     fY,x
        stz     fVY,x
        sec
        rts
@no:    clc
        rts

toDown:
        .a16
        lda     #SFX_THUD
        jsr     playSfx
        stz     fY,x
        stz     fVY,x
        lda     gmode
        cmp     #GM_PRACT
        bne     :+
        lda     fHP,x                   ; practice: a "KO" just puts them down, healed
        bne     :+
        lda     #HPMAX
        sta     fHP,x
        lda     #1
        sta     hudChg
:       lda     fHP,x
        bne     :+
        lda     slowmo
        bne     @kst
        lda     #60
        sta     slowmo
@kst:   lda     #ST_KO
        sta     fState,x
        lda     #AN_KO
        jmp     setAnim
:       lda     #ST_DOWN
        sta     fState,x
        lda     #50
        sta     fTimer,x
        lda     #AN_DOWN
        jmp     setAnim

stDown:
        .a16
        ; tech: a button after 16 ticks gets up early
        lda     fTimer,x
        cmp     #34
        bcs     :+
        lda     fVinP,x
        and     #(BUTTONS | PAD_UP | PAD_DOWN | FWD | BACK)
        beq     :+
        lda     #1
        sta     fTimer,x
:       dec     fTimer,x
        bne     :+
        lda     #ST_GETUP
        sta     fState,x
        lda     #AN_GETUP
        jmp     setAnim
:       rts

stGetup:
        .a16
        lda     fAnimEnd,x
        beq     :+
        stz     fState,x
        lda     gmode
        cmp     #GM_PRACT
        bne     :+
        lda     finPhase                ; practice: finisher over, camera back
        beq     :+
        stz     finPhase
        stz     finOrb
        stz     camOrbit
:       rts

stKO:
stWin:
        .a16
        rts

; ---------------------------------------------------------------- movement helpers
; A16 = speed (1/256 hu per tick, signed) along this fighter's facing
walkSelf:
        .a16
        pha
        lda     fFace,x
        and     #$00FF
        tay
        pla
        ; fall through
; A16 = speed, Y = angle (0..255): fX,fZ += speed * (cos, sin)  (with 8-bit fractions)
addPos:
        .a16
        sta     mBw
        sty     tmp6
        MA8
        lda     cos8,y
        sta     mB
        jsr     smul16x8
        .a16
        sta     tmp5
        MA8
        clc
        lda     fXF,x
        adc     tmp5
        sta     fXF,x
        MA16
        lda     tmp5
        xba
        and     #$00FF
        bit     #$0080
        beq     :+
        ora     #$FF00
:       adc     fX,x
        sta     fX,x
        ldy     tmp6
        MA8
        lda     sin8,y
        sta     mB
        jsr     smul16x8
        .a16
        sta     tmp5
        MA8
        clc
        lda     fZF,x
        adc     tmp5
        sta     fZF,x
        MA16
        lda     tmp5
        xba
        and     #$00FF
        bit     #$0080
        beq     :+
        ora     #$FF00
:       adc     fZ,x
        sta     fZ,x
        rts

; ease facing toward the opponent (4 units per tick): sidesteps make attacks whiff
turnToward:
        .a16
        lda     lineAng
        cpx     #0
        beq     :+
        clc
        adc     #128
:       and     #$00FF
        sec
        sbc     fFace,x
        and     #$00FF
        cmp     #$0080
        bcc     :+
        ora     #$FF00
:       ora     #0                      ; A = signed difference
        bmi     @neg
        cmp     #5
        bcc     @snap
        lda     fFace,x
        clc
        adc     #4
        bra     @st
@neg:   cmp     #.loword(-4)
        bcs     @snap
        lda     fFace,x
        sec
        sbc     #4
        bra     @st
@snap:  lda     lineAng
        cpx     #0
        beq     @st
        clc
        adc     #128
@st:    and     #$00FF
        sta     fFace,x
        rts

; keep fighters apart; dist = separation along the line between them
collide:
        .a16
        lda     fX+2
        sec
        sbc     fX
        sta     mBw
        MA8
        ldy     lineAng
        lda     cos8,y
        sta     mB
        jsr     smul16x8
        .a16
        sta     tmp4
        lda     fZ+2
        sec
        sbc     fZ
        sta     mBw
        MA8
        ldy     lineAng
        lda     sin8,y
        sta     mB
        jsr     smul16x8
        .a16
        clc
        adc     tmp4
        sta     dist
        ; airborne fighters pass over
        lda     fY
        ora     fY+2
        cmp     #24
        bcs     @done
        lda     dist
        bmi     :+
        cmp     #36
        bcs     @done
:       lda     #36
        sec
        sbc     dist
        cmp     #36
        bcc     :+
        lda     #36
:       asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a                       ; *128: half the overlap per fighter
        sta     tmp7
        ldx     #2
        ldy     lineAng
        jsr     addPos
        lda     lineAng
        clc
        adc     #128
        and     #$00FF
        tay
        lda     tmp7
        ldx     #0
        jsr     addPos
@done:  rts

; arena edge: walking stops at the rim; knocked-back fighters fall out (ring out)
bounds:
        .a16
        lda     fX,x
        bpl     :+
        eor     #$FFFF
        inc     a
:       sta     tmp0
        cmp     #330
        bcs     @out
        lda     fZ,x
        bpl     :+
        eor     #$FFFF
        inc     a
:       cmp     #330
        bcs     @out
        clc
        adc     tmp0
        cmp     #460
        bcs     @out
        rts
@out:   lda     gmode
        cmp     #GM_PRACT
        bne     :+
        lda     fOldX,x                 ; practice: the edge is a wall
        sta     fX,x
        lda     fOldZ,x
        sta     fZ,x
        rts
:       lda     fState,x
        cmp     #ST_FALL
        beq     @ring
        cmp     #ST_AIR
        beq     @ring
        cmp     #ST_THROWN
        beq     @ring
        cmp     #ST_HIT
        bne     :+
        lda     fPush,x                 ; a strong stagger at the edge also goes over
        cmp     #300
        bcs     @ring
:       cmp     #ST_RINGOUT
        beq     @rts
        lda     fOldX,x
        sta     fX,x
        lda     fOldZ,x
        sta     fZ,x
@rts:   rts
@ring:  lda     #SFX_SPLASH
        jsr     playSfx
        lda     #ST_RINGOUT
        sta     fState,x
        lda     #200
        sta     fVY,x
        lda     #AN_LAUNCHED
        jmp     setAnim

; ---------------------------------------------------------------- hits
hitCheck:
        .a16
        lda     fState,x
        cmp     #ST_ATTACK
        beq     :+
@no:    rts
:       lda     fHitDone,x
        bne     @no
        jsr     setMovePtr
        ldy     #MR_A0
        lda     [mp],y
        and     #$00FF
        sta     tmp0
        lda     fFrame,x
        cmp     tmp0
        bcc     @no
        ldy     #MR_A1
        lda     [mp],y
        and     #$00FF
        sta     tmp0
        lda     fFrame,x
        cmp     tmp0
        bcs     @no
        txa
        eor     #2
        sta     oi
        tay
        ; can the opponent be hit at all?
        lda     fState,y
        cmp     #ST_FALL
        beq     @no
        cmp     #ST_DIZZY
        bne     :+
        lda     fTimer,y                ; a moment of grace for the finisher input
        cmp     #270
        bcs     @no
        lda     fState,y
:       cmp     #ST_JUMP
        bcs     :+                      ; jump, landing, dash: open
        cmp     #ST_DOWN
        bcs     @no                     ; down, getup, thrown, KO, win, ring out
:       lda     fLevel,x
        cmp     #9
        bne     @strike
        ; throw: standing, grounded, not mid-hit
        lda     fState,y
        cmp     #ST_HIT
        bcs     @no
        lda     fCrouch,y
        bne     @no
        lda     fAir,y
        bne     @no
        bra     @geo
@strike:
        ; lows pass under jumpers
        cmp     #2
        bne     :+
        lda     fY,y
        cmp     #12
        bcs     @no
        lda     fLevel,x
:       ; high attacks pass over crouchers
        cmp     #0
        bne     @geo
        lda     fCrouch,y
        beq     @geo
        rts
@geo:   ; opponent position in the attacker's local frame
        lda     fX,y
        sec
        sbc     fX,x
        sta     tmp2                    ; dx
        lda     fZ,y
        sec
        sbc     fZ,x
        sta     tmp3                    ; dz
        lda     fFace,x
        and     #$00FF
        sta     tmp7
        lda     tmp2
        sta     mBw
        MA8
        ldy     tmp7
        lda     cos8,y
        sta     mB
        jsr     smul16x8
        .a16
        sta     tmp4                    ; dx*cos
        lda     tmp3
        sta     mBw
        MA8
        ldy     tmp7
        lda     sin8,y
        sta     mB
        jsr     smul16x8
        .a16
        clc
        adc     tmp4
        sta     tmp4                    ; lf = forward distance
        lda     tmp2
        sta     mBw
        MA8
        ldy     tmp7
        lda     sin8,y
        sta     mB
        jsr     smul16x8
        .a16
        sta     tmp5
        lda     tmp3
        sta     mBw
        MA8
        ldy     tmp7
        lda     cos8,y
        sta     mB
        jsr     smul16x8
        .a16
        eor     #$FFFF
        sec
        adc     tmp5
        sta     tmp5                    ; ll = lateral offset (+ = local z)
        lda     fLevel,x
        cmp     #9
        bne     @joint
        ; throw range: in front, close
        lda     tmp4
        sec
        sbc     #8
        cmp     #40
        bcs     @miss
        lda     tmp5
        clc
        adc     #24
        cmp     #49
        bcs     @miss
        jmp     resolveHit
@miss:  rts
@joint: ; the striking joint (hand / foot) this frame
        txy
        cpx     #0
        beq     :+
        ldy     #3
:       lda     fPtr,y
        sta     jp
        lda     fPtr+1,y
        sta     jp+1
        ldy     #MR_HJ
        lda     [mp],y
        and     #$00FF
        tay
        lda     [jp],y                  ; jx (lo) / jy (hi)
        and     #$00FF
        bit     #$0080
        beq     :+
        ora     #$FF00
:       sta     tmp0
        iny
        iny
        lda     [jp],y                  ; jz
        and     #$00FF
        bit     #$0080
        beq     :+
        ora     #$FF00
:       sta     tmp1
        ; |lf - jx| <= 20 and |ll - jz| <= 20
        lda     tmp4
        sec
        sbc     tmp0
        clc
        adc     #20
        cmp     #45
        bcs     @miss
        lda     tmp5
        sec
        sbc     tmp1
        clc
        adc     #20
        cmp     #41
        bcs     @miss
        ; fall through

; X = attacker, oi = defender, mp = move
resolveHit:
        .a16
        lda     #1
        sta     fHitDone,x
        ; spark on the striking joint (index into the projected joint arrays)
        ldy     #MR_HJ
        lda     [mp],y
        and     #$00FF
        ldy     #0
:       cmp     #3
        bcc     :+
        sbc     #3
        iny
        iny
        bra     :-
:       tya
        cpx     #0
        beq     :+
        clc
        adc     #40
:       sta     sparkJ
        lda     #12
        sta     sparkT
        lda     #1
        sta     hudChg
        ; attacker's remaining frames -> stun base (ticks)
        ldy     #MR_TOTAL
        lda     [mp],y
        and     #$00FF
        sec
        sbc     fFrame,x
        asl     a
        sta     tmp6
        ldy     #MR_ADV
        lda     [mp],y
        and     #$00FF
        bit     #$0080
        beq     :+
        ora     #$FF00
:       asl     a
        clc
        adc     tmp6
        sta     tmp6                    ; remaining + advantage (ticks)
        lda     fFace,x
        and     #$00FF
        sta     tmp7                    ; push direction
        ldy     oi
        ; ---- blocked?
        lda     fLevel,x
        cmp     #9
        beq     @hit
        lda     fGuard,y
        beq     @hit
        lda     fState,y
        beq     :+                      ; neutral (incl. walking back) guards
        cmp     #ST_BLOCK
        bne     @hit                    ; ... and so does blockstun
:
        lda     fCrouch,y
        beq     @stGuard
        lda     fLevel,x
        cmp     #2
        bne     @hit                    ; mids beat crouch guard
        bra     @block
@stGuard:
        lda     fLevel,x
        cmp     #2
        beq     @hit                    ; lows beat standing guard
@block: phx
        tyx
        lda     #ST_BLOCK
        sta     fState,x
        lda     tmp6
        cmp     #6
        bpl     :+
        lda     #6
:       sta     fTimer,x
        lda     #380
        sta     fPush,x
        lda     tmp7
        sta     fPushA,x
        lda     #4
        sta     hitStop
        lda     #6
        sta     sparkT
        lda     #SFX_BLOCK
        jsr     playSfx
        plx
        rts
@hit:   lda     #2
        sta     fHitDone,x              ; connected: cancels open up
        ; ---- combo breaker: defender mashes L from the 3rd hit on (once per round)
        lda     fCombo,x
        cmp     #2
        bcc     @nobrk
        lda     fLevel,x
        cmp     #9
        beq     @nobrk
        ldy     oi
        lda     fState,y
        cmp     #ST_HIT
        bne     @nobrk
        lda     fBreak,y
        beq     @nobrk
        lda     fBufT,y
        beq     @nobrk
        lda     fBuf,y
        and     #PAD_L
        beq     @nobrk
        jmp     comboBreaker
@nobrk: ; ---- combo count: hits on an opponent still reeling
        ldy     oi
        lda     fState,y
        cmp     #ST_HIT
        beq     :+
        cmp     #ST_AIR
        beq     :+
        stz     fCombo,x
        stz     fUsed1,x
        stz     fUsed2,x
        stz     fUsed3,x
:       inc     fCombo,x
        lda     fMove,x                 ; each move counts 3 times at most per combo
        asl     a
        tay
        lda     bitTab,y
        sta     tmp3
        and     fUsed2,x
        beq     :+
        lda     tmp3
        ora     fUsed3,x
        sta     fUsed3,x
:       lda     tmp3
        and     fUsed1,x
        beq     :+
        lda     tmp3
        ora     fUsed2,x
        sta     fUsed2,x
:       lda     tmp3
        ora     fUsed1,x
        sta     fUsed1,x
        lda     fCombo,x
        cmp     #2
        bcc     :+
        jsr     showCombo
:       ; ---- damage: single hits are weak (half), every combo hit adds 1/16 more
        ;      (up to 2.5x); throws full; counter hit +25%, juggles 75%
        ldy     #MR_DMG
        lda     [mp],y
        and     #$00FF
        ldy     fLevel,x
        cpy     #9
        beq     @dmg
        lsr     a
        sta     tmp3
        lda     fCombo,x
        dec     a
        cmp     #24
        bcc     :+
        lda     #24
:       clc
        adc     #16
        tay
        lda     #0
:       clc
        adc     tmp3
        dey
        bne     :-
        lsr     a
        lsr     a
        lsr     a
        lsr     a
        bne     @dmg
        lda     #1
@dmg:   sta     tmp0
        ldy     oi
        lda     fState,y
        cmp     #ST_ATTACK
        bne     :+
        lda     tmp0
        lsr     a
        lsr     a
        clc
        adc     tmp0
        sta     tmp0
:       lda     fState,y
        cmp     #ST_AIR
        bne     :+
        lda     tmp0
        lsr     a
        lsr     a
        eor     #$FFFF
        sec
        adc     tmp0
        sta     tmp0
:       ; ---- reaction: knockdowns / launches only end combos (3+ hits), punish a
        ;      counter hit, or as sweeps (3); otherwise a stagger
        ldy     #MR_REACT
        lda     [mp],y
        and     #$00FF
        sta     tmp1
        beq     @rdone
        cmp     #3
        bne     :+
        lda     #1
        sta     tmp1
        bra     @rdone
:       ldy     #5                      ; knockdown ender: 5+ hits
        cmp     #1
        beq     :+
        ldy     #4                      ; launcher: 4+ hits
:       tya
        dec     a
        cmp     fCombo,x
        bcc     @rdone
        stz     tmp1
@rdone: lda     fCombo,x
        sta     tmp4
        lda     fLevel,x
        sta     tmp2
        phx
        ldx     oi
        lda     fHP,x
        sec
        sbc     tmp0
        bcs     :+
        lda     #0
:       sta     fHP,x
        bne     :+
        jsr     tryDizzy                ; match-deciding KO: FINISH THEM!
        bcc     :+
        plx
        rts
:       lda     fHP,x
        bne     :+
        lda     tmp4
        cmp     #3
        bcs     :+                      ; in a combo: keep them up (overkill!)
        lda     #90
        sta     slowmo
        lda     tmp1                    ; KO: at least a knockdown
        bne     :+
        inc     tmp1
:       lda     tmp7
        sta     fPushA,x
        stz     fCrouch,x
        stz     fGuard,x
        lda     #7
        sta     hitStop
        lda     #6
        sta     fFlash,x
        lda     #SFX_HIT
        ldy     tmp1
        bne     :+
        ldy     tmp4
        cpy     #5
        bcc     :++
:       lda     #SFX_HITHV
:       jsr     playSfx
        lda     tmp2
        cmp     #9
        bne     :+
        jmp     @thrown
:       lda     fAir,x
        beq     :+
        stz     fAir,x                  ; knocked out of a jump
        lda     #500
        sta     fVY,x
        bra     @air2
:       lda     fState,x
        cmp     #ST_AIR
        bne     :+
        brl     @juggle
:
        lda     tmp1
        cmp     #1
        beq     @knock
        cmp     #2
        beq     @launch
        ; stagger: long enough to link the next hit; little push inside a combo
        lda     #ST_HIT
        sta     fState,x
        lda     tmp6
        clc
        adc     #18
        cmp     #26
        bpl     :+
        lda     #26
:       sta     fTimer,x
        lda     #300
        ldy     tmp4
        cpy     #2
        bcc     :+
        lda     #120
:       sta     fPush,x
        lda     #AN_HIT
        ldy     tmp2
        cpy     #2
        bne     :+
        lda     #AN_HITLOW
:       jsr     setAnim
        plx
        rts
@knock: lda     #ST_FALL
        sta     fState,x
        lda     #28
        sta     fTimer,x
        lda     #760
        sta     fPush,x
        lda     #9
        sta     hitStop
        lda     #AN_FALL
        jsr     setAnim
        plx
        rts
@launch:
        lda     #1500
        sta     fVY,x
@air2:  stz     fAirHits,x
        lda     #ST_AIR
        sta     fState,x
        lda     #300
        sta     fPush,x
        lda     #9
        sta     hitStop
        lda     #AN_LAUNCHED
        jsr     setAnim
        plx
        rts
@juggle:
        inc     fAirHits,x
        lda     fAirHits,x
        cmp     #8
        bcs     :+
        lda     #1000                   ; pop back up (less each hit)
        sta     fVY,x
:       lda     #340
        sta     fPush,x
        plx
        rts
@thrown:
        lda     #ST_THROWN
        sta     fState,x
        lda     #40
        sta     fTimer,x
        stz     fPush,x
        lda     #10
        sta     hitStop
        lda     #AN_THROWN
        jsr     setAnim
        plx
        rts

; ---------------------------------------------------------------- animation
; A16 = anim id
setAnim:
        .a16
        sta     fAnim,x
        stz     fFrame,x
        stz     fTick,x
        stz     fAnimEnd,x
        MA8
        jsr     framePtr
        MA16
        rts

; advance every 2 ticks (30 fps animation); loops or holds the last frame
animStep:
        .a16
        inc     fTick,x
        lda     fTick,x
        lsr     a
        bcs     @done
        lda     fChar,x
        and     #$00FF
        asl     a
        asl     a
        tay
        lda     fAnim,x
        asl     a
        asl     a
        clc
        adc     #2
        adc     animTabLo,y
        sta     tmp0
        MA8
        lda     animTabBk,y
        sta     tmp0+2
        lda     [tmp0]
        MA16
        and     #$00FF
        sta     tmp2
        lda     fFrame,x
        inc     a
        cmp     tmp2
        bcc     @set
        ldy     fAnim,x
        cpy     #NBASEANIM
        bcs     :+                      ; moves never loop
        lda     animLoop,y
        and     #$00FF
        bne     @wrap
:
        lda     #1
        sta     fAnimEnd,x
@done:  rts
@wrap:  lda     #0
@set:   sta     fFrame,x
        MA8
        jsr     framePtr
        MA16
        rts

; ---------------------------------------------------------------- rounds
phaseLogic:
        .a16
        inc     phaseT
        lda     phase
        asl     a
        tay
        lda     phaseTab,y
        sta     tmp6
        jmp     (tmp6)
phaseTab: .word .loword(phIntro), .loword(phFight), .loword(phEnd), .loword(phMatch)

phIntro:
        .a16
        lda     phaseT
        cmp     #1
        bne     :+
        ldy     #.loword(txtRound)
        jsr     setMsg
        lda     roundNum
        clc
        adc     #'0'
        MA8
        sta     msgBuf+6
        MA16
        rts
:       cmp     #80
        bne     :+
        lda     #SFX_GONG
        jsr     playSfx
        ldy     #.loword(txtFight)
        jmp     setMsg
:       cmp     #100
        bne     :+
        lda     #PH_FIGHT
        sta     phase
:       rts

phFight:
        .a16
        lda     phaseT
        cmp     #150
        bne     :+
        ldy     #0
        jsr     setMsg
:       lda     gmode
        cmp     #GM_PRACT
        bne     :+
        lda     phaseT                  ; practice: no clock, nobody loses
        cmp     #160
        bne     @prr
        ldy     #.loword(txtPrHint)
        jsr     setMsg
@prr:   rts
:       lda     gmode
        bne     :+
        inc     tTime                   ; tournament time (fighting only)
        bne     :+
        dec     tTime
:       lda     finPhase
        beq     :+
        cmp     #3
        bne     @noclk
:       ; clock
        inc     secTick
        lda     secTick
        cmp     #60
        bcc     :+
        stz     secTick
        lda     #1
        sta     hudChg
        dec     timeSec
        bne     @noclk
        lda     #2
        sta     endKind
        ldy     #.loword(txtTime)
        jmp     endRound
:
@noclk: ; ring out?
        lda     fState
        cmp     #ST_RINGOUT
        beq     @ring
        lda     fState+2
        cmp     #ST_RINGOUT
        beq     @ring
        ; KO?  (an empty bar only counts once they're down: combos can overkill)
        lda     fState
        cmp     #ST_KO
        beq     @ko
        lda     fState+2
        cmp     #ST_KO
        beq     @ko
        rts
@ring:  lda     #1
        sta     endKind
        ldy     #.loword(txtRing)
        lda     finPhase
        cmp     #3
        bne     :+
        ldy     #.loword(txtFin)
:       jmp     endRound
@ko:    stz     endKind
        ldy     #.loword(txtKO)
        lda     finPhase
        cmp     #3
        bne     :+
        ldy     #.loword(txtFin)
:
        ; fall through
endRound:
        .a16
        jsr     setMsg
        lda     #SFX_GONG
        jsr     playSfx
        lda     #PH_END
        sta     phase
        stz     phaseT
        ; winner: ring-out loser / KO / more health; $FF = draw
        lda     #$FF
        sta     winner
        lda     fState
        cmp     #ST_RINGOUT
        bne     :+
        lda     #2
        sta     winner
        rts
:       lda     fState+2
        cmp     #ST_RINGOUT
        bne     :+
        stz     winner
        rts
:       lda     fHP
        cmp     fHP+2
        beq     :+
        bcc     @p2
        stz     winner
        rts
@p2:    lda     #2
        sta     winner
:       rts

phEnd:
        .a16
        lda     phaseT
        cmp     #100
        bne     @t2
        ldx     winner
        cpx     #4
        bcs     :+
        inc     fWins,x
        lda     #1
        sta     hudChg
        lda     fState,x
        cmp     #ST_BLOCK + 1
        bcs     :+
        lda     #ST_WIN
        sta     fState,x
        lda     #AN_WIN
        jsr     setAnim
:       rts
@t2:    cmp     #130
        bne     @t3
        ; announce the winner
        ldx     winner
        cpx     #4
        bcs     :+
        jsr     msgWins
:       rts
@t3:    cmp     #260
        bne     :+
        lda     fWins
        cmp     #2
        bcs     @match
        lda     fWins+2
        cmp     #2
        bcs     @match
        inc     roundNum
        MA8
        jsr     newRound
        MA16
:       rts
@match: lda     #PH_MATCH
        sta     phase
        stz     phaseT
        rts

phMatch:
        .a16
        lda     phaseT
        cmp     #1
        bne     :+
        lda     scene
        bne     :+
        lda     #SONG_WIN
        jmp     playSong
:       cmp     #40
        bne     @t2
        lda     scene
        bne     :+                      ; attract: nothing to say
        lda     gmode
        bne     :+
        ldy     #.loword(txtOver)
        lda     fWins
        cmp     #2
        bcc     @say
        lda     ladder
        cmp     #4
        bcc     :+
        ldy     #.loword(txtChamp)
@say:   jmp     setMsg
:       rts
@t2:    cmp     #200
        beq     :+
        rts
:       lda     scene
        beq     :+
        jmp     toSplash                ; attract: back to the splash
:       lda     gmode
        beq     :+
        jmp     toSelect                ; versus: back to the select screen
:       lda     fWins                   ; tournament
        cmp     #2
        bcs     :+
        stz     mSel
        jmp     toMenu                  ; lost: game over
:       inc     ladder
        lda     ladder
        cmp     #5
        bcc     :+
        jmp     champion                ; won the tournament!
:       jsr     oppChar
        sta     fChar+2
        MA8
        jsr     newMatch
        MA16
        rts

; tournament cleared: record time + combos, show the table
champion:
        .a16
        jsr     enterMenuDisplay        ; (GSU idle: the save RAM is ours)
        jsr     addRecord
        jsr     saveRecords
        jmp     toRecords

; ---------------------------------------------------------------- pause menu
; items: RESUME, MOVE LIST (not in 2 player), FORFEIT / EXIT
pauseTick:
        .a16
        lda     pauseSlot
        tax
        lda     padP,x
        sta     tmp0
        ldy     #4                      ; last item index * 2
        lda     gmode
        cmp     #GM_VS
        bne     :+
        ldy     #2
:       sty     tmp1
        lda     tmp0
        and     #PAD_DOWN
        beq     :++
        lda     pauseSel
        cmp     tmp1
        bcc     :+
        lda     #$FFFE
:       inc     a
        inc     a
        sta     pauseSel
        bra     @mv
:       lda     tmp0
        and     #PAD_UP
        beq     @sel
        lda     pauseSel
        bne     :+
        lda     tmp1
        inc     a
        inc     a
:       dec     a
        dec     a
        sta     pauseSel
@mv:    lda     #1
        sta     hudChg
        lda     #SFX_SELECT
        jmp     playSfx
@sel:   lda     tmp0
        and     #PAD_START
        beq     :+
        stz     pauseSel                ; START again: resume
        bra     @go
:       lda     tmp0
        and     #(PAD_A | PAD_B)
        bne     :+
        rts
:       and     #PAD_B
        beq     @go
        stz     pauseSel                ; B: resume
@go:    lda     #SFX_CONFIRM
        jsr     playSfx
        lda     pauseSel
        beq     @resume
        lda     gmode
        cmp     #GM_VS
        bne     :+
        lda     pauseSel                ; 2 player: item 1 = forfeit
        cmp     #2
        beq     @quit
:       lda     pauseSel
        cmp     #2
        bne     @quit
        ldx     pauseSlot               ; move list for whoever paused
        lda     fChar,x
        and     #$00FF
        jmp     toMoves
@quit:  stz     paused
        stz     mSel
        jmp     toMenu
@resume:
        stz     paused
        lda     #1
        sta     hudChg
        rts

; arcade opponent: the characters after the player's, in order
oppChar:
        .a16
        lda     fChar
        and     #$00FF
        sec
        adc     ladder                  ; char + 1 + ladder
:       cmp     #6
        bcc     :+
        sbc     #6
        bra     :-
:       rts

; random 0..5
rnd6:
        .a16
        jsr     rngStep
        lda     rng
        and     #$001F
:       cmp     #6
        bcc     :+
        sbc     #6
        bra     :-
:       rts

toTitle:
        .a16
        lda     #SONG_TITLE
        jsr     playSong
        lda     #SC_TITLE
        sta     scene
        stz     paused
        lda     dispMode
        bne     :+
        jsr     dispOff                 ; (already in the fight display: re-pick the HDMA tables)
        MA8
        jsr     setupHdma
        MA16
        jsr     dispOn
        bra     :++
:       jsr     enterFightDisplay
:       lda     #1
        sta     bandDirty
        lda     #1
        sta     demo
        stz     p2Human
        jsr     rnd6
        sta     fChar
        jsr     rnd6
        sta     fChar+2
        lda     #1
        sta     hudChg
        MA8
        jsr     newMatch
        MA16
        rts

toSelect:
        .a16
        lda     #SC_SELECT
        sta     scene
        stz     demo
        lda     gmode
        cmp     #GM_VS
        beq     :+
        lda     #0
:       sta     p2Human
        stz     selDone
        stz     selDone+2
        stz     selT
        stz     ladder
        lda     gmode
        bne     :+
        jsr     oppChar
        sta     fChar+2
:       lda     #1
        sta     hudChg
        MA8
        sta     palDirty
        sta     shapeDirty
        jsr     newRound
        MA16
        rts

; character select: left/right cycles the fighter (shown live in the arena), a button locks in
selectTick:
        .a16
        ; B before locking in: back (practice dummy pick -> fighter pick -> main menu)
        lda     padP
        and     #PAD_B
        beq     @nob
        lda     gmode
        cmp     #GM_PRACT
        bne     :+
        lda     selDone
        beq     :+
        stz     selDone
        lda     #1
        sta     hudChg
        rts
:       lda     selDone
        bne     @nob
        lda     #SFX_CONFIRM
        jsr     playSfx
        jmp     toMenu
@nob:   ldx     #0
        lda     padP
        jsr     selPad
        lda     gmode
        beq     @cpu
        cmp     #GM_PRACT
        bne     @vs
        ; practice: once your fighter is locked, the same pad picks the dummy
        lda     selDone
        beq     @chk
        cmp     #2
        beq     :+
        lda     #2                      ; (wait for a fresh press)
        sta     selDone
        lda     #1
        sta     hudChg
        bra     @chk
:       ldx     #2
        lda     padP
        jsr     selPad
        bra     @chk
@vs:    ldx     #2
        lda     padP+2                  ; P2 on the right: screen directions
        jsr     selPad
        bra     @chk
@cpu:   lda     selDone
        sta     selDone+2
        jsr     oppChar
        cmp     fChar+2
        beq     @chk
        ldx     #2
        jsr     selSet
@chk:   lda     selDone
        beq     :+
        lda     selDone+2
        beq     :+
        inc     selT
        lda     selT
        cmp     #60
        bcc     :+
        stz     scene                   ; FIGHT!
        MA8
        jsr     newMatch
        MA16
:       rts

; X = slot, A = newly pressed buttons
selPad:
        .a16
        sta     tmp4
        lda     selDone,x
        bne     @done
        lda     tmp4
        and     #PAD_RIGHT
        beq     :++
        lda     fChar,x
        inc     a
        cmp     #6
        bcc     :+
        lda     #0
:       jsr     selSet
:       lda     tmp4
        and     #PAD_LEFT
        beq     :++
        lda     fChar,x
        dec     a
        bpl     :+
        lda     #5
:       jsr     selSet
:       lda     tmp4
        and     #(PAD_A | PAD_X | PAD_Y | PAD_START)
        beq     @done
        lda     #SFX_CONFIRM
        jsr     playSfx
        lda     #1
        sta     selDone,x
        sta     hudChg
        lda     #AN_WIN
        jmp     setAnim
@done:  rts

; X = slot, A = character
selSet:
        .a16
        and     #$00FF
        sta     fChar,x
        MA8
        lda     #1
        sta     palDirty
        sta     shapeDirty
        MA16
        sta     hudChg
        lda     #SFX_SELECT
        jsr     playSfx
        lda     #AN_IDLE
        jmp     setAnim

; Y = text address (0-terminated, RODATA) or 0 to clear
setMsg:
        .a16
        lda     #1
        sta     hudChg
        MA8
        ldx     #0
        cpy     #0
        beq     @end
:       lda     a:0,y
        beq     @end
        sta     msgBuf,x
        iny
        inx
        cpx     #19
        bne     :-
@end:   stz     msgBuf,x
        MA16
        rts

; A16 = n -> comboBuf = "<n><Y text>", Y text 0-terminated (X preserved)
numText:
        .a16
        phx
        phy
        ldy     #0
:       cmp     #10
        bcc     :+
        sbc     #10
        iny
        bra     :-
:       sta     tmp3
        ldx     #0
        tya
        beq     :+
        clc
        adc     #'0'
        MA8
        sta     comboBuf
        MA16
        inx
:       lda     tmp3
        clc
        adc     #'0'
        MA8
        sta     comboBuf,x
        inx
        ply
:       lda     a:0,y
        sta     comboBuf,x
        beq     :+
        iny
        inx
        bra     :-
:       MA16
        lda     #1
        sta     hudChg
        plx
        rts

; A16 = hit count during a combo
showCombo:
        .a16
        ldy     #.loword(txtHits)
        jsr     numText
        lda     #90
        sta     comboT
        rts

; combo over?  (defender back on their feet / blocking / down) -> rank it
comboTick:
        .a16
        ldx     #0
        jsr     comboEnd
        ldx     #2
        jsr     comboEnd
        lda     comboT
        beq     :+
        dec     comboT
        bne     :+
        MA8
        stz     comboBuf
        MA16
        lda     #1
        sta     hudChg
:       rts

comboEnd:
        .a16
        lda     fCombo,x
        beq     @r
        txa
        eor     #2
        tay
        lda     fState,y
        cmp     #ST_HIT
        beq     @r
        cmp     #ST_AIR
        beq     @r
        cmp     #ST_FALL
        beq     @r
        cmp     #ST_FINISHED
        beq     @r
        lda     gmode
        cmp     #GM_PRACT
        bne     :+
        lda     fHP,y                   ; practice: the dummy heals between combos
        beq     :+
        lda     #HPMAX
        sta     fHP,y
        lda     #1
        sta     hudChg
:       lda     fCombo,x
        stz     fCombo,x
        cmp     #3
        bcc     @r
        pha
        lda     gmode
        bne     :+
        cpx     #0
        bne     :+
        lda     scene
        bne     :+
        inc     tCombos                 ; tournament: combos of 3+ hits
:       pla
        ; "<n> HIT <RANK> COMBO"
        pha
        cmp     #22
        bcc     :+
        lda     #21
:       asl     a
        tay
        lda     rankTab-6,y
        tay
        pla
        jsr     numText
        lda     #150
        sta     comboT
        lda     #SFX_COMBO
        jmp     playSfx
@r:     rts

rankTab: .word  .loword(rk3), .loword(rk4), .loword(rk5), .loword(rk6), .loword(rk7), .loword(rk8)
        .word   .loword(rk9), .loword(rk10), .loword(rk11), .loword(rk12), .loword(rk12), .loword(rk12)
        .word   .loword(rk12), .loword(rk16), .loword(rk16), .loword(rk16), .loword(rk16), .loword(rk16), .loword(rk21)
rk3:    .byte   " HIT TRIPLE COMBO", 0
rk4:    .byte   " HIT SUPER COMBO", 0
rk5:    .byte   " HIT HYPER COMBO", 0
rk6:    .byte   " HIT BRUTAL COMBO", 0
rk7:    .byte   " HIT MASTER COMBO", 0
rk8:    .byte   " HIT AWESOME COMBO", 0
rk9:    .byte   " HIT BLASTER COMBO", 0
rk10:   .byte   " HIT MONSTER COMBO", 0
rk11:   .byte   " HIT KING COMBO", 0
rk12:   .byte   " HIT KILLER COMBO!", 0
rk16:   .byte   " HIT INSANE COMBO!", 0
rk21:   .byte   " HIT ULTRA COMBO!!!", 0
txtBreak: .byte "COMBO BREAKER!", 0

; X = attacker, oi = defender who broke the combo
comboBreaker:
        .a16
        stz     fCombo,x
        ldy     oi
        lda     fBreak,y
        dec     a
        sta     fBreak,y
        lda     #0
        sta     fBufT,y
        sta     fState,y                ; defender recovers at once
        lda     fFace,y
        and     #$00FF
        sta     fPushA,x
        lda     #600
        sta     fPush,x
        lda     #ST_HIT
        sta     fState,x
        lda     #34
        sta     fTimer,x
        lda     #8
        sta     fFlash,x
        lda     #AN_HIT
        jsr     setAnim
        phx
        ldx     oi
        lda     #AN_GUARD
        jsr     setAnim
        plx
        lda     #14
        sta     hitStop
        lda     #SFX_BREAKER
        jsr     playSfx
        MA8
        ldy     #0
:       lda     txtBreak,y
        sta     comboBuf,y
        beq     :+
        iny
        bra     :-
:       MA16
        lda     #150
        sta     comboT
        lda     #1
        sta     hudChg
        rts

; X = winner slot: "<NAME> WINS"
msgWins:
        .a16
        lda     fChar,x
        and     #$00FF
        sta     tmp0
        asl     a
        asl     a
        asl     a
        sec
        sbc     tmp0                    ; *7
        tay
        MA8
        ldx     #0
:       lda     fighterNames,y
        cmp     #' '
        beq     :+
        sta     msgBuf,x
        iny
        inx
        cpx     #7
        bne     :-
:       ldy     #0
:       lda     txtWins,y
        sta     msgBuf,x
        beq     :+
        iny
        inx
        bra     :-
:       lda     #1
        sta     hudChg
        MA16
        rts

txtRound: .byte "ROUND 1", 0
txtFight: .byte "FIGHT!", 0
txtKO:    .byte "K.O.", 0
txtRing:  .byte "RING OUT!", 0
txtTime:  .byte "TIME", 0
txtWins:  .byte " WINS", 0
txtPaused: .byte "- PAUSED -", 0
txtPrHint: .byte "SELECT: DIZZY THE DUMMY", 0
txtSelP:  .byte "PRACTICE: PICK YOUR FIGHTER", 0
txtSelD:  .byte "PICK YOUR SPARRING DUMMY", 0
pauseTxt:  .word .loword(tpR), .loword(tpM), .loword(tpF), .loword(tpE)
pauseTxtS: .word .loword(tpR2), .loword(tpM2), .loword(tpF2), .loword(tpE2)
tpR:  .byte "RESUME", 0
tpM:  .byte "MOVE LIST", 0
tpF:  .byte "FORFEIT", 0
tpE:  .byte "EXIT PRACTICE", 0
tpR2: .byte "> RESUME <", 0
tpM2: .byte "> MOVE LIST <", 0
tpF2: .byte "> FORFEIT <", 0
tpE2: .byte "> EXIT PRACTICE <", 0
txtHits:  .byte " HITS", 0
txtFin:   .byte "FINISHED!", 0
txtFinish: .byte "FINISH THEM!", 0
txtOver:  .byte "GAME OVER", 0
txtChamp: .byte "CHAMPION!", 0
txtTitle: .byte "ARENA FIGHTER", 0
txtStart: .byte "PRESS START", 0
txtSel:   .byte "SELECT YOUR FIGHTER", 0
txtP1:    .byte "P1", 0
txtP2:    .byte "P2", 0
txtCPU:   .byte "CPU", 0
txtReady: .byte "READY!", 0
styleTab: .word .loword(sty0), .loword(sty1), .loword(sty2), .loword(sty3), .loword(sty4), .loword(sty5)
sty0:     .byte "KARATE", 0
sty1:     .byte "KUNG FU", 0
sty2:     .byte "WRESTLING", 0
sty3:     .byte "VIKING", 0
sty4:     .byte "BOXING", 0
sty5:     .byte "CAPOEIRA", 0

; ---------------------------------------------------------------- HUD (BG3 rows 1..4)
; row 0: names + round pips, row 1: health bars + clock, row 3: message
hudCompose:
        .a8
        lda     hudChg
        bne     :+
        rts
:       stz     hudChg
        MA16
        ldx     #0
        lda     #$2000                  ; blank, priority
:       sta     hudBuf,x
        inx
        inx
        cpx     #256
        bne     :-
        lda     scene
        bne     :+
        jmp     @fight
:       cmp     #SC_TITLE
        bne     @sel
        jsr     bandCompose
        jmp     @out
@sel:   ldy     #.loword(txtSel)
        lda     gmode
        cmp     #GM_PRACT
        bne     :+
        ldy     #.loword(txtSelP)
        lda     selDone
        beq     :+
        ldy     #.loword(txtSelD)
:       lda     #0
        jsr     hudCenter
        ldy     #.loword(txtP1)
        ldx     #(64 + 1 * 2)
        jsr     hudText
        ldy     #.loword(txtCPU)
        lda     gmode
        beq     :+
        ldy     #.loword(txtP2)
:       ldx     #(64 + 28 * 2)
        jsr     hudText
        lda     fChar
        ldx     #(128 + 1 * 2)
        jsr     hudName
        lda     fChar+2
        ldx     #(128 + 24 * 2)
        jsr     hudName
        ldx     #0
        ldy     #(192 + 1 * 2)
        jsr     hudStyle
        ldx     #2
        ldy     #(192 + 22 * 2)
        jsr     hudStyle
        jmp     @out
@fight: lda     paused
        beq     @names
        ; pause menu over the HUD rows
        ldy     #.loword(txtPaused)
        lda     #0
        jsr     hudCenter
        ldx     #0
@pi:    phx
        txa
        lsr     a
        inc     a
        sta     tmp6                    ; row
        lda     gmode
        cmp     #GM_VS
        bne     :+
        txa                             ; 2 player: no move list (memory only!)
        beq     :+
        clc
        adc     #2
        tax
:       lda     gmode
        cmp     #GM_PRACT
        bne     :+
        cpx     #4
        bne     :+
        ldx     #6                      ; practice: "EXIT PRACTICE"
:       ldy     pauseTxt,x
        lda     1,s
        cmp     pauseSel
        bne     :+
        ldy     pauseTxtS,x
:       lda     tmp6
        jsr     hudCenter
        plx
        inx
        inx
        lda     gmode
        cmp     #GM_VS
        bne     :+
        cpx     #4
        beq     @pd
:       cpx     #6
        bne     @pi
@pd:    jmp     @out
@names: ; names
        lda     fChar
        ldx     #1*2
        jsr     hudName
        lda     fChar+2
        ldx     #24*2
        jsr     hudName
        ; round pips
        ldx     #9*2
        lda     fWins
        ldy     #$2400
        jsr     hudPips
        ldx     #21*2
        lda     fWins+2
        ldy     #$2800
        jsr     hudPips
        ; P1 bar (cols 1..13, fills from the left)
        lda     fHP
        lsr     a
        sta     tmp0
        ldx     #(32 + 1) * 2
        ldy     #13
:       lda     tmp0
        cmp     #9
        bcc     :+
        lda     #8
:       pha
        clc
        adc     #BAR_TILE0 | $2400
        sta     hudBuf,x
        pla
        eor     #$FFFF
        sec
        adc     tmp0
        sta     tmp0
        inx
        inx
        dey
        bne     :--
        ; P2 bar (cols 30..18, mirrored)
        lda     fHP+2
        lsr     a
        sta     tmp0
        ldx     #(32 + 30) * 2
        ldy     #13
:       lda     tmp0
        cmp     #9
        bcc     :+
        lda     #8
:       pha
        clc
        adc     #BAR_TILE0 | $6800
        sta     hudBuf,x
        pla
        eor     #$FFFF
        sec
        adc     tmp0
        sta     tmp0
        dex
        dex
        dey
        bne     :--
        ; clock
        lda     timeSec
        ldy     #0
:       cmp     #10
        bcc     :+
        sbc     #10
        iny
        bra     :-
:       clc
        adc     #('0' - 32) | $2000
        sta     hudBuf + (32 + 16) * 2
        tya
        clc
        adc     #('0' - 32) | $2000
        sta     hudBuf + (32 + 15) * 2
        ; combo counter / rank on row 2
        ldy     #.loword(comboBuf)
        lda     #2
        jsr     hudCenter
        ; message, centred on row 3
        ldy     #.loword(msgBuf)
        lda     #3
        jsr     hudCenter
@out:   MA8
        lda     #1
        sta     hudDirty
        rts

; Y = 0-terminated text (bank $80 / low RAM), A = row: centred
hudCenter:
        .a16
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        sta     tmp2                    ; row * 64
        sty     tmp3
        ldx     #0
:       lda     a:0,y
        and     #$00FF
        beq     :+
        iny
        inx
        bra     :-
:       txa
        lsr     a
        eor     #$FFFF
        sec
        adc     #16
        asl     a
        clc
        adc     tmp2
        tax
        ldy     tmp3
        ; fall through
; Y = text, X = hud offset
hudText:
        .a16
:       lda     a:0,y
        and     #$00FF
        beq     :+
        sec
        sbc     #32
        ora     #$2000
        sta     hudBuf,x
        inx
        inx
        iny
        bra     :-
:       rts

; X = slot, Y = hud offset: style name, or READY! once locked in
hudStyle:
        .a16
        phy
        lda     selDone,x
        beq     :+
        ldy     #.loword(txtReady)
        bra     @go
:       lda     fChar,x
        and     #$00FF
        asl     a
        tay
        lda     styleTab,y
        tay
@go:    plx
        jmp     hudText

; A = character, X = hud offset
hudName:
        .a16
        and     #$00FF
        sta     tmp0
        asl     a
        asl     a
        asl     a
        sec
        sbc     tmp0
        tay
        lda     #7
        sta     tmp1
:       lda     fighterNames,y
        and     #$00FF
        sec
        sbc     #32
        ora     #$2000
        sta     hudBuf,x
        iny
        inx
        inx
        dec     tmp1
        bne     :-
        rts

; A = wins, X = hud offset, Y = attribute
hudPips:
        .a16
        sta     tmp0
        sty     tmp1
        lda     #BAR_TILE0
        ldy     tmp0
        beq     :+
        lda     #BAR_TILE0 + 8
:       ora     tmp1
        sta     hudBuf,x
        lda     #BAR_TILE0
        ldy     tmp0
        cpy     #2
        bcc     :+
        lda     #BAR_TILE0 + 8
:       ora     tmp1
        sta     hudBuf+2,x
        rts

; ---------------------------------------------------------------- CPU fighter (X = slot)
; returns A16 = virtual pad for this tick
aiThink:
        .a16
        jsr     rngStep
        txa
        eor     #2
        tay                             ; Y = opponent
        jsr     aiLevel
        sta     aiLv
        ; opponent dizzy: go for the finisher (more often at higher levels)
        lda     fState,y
        cmp     #ST_DIZZY
        beq     :+
        stz     aiFinGo,x
        brl     @nfin
:       lda     aiFinGo,x
        bne     @fgo
        lda     #2
        sta     aiFinGo,x
        lda     aiLv
        clc
        adc     #3
        sta     tmp0
        lda     rng
        and     #$0007
        cmp     tmp0
        bcs     @fgo2                   ; no: just knock them out
        lda     #1
        sta     aiFinGo,x
        stz     aiSeqI,x
        lda     #10                     ; let go of the stick first
        sta     aiSeqT,x
@fgo:   cmp     #1
        beq     :+
@fgo2:  brl     @nfin
:       stz     aiPress,x
        lda     dist
        bpl     :+
        eor     #$FFFF
        inc     a
:       cmp     #60
        bcc     @seq
        stz     aiSeqI,x
        lda     #10
        sta     aiSeqT,x
        lda     #FWD
        sta     aiHold,x
        brl     @out
@seq:   stz     aiHold,x
        lda     aiSeqT,x
        beq     :+
        dec     aiSeqT,x
        brl     @out
:       lda     aiSeqI,x
        cmp     #4
        bcc     :+
        stz     aiSeqI,x                ; didn't take: try again
        lda     #40
        sta     aiSeqT,x
        brl     @out
:       lda     fChar,x
        and     #$00FF
        asl     a
        asl     a
        clc
        adc     aiSeqI,x
        tay
        lda     finSeqTab,y
        and     #$00FF
        dec     a
        asl     a
        tay
        lda     histBits,y
        sta     aiPress,x
        inc     aiSeqI,x
        lda     #6
        sta     aiSeqT,x
        brl     @out
@nfin:
        ; combo breaker attempts (level 1+) when caught in a combo
        lda     fState,x
        cmp     #ST_HIT
        bne     @nbrk
        lda     fCombo,y
        cmp     #2
        bcc     @nbrk
        lda     rng
        and     #$001F
        cmp     aiLv
        bcs     @nbrk
        lda     #PAD_L
        sta     aiPress,x
        brl     @out
@nbrk:  ; combos: after a connecting hit, press a follow-up (longer combos at higher levels)
        lda     fState,x
        cmp     #ST_ATTACK
        bne     @nstr
        lda     fHitDone,x
        cmp     #2
        bne     @nstr
        lda     aiLv
        asl     a
        adc     #2
        cmp     fCombo,x
        bcc     @nstr                   ; long enough for this level
        beq     @nstr
        lda     rng
        and     #$0003
        bne     @nstr
        lda     fChar,x
        and     #$00FF
        asl     a
        phy
        tay
        lda     aiChTab,y
        sta     tmp2
        lda     fMove,x
        asl     a
        tay
        lda     (tmp2),y
        bne     :+
        lda     fChar,x                 ; no string: cancel into a random move
        and     #$00FF
        asl     a
        tay
        lda     aiTab,y
        sta     tmp2
        lda     rng+1
        and     #$000F
        asl     a
        tay
        lda     (tmp2),y
        sta     tmp0
        and     #(PAD_DOWN | PAD_LEFT | PAD_RIGHT)
        sta     aiHold,x
        lda     tmp0
        and     #(PAD_Y | PAD_X | PAD_B | PAD_A)
:       ply
        sta     aiPress,x
        brl     @out
@nstr:  ; air: kick on the way down when in range
        lda     fState,x
        cmp     #ST_JUMP
        bne     @nair
        lda     fVY,x
        bmi     :+
        brl     @out
:
        lda     dist
        cmp     #90
        bcc     :+
        brl     @out
:
        lda     #PAD_B
        sta     aiPress,x
        brl     @out
@nair:  lda     aiT,x
        beq     :+
        dec     aiT,x
        brl     @out
:       stz     aiHold,x
        lda     aiLv                    ; reaction time: 34..49 ticks (level 0)
        asl     a                       ; down to 16..31 (level 3)
        adc     aiLv
        asl     a
        sta     tmp0
        lda     rng
        and     #$000F
        clc
        adc     #34
        sec
        sbc     tmp0
        sta     aiT,x
        lda     fState,x
        cmp     #ST_ATTACK
        bcs     @out                    ; busy
        lda     rng+1
        and     #$00FF
        sta     tmp0                    ; r
        lda     fState,y
        cmp     #ST_ATTACK
        bne     @notAtk
        lda     dist
        cmp     #100
        bcs     @notAtk
        ; defend
        lda     tmp0
        cmp     #120
        bcs     @d2
        lda     #BACK
        pha
        lda     fLevel,y
        cmp     #2
        bne     :+
        pla
        ora     #PAD_DOWN               ; low: crouch guard
        pha
:       lda     fLevel,y
        bne     :+
        lda     tmp0
        cmp     #60
        bcs     :+
        pla                             ; high: sometimes duck under it
        lda     #PAD_DOWN
        pha
:       pla
        sta     aiHold,x
        lda     #10
        sta     aiT,x
        bra     @out
@d2:    cmp     #165
        bcs     :+
        lda     #PAD_R                  ; sidestep the attack
        sta     aiHold,x
        lda     #6
        sta     aiT,x
        lda     #PAD_UP
        bra     @press
:       lda     #PAD_Y
@press: sta     aiPress,x
@out:   lda     aiHold,x
        ora     aiPress,x
        stz     aiPress,x
        rts
@notAtk:
        lda     fState,y
        cmp     #ST_AIR
        bne     :+
        lda     dist
        cmp     #70
        bcs     @wait
        lda     #PAD_X                  ; juggle!
        bra     @press
:       cmp     #ST_FALL
        bcs     @wait
        lda     dist
        bmi     @close
        cmp     #64
        bcc     @close
        lda     #FWD
        sta     aiHold,x
        lda     tmp0
        cmp     #14
        bcs     @out
        lda     dist
        cmp     #150
        bcs     @out
        lda     #PAD_UP                 ; jump in
        bra     @press
@wait:  lda     #10
        sta     aiT,x
        bra     @out
@close: lda     aiLv                    ; attack chance 45/256 .. 150/256
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        clc
        adc     aiLv
        adc     aiLv
        adc     aiLv
        adc     #45
        sta     tmp1
        lda     tmp0
        cmp     tmp1
        bcs     @c2
        ; attack: pick one of this fighter's ground moves; then a breather
        ;         (24 ticks at level 0 .. none at level 3)
        lda     #3
        sec
        sbc     aiLv
        asl     a
        asl     a
        asl     a
        sta     tmp1
        asl     a
        adc     tmp1
        adc     aiT,x
        sta     aiT,x
        lda     fChar,x
        and     #$00FF
        asl     a
        tay
        lda     aiTab,y
        sta     tmp2
        lda     rng
        and     #$000F
        asl     a
        tay
        lda     (tmp2),y
        bit     #PAD_L
        beq     :+
        ldy     dist
        cpy     #42
        bcc     :+
        lda     #PAD_Y                  ; too far to throw: jab instead
:       sta     tmp0
        and     #(PAD_UP | PAD_DOWN | PAD_LEFT | PAD_RIGHT)
        sta     aiHold,x
        lda     tmp0
        and     #BUTTONS
        brl     @press
@c2:    cmp     #190
        bcs     :+
        lda     #BACK
        sta     aiHold,x
        lda     #12
        sta     aiT,x
        brl     @out
:       cmp     #222
        bcs     :+
        lda     #PAD_R                  ; sidestep out
        sta     aiHold,x
        lda     #6
        sta     aiT,x
        lda     #PAD_DOWN
        brl     @press
:       lda     #PAD_R
        sta     aiHold,x
        lda     #14
        sta     aiT,x
        brl     @out

; CPU difficulty 0..3: arcade ladder position; attract demo plays at 3
aiLevel:
        .a16
        lda     scene
        bne     @hi
        lda     gmode
        bne     @hi
        lda     ladder
        cmp     #4
        bcc     :+
@hi:    lda     #3
:       rts

aiTab:  .word   .loword(ch0_ai), .loword(ch1_ai), .loword(ch2_ai), .loword(ch3_ai), .loword(ch4_ai), .loword(ch5_ai)
aiChTab: .word  .loword(ch0_aichain), .loword(ch1_aichain), .loword(ch2_aichain)
        .word   .loword(ch3_aichain), .loword(ch4_aichain), .loword(ch5_aichain)
