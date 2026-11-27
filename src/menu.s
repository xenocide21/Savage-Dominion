; =============================================================================
; Menus & presentation: the static "menu display" (Mode 1: BG1 fighter lineup,
; BG2 sunset arena with drifting clouds, BG3 text/logo, OBJ embers, HDMA sky), the
; splash sequence, main menu, options, records, move lists, saved tournament records.
; All routines: A16 / I16 unless noted.
; =============================================================================
.include "menu.inc"
.import line_tiles, scen_tiles, line_map, scen_map, logo2, logo_map, menu_pal, menu_sky, menu_obj
.import movelists, fadeTab

SC_SPLASH  = 3
SC_MENU    = 4
SC_OPTIONS = 5
SC_RECORDS = 6
SC_MOVES   = 7

GM_TOURN = 0
GM_VS    = 1
GM_PRACT = 2

NGROUP   = 12           ; palette fade groups
G_TEXT   = 0
G_LOGO1  = 1
G_LOGO2  = 2
G_LOGO3  = 3
G_SCEN   = 4
G_FIGHT  = 5            ; 5..10
G_EMBER  = 11
NEMBER   = 12
REC_ADDR = $F000        ; tournament records in battery-backed Game Pak RAM ($70:F000)

; ---------------------------------------------------------------- display switching
; full-screen loads happen in forced blank with NMI off; the GSU must be idle first
dispOff:
        .a16
        MA8
        lda     #$80
        sta     INIDISP
        lda     #$01
        sta     NMITIMEN                ; joypad only
:       lda     GSU_SFR
        and     #$20
        bne     :-
        lda     #SCMR_CPU
        sta     GSU_SCMR
        stz     upState
        stz     HDMAEN
        MA16
        rts

dispOn:
        .a16
        MA8
        lda     nmiFlag
        sta     lastNmi
        lda     #$81
        sta     NMITIMEN
        MA16
        rts

.macro VDMA src, dst, size
        ldx     #dst
        stx     VMADDL
        ldx     #$1801
        stx     DMAP0
        ldx     #.loword(src)
        stx     A1T0L
        lda     #^src
        sta     A1B0
        ldx     #size
        stx     DAS0L
        lda     #$01
        sta     MDMAEN
.endmacro

enterMenuDisplay:
        .a16
        lda     dispMode
        beq     :+
        rts                             ; already there
:       jsr     dispOff
        MA8
        jsr     initHardware
        lda     #$80
        sta     VMAIN
        VDMA    line_tiles, $0000, LINE_NT * 32
        VDMA    scen_tiles, $3000, SCEN_NT * 32
        VDMA    line_map, $7000, 2048
        VDMA    scen_map, $7400, 2048
        VDMA    menu_obj, $6000, 1024
        lda     #$09                    ; mode 1, BG3 priority
        sta     BGMODE
        lda     #$70
        sta     BG1SC
        lda     #$74
        sta     BG2SC
        lda     #$58
        sta     BG3SC
        lda     #$30
        sta     BG12NBA
        lda     #$05
        sta     BG34NBA
        lda     #$63
        sta     OBSEL
        lda     #$17
        sta     TM
        stz     TS
        stz     CGWSEL
        stz     CGADSUB
        ; HDMA ch7: sky colour (CGRAM 0) per 2 lines; ch6: BG2 h-scroll (clouds)
        lda     #$03
        sta     DMAP7
        lda     #<CGADD
        sta     BBAD7
        ldx     #.loword(menu_sky)
        stx     A1T7L
        lda     #^menu_sky
        sta     A1B7
        lda     #$02
        sta     DMAP6
        lda     #<BG2HOFS
        sta     BBAD6
        ldx     #.loword(cloudTab)
        stx     A1T6L
        lda     #$80
        sta     A1B6
        lda     #$C0
        sta     HDMAEN
        MA16
        lda     #1
        sta     dispMode
        jsr     cloudInit
        jsr     emberInit
        jsr     scrClear
        lda     #1
        sta     fadeChg
        jsr     fadeApply
        jsr     dispOn
        rts

enterFightDisplay:
        .a16
        lda     dispMode
        bne     :+
        rts
:       jsr     dispOff
        MA8
        jsr     initHardware
        jsr     loadGraphics
        jsr     setupHdma
        lda     #1
        sta     palDirty
        sta     shapeDirty
        MA16
        stz     dispMode
        stz     bright
        lda     #1
        sta     hudChg
        sta     bandDirty
        jsr     dispOn
        rts

