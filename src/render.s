; =============================================================================
; render: camera -> Mode 7 registers, fighters -> projected joints -> depth-sorted
;         ball sprites + shadows in oamBuf.  Sets renderReady for the NMI.
; =============================================================================
CAMH2 = CAMH * 2
.macro TAX8                         ; X = A (8-bit), clearing the hidden high byte
        rep     #$20
        and     #$00FF
        tax
        sep     #$20
.endmacro
.macro TAY8
        rep     #$20
        and     #$00FF
        tay
        sep     #$20
.endmacro

render:
        .a8
        .i16
        jsr     cameraRegs
        ldx     #0
        stx     nBall
        ldx     #0                  ; fighter 0
        jsr     projectFighter
        ldx     #2
        jsr     projectFighter
        ldx     #0
        jsr     fighterParts
        ldx     nBall
        stx     nB0
        ldx     #2
        jsr     fighterParts
        jsr     sortBalls
        rep     #$20
        .a16
        ldx     #0
        jsr     trailUpdate
        ldx     #2
        jsr     trailUpdate
        sep     #$20
        .a8
        jsr     buildDL
        ; the previous frame must be on screen (uploaded by the NMI) before we reuse
        ; OAM / camera / GSU RAM; everything above overlapped with its drawing
:       lda     upState
        bne     :-
        rep     #$20
        .a16
        lda     nM7x
        sta     m7x
        lda     nM7y
        sta     m7y
        lda     nM7h
        sta     m7h
        lda     nM7v
        sta     m7v
        lda     nPanX
        sta     panX
        lda     nYaw
        sta     pYaw
        sep     #$20
        .a8
        jsr     buildOAM
        jmp     gsuKick

; ---------------------------------------------------------------- camera
; Mode 7: centre = camera map position; HOFS/VOFS so screen (128, HORIZON) is the centre.
cameraRegs:
        rep     #$20
        .a16
        lda     camX
        cmp     #$8000
        ror     a                   ; hu -> texels (signed)
        clc
        adc     #ARENA_CX
        sta     nM7x
        sec
        sbc     #128
        and     #$1FFF
        sta     nM7h
        lda     camZ
        cmp     #$8000
        ror     a
        clc
        adc     #ARENA_CY
        sta     nM7y
        sec
        sbc     #HORIZON
        and     #$1FFF
        sta     nM7v
        lda     camYaw              ; panorama: 2 px per yaw step
        sta     nYaw
        asl     a
        sta     nPanX
        sep     #$20
        .a8
        ldx     camYaw
        lda     f:cos8,x
        sta     cA
        lda     f:sin8,x
        sta     sA
        rts

; ---------------------------------------------------------------- joints
; X = fighter*2.  Projects the 20 joints of the fighter's current frame.
projectFighter:
        .a8
        stx     tmp7                ; fighter slot
        ; long pointer to the joint frame (fPtr is 3 bytes per fighter: slot*3/2)
        ldy     #0
        cpx     #0
        beq     :+
        ldy     #3
:
        lda     fPtr,y
        sta     jp
        lda     fPtr+1,y
        sta     jp+1
        lda     fPtr+2,y
        sta     jp+2
        ; relative position -> camera space origin
        rep     #$20
        .a16
        lda     fX,x
        sec
        sbc     camX
        sta     tmp0                ; relx
        lda     fZ,x
        sec
        sbc     camZ
        sta     tmp1                ; relz
        lda     fY,x
        sta     yOff
        sep     #$20
        .a8
        ; R0 = (relx*cA + relz*sA) >> 7 ; F0 = (relx*sA - relz*cA) >> 7
        rep     #$20
        .a16
        lda     tmp0
        sta     mBw
        sep     #$20
        .a8
        lda     cA
        sta     mB
        jsr     smul16x8
        .a16
        sta     R0
        sep     #$20
        .a8
        lda     sA
        sta     mB
        jsr     smul16x8
        .a16
        sta     F0
        lda     tmp1
        sta     mBw
        sep     #$20
        .a8
        lda     sA
        sta     mB
        jsr     smul16x8
        .a16
        clc
        adc     R0
        sta     R0
        sep     #$20
        .a8
        lda     cA
        sta     mB
        jsr     smul16x8
        .a16
        sta     tmp2
        lda     F0
        sec
        sbc     tmp2
        sta     F0
        sep     #$20
        .a8
        ; relative facing; within 4 steps of side-on counts as side-on (no rotation maths)
        ldx     tmp7
        lda     fFace,x
        sec
        sbc     camYaw
        sta     tmp6
        stz     fast
        clc
        adc     #4
        cmp     #9
        bcs     :+
        lda     #1                  ; side-on, facing camera-right: right = jx, fwd = jz
        sta     fast
        stz     fFlip,x
        bra     @gen
:       lda     tmp6
        sec
        sbc     #124
        cmp     #9
        bcs     :+
        lda     #$FF                ; side-on, facing camera-left: right = -jx, fwd = -jz
        sta     fast
        lda     #1
        sta     fFlip,x
        bra     @gen
:       lda     tmp6
        TAX8
        lda     f:cos8,x
        sta     cD
        lda     f:sin8,x
        sta     sD
        ldx     tmp7
        lda     cD
        rol     a                   ; forward points screen-left -> mirror the models
        lda     #0
        rol     a
        sta     fFlip,x
@gen:   lda     tmp7
        bne     :+
        ldx     #0
        bra     :++
:       ldx     #40
:       stx     jIdx
        ldy     #0
@joint: lda     fast
        beq     @rot
        ; fast path
        lda     [jp],y              ; jx
        rep     #$20
        .a16
        and     #$00FF
        cmp     #$0080
        bcc     :+
        ora     #$FF00
:       bit     fast-1              ; fast = $FF -> negate
        bpl     :+
        eor     #$FFFF
        inc     a
:       clc
        adc     R0
        sta     tmp3
        sep     #$20
        .a8
        iny
        iny
        lda     [jp],y              ; jz
        dey
        dey
        rep     #$20
        .a16
        and     #$00FF
        cmp     #$0080
        bcc     :+
        ora     #$FF00
