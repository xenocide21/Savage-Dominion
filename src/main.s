; =============================================================================
;  ARENA FIGHTER (working title) - SNES, 65816 assembly (ca65)
;  Mode 7 perspective arena + ball-jointed 3D fighters.
;
;  Screen layout (per scanline, switched by HDMA):
;    0..71   Mode 1: sky gradient (colour math), panorama (BG2), HUD (BG3), sprites
;    72..81  fog band: backdrop only + sprites
;    82..223 Mode 7: perspective floor (BG1), sprites, half-transparent shadows
;
;  World units: "hu" = half floor texels.  Fighter positions are relative to the
;  arena centre (map texel 512,512).  Camera yaw a (0..255): right = (cos a, sin a),
;  forward = (sin a, -cos a) in map coordinates (x right, y down).
; =============================================================================
.p816
.smart
.include "consts.inc"
.include "fighters.inc"
.include "regs.inc"

.import m7_vram0, persp_A0, persp_A1, persp_B0, persp_B1, persp_C0, persp_C1, persp_D0, persp_D1
.import sky_r, bg_pal, pan_tiles, pan_map, font2, bar2, obj_tiles
.import gsu_code, gsu_circ, sin8, cos8, recip, atan64, scale8
.import ch0_frames, ch0_anim, ch0_balls, ch0_nballs, ch0_pal, ch0_move
.import ch1_frames, ch1_anim, ch1_balls, ch1_nballs, ch1_pal, ch1_move
.import ch2_frames, ch2_anim, ch2_balls, ch2_nballs, ch2_pal, ch2_move
.import ch3_frames, ch3_anim, ch3_balls, ch3_nballs, ch3_pal, ch3_move
.import ch4_frames, ch4_anim, ch4_balls, ch4_nballs, ch4_pal, ch4_move
.import ch5_frames, ch5_anim, ch5_balls, ch5_nballs, ch5_pal, ch5_move
.import fighterNames, animLoop, ballCount, segCount
.import ch0_inputs, ch1_inputs, ch2_inputs, ch3_inputs, ch4_inputs, ch5_inputs
.import ch0_ai, ch1_ai, ch2_ai, ch3_ai, ch4_ai, ch5_ai
.import ch0_aichain, ch1_aichain, ch2_aichain, ch3_aichain, ch4_aichain, ch5_aichain
.import ch0_fin, ch1_fin, ch2_fin, ch3_fin, ch4_fin, ch5_fin
.import ch0_finName, ch1_finName, ch2_finName, ch3_finName, ch4_finName, ch5_finName
.import ch0_segs, ch1_segs, ch2_segs, ch3_segs, ch4_segs, ch5_segs
.import ch0_parts, ch1_parts, ch2_parts, ch3_parts, ch4_parts, ch5_parts
.import ch0_shapes, ch1_shapes, ch2_shapes, ch3_shapes, ch4_shapes, ch5_shapes
.export frameCount

.include "vars.inc"

.segment "CODE"
; -----------------------------------------------------------------------------
reset:
        sei
        clc
        xce
        jml     :+                  ; run from the FastROM mirror
:       rep     #$38
        .a16
        .i16
        ldx     #$1FFF
        txs
        lda     #$0000
        tcd
        sep     #$20
        .a8
        lda     #$80
        pha
        plb                         ; data bank = $80 (WRAM low, I/O, bank-0 ROM)
        lda     #$01
        sta     MEMSEL              ; FastROM
        jsr     initHardware
        jsr     spcUpload
        jsr     clearRam
        jsr     loadGraphics
        jsr     gsuInit
        rep     #$20
        jsr     loadRecords
        sep     #$20
        jsr     setupHdma
        jsr     gameInit
        lda     #$81
        sta     NMITIMEN            ; NMI + auto joypad
        lda     #$0F
        sta     INIDISP
mainLoop:
        lda     nmiFlag             ; a vblank already passed while rendering? go on
        cmp     lastNmi
        bne     :+
        jsr     waitFrame
:
        ; fixed 60 Hz game logic: run one tick per elapsed video frame (max 4)
        lda     nmiFlag
        sec
        sbc     lastNmi
        cmp     #5
        bcc     :+
        lda     #4
:       sta     tickN
        lda     nmiFlag
        sta     lastNmi
@tick:  jsr     readPads
        jsr     gameTick
        dec     tickN
        bne     @tick
        lda     dispMode
        beq     :+
        rep     #$20
        jsr     menuCompose
        sep     #$20
        bra     :++
