; =============================================================================
;  SAVAGE DOMINION - SNES, 65816 assembly (ca65)
;  Side-view fighter: polygon fighters drawn by the Super FX over a tiled stage.
;  Built on Arena Fighter FX (MIT).
;
;  Mode 1 screen: BG1 lamps / barrier / floor, BG2 far wall and crowd, BG3 HUD,
;  sprites for fighters and shadows.  HDMA: ch1 BG1 scroll per floor line
;  (pseudo-perspective), ch2 colour math (translucent shadows), ch3 title band.
;
;  World units: "hu", relative to the stage centre.  Fighters stay on the z = 0
;  plane; the camera looks straight at it and only tracks x.
; =============================================================================
.p816
.smart
.include "consts.inc"
.include "fighters.inc"
.include "regs.inc"

.import near_tiles, near_map, far_tiles, far_map, floor_k, math_fight, math_title, tm_title
.import bg_pal, font2, bar2, obj_tiles
.import gsu_code, gsu_circ, sin8, cos8, recip, atan64, scale8
.import palTab, ballListTab, moveTab, segTab, partTab, shapeTab, animTabLo, animTabBk
.import inTab, aiTab, aiChTab, finTab, finNameTab, finLoTab, finHiTab, finSeqTab, styleTab
.import fighterNames, animLoop, ballCount, segCount
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
        ; fixed 60 Hz game logic: the NMI queues one controller sample per video frame
        ; and each tick consumes one, so a tap shorter than a rendered frame still counts
:       lda     padHead
        sec
        sbc     padTail
        beq     :-                  ; nothing new yet
        cmp     #PADQ_MAX + 1
        bcc     :+
        lda     padHead             ; far behind (a long load): drop the oldest samples
        sec
        sbc     #PADQ_MAX
        sta     padTail
        lda     #PADQ_MAX
:       sta     tickN
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
        ; this frame's stage scroll (before the long DMA, safely inside vblank)
        lda     panX
        sta     BG2HOFS
        lda     panX+1
        sta     BG2HOFS
        ldx     #.loword(scrTab)
        lda     backSetBit+1
        beq     :+
        ldx     #.loword(scrTab + SCRLEN)
:       stx     A1T1L
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
        rep     #$10
        sep     #$20
        .a8
        jsr     samplePads
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

; push this frame's controller state into the queue (called at the end of every NMI)
samplePads:
        .a8
@early: lda     STAT78              ; (resets the counter read order)
        lda     SLHV                ; latch the beam position
        lda     OPVCT
        sec
        sbc     #225
        cmp     #3
        bcc     @early              ; lines 225..227: auto-read may not have run yet
@busy:  lda     HVBJOY
        and     #$01
        bne     @busy
        rep     #$20
        .a16
        lda     padHead
        and     #PADQ_LEN - 1
        asl     a
        asl     a
        tax
        lda     JOY1L
        sta     padQ,x
        lda     JOY2L
        sta     padQ+2,x
        inc     padHead
        sep     #$20
        .a8
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
        VRAM_DMA near_tiles, $0000, NEAR_TILES*32
        VRAM_DMA far_tiles, $2000, FAR_TILES*32
        VRAM_DMA near_map, $3000, 4096
        VRAM_DMA far_map, $3800, 4096
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
        ; OBJ palette 3: hit sparks (white/yellow/orange)
        lda     #$B0
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
        lda     #$31                ; BG1 map $3000, 64x32
        sta     BG1SC
        lda     #$39                ; BG2 map $3800, 64x32
        sta     BG2SC
        lda     #$58                ; BG3 map $5800
        sta     BG3SC
        lda     #$20                ; BG1 tiles $0000, BG2 tiles $2000
        sta     BG12NBA
        lda     #$05                ; BG3 tiles $5000
        sta     BG34NBA
        lda     #$63                ; OBJ 16x16/32x32, base $6000
        sta     OBSEL
        lda     #$17                ; main screen: BG1-3 + OBJ
        sta     TM
        lda     #$01                ; sub screen: BG1 (shows through the shadows)
        sta     TS
        lda     #$02                ; colour math source: sub screen
        sta     CGWSEL
        lda     #$E0                ; fixed colour black
        sta     COLDATA
        lda     #$FF                ; v-scroll: row 0 at line 1
        sta     BG1VOFS
        stz     BG1VOFS
        sta     BG2VOFS
        stz     BG2VOFS
        sta     BG3VOFS
        stz     BG3VOFS
        rts

sparkPal: .word $0000, $7FFF, $3BFF, $11FF

; -----------------------------------------------------------------------------
; HDMA: ch1 BG1HOFS per line (table built by the renderer), ch2 CGADSUB + COLDATA,
; ch3 TM (title screen only: the bottom lines become the logo band)
setupHdma:
        .a8
        rep     #$20
        .a16
        stz     camX
        ldx     #0
        jsr     buildScroll
        .a16
        ldx     #SCRLEN
        jsr     buildScroll
        .a16
        sep     #$20
        .a8
        lda     #$02                ; mode 2: write twice
        sta     DMAP1
        lda     #<BG1HOFS
        sta     BBAD1
        ldx     #.loword(scrTab)
        stx     A1T1L
        lda     #$7E
        sta     A1B1
        lda     #$01                ; mode 1: two registers
        sta     DMAP2
        lda     #<CGADSUB
        sta     BBAD2
        ldx     #.loword(math_fight)
        lda     scene
        cmp     #SC_TITLE
        bne     :+
        ldx     #.loword(math_title)
:       stx     A1T2L
        lda     #^math_fight
        sta     A1B2
        stz     DMAP3               ; mode 0
        lda     #<TM
        sta     BBAD3
        ldx     #.loword(tm_title)
        stx     A1T3L
        lda     #^tm_title
        sta     A1B3
        lda     panX
        sta     BG2HOFS
        lda     panX+1
        sta     BG2HOFS
        lda     scene
        cmp     #SC_TITLE
        beq     :+
        lda     #%00000110
        bra     :++
:       lda     #%00001110
:       sta     HDMAEN
        rts

.include "math.s"
.include "render.s"
.include "game.s"
.include "sound.s"
.include "menu.s"

; -----------------------------------------------------------------------------
.segment "HEADER"
        .byte   "SAVAGE DOMINION      "  ; 21 bytes
        .byte   $30                 ; LoROM + FastROM
        .byte   $15                 ; Super FX (GSU-2) + RAM + battery
        .byte   $0B                 ; 2 MB
        .byte   $06                 ; 64 KB battery-backed Game Pak RAM (records at $70:F000)
        .byte   $01
        .byte   $33
        .byte   $00
        .word   $FFFF, $0000
.segment "VECTORS"
        .word   0, 0, 0, 0, 0, .loword(nmi), 0, .loword(irq)
        .word   0, 0, 0, 0, 0, 0, .loword(reset), 0
