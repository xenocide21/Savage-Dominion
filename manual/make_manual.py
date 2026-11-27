#!/usr/bin/env python3
"""Builds manual.pdf (4.75 in square jewel-case booklet) for ARENA FIGHTER FX.
Needs art/cover_front.png (run make_art.py first) and ../MOVELIST.md."""
import os, re
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Table, TableStyle, Frame
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors

HERE = os.path.dirname(os.path.abspath(__file__)); SNES = os.path.dirname(HERE)
pdfmetrics.registerFont(TTFont("Anton", "/usr/share/fonts/truetype/google-fonts/ofl/anton/Anton-Regular.ttf"))
D = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("S", D + "DejaVuSansCondensed.ttf")); pdfmetrics.registerFont(TTFont("SB", D + "DejaVuSansCondensed-Bold.ttf"))
pdfmetrics.registerFont(TTFont("SI", D + "DejaVuSansCondensed-Oblique.ttf")); pdfmetrics.registerFont(TTFont("M", D + "DejaVuSansMono.ttf"))
pdfmetrics.registerFontFamily("S", normal="S", bold="SB", italic="SI", boldItalic="SB")

PW = 4.75 * inch; MG = 0.3 * inch
INK = colors.HexColor("#1b1530"); PURP = colors.HexColor("#5a1f7a"); GOLD = colors.HexColor("#e08a10"); CREAM = colors.HexColor("#f7f0e0")
DARK = colors.HexColor("#120a2a"); BLUEC = colors.HexColor("#2d6fe0")
body = ParagraphStyle("b", fontName="S", fontSize=7.4, leading=9.6, textColor=INK, spaceAfter=3)
small = ParagraphStyle("s", parent=body, fontSize=6.3, leading=8)
cell = ParagraphStyle("c", parent=body, fontSize=6.2, leading=7.4, spaceAfter=0)
cellb = ParagraphStyle("cb", parent=cell, fontName="SB")
bul = ParagraphStyle("bu", parent=body, leftIndent=8, bulletIndent=0, spaceAfter=2)
H2 = ParagraphStyle("h2", fontName="SB", fontSize=8.2, leading=10, textColor=PURP, spaceBefore=3, spaceAfter=2)

def arrows(s):
    s = s.replace("->", "→").replace("<-", "←").replace("Down+", "↓+").replace("Down ", "↓ ").replace("Down", "↓")
    return s

pages = []   # list of callables(c)
def page(title=None):
    def deco(fn): pages.append((title, fn)); return fn
    return deco

def flow(c, items, top=None, x=MG, w=None, bottom=0.45 * inch):
    top = top or PW - 0.62 * inch
    f = Frame(x, bottom, w or PW - 2 * MG, top - bottom, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, showBoundary=0)
    rest = f.addFromList(items, c) or items
    if items: raise SystemExit("OVERFLOW on page %d: %s" % (c.getPageNumber(), [str(i)[:60] for i in items[:2]]))

from reportlab.platypus import Spacer
def Sp(h): return Spacer(1, h)
def P(t, st=body): return Paragraph(t, st)
def B(t): return Paragraph(t, bul, bulletText="•")

def chrome(c, title, n):
    c.setFillColor(CREAM); c.rect(0, 0, PW, PW, fill=1, stroke=0)
    c.setFillColor(DARK); c.rect(0, PW - 0.5 * inch, PW, 0.5 * inch, fill=1, stroke=0)
    c.setFillColor(GOLD); c.rect(0, PW - 0.5 * inch - 2, PW, 2, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#ffd36a")); c.setFont("Anton", 17); c.drawString(MG, PW - 0.36 * inch, title.upper())
    c.setFont("Anton", 8); c.setFillColor(colors.HexColor("#6fb0ff")); c.drawRightString(PW - MG, PW - 0.34 * inch, "ARENA FIGHTER FX")
    c.setFillColor(PURP); c.setFont("SB", 6.5); c.drawCentredString(PW / 2, 0.2 * inch, str(n))
    c.setStrokeColor(GOLD); c.setLineWidth(.6); c.line(MG, 0.33 * inch, PW - MG, 0.33 * inch)

def tbl(rows, widths, head=True, zebra=True, extra=None):
    t = Table(rows, colWidths=widths, repeatRows=1 if head else 0)
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 1.3), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.3),
          ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3), ("LINEBELOW", (0, 0), (-1, -1), .25, colors.HexColor("#d8cdb4"))]
    if head: st += [("BACKGROUND", (0, 0), (-1, 0), DARK)]
    if zebra: st += [("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#fffaf0"), colors.HexColor("#efe5cf")])]
    t.setStyle(TableStyle(st + (extra or []))); return t

