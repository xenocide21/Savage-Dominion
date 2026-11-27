; =============================================================================
; game: pads, palettes, line-of-fight angle, joint-frame pointers, camera
; =============================================================================
readPads:                           ; take the oldest queued sample (one per logic tick)
        .a8
        rep     #$20
        .a16
        lda     padTail
        and     #PADQ_LEN - 1
        asl     a
        asl     a
        tax
        lda     padQ,x
        sta     pad
        eor     padOld
        and     pad
        sta     padP
        lda     pad
        sta     padOld
        lda     padQ+2,x
        sta     pad+2
        eor     padOld+2
        and     pad+2
        sta     padP+2
        lda     pad+2
        sta     padOld+2
        inc     padTail
        sep     #$20
        .a8
        rts

; palettes: fighter 0 -> OBJ 0,1 ; fighter 1 -> OBJ 2,3 (alt costume if same character)
loadFighterPalettes:
        .a8
        ; OBJ palette 2: hit flash (white-hot)
        lda     #$A0
        sta     CGADD
        ldx     #0
:       lda     flashPal,x
        sta     CGDATA
        inx
        cpx     #32
        bne     :-
        lda     #$80                ; fighter 0 -> OBJ palette 0
        sta     CGADD
        ldx     #0
        jsr     onePal
        lda     #$90                ; fighter 1 -> OBJ palette 1
        sta     CGADD
        ldx     #2
        ; fall through
onePal:
        lda     fChar,x
        asl     a
        clc
        adc     fChar,x
        rep     #$20
        .a16
        and     #$00FF
        tay
        lda     palTab,y
        sta     npt
        lda     palTab+1,y
        sta     npt+1
        sep     #$20
        .a8
        ldy     #0
        cpx     #0
        beq     :+
        lda     fChar
        cmp     fChar+2
        bne     :+
        ldy     #32                 ; same character: alternate costume
:       lda     [npt],y
        sta     CGDATA
        iny
        tya
        and     #$1F
        bne     :-
        rts
flashPal: .word 0
        .repeat 15, i
        .word   ((31 - (14 - i) / 3) << 10) | ((31 - (14 - i) / 4) << 5) | 31
        .endrepeat

; lineAng = angle of (p2 - p1)
facing:
        .a8
        rep     #$20
        .a16
        lda     fX+2
        sec
        sbc     fX
        sta     tmp0
        lda     fZ+2
        sec
        sbc     fZ
        sta     tmp1
        ; scale down until both fit in -32..31
:       lda     tmp0
        clc
        adc     #32
        cmp     #64
        bcs     @shr
        lda     tmp1
        clc
        adc     #32
        cmp     #64
        bcc     @ok
@shr:   lda     tmp0
        cmp     #$8000
        ror     a
        sta     tmp0
        lda     tmp1
        cmp     #$8000
        ror     a
        sta     tmp1
        bra     :-
@ok:    lda     tmp1
        clc
        adc     #32
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a                   ; (dy+32)*64
        clc
        adc     tmp0
        clc
        adc     #32
        tax
        sep     #$20
        .a8
        lda     f:atan64,x
        sta     lineAng
        stz     lineAng+1
        rts

; X = fighter*2 -> fPtr = anim frame data + frame * FRAMESZ (each anim entry: addr, count, bank)
framePtr:
        .a8
        stx     tmp7
        lda     fChar,x
        asl     a
        asl     a                   ; *4: per-char anim table pointer
        rep     #$20
        .a16
        and     #$00FF
        tay
        lda     fAnim,x
        asl     a
        asl     a                   ; anim entry 4 bytes
        clc
        adc     animTabLo,y
        sta     tmp0
        sep     #$20
        .a8
        lda     animTabBk,y
        sta     tmp0+2
        rep     #$20
        .a16
        ldy     #0
        lda     [tmp0],y            ; frame data address
        sta     tmp2
        lda     #0                  ; fFrame * FRAMESZ (shift and add)
        .repeat 8, i
        asl     a
        .if (FRAMESZ >> (7 - i)) & 1
        clc
        adc     fFrame,x
        .endif
        .endrepeat
        clc
        adc     tmp2
        ldy     tmp7                ; slot -> fPtr offset (0 or 3)
        beq     :+
        ldy     #3
:       sta     fPtr,y
        sep     #$20
        .a8
        phy
        ldy     #3
        lda     [tmp0],y            ; bank
        ply
        sta     fPtr+2,y
        ldx     tmp7
        rts


; camera: side on, tracking the midpoint between the fighters, stopping near the walls
cameraFollow:
        .a8
        rep     #$20
        .a16
        stz     camYaw
        lda     camDist
        sta     camZ
        lda     fX
        clc
        adc     fX+2
        cmp     #$8000
        ror     a                   ; mid x
        bmi     @neg
        cmp     #CAMX_MAX
        bcc     @st
        lda     #CAMX_MAX
        bra     @st
@neg:   cmp     #.loword(-CAMX_MAX)
        bcs     @st
        lda     #.loword(-CAMX_MAX)
@st:    sta     camX
        sep     #$20
        .a8
        rts

.include "engine.s"