; ---------------------------------------------------------------- NMI (menu display)
menuNmi:
        .a8
        ; OAM
        stz     OAMADDL
        stz     OAMADDH
        ldx     #$0400
        stx     DMAP0
        ldx     #oamBuf
        stx     A1T0L
        lda     #$80
        sta     A1B0
        ldx     #544
        stx     DAS0L
        lda     #$01
        sta     MDMAEN
        ; palettes
        lda     cgDirty
        beq     :+
        stz     cgDirty
        stz     CGADD
        ldx     #$2200
        stx     DMAP0
        ldx     #cgBuf
        stx     A1T0L
        lda     #$80
        sta     A1B0
        ldx     #288
        stx     DAS0L
        lda     #$01
        sta     MDMAEN
:       ; text layer
        lda     scrDirty
        beq     :+
        stz     scrDirty
        lda     #$80
        sta     VMAIN
        ldx     #$5800
        stx     VMADDL
        ldx     #$1801
        stx     DMAP0
        ldx     #.loword(scrBuf)
        stx     A1T0L
        lda     #^scrBuf
        sta     A1B0
        ldx     #32 * 28 * 2
        stx     DAS0L
        lda     #$01
        sta     MDMAEN
:       lda     bright
        sta     INIDISP
        rts

; ---------------------------------------------------------------- per frame (menu display)
menuCompose:
        .a16
        lda     fadeChg
        beq     :+
        jsr     fadeApply
:       jsr     emberStep
        jsr     cloudStep
        rts

; ---------------------------------------------------------------- palette fades
; fadeLv[g]: 0 black .. 16 normal .. 32 white.  Rebuilds cgBuf for every group.
fadeApply:
        .a16
        stz     fadeChg
        ldx     #0
@g:     phx
        lda     fadeLv,x
        cmp     #33
        bcc     :+
        lda     #32
:       asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        sta     tmp1                    ; lv * 32
        lda     grpStart,x
        asl     a
        sta     tmp2                    ; colour offset (bytes)
        lda     grpCount,x
        sta     tmp3
@c:     ldx     tmp2
        lda     f:menu_pal,x
        sta     tmp0
        and     #$001F
        jsr     @ch
        sta     tmp4
        lda     tmp0
        lsr     a
        lsr     a
        lsr     a
        lsr     a
        lsr     a
        and     #$001F
        jsr     @ch
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        ora     tmp4
        sta     tmp4
        lda     tmp0
        xba
        lsr     a
        lsr     a
        and     #$001F
        jsr     @ch
        xba
        asl     a
        asl     a
        ora     tmp4
        ldx     tmp2
        sta     cgBuf,x
        inc     tmp2
        inc     tmp2
        dec     tmp3
        bne     @c
        plx
        inx
        inx
        cpx     #NGROUP * 2
        bne     @g
        lda     f:menu_pal
        sta     cgBuf
        lda     #1
        sta     cgDirty
        rts
@ch:    clc
        adc     tmp1
        tay
        lda     fadeTab,y
        and     #$00FF
        rts
grpStart: .word 1, 5, 9, 13, 17, 33, 49, 65, 81, 97, 113, 129
grpCount: .word 3, 3, 3, 3, 15, 15, 15, 15, 15, 15, 15, 3

; A = level: all groups
fadeAll:
        .a16
        ldx     #0
:       sta     fadeLv,x
        inx
        inx
        cpx     #NGROUP * 2
        bne     :-
        ldx     #1
        stx     fadeChg
        rts

; X = first group*2, Y = last group*2 (inclusive), A = level
fadeSet:
        .a16
        sty     tmp0
:       sta     fadeLv,x
        cpx     tmp0
        beq     :+
        inx
        inx
        bra     :-
:       ldx     #1
        stx     fadeChg
        rts

; ease group X*2 toward level A by 1 per call
fadeToward:
        .a16
        cmp     fadeLv,x
        beq     @r
        bcs     :+
        dec     fadeLv,x
        bra     @c
:       inc     fadeLv,x
@c:     lda     #1
        sta     fadeChg
@r:     rts

; ---------------------------------------------------------------- clouds (BG2 h-scroll via HDMA)
cloudInit:
        .a16
        stz     cl1
        stz     cl2
        ; table: [16 lines: 0] [22: far] [22: near] [1: 0] [0]
        MA8
        lda     #CLOUD_Y0
        sta     cloudTab
        lda     #(CLOUD_Y1 - CLOUD_Y0) / 2
        sta     cloudTab + 3
        sta     cloudTab + 6
        lda     #1
        sta     cloudTab + 9
        stz     cloudTab + 12
        MA16
        stz     cloudTab + 1
        stz     cloudTab + 10
        jmp     cloudStep

cloudStep:
        .a16
        lda     cl1
        clc
        adc     #24                     ; far clouds: slow
        sta     cl1
        lda     cl2
        clc
        adc     #56
        sta     cl2
        lda     cl1
        xba
        and     #$00FF
        sta     cloudTab + 4
        lda     cl2
        xba
        and     #$00FF
        sta     cloudTab + 7
        rts