def th(t): return Paragraph('<font color="#ffd36a">%s</font>' % t, cellb)

W = PW - 2 * MG

# ---- roster data from MOVELIST.md ----
def parse_moves():
    txt = open(os.path.join(SNES, "MOVELIST.md")).read()
    out = []
    for blk in re.split(r"^## ", txt, flags=re.M)[1:]:
        head, *lines = blk.split("\n")
        name, style = [s.strip() for s in head.split(" - ", 1)]
        rows, fin = [], None
        for ln in lines:
            if not ln.startswith("|") or ln.startswith("|---") or ln.startswith("| Move"): continue
            cs = [x.strip() for x in ln.strip().strip("|").split("|")]
            if cs[0].startswith("**FINISHER"):
                fin = (cs[0].replace("**FINISHER: ", "").replace("**", ""), cs[1]); continue
            note = cs[3]
            note = ("ender" if "ender" in note else "launcher" if "launcher" in note else "throw" if note.startswith("throw") else note)
            rows.append((cs[0], cs[1], cs[2], note))
        out.append((name, style, rows, fin))
    return out
ROSTER = parse_moves()
BLURB = {
 "KAZE": "Disciplined karate: quick jabs, long straight punches and a hard-hitting kick game. A good first fighter.",
 "LIN": "Kung fu with flowing palm chains, spinning kicks and sweeping low attacks. Fast and slippery.",
 "BRUTUS": "Pro wrestler. Slow, huge and strong: shoulder charges, leg drops, suplex and a mighty finisher.",
 "VALKA": "Viking brawler: heavy hammer fists, knees and a bear hug slam. Strong at close range.",
 "ROCCO": "Boxer / MMA fighter. Fast hands and strings that flow jab, cross, hook, uppercut.",
 "NOVA": "Capoeira dancer. Low, swaying stance, sweeping kicks and tricky angles.",
}

# ================= PAGES =================
@page()
def cover(c, n):
    c.drawImage(os.path.join(HERE, "art/cover_front.png"), 0, 0, PW, PW)

@page("Contents")
def contents(c, n):
    items = [P("<b>ARENA FIGHTER FX</b> is a 3D arena fighter for the Super Nintendo (SNES / Super Famicom), built on the <b>Super FX</b> chip. Six fighters, a rotating Mode 7 arena, Killer Instinct style combos and cinematic finishing moves."),
             Sp(4)]
    toc = [("Welcome", 3), ("Getting started", 4), ("Controls", 5), ("Game modes and menus", 6), ("Fighting rules", 7), ("Combos", 8), ("Finishing moves", 9),
           ("The fighters (move lists)", "10-15"), ("Tips", 16), ("Records, saving, troubleshooting", 17), ("Credits and technical notes", 18), ("License", 19)]
    rows = [[P(a, body), P(str(b), body)] for a, b in toc]
    t = Table(rows, colWidths=[W - 0.7 * inch, 0.6 * inch]); t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), .3, colors.HexColor("#d8cdb4")), ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    items += [t, Sp(6), P("<b>Free and open source.</b> This game and this manual are released under the MIT License (see page 19). Not for sale. Share it, change it, make your own.", small),
              P("<b>Made with AI, openly.</b> Game concept and direction: Xenocide21. Code, art and manual were written with Claude, an AI model made by Anthropic.", small),
              P("This is an independent fan-made homebrew. It is not affiliated with, endorsed or sponsored by Nintendo or any other company. Super Nintendo, SNES and Super Famicom are trademarks of their respective owners.", small)]
    flow(c, items)