:       bit     fast-1
        bpl     :+
        eor     #$FFFF
        inc     a
:       clc
        adc     F0
        jmp     @proj
        .a8
@rot:   ; right = R0 + (jx*cD + jz*sD)>>7 ; fwd = F0 + (jz*cD - jx*sD)>>7
        lda     [jp],y              ; jx
        sta     mA
        lda     cD
        sta     mB
        jsr     smul8
        .a16
        sta     tmp2
        sep     #$20
        .a8
        iny
        iny
        lda     [jp],y              ; jz
        sta     mA
        lda     sD
        sta     mB
        jsr     smul8
        .a16
        clc
        adc     tmp2
        jsr     asr7
        clc
        adc     R0
        sta     tmp3                ; right (hu)
        sep     #$20
        .a8
        lda     cD
        sta     mB
        jsr     smul8               ; jz*cD  (mA still jz)
        .a16
        sta     tmp2
        sep     #$20
        .a8
        dey
        dey
        lda     [jp],y              ; jx
        sta     mA
        lda     sD
        sta     mB
        jsr     smul8
        .a16
        sta     tmp4
        lda     tmp2
        sec
        sbc     tmp4
        jsr     asr7
        clc
        adc     F0
@proj:  .a16
        cmp     #260                ; nearest allowed depth (keeps the scale in 8 bits)
        bpl     :+
        lda     #260
:       ldx     jIdx
        sta     jFW,x
        lsr     a
        lsr     a
        cmp     #255
        bcc     :+
        lda     #255
:       tax
        sep     #$20
        .a8
        lda     f:scale8,x
        sta     sc
        ; sx = 128 + right * sc >> 8
        rep     #$20
        .a16
        lda     tmp3
        jsr     mulSc
        .a16
        clc
        adc     #128
        ldx     jIdx
        sta     jSX,x
        ; sy = HORIZON + (CAMH2 - (jy + yOff)) * sc >> 8
        sep     #$20
        .a8
        iny
        lda     [jp],y              ; jy
        rep     #$20
        .a16
        and     #$00FF
        cmp     #$0080
        bcc     :+
        ora     #$FF00
:       clc
        adc     yOff
        sta     tmp4
        lda     #CAMH2
        sec
        sbc     tmp4
        jsr     mulSc
        .a16
        clc
        adc     #HORIZON
        ldx     jIdx
        sta     jSY,x
        inx
        inx
        stx     jIdx
        iny
        iny                         ; next joint (3 bytes)
        sep     #$20
        .a8
        cpy     #NJOINT*3
        beq     :+
        jmp     @joint
:       rts

asr7:   .a16
        cmp     #$8000
        ror     a
        cmp     #$8000
        ror     a
        cmp     #$8000
        ror     a
        cmp     #$8000
        ror     a
        cmp     #$8000
        ror     a
        cmp     #$8000
        ror     a
        cmp     #$8000
        ror     a
        rts

; A16 = signed v -> A16 = (v * sc) >> 8   (two 8x8 hardware multiplies)
mulSc:  .a16
        sta     tmp5
        bpl     :+
        eor     #$FFFF
        inc     a
:       sep     #$20
        .a8
        sta     WRMPYA              ; low byte
        lda     sc
        sta     WRMPYB
        xba                         ; high byte (while the multiplier works)
        nop
        nop
        ldx     RDMPYL
        stx     mu32
        sta     WRMPYA
        lda     sc
        sta     WRMPYB
        rep     #$20
        .a16
        nop
        nop
        nop
        lda     RDMPYL              ; hi * sc
        sta     mu32+2
        lda     mu32+1
        and     #$00FF
        clc
        adc     mu32+2
        bit     tmp5
        bpl     :+
        eor     #$FFFF
        inc     a
:       rts

; A16 = signed value v; returns A16 = v * muB >> 9 (muB = scale)
scaleSigned:
        .a16
        sta     tmp5
        bpl     :+
        eor     #$FFFF
        inc     a
:       sta     muA
        sep     #$20
        .a8
        phy
        jsr     umul16
        .a8
        ply
        rep     #$20
        .a16
        lda     mu32+1              ; >> 8
        lsr     a                   ; >> 9
        bit     tmp5
        bpl     :+
        eor     #$FFFF
        inc     a
:       rts

; ---------------------------------------------------------------- balls
; X = fighter*2.  Emits one record per ball of the fighter's character.
fighterBalls:
        .a8
        stx     tmp7
        rep     #$20
        .a16
        lda     #$7FFF
        sta     curMinX
        sta     curMinY
        stz     curMaxX
        stz     curMaxY
        sep     #$20
        .a8
        lda     fChar,x
        asl     a
        clc
        adc     fChar,x             ; *3
        TAY8
        lda     ballListTab,y
        sta     bp
        lda     ballListTab+1,y
        sta     bp+1
        lda     ballListTab+2,y
        sta     bp+2
        lda     fChar,x
        TAY8
        lda     ballCount,y
        sta     ballsLeft
        lda     tmp7                ; palette base: fighter 0 -> 0, fighter 1 -> 2
        sta     palBase
        ldy     #0
@ball:  ldx     nBall
        cpx     #80
        bcc     :+
        jmp     @fin