; ---------------------------------------------------------------- embers (OBJ)
emberInit:
        .a16
        ldx     #0
        lda     #$F000                  ; all sprites off screen (y = 240)
:       sta     oamBuf,x
        inx
        inx
        cpx     #512
        bne     :-
:       stz     oamBuf,x                ; high table: small, x < 256
        inx
        inx
        cpx     #544
        bne     :-
        ldx     #0
@e:     jsr     rngStep
        lda     rng
        and     #$00FF
        sta     emX,x
        lda     rng+1
        and     #$00FF
        cmp     #224
        bcc     :+
        sbc     #100
:       xba
        sta     emY,x
        lda     rng
        and     #$007F
        clc
        adc     #60
        sta     emV,x
        inx
        inx
        cpx     #NEMBER * 2
        bne     @e
        rts

emberStep:
        .a16
        ldx     #0
        ldy     #0
@e:     lda     emY,x
        sec
        sbc     emV,x
        bcs     :+
        jsr     rngStep                 ; off the top: respawn at the bottom
        lda     rng
        and     #$00FF
        sta     emX,x
        lda     #(224 << 8)
:       sta     emY,x
        ; x wobble
        txa
        asl     a
        asl     a
        asl     a
        asl     a
        clc
        adc     frameCount
        and     #$00FF
        phx
        tax
        lda     sin8,x
        plx
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
        ror     a
        clc
        adc     emX,x
        sec
        sbc     #8
        MA8
        sta     oamBuf,y
        lda     emY+1,x
        sec
        sbc     #8
        sta     oamBuf+1,y
        lda     #0
        sta     oamBuf+2,y
        lda     #$30                    ; priority 3, palette 0
        sta     oamBuf+3,y
        MA16
        iny
        iny
        iny
        iny
        inx
        inx
        cpx     #NEMBER * 2
        bne     @e
        lda     emberOn
        bne     :+
        ldx     #0                      ; hidden: park them below the screen
@h:     lda     #$F0
        MA8
        sta     oamBuf+1,x
        MA16
        inx
        inx
        inx
        inx
        cpx     #NEMBER * 4
        bne     @h
:       rts

; ---------------------------------------------------------------- text layer
scrClear:
        .a16
        ldx     #0
:       lda     #$2000
        sta     f:scrBuf,x
        inx
        inx
        cpx     #32 * 28 * 2
        bne     :-
        lda     #1
        sta     scrDirty
        rts

; A = row*32 + col, Y = text (bank $80), scrAttr = palette/priority bits
scrStr:
        .a16
        asl     a
        tax
@lp:    lda     a:0,y
        and     #$00FF
        beq     @end
        sec
        sbc     #32
        ora     scrAttr
        sta     f:scrBuf,x
        inx
        inx
        iny
        bra     @lp
@end:   lda     #1
        sta     scrDirty
        rts

; A = row, Y = text: centred
scrCenter:
        .a16
        sta     tmp0
        phy
        ldx     #0
:       lda     a:0,y
        and     #$00FF
        beq     :+
        inx
        iny
        bra     :-
:       txa
        eor     #$FFFF
        sec
        adc     #32
        lsr     a                       ; (32 - len) / 2
        sta     tmp1
        lda     tmp0
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        clc
        adc     tmp1
        ply
        jmp     scrStr

; A = row: the logo (28 x 4) at columns 2..29
scrLogo:
        .a16
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        clc
        adc     #2
        asl     a
        sta     tmp0
        ldy     #0
        lda     #LOGO_H
        sta     tmp2
@row:   ldx     tmp0
        lda     #28
        sta     tmp1
:       phx
        tyx
        lda     f:logo_map,x
        plx
        sta     f:scrBuf,x
        inx
        inx
        iny
        iny
        dec     tmp1
        bne     :-
        lda     tmp0
        clc
        adc     #64
        sta     tmp0
        dec     tmp2
        bne     @row
        lda     #1
        sta     scrDirty
        rts

; A = number (0..65535), X = row*32+col: right-aligned in 5 digits? no: left-aligned, no padding
; -> writes digits into numBuf (0-terminated) for scrStr
numStr:
        .a16
        ldy     #0
        sta     tmp0
        lda     #10000
        sta     tmp1
        stz     tmp3                    ; leading digit seen
@d:     ldx     #0
        lda     tmp0
:       cmp     tmp1
        bcc     :+
        sbc     tmp1
        inx
        bra     :-
:       sta     tmp0
        txa
        bne     @put
        lda     tmp3
        bne     @put
        lda     tmp1
        cmp     #1
        bne     @skip
@put:   inc     tmp3
        txa
        clc
        adc     #'0'
        MA8
        sta     numBuf,y
        MA16
        iny
@skip:  lda     tmp1
        cmp     #1
        beq     @end
        cmp     #10000
        bne     :+
        lda     #1000
        bra     @nx