from reportlab.platypus import Spacer
def Sp(h): return Spacer(1, h)

@page("Welcome")
def welcome(c, n):
    flow(c, [P("The arena is lit. Six fighters have come to find out who is the greatest, and the only way to settle it is to climb the ladder."),
             P("Each fighter has a different <b>fighting style</b> and their own set of moves. You can win with patience, with speed, or with one huge combo."),
             P("Highlights", H2),
             B("<b>Mode 7 arena</b> that rotates with the camera as the fighters circle each other."),
             B("<b>Polygon fighters</b> drawn live, every frame, by the Super FX (GSU-2) chip: jointed bodies with shaded limbs, hair, clothes and motion trails."),
             B("<b>Combos that grow</b> from TRIPLE all the way to <b>ULTRA</b> (21+ hits). Single hits are weak; big combos win rounds."),
             B("<b>Dizzy and FINISH THEM:</b> when a knockout would win the match, the loser is left dizzy and you can enter a secret code for a cinematic finishing move."),
             B("<b>Tournament, Practice and 2 Player</b> modes, an options menu, and a records table of the fastest tournament clears."),
             B("<b>Pause menu</b> with each fighter's move list (locked out in 2 player matches).")])

@page("Getting started")
def start(c, n):
    flow(c, [P("What you need", H2),
             B("A SNES / Super Famicom setup that can run a <b>Super FX (GSU-2)</b> cartridge: original hardware with a flash cartridge that supports the Super FX chip, or an emulator such as snes9x, bsnes, Mesen-S or ares."),
             B("The ROM file: 1 MB, LoROM / FastROM, with 64 KB of battery-backed Game Pak RAM for the records table."),
             B("One controller, or two for the 2 Player mode."),
             P("Starting the game", H2),
             B("Load the ROM and power on. The <b>splash screen</b> shows all six fighters; each lights up and their name appears, then the logo fades in."),
             B("Press <b>START</b> to reach the home screen, where two CPU fighters battle while you wait. Press <b>START</b> again for the <b>main menu</b>."),
             B("Left alone, the home screen returns to the splash, like a real arcade machine."),
             P("In menus: D-pad Up/Down chooses, <b>A</b> selects, <b>B</b> goes back.", body)])

@page("Controls")
def controls(c, n):
    rows = [[th("Input"), th("Action")],
            [P("<b>Left / Right</b>", cell), P("Walk. Holding away from your opponent also guards.", cell)],
            [P("<b>Up</b>", cell), P("Jump (Up + toward / away jumps in / out).", cell)],
            [P("<b>Down</b>", cell), P("Crouch. High attacks pass over you.", cell)],
            [P("<b>Double-tap</b> toward / away", cell), P("Dash in / backdash.", cell)],
            [P("<b>R</b>", cell), P("Guard. Down + R is crouch guard.", cell)],
            [P("<b>R + Up / R + Down</b>", cell), P("Sidestep into / out of the screen (hold to keep circling).", cell)],
            [P("<b>Y / X</b>", cell), P("Punch / power punch (each fighter has their own).", cell)],
            [P("<b>B / A</b>", cell), P("Kick / power kick.", cell)],
            [P("<b>Direction + button</b>", cell), P("Each fighter's special moves (toward, away or down).", cell)],
            [P("<b>L</b>", cell), P("Throw: unblockable, close range, misses crouchers and jumpers. During a combo against you, <b>COMBO BREAKER</b>.", cell)],
            [P("<b>Any button</b> while down", cell), P("Get up early.", cell)],
            [P("<b>A / B / X / Y</b> in the air", cell), P("Air attacks (punch with Y / X, kick with B / A).", cell)],
            [P("<b>START</b>", cell), P("Pause menu (resume, move list, forfeit).", cell)]]
    flow(c, [tbl(rows, [1.25 * inch, W - 1.25 * inch]), Sp(4), P("Directions are relative to your opponent: <b>→</b> means toward them, <b>←</b> away.", small)])

