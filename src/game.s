; =============================================================================
; game: pads, palettes, line-of-fight angle, joint-frame pointers, camera
; =============================================================================
readPads:
        .a8
:       lda     HVBJOY              ; wait for auto-joypad read to finish
        and     #$01
        bne     :-
        rep     #$20
        .a16
        lda     JOY1L
        tax
        eor     padOld
        and     JOY1L
        sta     padP
        stx     padOld
        stx     pad
        lda     JOY2L
        tax
        eor     padOld+2
        and     JOY2L
        sta     padP+2
        stx     padOld+2
        stx     pad+2
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
palTab: .faraddr ch0_pal, ch1_pal, ch2_pal, ch3_pal, ch4_pal, ch5_pal

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

; X = fighter*2 -> fPtr = anim frame data + frame * 60 (each anim entry: addr, count, bank)
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
        lda     fFrame,x
        asl     a
        asl     a                   ; *4
        sta     tmp4
        asl     a
        asl     a                   ; *16
        clc
        adc     tmp4                ; *20
        sta     tmp4
        asl     a
        clc
        adc     tmp4                ; *60
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

; per character anim table (lo word, bank), 4 bytes per char
animTabLo: .word .loword(ch0_anim)
animTabBk: .byte ^ch0_anim, 0
           .word .loword(ch1_anim)
           .byte ^ch1_anim, 0
           .word .loword(ch2_anim)
           .byte ^ch2_anim, 0
           .word .loword(ch3_anim)
           .byte ^ch3_anim, 0
           .word .loword(ch4_anim)
           .byte ^ch4_anim, 0
           .word .loword(ch5_anim)
           .byte ^ch5_anim, 0

; camera: yaw eases toward fighter 0's facing (so P1 is on the left), position =
; midpoint - forward * distance
cameraFollow:
        .a8
        lda     lineAng
        clc
        adc     camOrbit                ; finishers swing the camera around
        sec
        sbc     camYaw
        beq     @pos
        bmi     @dec
        inc     camYaw
        cmp     #8
        bcc     @pos
        inc     camYaw
        bra     @pos
@dec:   dec     camYaw
        cmp     #$F8
        bcs     @pos
        dec     camYaw
@pos:   ; distance grows with separation
        rep     #$20
        .a16
        lda     fX
        clc
        adc     fX+2
        cmp     #$8000
        ror     a
        sta     tmp0                ; mid x
        lda     fZ
        clc
        adc     fZ+2
        cmp     #$8000
        ror     a
        sta     tmp1                ; mid z
        ; camX = midx - sin(a)*dist >> 7 ; camZ = midz + cos(a)*dist >> 7
        lda     camDist
        sta     mBw
        sep     #$20
        .a8
        ldx     camYaw
        lda     sin8,x
        sta     mB
        jsr     smul16x8
        .a16
        sta     tmp2
        lda     tmp0
        sec
        sbc     tmp2
        sta     camX
        sep     #$20
        .a8
        ldx     camYaw
        lda     cos8,x
        sta     mB
        jsr     smul16x8
        .a16
        clc
        adc     tmp1
        sta     camZ
        sep     #$20
        .a8
        rts

.include "engine.s"