:       cmp     #1000
        bne     :+
        lda     #100
        bra     @nx
:       cmp     #100
        bne     :+
        lda     #10
        bra     @nx
:       lda     #1
@nx:    sta     tmp1
        bra     @d
@end:   MA8
        lda     #0
        sta     numBuf,y
        MA16
        rts

; A = frames -> numBuf = "M:SS"
timeStr:
        .a16
        ; seconds = frames / 60
        sta     WRDIVL
        MA8
        lda     #60
        sta     WRDIVB
        MA16
        nop
        nop
        nop
        nop
        nop
        nop
        nop
        nop
        lda     RDDIVL
        ; minutes = s / 60, ss = s % 60
        sta     WRDIVL
        MA8
        lda     #60
        sta     WRDIVB
        MA16
        nop
        nop
        nop
        nop
        nop
        nop
        nop
        nop
        lda     RDMPYL                  ; remainder
        sta     tmp5
        lda     RDDIVL
        cmp     #10
        bcc     :+
        lda     #9                      ; (cap 9:59 display)
        ldx     #59
        stx     tmp5
:       clc
        adc     #'0'
        MA8
        sta     numBuf
        lda     #':'
        sta     numBuf+1
        MA16
        lda     tmp5
        ldx     #0
:       cmp     #10
        bcc     :+
        sbc     #10
        inx
        bra     :-
:       clc
        adc     #'0'
        MA8
        sta     numBuf+3
        txa
        clc
        adc     #'0'
        sta     numBuf+2
        stz     numBuf+4
        MA16
        rts

; ---------------------------------------------------------------- volume
; APU port 3: music level (high nibble) | effects level (low nibble), 0..10 each
writeVol:
        .a16
        lda     musLv
        asl     a
        asl     a
        asl     a
        asl     a
        ora     sfxLv
        MA8
        sta     APUIO3
        MA16
        rts

; ---------------------------------------------------------------- records (battery RAM)
; layout at $70:F000: "AFFX", 5 x (time word, combos word, char byte, pad), checksum word
loadRecords:
        .a16
        MA8
        lda     #SCMR_CPU
        sta     GSU_SCMR
        MA16
        lda     f:$700000 + REC_ADDR
        cmp     #$4641                  ; "AF"
        bne     @fresh
        lda     f:$700000 + REC_ADDR + 2
        cmp     #$5846                  ; "FX"
        bne     @fresh
        ldx     #0
        stz     tmp0
:       lda     f:$700000 + REC_ADDR + 4,x
        sta     recs,x
        clc
        adc     tmp0
        sta     tmp0
        inx
        inx
        cpx     #30
        bne     :-
        lda     f:$700000 + REC_ADDR + 34
        cmp     tmp0
        beq     @ok
@fresh: ldx     #0
:       lda     #$FFFF                  ; empty slot: time $FFFF
        sta     recs,x
        stz     recs+2,x
        stz     recs+4,x
        txa
        clc
        adc     #6
        tax
        cpx     #30
        bne     :-
@ok:    rts

saveRecords:
        .a16
        MA8
        lda     #SCMR_CPU
        sta     GSU_SCMR
        MA16
        lda     #$4641
        sta     f:$700000 + REC_ADDR
        lda     #$5846
        sta     f:$700000 + REC_ADDR + 2
        ldx     #0
        stz     tmp0
:       lda     recs,x
        sta     f:$700000 + REC_ADDR + 4,x
        clc
        adc     tmp0
        sta     tmp0
        inx
        inx
        cpx     #30
        bne     :-
        lda     tmp0
        sta     f:$700000 + REC_ADDR + 34
        rts

; tournament won: insert (tTime, tCombos, fChar) by time -> recNew = slot (or $FF)
addRecord:
        .a16
        lda     #$FF
        sta     recNew
        ldx     #0
        ldy     #0
@f:     lda     tTime
        cmp     recs,x
        bcc     @ins
        txa
        clc
        adc     #6
        tax
        iny
        cpx     #30
        bne     @f
        rts
@ins:   sty     recNew
        ; shift slots down from the end
        stx     tmp0
        ldx     #24
:       cpx     tmp0
        beq     :+
        lda     recs-6,x
        sta     recs,x
        lda     recs-4,x
        sta     recs+2,x
        lda     recs-2,x
        sta     recs+4,x
        txa
        sec
        sbc     #6
        tax
        bra     :-
:       lda     tTime
        sta     recs,x
        lda     tCombos
        sta     recs+2,x
        lda     fChar
        and     #$00FF
        sta     recs+4,x
        rts