@page("Game modes")
def modes(c, n):
    flow(c, [P("<b>TOURNAMENT</b> - pick a fighter and beat the other five in a row to become champion. The CPU starts slow and patient and gets faster, more aggressive and better at combos (and breakers) with each opponent. Your total fighting time and the number of combos (3+ hits) you land are recorded.", body),
             P("<b>PRACTICE</b> - pick your fighter, then a sparring dummy. The dummy never fights back, heals between combos, and cannot be knocked out of the ring (the edge acts as a wall). No clock. Press <b>SELECT</b> to leave the dummy dizzy so you can practice your finishing move.", body),
             P("<b>2 PLAYER</b> - both players choose a fighter. Choosing the same fighter gives player 2 an alternate costume. The move list is locked out in the pause menu: fight from memory.", body),
             P("<b>OPTIONS</b> - music and sound effects volume, 0 to 10. (Options are not saved.)", body),
             P("<b>RECORDS</b> - the five fastest tournament clears with time, combos and fighter.", body),
             P("Pause menu", H2),
             P("Press <b>START</b> during a fight: <b>RESUME</b>, <b>MOVE LIST</b> (that fighter's moves, strings and finisher code; not in 2 player) or <b>FORFEIT</b> (<b>EXIT PRACTICE</b> in practice), which returns you to the main menu.", body)])

@page("Fighting rules")
def rules(c, n):
    flow(c, [B("A match is <b>best of 3 rounds</b>. Rounds last <b>60 seconds</b>. On time-out, the fighter with more health wins."),
             B("<b>Highs</b> whiff on crouching fighters. <b>Lows</b> beat a standing guard. <b>Mids</b> beat crouch guard."),
             B("A well-timed <b>sidestep</b> makes a committed attack miss."),
             B("<b>Counter hits</b> (hitting someone mid-attack) do +25% damage."),
             B("<b>Jumping</b> clears low attacks, but getting hit in the air always knocks you down. Jump attacks are mids."),
             B("<b>Throws</b> are unblockable but miss crouchers and jumpers."),
             B("<b>Ring out:</b> knockdowns and launches push fighters back, and near the edge they go over."),
             B("<b>Strings:</b> many moves chain into a follow-up if you press the next button while the first hit is still out (for example ROCCO's jab, cross, hook, uppercut is <b>Y, X, Y, X</b>)."),
             B("<b>Input buffer:</b> presses are remembered for a moment, so you can press the next button a little early.")])

@page("Combos")
def combos(c, n):
    ranks = [["3", "TRIPLE"], ["4", "SUPER"], ["5", "HYPER"], ["6", "BRUTAL"], ["7", "MASTER"], ["8", "AWESOME"], ["9", "BLASTER"], ["10", "MONSTER"], ["11", "KING"], ["12-15", "KILLER"], ["16-20", "INSANE"], ["21+", "ULTRA"]]
    rt = Table([[P("<b>%s</b>" % a, cell), P(b, cell)] for a, b in ranks], colWidths=[0.45 * inch, 0.85 * inch])
    rt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#efe5cf")), ("LINEBELOW", (0, 0), (-1, -1), .25, colors.HexColor("#d8cdb4")), ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    left = [P("Once a hit connects, <b>any ground move can cancel into any other</b> (each move up to 3 times per combo). Mix strings and cancels to build long combos.", body),
            B("Single hits are weak (half damage). Every extra hit adds more, up to <b>2.5x</b>."),
            B("<b>Knockdowns</b> only come from enders at the end of a 5+ hit combo, launchers in a 4+ hit combo, sweeps, throws, K.O.s, or hitting someone in the air."),
            B("<b>Overkill:</b> a combo that empties the health bar keeps going until it ends."),
            B("<b>COMBO BREAKER:</b> press <b>L</b> while being comboed (from the 3rd hit on), once per round."),
            B("Juggles do 75% damage and are capped.")]
    t = Table([[left, [P("Announcer ranks", H2), rt]]], colWidths=[W - 1.45 * inch, 1.4 * inch])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (0, 0), 8)]))
    flow(c, [t])

