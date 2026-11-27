; =============================================================================
; sound: upload the SPC700 program through the IPL boot ROM, then talk to the
; driver through the APU ports (see tools/spc.py)
; =============================================================================
.include "sound.inc"

spcUpload:
        .a8
:       ldx     APUIO0
        cpx     #$BBAA                  ; IPL ready
        bne     :-
        ldx     #SPC_LOAD
        stx     APUIO2
        lda     #1
        sta     APUIO1
        lda     #$CC
        sta     APUIO0
:       cmp     APUIO0
        bne     :-
        ldx     #0
@lp:    lda     f:spcData,x
        sta     APUIO1
        txa
        sta     APUIO0
:       cmp     APUIO0
        bne     :-
        inx
        cpx     #SPC_SIZE
        bne     @lp
        ldy     #SPC_ENTRY
        sty     APUIO2
        stz     APUIO1
        txa
        inc     a
        bne     :+
        inc     a
:       sta     APUIO0
:       cmp     APUIO0
        bne     :-
        stz     sndSeq
        rts

; A16 = sound effect id
playSfx:
        .a16
        sep     #$20
        .a8
        sta     APUIO1
        inc     sndSeq
        lda     sndSeq
        sta     APUIO0
        rep     #$20
        .a16
        rts

; A16 = song id (0 stops)
playSong:
        .a16
        sep     #$20
        .a8
        sta     APUIO2
        rep     #$20
        .a16
        rts

.segment "BANK14"
spcData: .incbin "spc.bin"
.segment "CODE"