; =============================================================================
; scenes
; =============================================================================
; menu scene dispatcher (from gameTick, A16)
menuSceneTick:
        .a16
        inc     mT
        lda     scene
        sec
        sbc     #SC_SPLASH
        asl     a
        tax
        lda     @tab,x
        sta     tmp6
        jmp     (tmp6)
@tab:   .word   .loword(splashTick), .loword(mainTick), .loword(optTick), .loword(recTick), .loword(movesTick)

; any of these pressed on either pad (newly)
anyPress:
        .a16
        lda     padP
        ora     padP+2
        rts

; ---------------------------------------------------------------- splash
toSplash:
        .a16
        lda     #SC_SPLASH
        sta     scene
        stz     paused
        jsr     enterMenuDisplay
        stz     mT
        lda     #0
        jsr     fadeAll
        ldx     #G_SCEN * 2
        lda     #16
        sta     fadeLv,x
        ldx     #G_EMBER * 2
        sta     fadeLv,x
        ldx     #G_TEXT * 2
        sta     fadeLv,x
        stz     bright
        lda     #1
        sta     emberOn
        lda     #$17
        jsr     setTM
        lda     #SONG_TITLE
        jsr     playSong
        rts

; A = TM value
setTM:
        .a16
        MA8
        sta     TM
        MA16
        rts

splashTick:
        .a16
        ; brightness up over the first 30 ticks
        lda     mT
        cmp     #30
        bcs     :+
        lsr     a
        sta     bright
        bra     @rev
:       lda     #15
        sta     bright
@rev:   ; fighters light up one by one (every 36 ticks from 50): a white flash, then colour
        ldx     #0
        lda     #50
@f:     cmp     mT
        bne     :+
        phx
        stx     tmp7
        jsr     revealName
        lda     #SFX_HITHV
        jsr     playSfx
        plx
        lda     #32
        sta     fadeLv + G_FIGHT * 2,x
        lda     #1
        sta     fadeChg
        bra     @ease
:       clc
        adc     #36
        inx
        inx
        cpx     #12
        bne     @f
@ease:  lda     mT
        lsr     a
        bcs     @title
        ldx     #G_FIGHT * 2
:       lda     fadeLv,x
        cmp     #17
        bcc     :+
        dec     fadeLv,x
        lda     #1
        sta     fadeChg
:       inx
        inx
        cpx     #(G_FIGHT + 6) * 2
        bne     :--
@title: lda     mT
        cmp     #50 + 6 * 36
        bne     :+
        lda     #1
        jsr     scrLogo
        lda     #SFX_GONG
        jsr     playSfx
:       lda     mT
        cmp     #50 + 6 * 36
        bcc     @inp
        and     #3
        bne     :+
        ldx     #G_LOGO1 * 2
        lda     #16
        jsr     fadeToward
        ldx     #G_LOGO2 * 2
        lda     #16
        jsr     fadeToward
        ldx     #G_LOGO3 * 2
        lda     #16
        jsr     fadeToward
:       ; PRESS START blink
        lda     mT
        cmp     #50 + 6 * 36 + 70
        bcc     @inp
        and     #$1F
        bne     @inp
        lda     mT
        and     #$20
        beq     :+
        ldy     #.loword(txtBlank)
        bra     :++
:       ldy     #.loword(txtStart)
:       lda     #$2000
        sta     scrAttr
        lda     #26
        jsr     scrCenter
@inp:   ; START: to the home screen; or after a while on its own
        lda     mT
        cmp     #20
        bcc     :+
        jsr     anyPress
        and     #(PAD_START | PAD_A)
        bne     @go
:       lda     mT
        cmp     #1000
        bcc     :+
@go:    jmp     toTitle
:       rts

; X = fighter*2: the name above them (alternating rows so long names fit)
revealName:
        .a16
        txa
        lsr     a
        sta     tmp0
        tay
        lda     lineX,x
        lsr     a
        lsr     a
        lsr     a
        sta     tmp1                    ; centre column
        ; name length
        lda     tmp0
        asl     a
        asl     a
        asl     a
        sec
        sbc     tmp0
        tay                             ; fighterNames + 7*i
        ldx     #0
:       lda     fighterNames,y
        and     #$00FF
        cmp     #' '
        beq     :+
        sta     nameBuf,x               ; (word writes, fixed up below)
        iny
        inx
        cpx     #7
        bne     :-
:       MA8
        stz     nameBuf,x
        MA16
        txa
        lsr     a
        eor     #$FFFF
        sec
        adc     tmp1
        sta     tmp1                    ; start column
        lda     tmp0
        lsr     a
        lda     #11 * 32
        bcc     :+
        lda     #10 * 32
:       clc
        adc     tmp1
        ldy     #$2000
        sty     scrAttr
        ldy     #.loword(nameBuf)
        jmp     scrStr
lineX:  .word   LINE_X