:       jsr     hudCompose
        jsr     render
:       rep     #$20
        inc     loopCount
        sep     #$20
        bra     mainLoop

waitFrame:
        lda     nmiFlag
:       cmp     nmiFlag
        beq     :-
        rts

; -----------------------------------------------------------------------------
nmi:
        rep     #$30
        pha
        phx
        phy
        phb
        phd
        sep     #$20
        lda     #$80
        pha
        plb
        lda     #$00
        xba
        lda     #$00
        rep     #$20
        tcd
        sep     #$20
        lda     RDNMI
        lda     dispMode
        beq     :+
        jsr     menuNmi
        jmp     @done
:       ; ---- Super FX frame upload: all fighter tiles + OAM + camera in one go.
        ; 6 KB is a little more than vblank holds, so the screen stays blanked until
        ; the DMA is done (a few lines of top overscan at most).
        lda     upState
        bne     :+
        jmp     @common
:       lda     GSU_SFR
        and     #$20
        beq     :+
        inc     dbgBusy
        jmp     @common             ; still drawing
:       lda     #$80
        sta     INIDISP
        lda     #SCMR_CPU
        sta     GSU_SCMR
        lda     #$80
        sta     VMAIN
        ldx     #$6000
        lda     backSetBit+1
        beq     :+
        ldx     #$7000
:       stx     VMADDL
        ldx     #$1801
        stx     DMAP0
        ldx     #$0800
        stx     A1T0L
        lda     #$70
        sta     A1B0
        ldx     #6144
        stx     DAS0L
        lda     #$01
        sta     MDMAEN
        ; OAM
        stz     OAMADDL
        stz     OAMADDH
        ldx     #$0400
        stx     DMAP0               ; mode 0 -> $2104
        ldx     #oamBuf
        stx     A1T0L
        lda     #$80
        sta     A1B0
        ldx     #544
        stx     DAS0L
        lda     #$01
        sta     MDMAEN
        ; Mode 7 centre / scroll for this frame's camera
        lda     m7x
        sta     M7X
        lda     m7x+1
        sta     M7X
        lda     m7y
        sta     M7Y
        lda     m7y+1
        sta     M7Y
        lda     m7h
        sta     M7HOFS
        lda     m7h+1
        sta     M7HOFS
        lda     m7v
        sta     M7VOFS
        lda     m7v+1
        sta     M7VOFS
        lda     panX
        sta     BG2HOFS
        lda     panX+1
        sta     BG2HOFS
        jsr     setPerspective
        lda     backSetBit+1        ; the next frame goes to the other tile set
        eor     #1
        sta     backSetBit+1
        stz     upState
        inc     dbgUp
@common:
        ; fighter palettes (after a character change)
        lda     palDirty
        beq     :+
        stz     palDirty
        jsr     loadFighterPalettes
:       ; HUD rows (BG3 map rows 1..4) if changed
        lda     hudDirty
        beq     @skip
        stz     hudDirty
        lda     #$80
        sta     VMAIN
        ldx     #$5820              ; BG3 map row 1
        stx     VMADDL
        ldx     #$1801
        stx     DMAP0
        ldx     #hudBuf
        stx     A1T0L
        lda     #$80
        sta     A1B0
        ldx     #128*2
        stx     DAS0L
        lda     #$01
        sta     MDMAEN
@skip:  ; home-screen logo band (BG3 rows 22..26)
        lda     bandDirty
        beq     :+
        stz     bandDirty
        lda     #$80
        sta     VMAIN
        ldx     #$5800 + 22 * 32
        stx     VMADDL
        ldx     #$1801
        stx     DMAP0
        ldx     #.loword(bandBuf)
        stx     A1T0L
        lda     #^bandBuf
        sta     A1B0
        ldx     #5 * 32 * 2
        stx     DAS0L
        lda     #$01
        sta     MDMAEN
:       lda     #$0F
        sec
        sbc     dimLvl
        sta     INIDISP
@done:
        inc     nmiFlag
        rep     #$30
        pld
        plb
        ply
        plx
        pla
        rti

irq:
        rti