:       ; joints a, b (word indexes within this fighter's 20)
        lda     tmp7
        beq     :+
        lda     #40
:       sta     tmp0                ; fighter's joint base
        stz     tmp0+1
        lda     [bp],y              ; a*2
        clc
        adc     tmp0
        sta     tmp1
        stz     tmp1+1
        iny
        lda     [bp],y              ; b*2
        clc
        adc     tmp0
        sta     tmp2
        stz     tmp2+1
        iny
        lda     [bp],y              ; t
        sta     tmp3
        iny
        lda     [bp],y              ; radius (quarter texels)
        sta     tmp4
        stz     tmp4+1
        iny
        lda     [bp],y              ; material
        sta     tmp5
        iny
        phy
        lda     tmp3
        bne     @lerp
        ldx     tmp1
        rep     #$20
        .a16
        lda     jSX,x
        sta     tmp0
        lda     jSY,x
        sta     tmp3
        lda     jFW,x
        sta     tmp2
        bra     @have
        .a8
@lerp:  ; p = a + (b - a) * t >> 8  for sx, sy, fw
        rep     #$20
        .a16
        ldx     tmp2
        lda     jSX,x
        ldx     tmp1
        sec
        sbc     jSX,x
        jsr     lerpT
        .a16
        clc
        adc     jSX,x
        sta     tmp0                ; sx
        ldx     tmp1                ; depth: the nearer joint is plenty for sorting/size
        lda     tmp3
        and     #$0080
        beq     :+
        ldx     tmp2
:       lda     jFW,x
        pha
        ldx     tmp2
        lda     jSY,x
        ldx     tmp1
        sec
        sbc     jSY,x
        jsr     lerpT
        .a16
        clc
        adc     jSY,x
        sta     tmp3                ; sy
        pla
        sta     tmp2                ; fw
@have:  ; size in pixels = r4 * scale8[fw/4] >> 9
        lda     tmp2
        lsr     a
        lsr     a
        cmp     #255
        bcc     :+
        lda     #255
:       tax
        sep     #$20
        .a8
        lda     f:scale8,x
        sta     WRMPYA
        lda     tmp4
        sta     WRMPYB
        rep     #$20
        .a16
        nop
        nop
        nop
        lda     RDMPYL
        xba
        and     #$00FF
        lsr     a                   ; >> 9
        cmp     #31
        bcc     :+
        lda     #31
:       sta     tmp4                ; size index
        ; cull: centre outside -40..296 / -40..264
        lda     tmp0
        clc
        adc     #40
        cmp     #336
        bcs     @skip
        lda     tmp3
        clc
        adc     #40
        cmp     #304
        bcs     @skip
        ; record: centre, radius, colour base (1 + 3 * material), depth key
        ldx     nBall
        lda     tmp2                ; depth key = fw/8 (0..127)
        lsr     a
        lsr     a
        lsr     a
        cmp     #127
        bcc     :+
        lda     #127
:       sep     #$20
        .a8
        sta     bKey,x
        lda     tmp4
        sta     bSz,x
        rep     #$20
        .a16
        txa
        asl     a
        tax
        lda     tmp0
        sta     bSX,x
        clc
        adc     #BIAS
        sec
        sbc     tmp4
        cmp     curMinX
        bcs     :+
        sta     curMinX
:       clc
        adc     tmp4
        adc     tmp4
        cmp     curMaxX
        bcc     :+
        sta     curMaxX
:       lda     tmp3
        sta     bSY,x
        clc
        adc     #BIAS
        sec
        sbc     tmp4
        cmp     curMinY
        bcs     :+
        sta     curMinY
:       clc
        adc     tmp4
        adc     tmp4
        cmp     curMaxY
        bcc     :+
        sta     curMaxY
:       lda     tmp3
        lda     tmp5
        and     #$0003
        sta     tmp1
        asl     a
        adc     tmp1
        inc     a
        sta     bAttr,x
        inc     nBall
@skip:  sep     #$20
        .a8
        ply
        dec     ballsLeft
        beq     @fin
        jmp     @ball
@fin:   rep     #$20
        .a16
        jsr     fighterSegs
        ldx     tmp7
        lda     curMinX
        sta     boxX0,x
        lda     curMaxX
        sta     boxX1,x
        lda     curMinY
        sta     boxY0,x
        lda     curMaxY
        sta     boxY1,x
        sep     #$20
        .a8
        rts

; A16 = d (signed, |d| < 256); returns (d * t) >> 8 (signed), preserves X.  t = tmp3 low byte
lerpT:
        .a16
        sta     mBw
        bpl     :+
        eor     #$FFFF
        inc     a
:       cmp     #255
        bcc     :+
        lda     #255
:       sep     #$20
        .a8
        sta     WRMPYA
        lda     tmp3
        sta     WRMPYB
        rep     #$20
        .a16
        nop
        nop
        nop
        lda     RDMPYL
        xba
        and     #$00FF
        bit     mBw
        bpl     :+
        eor     #$FFFF
        inc     a
:       rts

ballListTab:
        .faraddr ch0_balls, ch1_balls, ch2_balls, ch3_balls, ch4_balls, ch5_balls

; ---------------------------------------------------------------- shadows (2 x 16x16 per fighter, palette 7)
; =============================================================================
; Super FX frame building
; =============================================================================
GSU_SFR  = $3030
GSU_PBR  = $3034
GSU_CFGR = $3037
GSU_SCBR = $3038
GSU_CLSR = $3039
GSU_SCMR = $303A
GSU_R15  = $301E
SCMR_CPU = $25                      ; OBJ mode, 4bpp, ROM + RAM to the 65816
SCMR_GSU = $2D                      ; ... RAM to the GSU (it never needs the ROM)
DLMAX    = 48
BIAS     = $4000

; ---------------------------------------------------------------- depth sort -> order (near first)
sortBalls:
        .a8
        rep     #$20
        .a16
        ldx     #0
:       stz     bucketN,x
        inx
        inx
        cpx     #128
        bne     :-
        sep     #$30                ; 8-bit A and index
        .a8
        .i8
        ldy     #0
:       cpy     nBall
        beq     :+
        ldx     bKey,y
        inc     bucketN,x
        iny
        bra     :-
:       lda     #0
        ldx     #0
        clc
:       sta     bucketS,x
        adc     bucketN,x
        inx
        bpl     :-                  ; 128 buckets
        ldy     #0
:       cpy     nBall
        beq     :+
        ldx     bKey,y
        lda     bucketS,x
        inc     bucketS,x
        tax
        tya
        sta     order,x
        iny
        bra     :-
:       rep     #$10
        .i16
        rts

; ---------------------------------------------------------------- boxes + display lists
buildDL:
        .a8
        rep     #$20
        .a16
        stz     tmp6
        lda     nB0
        sta     tmp7
        ldx     #0
        jsr     fighterBox
        lda     nB0
        sta     tmp6
        lda     nBall
        sta     tmp7
        ldx     #2
        jsr     fighterBox
        ldx     #0
        jsr     trailDL
        ldx     #2
        jsr     trailDL
        ; entries, far -> near (painter's order within each fighter)
        ldy     nBall
@lp:    cpy     #0
        bne     :+
        jmp     @done
:       dey
        phy
        lda     order,y
        and     #$00FF
        tay                         ; ball index
        ldx     #0
        cpy     nB0
        bcc     :+
        ldx     #2
:       lda     dlN,x
        cmp     #DLMAX
        bcc     :+
        jmp     @next
:       inc     dlN,x
        sta     tmp0                ; n
        asl     a
        adc     tmp0                ; *3
        asl     a
        asl     a                   ; *12
        adc     #14
        cpx     #0
        beq     :+
        clc
        adc     #dl1 - dl0
:       tax                         ; offset from dl0
        tya
        asl     a
        tay                         ; item word index
        lda     bSX,y
        sta     dl0+4,x
        lda     bSY,y
        sta     dl0+6,x
        lda     bSX2,y
        sta     dl0+8,x
        lda     bSY2,y
        sta     dl0+10,x
        lda     bAttr,y             ; flags | k/2 << 8
        sta     dl0,x
        lda     bShp,y              ; shape address in Game Pak RAM
        sta     dl0+2,x
@next:  ply
        jmp     @lp
@done:  jsr     burstDL
        jsr     starsDL
        ; headers: W, H, BW, FB, N
        ldx     #0
        jsr     dlHeader
        rep     #$20
        .a16
        ldx     #2
        ; fall through
dlHeader:
        .a16
        lda     dlBase,x
        sta     tmp0
        lda     boxW,x
        sta     (tmp0)
        ldy     #2
        lda     boxH,x
        sta     (tmp0),y
        ldy     #4
        lda     boxBW,x
        sta     (tmp0),y
        ldy     #6
        lda     #0
        cpx     #0
        beq     :+
        lda     #64
:       sta     (tmp0),y
        ldy     #8
        lda     dlN,x
        sta     (tmp0),y
        ldy     #10
        lda     boxOX,x
        sta     (tmp0),y
        ldy     #12
        lda     boxOY,x
        sta     (tmp0),y
        sep     #$20
        .a8
        rts

dlBase: .word   dl0, dl1

; X = fighter slot, balls tmp6..tmp7: bounding box, block layout, box origin
fighterBox:
        .a16
        stz     dlN,x
        lda     boxX0,x             ; biased bounds from fighterBalls
        sta     tmp0
        lda     boxX1,x
        sta     tmp1
        lda     boxY0,x
        sta     tmp2
        lda     boxY1,x
        sta     tmp3
@lay:   lda     tmp1
        cmp     tmp0
        bcs     :+
        lda     #BIAS               ; no balls: empty 0x0 box off to the side
        sta     tmp0
        sta     tmp1
        sta     tmp2
        sta     tmp3
:       ; keep the box for sprite culling (unbiased)
        lda     tmp0
        sec
        sbc     #BIAS
        sta     boxX0,x
        lda     tmp1
        sec
        sbc     #BIAS
        sta     boxX1,x
        lda     tmp2
        sec
        sbc     #BIAS
        sta     boxY0,x
        lda     tmp3
        sec
        sbc     #BIAS
        sta     boxY1,x
        ; wide poses (knockdowns, sweeps) use 3x2 blocks, everything else 2x3
        lda     tmp1
        sec
        sbc     tmp0
        sta     tmp4                ; width - 1
        lda     tmp3
        sec
        sbc     tmp2                ; height - 1
        cmp     tmp4
        bcs     @tall
        lda     tmp4
        cmp     #64
        bcc     @tall
        lda     #3
        sta     boxBW,x
        lda     #96
        sta     boxW,x
        lda     #64
        sta     boxH,x
        bra     @org
@tall:  lda     #2
        sta     boxBW,x
        lda     #64
        sta     boxW,x
        lda     #96
        sta     boxH,x
@org:   lda     tmp0
        clc
        adc     tmp1
        lsr     a
        sec
        sbc     #BIAS
        sta     tmp4
        lda     boxW,x
        lsr     a
        eor     #$FFFF
        sec
        adc     tmp4
        sta     boxOX,x
        lda     tmp2
        clc
        adc     tmp3
        lsr     a
        sec
        sbc     #BIAS
        sta     tmp4
        lda     boxH,x
        lsr     a
        eor     #$FFFF
        sec
        adc     tmp4
        sta     boxOY,x
        rts

; ---------------------------------------------------------------- OAM for the frame being rendered
buildOAM:
        .a8
        rep     #$20
        .a16
        stz     oamN
        ldx     #0
:       stz     oamBuf+512,x
        inx
        inx
        cpx     #32
        bne     :-
        ; hit spark on top
        lda     sparkT
        beq     @fig
        ldy     #SPARK_TILE
        cmp     #9
        bcs     :+
        ldy     #SPARK_TILE1
        cmp     #5
        bcs     :+
        ldy     #SPARK_TILE2
:       tya
        ora     #(6 << 9) | $3000
        sta     tmp2
        ldy     sparkJ
        lda     jSX,y
        sec
        sbc     #8
        sta     tmp0
        lda     jSY,y
        sec
        sbc     #8
        sta     tmp1
        stz     tmp3
        jsr     emitSpr
@fig:   ; nearer fighter first (lower OAM index wins)
        lda     jFW
        cmp     jFW+40
        bcs     :+
        ldx     #0
        jsr     fighterSprites
        ldx     #2
        jsr     fighterSprites
        bra     @sh
:       ldx     #2
        jsr     fighterSprites
        ldx     #0
        jsr     fighterSprites
@sh:    ldx     #0
        jsr     shadowOne
        ldx     #40
        jsr     shadowOne
        ; hide the rest
        lda     oamN
        asl     a
        asl     a
        tax
        sep     #$20
        .a8
:       cpx     #512
        bcs     :+
        lda     #224
        sta     oamBuf+1,x
        inx
        inx
        inx
        inx
        bra     :-
:       rts

; X = fighter slot: up to six 32x32 sprites over its box
fighterSprites:
        .a16
        stx     tmp5
        ldy     #0
@b:     sty     tmp6                ; logical block b
        ; bx, by for this layout
        lda     boxBW,x
        cmp     #3
        beq     :+
        tya
        and     #1
        sta     tmp0
        tya
        lsr     a
        sta     tmp1
        bra     :++
:       lda     blk3x,y
        and     #$00FF
        sta     tmp0
        lda     blk3y,y
        and     #$00FF
        sta     tmp1
:       ; screen position
        lda     tmp0
        xba
        lsr     a
        lsr     a
        lsr     a                   ; *32
        clc
        adc     boxOX,x
        sta     tmp0
        lda     tmp1
        xba
        lsr     a
        lsr     a
        lsr     a
        clc
        adc     boxOY,x
        sta     tmp1
        ; cull against the fighter's bounding box and the screen
        lda     tmp0
        sec
        sbc     boxX1,x
        dec     a
        bpl     @skip               ; block left of ... starts right of max x
        lda     tmp0
        clc
        adc     #31
        sec
        sbc     boxX0,x
        bmi     @skip
        lda     tmp1
        sec
        sbc     boxY1,x
        dec     a
        bpl     @skip
        lda     tmp1
        clc
        adc     #31
        sec
        sbc     boxY0,x
        bmi     @skip
        lda     tmp0
        clc
        adc     #32
        cmp     #256 + 32
        bcs     @skip
        lda     tmp1
        clc
        adc     #32
        cmp     #224 + 32
        bcs     @skip
        ; tile: columns 0-1 map 1:1 (by*64 + bx*4); a third column sits in tile row 8
        lda     bTile,y
        and     #$00FF
        ldy     boxBW,x
        cpy     #3
        bne     :+
        ldy     tmp6
        lda     bTile3,y
        and     #$00FF
:
        cpx     #0
        beq     :+
        ora     #8
:       ora     backSetBit
        sta     tmp2
        ; palette: fighter's own, or white-hot while flashing
        lda     fFlash,x
        beq     :+
        lda     #(2 << 9) | $3000
        bra     :++
:       txa
        lsr     a
        xba
        asl     a                   ; slot/2 << 9
        ora     #$3000
:       ora     tmp2
        sta     tmp2
        lda     #1
        sta     tmp3
        jsr     emitSpr
        ldx     tmp5
@skip:  ldx     tmp5
        ldy     tmp6
        iny
        cpy     #6
        beq     :+
        jmp     @b
:       rts

bTile:  .byte   0, 4, 64, 68, 128, 132
bTile3: .byte   0, 4, 128, 64, 68, 132
blk3x:  .byte   0, 1, 2, 0, 1, 2
blk3y:  .byte   0, 0, 0, 1, 1, 1

; X = pelvis joint index (0 / 40): two 16x16 halves of the ground shadow
shadowOne:
        .a16
        lda     jSX,x
        sta     tmp7
        lda     jFW,x
        lsr     a
        lsr     a
        cmp     #255
        bcc     :+
        lda     #255
:       tax
        sep     #$20
        .a8
        lda     f:scale8,x
        sta     sc
        rep     #$20
        .a16
        lda     #CAMH2
        jsr     mulSc
        .a16
        clc
        adc     #HORIZON
        sec
        sbc     #8
        sta     tmp1
        lda     tmp7
        sec
        sbc     #16
        sta     tmp0
        lda     #SHADOW_TILE | (7 << 9) | $3000
        sta     tmp2
        stz     tmp3
        jsr     emitSpr
        lda     tmp7
        sta     tmp0
        lda     #SHADOW_TILE2 | (7 << 9) | $3000
        sta     tmp2
        jmp     emitSpr

; tmp0 = x, tmp1 = y, tmp2 = attribute word, tmp3 = large (0/1)
emitSpr:
        .a16
        lda     oamN
        cmp     #128
        bcs     @rts
        asl     a
        asl     a
        tax
        lda     tmp0
        and     #$00FF
        sta     tmp4
        lda     tmp1
        xba
        ora     tmp4
        sta     oamBuf,x            ; x, y
        lda     tmp2
        sta     oamBuf+2,x          ; tile, attributes
        ; high table: (size << 1 | x bit 8) << (2 * (n & 3))
        lda     tmp3
        asl     a
        sta     tmp4
        lda     tmp0+1
        and     #1
        ora     tmp4
        sta     tmp4
        lda     oamN
        and     #3
        tay
        lda     tmp4
:       dey
        bmi     :+
        asl     a
        asl     a
        bra     :-
:       sta     tmp4
        lda     oamN
        lsr     a
        lsr     a
        tax
        sep     #$20
        .a8
        lda     oamBuf+512,x
        ora     tmp4
        sta     oamBuf+512,x
        rep     #$20
        .a16
        inc     oamN
@rts:   rts

; ---------------------------------------------------------------- hand the frame to the Super FX
gsuKick:
        .a16
        sep     #$20
        .a8
:       lda     GSU_SFR
        and     #$20
        bne     :-                  ; (it finished long ago; never spins in practice)
        lda     #SCMR_CPU
        sta     GSU_SCMR
        rep     #$20
        .a16
        lda     shapeDirty
        and     #$00FF
        beq     :+
        jsr     loadShapes
        sep     #$20
        .a8
        stz     shapeDirty
        rep     #$20
        .a16
:
        lda     dlN                 ; 14 + 12 * N bytes each
        asl     a
        adc     dlN
        asl     a
        asl     a
        clc
        adc     #14
        sta     tmp0
        ldx     #0
:       lda     dl0,x
        sta     f:$706000,x
        inx
        inx
        cpx     tmp0
        bcc     :-
        lda     dlN+2
        asl     a
        adc     dlN+2
        asl     a
        asl     a
        clc
        adc     #14
        sta     tmp0
        ldx     #0
:       lda     dl1,x
        sta     f:$706400,x
        inx
        inx
        cpx     tmp0
        bcc     :-
        sep     #$20
        .a8
        lda     #SCMR_GSU
        sta     GSU_SCMR
        lda     #$70
        sta     GSU_PBR
        ldx     #GSU_START
        stx     GSU_R15             ; writing R15's high byte starts the GSU
        lda     #1
        sta     upState
        rts

; ---------------------------------------------------------------- boot: Super FX setup
gsuInit:
        .a8
        lda     #1
        sta     GSU_CLSR            ; 21 MHz
        lda     #$80
        sta     GSU_CFGR            ; no IRQ on STOP
        lda     #2
        sta     GSU_SCBR            ; screen at $70:0800
        lda     #SCMR_CPU
        sta     GSU_SCMR
        ; program + circle table into Game Pak RAM
        ldx     #0
:       lda     f:gsu_code,x
        sta     f:$704000,x
        inx
        cpx     #GSU_SIZE
        bne     :-
        ldx     #0
:       lda     f:gsu_circ,x
        sta     f:$702000,x
        inx
        cpx     #512 + 1024
        bne     :-
        ; clear both tile sets' fighter rows in VRAM? (they start blank from the OBJ upload)
        stz     upState
        stz     backSetBit
        stz     backSetBit+1
        rts

; =============================================================================
; Super FX effects: motion trails on the striking limb, impact bursts
; =============================================================================
; X = slot: remember where the striking joint was over the last few frames
trailUpdate:
        .a16
        lda     fState,x
        cmp     #ST_ATTACK
        bne     @clear
        jsr     setMovePtr
        ldy     #MR_A1
        lda     [mp],y
        and     #$00FF
        clc
        adc     #3                  ; keep the trail a little past the hit
        cmp     fFrame,x
        bcc     @clear
        ldy     #MR_HJ
        lda     [mp],y
        and     #$00FF
        ldy     #0
:       cmp     #3                  ; joint*3 -> joint*2
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
:       tay
        lda     jSX,y
        sta     tmp2
        lda     jSY,y
        sta     tmp3
        txa
        asl     a
        asl     a                   ; slot*4 = byte base of this fighter's 4-word ring
        clc
        adc     trI,x
        adc     trI,x               ; + index*2
        tay
        lda     tmp2
        sta     trX,y
        lda     tmp3
        sta     trY,y
        lda     trI,x
        inc     a
        and     #3
        sta     trI,x
        lda     trN,x
        cmp     #4
        bcs     :+
        inc     trN,x
:       rts
@clear: stz     trN,x
        rts

; X = slot: ghost discs at the older positions, oldest (smallest) first
trailDL:
        .a16
        lda     trN,x
        cmp     #2
        bcs     :+
        rts
:       dec     a                   ; ages 1 .. n-1
        sta     tmp6
@age:   ; ring index of age k = (trI - 1 - k) & 3
        lda     trI,x
        clc
        sbc     tmp6
        and     #3
        asl     a
        sta     tmp7
        txa
        asl     a
        asl     a
        clc
        adc     tmp7
        tay
        lda     trX,y
        sta     tmp2
        lda     trY,y
        sta     tmp3
        ldy     tmp6
        lda     trailLook-1,y       ; age 1: r 4 white, 2: r 3 gold, 3: r 2 gold
        and     #$00FF
        asl     a
        tay
        lda     trailEnt,y
        sta     tmp4
        jsr     dlAdd
        dec     tmp6
        bne     @age
        rts
trailLook: .byte 0, 1, 2
trailEnt:  .word 4 | (13 << 8), 3 | (14 << 8), 2 | (14 << 8)

; dizzy: three stars circling the head
starsDL:
        .a16
        ldx     #0
        ldy     #6
        lda     fState
        cmp     #ST_DIZZY
        beq     @go
        ldx     #2
        ldy     #46
        lda     fState+2
        cmp     #ST_DIZZY
        beq     @go
        rts
@go:    lda     jSX,y
        sta     tmp5
        lda     jSY,y
        sec
        sbc     #8
        sta     tmp7
        lda     frameCount
        asl     a
        asl     a
        asl     a
        sta     tmp6
        lda     #3
        sta     tmp1
@one:   lda     tmp6
        and     #$00FF
        tay
        lda     cos8,y
        and     #$00FF
        cmp     #$0080
        bcc     :+
        ora     #$FF00
:       cmp     #$8000
        ror     a
        cmp     #$8000
        ror     a
        cmp     #$8000
        ror     a
        cmp     #$8000
        ror     a                       ; /16: +-8 px
        sta     tmp0
        cmp     #$8000
        ror     a
        clc
        adc     tmp0                    ; x1.5: +-12 px
        clc
        adc     tmp5
        sta     tmp2
        lda     sin8,y
        and     #$00FF
        cmp     #$0080
        bcc     :+
        ora     #$FF00
:       cmp     #$8000
        ror     a
        cmp     #$8000
        ror     a
        cmp     #$8000
        ror     a
        cmp     #$8000
        ror     a
        cmp     #$8000
        ror     a                       ; /32: +-4 px (a tilted ring)
        clc
        adc     tmp7
        sta     tmp3
        lda     tmp1
        lsr     a
        lda     #3 | (14 << 8)
        bcc     :+
        lda     #3 | (13 << 8)
:       sta     tmp4
        jsr     dlAdd
        lda     tmp6
        clc
        adc     #85
        sta     tmp6
        dec     tmp1
        bne     @one
        rts

; hit burst: six sparks flying out from the impact point (drawn in front)
burstDL:
        .a16
        lda     sparkT
        bne     :+
        rts
:       ldx     #0
        ldy     sparkJ
        cpy     #40
        bcc     :+
        ldx     #2
:       lda     jSX,y
        sta     tmp5
        lda     jSY,y
        sta     tmp7
        ; phase 0 (T 12..9), 1 (8..5), 2 (4..1)
        lda     sparkT
        ldy     #0
        cmp     #9
        bcs     :+
        ldy     #12
        cmp     #5
        bcs     :+
        ldy     #24
:       sty     tmp6
        lda     #6
        sta     tmp1
@one:   ldy     tmp6
        lda     burstXY,y
        and     #$00FF
        cmp     #$0080
        bcc     :+
        ora     #$FF00
:       clc
        adc     tmp5
        sta     tmp2
        lda     burstXY+1,y
        and     #$00FF
        cmp     #$0080
        bcc     :+
        ora     #$FF00
:       clc
        adc     tmp7
        sta     tmp3
        lda     tmp6
        cmp     #12
        lda     #3 | (13 << 8)
        bcc     :+
        lda     #2 | (14 << 8)
:       sta     tmp4
        jsr     dlAdd
        inc     tmp6
        inc     tmp6
        dec     tmp1
        bne     @one
        rts
burstXY: .byte  6, 0, 3, 5, <-3, 5, <-6, 0, <-3, <-5, 3, <-5
        .byte   12, 0, 6, 10, <-6, 10, <-12, 0, <-6, <-10, 6, <-10
        .byte   17, 0, 9, 15, <-9, 15, <-17, 0, <-9, <-15, 9, <-15

; X = slot, tmp2/tmp3 = screen centre, tmp4 = radius | colour << 8: append a disc
dlAdd:
        .a16
        lda     dlN,x
        cmp     #DLMAX
        bcs     @full
        inc     dlN,x
        sta     tmp0
        asl     a
        adc     tmp0
        asl     a
        asl     a
        adc     #14
        adc     dlBase,x
        sta     tmp0
        lda     tmp4                ; colour | r << 8
        xba
        sta     (tmp0)
        lda     #0
        ldy     #2
        sta     (tmp0),y
        lda     tmp2
        ldy     #4
        sta     (tmp0),y
        lda     tmp3
        ldy     #6
        sta     (tmp0),y
@full:  rts

; =============================================================================
; limb polygons: one entry per bone segment, straight from the projected joints
; =============================================================================
; tmp7 = slot.  Appends segments to the item arrays and grows the fighter's bbox.
fighterSegs:
        .a16
        ldx     tmp7
        lda     fChar,x
        and     #$00FF
        tay
        lda     segCount,y
        and     #$00FF
        sta     ballsLeft
        tya
        asl     a
        asl     a
        tay
        lda     segTab,y
        sta     bp
        lda     segTab+1,y
        sta     bp+1
        lda     #0
        cpx     #0
        beq     :+
        lda     #40
:       sta     tmp6                ; joint base of this fighter
        ldy     #0
@seg:   ldx     nBall
        cpx     #80
        bcc     :+
        rts
:       phy
        lda     [bp],y              ; a*2 | b*2 << 8
        pha
        and     #$00FF
        clc
        adc     tmp6
        sta     tmp1                ; joint A index
        pla
        xba
        and     #$00FF
        clc
        adc     tmp6
        sta     tmp2                ; joint B index
        iny
        iny
        lda     [bp],y              ; wa4 | wb4 << 8
        sta     tmp3
        iny
        iny
        lda     [bp],y
        and     #$0003
        sta     tmp5                ; material
        ; depth = mean of the ends
        ldx     tmp1
        lda     jFW,x
        ldx     tmp2
        clc
        adc     jFW,x
        ror     a
        sta     tmp4
        lsr     a
        lsr     a
        cmp     #255
        bcc     :+
        lda     #255
:       tax
        sep     #$20
        .a8
        lda     f:scale8,x
        sta     WRMPYA
        lda     tmp3
        sta     WRMPYB              ; wa
        rep     #$20
        .a16
        nop
        nop
        lda     RDMPYL
        xba
        and     #$00FF
        lsr     a
        cmp     #31
        bcc     :+
        lda     #31
:       sta     tmp0                ; wa (px)
        sep     #$20
        .a8
        lda     tmp3+1
        sta     WRMPYB              ; wb
        rep     #$20
        .a16
        nop
        nop
        lda     RDMPYL
        xba
        and     #$00FF
        lsr     a
        cmp     #31
        bcc     :+
        lda     #31
:       sta     tmp3                ; wb (px)
        ; record
        ldx     nBall
        lda     tmp4
        lsr     a
        lsr     a
        lsr     a
        cmp     #127
        bcc     :+
        lda     #127
:       sep     #$20
        .a8
        sta     bKey,x
        lda     tmp0
        sta     bSz,x
        lda     tmp3
        sta     bSz2,x
        rep     #$20
        .a16
        lda     tmp0                ; bbox margin = max width
        cmp     tmp3
        bcs     :+
        lda     tmp3
:       sta     tmp0
        txa
        asl     a
        tax
        lda     tmp5
        sta     tmp4
        asl     a
        adc     tmp4
        inc     a
        ora     #$0080              ; segment flag
        sta     bAttr,x
        ldy     tmp1
        lda     jSX,y
        sta     bSX,x
        jsr     bbX
        lda     jSY,y
        sta     bSY,x
        jsr     bbY
        ldy     tmp2
        lda     jSX,y
        sta     bSX2,x
        jsr     bbX
        lda     jSY,y
        sta     bSY2,x
        jsr     bbY
        inc     nBall
        ply
        iny
        iny
        iny
        iny
        iny
        dec     ballsLeft
        beq     :+
        jmp     @seg
:       rts

; grow the current bbox by point A (x or y) +- tmp0
bbX:    .a16
        clc
        adc     #BIAS
        sec
        sbc     tmp0
        cmp     curMinX
        bcs     :+
        sta     curMinX
:       clc
        adc     tmp0
        adc     tmp0
        cmp     curMaxX
        bcc     :+
        sta     curMaxX
:       rts
bbY:    .a16
        clc
        adc     #BIAS
        sec
        sbc     tmp0
        cmp     curMinY
        bcs     :+
        sta     curMinY
:       clc
        adc     tmp0
        adc     tmp0
        cmp     curMaxY
        bcc     :+
        sta     curMaxY
:       rts

segTab: .faraddr ch0_segs
        .byte   0
        .faraddr ch1_segs
        .byte   0
        .faraddr ch2_segs
        .byte   0
        .faraddr ch3_segs
        .byte   0
        .faraddr ch4_segs
        .byte   0
        .faraddr ch5_segs
        .byte   0

; A16 -> clamp to 0..255
clamp8: .a16
        bpl     :+
        lda     #0
        rts
:       cmp     #256
        bcc     :+
        lda     #255
:       rts

; =============================================================================
; sculpted parts: one display-list entry per body part
; =============================================================================
; X = slot.  Part table entry: a*2, b*2, side (0/1 n/2 f), bias near, bias far, 0, off near, off far
fighterParts:
        .a8
        stx     tmp7
        rep     #$20
        .a16
        lda     #$7FFF
        sta     curMinX
        sta     curMinY
        stz     curMaxX
        stz     curMaxY
        lda     fChar,x
        and     #$00FF
        sta     tmp0
        asl     a
        asl     a
        tay
        lda     partTab,y
        sta     bp
        lda     partTab+1,y
        sta     bp+1
        lda     [bp]
        and     #$00FF
        sta     ballsLeft
        ; joint base, GSU shape base, near side (smaller depth = nearer)
        lda     #0
        ldy     #$7000
        cpx     #0
        beq     :+
        lda     #40
        ldy     #$9000
:       sta     tmp6
        sty     tmp5
        tax
        stz     tmp4                ; tmp4 = 1 if the 'n' limbs are the near ones
        lda     jFW+8,x
        cmp     jFW+14,x
        bcs     :+
        inc     tmp4
:       ldy     #1
@part:  ldx     nBall
        cpx     #80
        bcc     :+
        jmp     @fin
:       phy
        lda     [bp],y              ; a*2 | b*2 << 8
        and     #$00FF
        clc
        adc     tmp6
        sta     tmp1
        lda     [bp],y
        xba
        and     #$00FF
        clc
        adc     tmp6
        sta     tmp2
        iny
        iny
        lda     [bp],y              ; side | bias near << 8
        sta     tmp3
        iny
        lda     [bp],y              ; bias near | bias far << 8
        sta     tmp0
        iny
        iny
        iny                         ; -> off near
        ; far limb? (side n and n not near) or (side f and n near)
        lda     tmp3
        and     #$00FF
        beq     @near
        cmp     #1
        bne     :+
        lda     tmp4
        bne     @near
        bra     @far
:       lda     tmp4
        beq     @near
@far:   iny
        iny                         ; -> off far
        lda     tmp0
        xba
        bra     :+
@near:  lda     tmp0
:       and     #$00FF
        cmp     #$0080
        bcc     :+
        ora     #$FF00
:       asl     a
        asl     a
        asl     a                   ; bias * 8 hu toward the camera
        sta     tmp0
        lda     [bp],y
        clc
        adc     tmp5
        pha                         ; shape address
        ; depth = mean of the ends - bias
        ldx     tmp1
        lda     jFW,x
        ldx     tmp2
        clc
        adc     jFW,x
        ror     a
        sec
        sbc     tmp0
        bpl     :+
        lda     #0
:       sta     tmp0
        ; scale for this depth
        lsr     a
        lsr     a
        cmp     #255
        bcc     :+
        lda     #255
:       tax
        sep     #$20
        .a8
        lda     f:scale8,x
        rep     #$20
        .a16
        and     #$00FF
        sta     tmp3                ; k
        ; record the item
        ldx     nBall
        lda     tmp0
        lsr     a
        lsr     a
        lsr     a
        cmp     #127
        bcc     :+
        lda     #127
:       sep     #$20
        .a8
        sta     bKey,x
        rep     #$20
        .a16
        txa
        asl     a
        tax
        pla
        sta     bShp,x
        lda     tmp3
        lsr     a
        xba                         ; k/2 << 8
        ldy     tmp7
        ora     fFlip,y
        ora     #$0040
        sta     bAttr,x
        ; ends + bounding box (margin ~12 units at this scale)
        lda     tmp3
        lsr     a
        lsr     a
        lsr     a
        lsr     a
        sta     tmp0
        ldy     tmp1
        lda     jSX,y
        sta     bSX,x
        jsr     bbX
        lda     jSY,y
        sta     bSY,x
        jsr     bbY
        ldy     tmp2
        lda     jSX,y
        sta     bSX2,x
        jsr     bbX
        lda     jSY,y
        sta     bSY2,x
        jsr     bbY
        inc     nBall
        ply
        tya
        clc
        adc     #10
        tay
        dec     ballsLeft
        beq     @fin
        jmp     @part
@fin:   ldx     tmp7
        lda     curMinX
        sta     boxX0,x
        lda     curMaxX
        sta     boxX1,x
        lda     curMinY
        sta     boxY0,x
        lda     curMaxY
        sta     boxY1,x
        sep     #$20
        .a8
        rts

partTab: .faraddr ch0_parts
        .byte   0
        .faraddr ch1_parts
        .byte   0
        .faraddr ch2_parts
        .byte   0
        .faraddr ch3_parts
        .byte   0
        .faraddr ch4_parts
        .byte   0
        .faraddr ch5_parts
        .byte   0
shapeTab: .faraddr ch0_shapes
        .byte   0
        .faraddr ch1_shapes
        .byte   0
        .faraddr ch2_shapes
        .byte   0
        .faraddr ch3_shapes
        .byte   0
        .faraddr ch4_shapes
        .byte   0
        .faraddr ch5_shapes
        .byte   0

; copy both fighters' shapes into Game Pak RAM ($70:7000 / $70:9000); GSU must be idle
loadShapes:
        .a16
        ldx     #0
        jsr     @one
        ldx     #2
@one:   lda     fChar,x
        and     #$00FF
        asl     a
        asl     a
        tay
        lda     shapeTab,y
        sta     bp
        lda     shapeTab+1,y
        sta     bp+1
        lda     [bp]
        sta     tmp1                ; size
        lda     #$7000
        cpx     #0
        beq     :+
        lda     #$9000
:       sta     jp
        sep     #$20
        .a8
        lda     #$70
        sta     jp+2
        rep     #$20
        .a16
        ldy     #0
:       iny
        iny
        lda     [bp],y
        dey
        dey
        sta     [jp],y
        iny
        iny
        cpy     tmp1
        bcc     :-
        rts