; ---------------------------------------------------------------- main menu
toMenu:
        .a16
        lda     #SC_MENU
        sta     scene
        stz     paused
        lda     #SONG_TITLE
        jsr     playSong
        jsr     enterMenuDisplay
menuBack:                               ; (re)draw the main menu over the dimmed lineup
        .a16
        lda     #SC_MENU
        sta     scene
        stz     mT
        jsr     menuLook
        jsr     scrClear
        lda     #2
        jsr     scrLogo
        jsr     drawMain
        rts

; standard look: dim fighters, full scenery / text / logo, embers on
menuLook:
        .a16
        lda     #16
        jsr     fadeAll
        ldx     #G_FIGHT * 2
        ldy     #(G_FIGHT + 5) * 2
        lda     #5
        jsr     fadeSet
        ldx     #G_SCEN * 2
        lda     #11
        sta     fadeLv,x
        lda     #15
        sta     bright
        lda     #1
        sta     emberOn
        lda     #$17
        jmp     setTM

drawMain:
        .a16
        ldx     #0
@i:     stx     tmp5
        lda     #$2000
        cpx     mSel
        bne     :+
        lda     #$2000 | (3 << 10)      ; selected: gold
:       sta     scrAttr
        ldy     #.loword(txtCurOff)
        cpx     mSel
        bne     :+
        ldy     #.loword(txtCur)
:       lda     mainRow,x
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        clc
        adc     #10
        jsr     scrStr
        ldx     tmp5
        lda     mainRow,x
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        clc
        adc     #12
        pha
        lda     mainTxt,x
        tay
        pla
        jsr     scrStr
        ldx     tmp5
        inx
        inx
        cpx     #10
        bne     @i
        lda     #$2000
        sta     scrAttr
        ldy     #.loword(txtMainHelp)
        lda     #26
        jmp     scrCenter
mainRow: .word  11, 13, 15, 17, 19
mainTxt: .word  .loword(txtTourn), .loword(txtPract), .loword(txt2P), .loword(txtOpts), .loword(txtRecs)

; up / down on pad 1 moves mSel over N items (A = N*2); carry set if it moved
menuNav:
        .a16
        sta     tmp7
        lda     padP
        and     #PAD_DOWN
        beq     :+
        lda     mSel
        inc     a
        inc     a
        cmp     tmp7
        bcc     @set
        lda     #0
        bra     @set
:       lda     padP
        and     #PAD_UP
        beq     @no
        lda     mSel
        bne     :+
        lda     tmp7
:       dec     a
        dec     a
@set:   sta     mSel
        stz     mT
        lda     #SFX_SELECT
        jsr     playSfx
        sec
        rts
@no:    clc
        rts

mainTick:
        .a16
        lda     #10
        jsr     menuNav
        bcc     :+
        jsr     drawMain
:       lda     padP
        and     #(PAD_A | PAD_START)
        bne     @go
        lda     mT
        cmp     #1800                   ; idle: back to the attract loop
        bcc     :+
        jmp     toSplash
:       rts
@go:    lda     #SFX_CONFIRM
        jsr     playSfx
        lda     mSel
        tax
        lda     @tab,x
        sta     tmp6
        jmp     (tmp6)
@tab:   .word   .loword(goTourn), .loword(goPract), .loword(goVs), .loword(toOptions), .loword(toRecords)

goTourn:
        .a16
        lda     #GM_TOURN
        bra     goSel
goPract:
        .a16
        lda     #GM_PRACT
        bra     goSel
goVs:   .a16
        lda     #GM_VS
goSel:  sta     gmode
        stz     tTime
        stz     tCombos
        lda     #SC_SELECT
        sta     scene
        jsr     enterFightDisplay
        lda     #SONG_TITLE
        jsr     playSong
        jmp     toSelect

; ---------------------------------------------------------------- options
toOptions:
        .a16
        lda     #SC_OPTIONS
        sta     scene
        stz     mSel
        jsr     scrClear
        lda     #2
        jsr     scrLogo
        jsr     drawOpts
        rts

drawOpts:
        .a16
        lda     #$2000
        sta     scrAttr
        ldy     #.loword(txtOptsT)
        lda     #9
        jsr     scrCenter
        ; music
        lda     #0
        ldy     #.loword(txtMus)
        ldx     musLv
        lda     #13
        jsr     optLine
        lda     #2
        ldy     #.loword(txtSfx)
        ldx     sfxLv
        lda     #15
        jsr     optLine2
        ; back
        lda     #$2000
        ldx     mSel
        cpx     #4
        bne     :+
        lda     #$2000 | (3 << 10)
:       sta     scrAttr
        ldy     #.loword(txtBack)
        lda     #19 * 32 + 13
        jsr     scrStr
        lda     #$2000
        sta     scrAttr
        ldy     #.loword(txtOptHelp)
        lda     #26
        jmp     scrCenter