@page("Finishing moves")
def finish(c, n):
    rows = [[th("Fighter"), th("Finisher"), th("Code")]] + [[P("<b>%s</b>" % nm, cell), P(f[0], cell), Paragraph('<font name="M">%s</font>' % arrows(f[1]), cell)] for nm, _, _, f in ROSTER]
    flow(c, [P("When a knockout would <b>decide the match</b>, the loser is not knocked out. They are left <b>dizzy</b> at a sliver of health for 5 seconds, stars circling their head: <b>FINISH THEM!</b> The clock stops.", body),
             P("Get close and enter your fighter's code, one press per step, quickly. The game takes over: the screen darkens, the camera swings around, and a flurry of hits ends in a launch, an air strike and a final blow: <b>FINISHED!</b>", body),
             tbl(rows, [0.7 * inch, 1.5 * inch, W - 2.2 * inch]), Sp(5),
             P("Any normal hit just knocks the dizzy fighter out, and if nobody acts in 5 seconds they drop on their own. <b>The CPU can finish you too</b> (more often at higher levels). Arrows are relative to your opponent. In Practice mode, press SELECT to make the dummy dizzy and practice.", body)])

def fighter_page(i):
    nm, style, rows, fin = ROSTER[i]
    def fn(c, n):
        fc = ParagraphStyle("fc", parent=cell, fontSize=7.1, leading=8.6)
        data = [[th("Move"), th("Input"), th("Hit"), th("Note")]]
        for mv, inp, lvl, note in rows:
            data.append([P(mv, fc), Paragraph(arrows(inp), fc), P(lvl, fc), P(note, fc)])
        items = [P("<b>%s</b> - %s" % (nm, BLURB[nm]), body),
                 tbl(data, [1.0 * inch, W - 1.0 * inch - 0.5 * inch - 0.62 * inch, 0.5 * inch, 0.62 * inch]), Sp(3),
                 P("<b>FINISHER: %s</b>  <font name='M'>%s</font>  (on a dizzy opponent, close range)" % (fin[0], arrows(fin[1])), body)]
        flow(c, items)
    pages.append((nm + " - " + style, fn))
for i in range(6): fighter_page(i)

@page("Tips")
def tips(c, n):
    flow(c, [B("Start in <b>Practice</b> mode. The dummy never hits back, so you can learn each string and cancel."),
             B("Press the next button <b>early</b>; the input buffer remembers it."),
             B("A string that connects can be cancelled into another move, so vary your buttons to reach bigger ranks without running out of uses (3 per move)."),
             B("<b>Keep your COMBO BREAKER</b> for the big ones: you only get one per round."),
             B("Sidestep (<b>R + Up/Down</b>) around slow, committed attacks, then punish."),
             B("Watch the edge. A knockdown near the rim can end the round with a ring out."),
             B("Learn your finisher code in Practice (SELECT makes the dummy dizzy)."),
             P("Reading the move lists", H2),
             P("<b>Hit:</b> high / mid / low / throw. <b>ender</b> = knocks down at the end of a 5+ hit combo. <b>launcher</b> = launches in a 4+ hit combo. <b>knockdown</b> = always knocks down. 'after X: Y' means press Y while move X is still out. Arrows are toward / away from your opponent.", small)])