; -----------------------------------------------------------------------------
; HDMA source for M7A..D: table of the current yaw (angles >= 128 live in the next bank)
setPerspective:
        rep     #$20
        .a16
        lda     pYaw
        and     #$007F
        sta     ntmp0
        asl     a                   ; *217 = *256 - *32 - *4 - *2 - *1
        asl     a
        asl     a
        asl     a
        asl     a
        sta     ntmp1                ; *32
        lda     ntmp0
        xba                         ; *256
        sec
        sbc     ntmp1
        sbc     ntmp0
        sbc     ntmp0
        sbc     ntmp0
        sbc     ntmp0
        sbc     ntmp0
        sbc     ntmp0
        sbc     ntmp0                ; 256-32-7 = 217
        sta     ntmp1                ; offset within the half-table
        sep     #$20
        .a8
        lda     pYaw
        bmi     @hi
        rep     #$20
        .a16
        lda     #.loword(persp_A0)
        clc
        adc     ntmp1
        sta     A1T1L
        lda     #.loword(persp_B0)
        clc
        adc     ntmp1
        sta     A1T2L
        lda     #.loword(persp_C0)
        clc
        adc     ntmp1
        sta     A1T3L
        lda     #.loword(persp_D0)
        clc
        adc     ntmp1
        sta     A1T4L
        sep     #$20
        .a8
        lda     #^persp_A0
        sta     A1B1
        lda     #^persp_B0
        sta     A1B2
        lda     #^persp_C0
        sta     A1B3
        lda     #^persp_D0
        sta     A1B4
        rts
@hi:    rep     #$20
        .a16
        lda     #.loword(persp_A1)
        clc
        adc     ntmp1
        sta     A1T1L
        lda     #.loword(persp_B1)
        clc
        adc     ntmp1
        sta     A1T2L
        lda     #.loword(persp_C1)
        clc
        adc     ntmp1
        sta     A1T3L
        lda     #.loword(persp_D1)
        clc
        adc     ntmp1
        sta     A1T4L
        sep     #$20
        .a8
        lda     #^persp_A1
        sta     A1B1
        lda     #^persp_B1
        sta     A1B2
        lda     #^persp_C1
        sta     A1B3
        lda     #^persp_D1
        sta     A1B4
        rts

; -----------------------------------------------------------------------------
initHardware:
        lda     #$80
        sta     INIDISP
        stz     NMITIMEN
        ldx     #$2101              ; clear PPU registers $2101-$2133
:       stz     $00,x
        inx
        cpx     #$2134
        bne     :-
        lda     #$80
        sta     INIDISP
        stz     NMITIMEN
        stz     HDMAEN
        rts

clearRam:
        rep     #$20
        .a16
        ldx     #$0000
:       stz     $0000,x
        inx
        inx
        cpx     #$1E00
        bne     :-
        sep     #$20
        .a8
        rts

; DMA helper: A1 (24-bit source) in tmp24, size in X, dest VRAM word address in Y, mode word writes
.macro VRAM_DMA src, dst, size
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

loadGraphics:
        lda     #$80
        sta     VMAIN               ; increment after high byte
        VRAM_DMA m7_vram0, $0000, $8000      ; Mode 7: map (low bytes) + 8bpp tiles (high bytes), words 0-$3FFF
        VRAM_DMA pan_tiles, $4000, PAN_TILES*32
        VRAM_DMA pan_map, $4800, 4096
        VRAM_DMA font2, $5000, 64*16
        VRAM_DMA bar2, $5200, 9*16
        VRAM_DMA logo2, $5000 + LOGO_T0 * 8, LOGO_NT * 16
        VRAM_DMA obj_tiles, $6000, $4000
        ; clear BG3 map ($5800, 32x32)
        ldx     #$5800
        stx     VMADDL
        ldx     #1024
:       stz     VMDATAL
        stz     VMDATAH
        dex
        bne     :-
        ; palettes: BG 0..127
        stz     CGADD
        ldx     #$2200
        stx     DMAP0
        ldx     #.loword(bg_pal)
        stx     A1T0L
        lda     #^bg_pal
        sta     A1B0
        ldx     #256
        stx     DAS0L
        lda     #$01
        sta     MDMAEN
        ; OBJ palette 7: shadow (black, drawn with half colour math)
        lda     #$F0
        sta     CGADD
        stz     CGDATA
        stz     CGDATA
        lda     #$00
        stz     CGDATA
        stz     CGDATA
        ; OBJ palette 6: hit sparks (white/yellow/orange)
        lda     #$E0
        sta     CGADD
        ldx     #0