; A = row, Y = label, X = level (item 0)
optLine:
        .a16
        sta     tmp6
        lda     #0
        bra     optL
; A = row, Y = label, X = level (item 1)
optLine2:
        .a16
        sta     tmp6
        lda     #2
optL:   stx     tmp5
        cmp     mSel
        php
        lda     #$2000
        plp
        bne     :+
        lda     #$2000 | (3 << 10)
:       sta     scrAttr
        lda     tmp6
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        clc
        adc     #4
        jsr     scrStr
        ; bar: 10 slots
        MA8
        ldx     #0
:       lda     #'='
        cpx     tmp5
        bcc     :+
        lda     #'-'
:       sta     nameBuf,x
        inx
        cpx     #10
        bne     :--
        stz     nameBuf,x
        MA16
        lda     tmp6
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        clc
        adc     #18
        ldy     #.loword(nameBuf)
        jmp     scrStr

optTick:
        .a16
        lda     #6                      ; items: music, effects, back
        jsr     menuNav
        bcc     :+
        jsr     drawOpts
:       lda     padP
        and     #PAD_B
        bne     @back
        lda     mSel
        cmp     #4
        bne     @adj
        lda     padP
        and     #(PAD_A | PAD_START)
        bne     @back
        rts
@back:  lda     #SFX_CONFIRM
        jsr     playSfx
        stz     mSel
        lda     #3 * 2
        sta     mSel
        jmp     menuBack
@adj:   ; left / right change the level
        ldx     #musLv
        lda     mSel
        beq     :+
        ldx     #sfxLv
:       stx     tmp4
        lda     padP
        and     #PAD_RIGHT
        beq     :+
        lda     (tmp4)
        cmp     #10
        bcs     :+
        inc     a
        sta     (tmp4)
        bra     @chg
:       lda     padP
        and     #PAD_LEFT
        beq     @r
        lda     (tmp4)
        beq     @r
        dec     a
        sta     (tmp4)
@chg:   jsr     writeVol
        lda     #SFX_HIT
        jsr     playSfx
        jsr     drawOpts
@r:     rts

; ---------------------------------------------------------------- records
toRecords:
        .a16
        lda     #SC_RECORDS
        sta     scene
        jsr     enterMenuDisplay
        jsr     menuLook
        jsr     scrClear
        lda     #1
        jsr     scrLogo
        lda     #$2000 | (3 << 10)
        sta     scrAttr
        ldy     #.loword(txtRecT)
        lda     #7
        jsr     scrCenter
        lda     #$2000
        sta     scrAttr
        ldy     #.loword(txtRecH)
        lda     #9 * 32 + 3
        jsr     scrStr
        ldx     #0
        stz     tmp7                    ; slot
@r:     phx
        lda     #$2000
        ldy     tmp7
        cpy     recNew
        bne     :+
        lda     #$2000 | (3 << 10)
:       sta     scrAttr
        lda     tmp7
        asl     a
        clc
        adc     #11
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        sta     tmp6                    ; row base
        ; rank
        lda     tmp7
        clc
        adc     #'1'
        sta     nameBuf
        lda     tmp6
        clc
        adc     #4
        ldy     #.loword(nameBuf)
        jsr     scrStr
        plx
        phx
        lda     recs,x
        cmp     #$FFFF
        bne     :+
        ldy     #.loword(txtNoRec)
        lda     tmp6
        clc
        adc     #8
        jsr     scrStr
        bra     @nx
:       jsr     timeStr
        ldy     #.loword(numBuf)
        lda     tmp6
        clc
        adc     #8
        jsr     scrStr
        plx
        phx
        lda     recs+2,x
        jsr     numStr
        ldy     #.loword(numBuf)
        lda     tmp6
        clc
        adc     #16
        jsr     scrStr
        plx
        phx
        lda     recs+4,x
        and     #$00FF
        sta     tmp0
        asl     a
        asl     a
        asl     a
        sec
        sbc     tmp0
        clc
        adc     #.loword(fighterNames)
        tay
        MA8
        ldx     #0
:       lda     a:0,y
        sta     nameBuf,x
        iny
        inx
        cpx     #7
        bne     :-
        stz     nameBuf,x
        MA16
        lda     tmp6
        clc
        adc     #23
        ldy     #.loword(nameBuf)
        jsr     scrStr
@nx:    plx
        txa
        clc
        adc     #6
        tax
        inc     tmp7
        cpx     #30
        beq     :+
        jmp     @r
:       lda     #$2000
        sta     scrAttr
        lda     recNew
        cmp     #$FF
        beq     :+
        ldy     #.loword(txtNewRec)
        lda     #22
        jsr     scrCenter
:       ldy     #.loword(txtBackHelp)
        lda     #26
        jsr     scrCenter
        stz     mT
        rts