@page("Records and help")
def records(c, n):
    flow(c, [P("Saving", H2),
             P("This is an arcade game: the only thing saved is the <b>records table</b> (fastest tournament times and the combos landed), in the cartridge's battery-backed RAM with a checksum. Options are not saved. If the table is ever damaged, it starts over empty.", body),
             P("Troubleshooting", H2),
             B("<b>Black screen or crash:</b> the ROM needs <b>Super FX (GSU-2)</b> support. Use an emulator or flash cart that supports it."),
             B("<b>No records after reopening the emulator:</b> make sure your emulator saves cartridge (battery) RAM."),
             B("<b>Slow or stuttering:</b> the game draws at about 30 frames per second with full 60 Hz game logic; that is normal."),
             B("<b>No music:</b> check the volume in OPTIONS (it resets to default every time)."),
             ])

@page("Credits")
def credits(c, n):
    flow(c, [P("<b>Game design and direction:</b> Xenocide21", body),
             P("<b>Programming, art, sound and manual:</b> Claude (an AI model made by Anthropic), working from Xenocide21's ideas.", body),
             P("<b>Technical notes</b>", H2),
             B("Written in 65816 assembly (ca65 / ld65) for the SNES CPU, with the polygon renderer in <b>Super FX (GSU-2)</b> assembly."),
             B("The Super FX transforms and fills about 60 shaded polygons per fighter each frame into sprite tiles; the SNES CPU builds the next frame meanwhile."),
             B("Fighters, animations, moves and finishers are generated from plain Python data (tools/fighters.py). Sound is a custom SPC700 driver with synthesized samples and music."),
             B("Mode 7 arena with per-scanline HDMA perspective, rotating camera, and a separate menu display mode."),
             P("<b>Fonts:</b> Anton (SIL Open Font License 1.1) for the logo and menu title art.", small),
             P("Source code, build tools and this manual's source are all in the project repository.", small)])

@page("License")
def lic(c, n):
    txt = open(os.path.join(HERE, "LICENSE_TEXT.txt")).read().split("\n\n")
    st = ParagraphStyle("l", parent=small, fontSize=5.6, leading=6.9, spaceAfter=2.5)
    items = [P(t.replace("\n", " "), st) for t in txt]
    items.append(P("<i>Anton font: Copyright 2020 The Anton Project Authors, SIL Open Font License 1.1 (scripts.sil.org/OFL). The font is not covered by the MIT License above.</i>", st))
    flow(c, items)

@page()
def backcover(c, n):
    c.setFillColor(DARK); c.rect(0, 0, PW, PW, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#ffd36a")); c.setFont("Anton", 26); c.drawCentredString(PW / 2, PW * .64, "ARENA FIGHTER")
    c.setFillColor(colors.HexColor("#6fb0ff")); c.setFont("Anton", 40); c.drawCentredString(PW / 2, PW * .50, "FX")
    c.setFillColor(colors.HexColor("#ffd5a0")); c.setFont("SB", 8); c.drawCentredString(PW / 2, PW * .42, "FOR THE SUPER FX CHIP")
    c.setFillColor(colors.HexColor("#c9bfe0")); c.setFont("S", 6.3)
    for i, t in enumerate(["(c) 2026 Xenocide21. MIT License. Free and open source. Not for sale.", "Made with Claude, an AI model made by Anthropic.",
                           "Not affiliated with or endorsed by Nintendo. SNES and Super Famicom are trademarks of their owners."]):
        c.drawCentredString(PW / 2, PW * .24 - i * 10, t)
    c.setStrokeColor(GOLD); c.setLineWidth(2); c.line(MG, PW * .33, PW - MG, PW * .33)

def build(path):
    c = canvas.Canvas(path, pagesize=(PW, PW)); c.setTitle("ARENA FIGHTER FX - Game Manual"); c.setAuthor("Xenocide21"); c.setSubject("Instruction booklet for the SNES homebrew ARENA FIGHTER FX")
    for n, (title, fn) in enumerate(pages, 1):
        if title: chrome(c, title, n)
        fn(c, n); c.showPage()
    c.save(); print("pages:", len(pages))

if __name__ == "__main__":
    build(os.path.join(HERE, "ARENA_FIGHTER_FX_manual.pdf"))
