; ---------------------------------------------------------------- arithmetic (hardware 8x8 multiplier)
; All routines: call with A 8-bit, X/Y 16-bit.  They return with A 16-bit (result) unless noted.

; A16 = mA * mB  (signed 8 x signed 8)
smul8:
        .a8
        lda     mA
        eor     mB
        sta     mS
        lda     mA
        bpl     :+
        eor     #$FF
        inc     a
:       sta     WRMPYA
        lda     mB
        bpl     :+
        eor     #$FF
        inc     a
:       sta     WRMPYB
        lda     mS              ; (waiting for the multiplier)
        rep     #$20
        .a16
        bmi     @neg
        lda     RDMPYL
        rts
@neg:   lda     RDMPYL
        eor     #$FFFF
        inc     a
        rts

; A16 = (mBw * mB) >> 7   (signed 16 x signed 8, 1.7 fixed sine/cosine)
smul16x8:
        .a8
        lda     mBw+1
        eor     mB
        sta     mS
        rep     #$20
        .a16
        lda     mBw
        bpl     :+
        eor     #$FFFF
        inc     a
:       sta     muA
        sep     #$20
        .a8
        lda     mB
        bpl     :+
        eor     #$FF
        inc     a
:       sta     muB
        lda     muA
        sta     WRMPYA
        lda     muB
        sta     WRMPYB          ; lo * b
        rep     #$20
        .a16
        nop
        nop
        nop
        lda     RDMPYL
        sta     mu32
        sep     #$20
        .a8
        lda     muA+1
        sta     WRMPYA
        lda     muB
        sta     WRMPYB          ; hi * b
        rep     #$20
        .a16
        stz     mu32+2
        nop
        lda     RDMPYL
        clc
        adc     mu32+1
        sta     mu32+1          ; 24-bit product in mu32..mu32+2
        sep     #$20            ; >> 7 = (bytes 1..2 << 1) | bit 7 of byte 0
        .a8
        lda     mu32
        asl     a
        rep     #$20
        .a16
        lda     mu32+1
        rol     a
        bit     mS-1            ; sign in bit 15 of (mS-1..mS)
        bpl     :+
        eor     #$FFFF
        inc     a
:       rts

; mu32 = muA * muB  (unsigned 16 x 16)
umul16:
        .a8
        lda     muA
        sta     WRMPYA
        lda     muB
        sta     WRMPYB
        rep     #$20
        .a16
        stz     mu32+2
        lda     RDMPYL
        sta     mu32
        sep     #$20
        .a8
        lda     muB+1
        sta     WRMPYB
        rep     #$20
        .a16
        nop
        nop
        nop
        lda     RDMPYL
        clc
        adc     mu32+1
        sta     mu32+1
        sep     #$20
        .a8
        lda     #0
        adc     #0
        sta     mu32+3
        lda     muA+1
        sta     WRMPYA
        lda     muB
        sta     WRMPYB
        rep     #$20
        .a16
        nop
        nop
        nop
        lda     RDMPYL
        clc
        adc     mu32+1
        sta     mu32+1
        sep     #$20
        .a8
        lda     mu32+3
        adc     #0
        sta     mu32+3
        lda     muB+1
        sta     WRMPYB
        rep     #$20
        .a16
        nop
        nop
        nop
        lda     RDMPYL
        clc
        adc     mu32+2
        sta     mu32+2
        sep     #$20
        .a8
        rts