recTick:
        .a16
        lda     mT
        cmp     #20
        bcc     :+
        lda     padP
        and     #(PAD_A | PAD_B | PAD_START)
        beq     :+
        lda     #$FF
        sta     recNew
        lda     #4 * 2
        sta     mSel
        lda     #SFX_CONFIRM
        jsr     playSfx
        jmp     menuBack
:       rts

; ---------------------------------------------------------------- move list (from the pause menu)
; A = character
toMoves:
        .a16
        sta     mlChar
        lda     #SC_MOVES
        sta     scene
        jsr     enterMenuDisplay
        lda     #16
        jsr     fadeAll
        ldx     #G_SCEN * 2
        lda     #5
        sta     fadeLv,x
        lda     #15
        sta     bright
        stz     emberOn
        lda     #$16                    ; no fighter lineup
        jsr     setTM
        jsr     scrClear
        ; copy the 26 x 32 text into rows 1..26
        ; char * 832 = char * (512 + 256 + 64)
        lda     mlChar
        xba
        asl     a                       ; *512
        sta     tmp1
        lda     mlChar
        xba                             ; *256
        clc
        adc     tmp1
        sta     tmp1
        lda     mlChar
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a                       ; *64
        clc
        adc     tmp1
        tay                             ; source offset
        ldx     #32 * 2                 ; row 1
        lda     #26 * 32
        sta     tmp2
@c:     phx
        tyx
        lda     f:movelists,x
        plx
        and     #$00FF
        sec
        sbc     #32
        ora     #$2000
        cpx     #(3 + 1) * 32 * 2       ; rows 1..3: title + header in gold
        bcs     :+
        ora     #(3 << 10)
:       cpx     #22 * 32 * 2            ; finisher rows: gold too
        bcc     :+
        cpx     #24 * 32 * 2
        bcs     :+
        ora     #(3 << 10)
:       sta     f:scrBuf,x
        inx
        inx
        iny
        dec     tmp2
        bne     @c
        lda     #$2000
        sta     scrAttr
        ldy     #.loword(txtBackHelp)
        lda     #27
        jsr     scrCenter
        stz     mT
        rts

movesTick:
        .a16
        lda     mT
        cmp     #10
        bcc     :+
        lda     padP
        ora     padP+2
        and     #(PAD_A | PAD_B | PAD_START)
        beq     :+
        ; back to the paused fight
        lda     #SC_FIGHT
        sta     scene
        jsr     enterFightDisplay
        lda     #1
        sta     hudChg
:       rts

; ---------------------------------------------------------------- text
txtBlank:    .byte "           ", 0
txtCur:      .byte ">", 0
txtCurOff:   .byte " ", 0
txtTourn:    .byte "TOURNAMENT", 0
txtPract:    .byte "PRACTICE", 0
txt2P:       .byte "2 PLAYER", 0
txtOpts:     .byte "OPTIONS", 0
txtRecs:     .byte "RECORDS", 0
txtMainHelp: .byte "UP/DOWN: CHOOSE    A: SELECT", 0
txtOptsT:    .byte "OPTIONS", 0
txtMus:      .byte "MUSIC", 0
txtSfx:      .byte "EFFECTS", 0
txtBack:     .byte "BACK", 0
txtOptHelp:  .byte "LEFT/RIGHT: VOLUME    B: BACK", 0
txtRecT:     .byte "TOURNAMENT RECORDS", 0
txtRecH:     .byte "#   TIME    COMBOS FIGHTER", 0
txtNoRec:    .byte "-:--    -      -", 0
txtNewRec:   .byte "NEW RECORD!", 0
txtBackHelp: .byte "B: BACK", 0

; ---------------------------------------------------------------- home screen band (fight display)
; BG3 rows 22..26: the logo + a blinking PRESS START
bandCompose:
        .a16
        ldx     #0
        lda     #$2000
:       sta     f:bandBuf,x
        inx
        inx
        cpx     #5 * 32 * 2
        bne     :-
        ldy     #0
        ldx     #2 * 2
        lda     #LOGO_H
        sta     tmp2
@row:   lda     #28
        sta     tmp1
:       phx
        tyx
        lda     f:logo_map,x
        plx
        sta     f:bandBuf,x
        inx
        inx
        iny
        iny
        dec     tmp1
        bne     :-
        txa
        clc
        adc     #(32 - 28) * 2
        tax
        dec     tmp2
        bne     @row
        lda     frameCount
        and     #$20
        bne     @done
        ldx     #(4 * 32 + 10) * 2
        ldy     #0
:       lda     txtStart,y
        and     #$00FF
        beq     @done
        sec
        sbc     #32
        ora     #$2000
        sta     f:bandBuf,x
        inx
        inx
        iny
        bra     :-
@done:  lda     #1
        sta     bandDirty
        rts