:       lda     sparkPal,x
        sta     CGDATA
        inx
        cpx     #8
        bne     :-
        ; video registers
        lda     #$09
        sta     BGMODE
        lda     #$49                ; BG2 map $4800, 64x32
        sta     BG2SC
        lda     #$58                ; BG3 map $5800
        sta     BG3SC
        lda     #$40                ; BG2 tiles $4000
        sta     BG12NBA
        lda     #$05                ; BG3 tiles $5000
        sta     BG34NBA
        lda     #$63                ; OBJ 16x16/32x32, base $6000
        sta     OBSEL
        lda     #$C0                ; Mode 7: outside the map -> tile 0 (water)
        sta     M7SEL
        lda     #$02                ; colour math source: sub screen (fixed colour as its backdrop)
        sta     CGWSEL
        lda     #$40|$08            ; fixed colour green component (sky)
        sta     COLDATA
        lda     #$FF                ; BG3 v-scroll: row 0 at line 1
        sta     BG3VOFS
        stz     BG3VOFS
        lda     #$FF
        sta     BG2VOFS
        stz     BG2VOFS
        rts

sparkPal: .word $0000, $7FFF, $3BFF, $11FF

; -----------------------------------------------------------------------------
; HDMA: ch1-4 Mode 7 matrix (perspective), ch5 BGMODE, ch6 TM/TS, ch7 CGADSUB/COLDATA (sky)
setupHdma:
        lda     #$02                ; mode 2: write twice
        sta     DMAP1
        sta     DMAP2
        sta     DMAP3
        sta     DMAP4
        lda     #<M7A
        sta     BBAD1
        lda     #<M7B
        sta     BBAD2
        lda     #<M7C
        sta     BBAD3
        lda     #<M7D
        sta     BBAD4
        stz     DMAP5               ; mode 0
        lda     #<BGMODE
        sta     BBAD5
        ldx     #.loword(hdmaMode)
        lda     scene
        cmp     #SC_TITLE
        bne     :+
        ldx     #.loword(hdmaModeT)
:       stx     A1T5L
        lda     #^hdmaMode
        sta     A1B5
        lda     #$01                ; mode 1: two registers
        sta     DMAP6
        lda     #<TM
        sta     BBAD6
        ldx     #.loword(hdmaLayers)
        lda     scene
        cmp     #SC_TITLE
        bne     :+
        ldx     #.loword(hdmaLayersT)
:       stx     A1T6L
        lda     #^hdmaLayers
        sta     A1B6
        lda     #$01
        sta     DMAP7
        lda     #<CGADSUB
        sta     BBAD7
        ldx     #.loword(sky_r)
        lda     scene
        cmp     #SC_TITLE
        bne     :+
        ldx     #.loword(skyT)
:       stx     A1T7L
        lda     #^sky_r
        sta     A1B7
        lda     scene
        cmp     #SC_TITLE
        bne     :+
        lda     #^skyT
        sta     A1B7
:
        jsr     setPerspective
        lda     #%11111110
        sta     HDMAEN
        rts

hdmaMode:   .byte FLOOR0, $09, 1, $07, 0
hdmaLayers: .byte HORIZON, $16, $00, FOG, $10, $00, 1, $11, $01, 0
; home screen: the bottom 48 lines go back to Mode 1 for the logo band (BG3 + sprites)
BAND = 176
skyT:
.repeat HORIZON + FOG, I
        .byte   1, $20, $A0 | (4 + 20 * I / (HORIZON + FOG))
.endrep
        .byte   BAND - FLOOR0, $50, $E0
        .byte   2, $20, $60 | 22        ; gold trim on top of the band
        .byte   2, $20, $60 | 9
        .byte   1, $00, $E0
        .byte   0
hdmaModeT:   .byte FLOOR0, $09, BAND - FLOOR0, $07, 1, $09, 0
hdmaLayersT: .byte HORIZON, $16, $00, FOG, $10, $00, BAND - FLOOR0, $11, $01, 1, $14, $00, 0

.include "math.s"
.include "render.s"
.include "game.s"
.include "sound.s"
.include "menu.s"

; -----------------------------------------------------------------------------
.segment "HEADER"
        .byte   "ARENA FIGHTER        "  ; 21 bytes
        .byte   $30                 ; LoROM + FastROM
        .byte   $15                 ; Super FX (GSU-2) + RAM + battery
        .byte   $0A                 ; 1 MB
        .byte   $06                 ; 64 KB battery-backed Game Pak RAM (records at $70:F000)
        .byte   $01
        .byte   $33
        .byte   $00
        .word   $FFFF, $0000
.segment "VECTORS"
        .word   0, 0, 0, 0, 0, .loword(nmi), 0, .loword(irq)
        .word   0, 0, 0, 0, 0, 0, .loword(reset), 0
