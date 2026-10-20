"""Notices on the silkscreen: no links, no OSHW logo, plain revision, copyright
of both authors.

Run with KiCad's Python; re-running changes nothing.  The original copyright
line stays: the board is CERN OHL v1.2 and the licence keeps all notices
intact; the SolderDemon notice is added after it.
"""
from pathlib import Path
import pcbnew as pcb
import wx

wx.Log.EnableLogging(False)
root = Path(__file__).resolve().parents[1]
board_path = root / 'design' / 'roscram01.kicad_pcb'
board = pcb.LoadBoard(str(board_path))
removed = []            # SWIG: keep deleted items alive until the board is saved
changed = False

REPLACE = {
    'Copyright ©2020 Ross Bamford & Contributors': '© 2020 Ross Bamford & Contributors · © 2026 SolderDemon',
    'Revision 1 (May 2020)': 'r1',
}
DROP = {'https://rosco-m68k.com'}

for d in list(board.GetDrawings()):
    if d.GetClass() != 'PCB_TEXT':
        continue
    text = d.GetText()
    if text in DROP:
        board.Remove(d); removed.append(d); changed = True
        print('dropped', repr(text))
    elif text in REPLACE:
        d.SetText(REPLACE[text]); changed = True
        print('replaced', repr(text))

for f in list(board.GetFootprints()):
    if f.GetFPIDAsString() == 'Symbol:OSHW-Logo2_9.8x8mm_SilkScreen':
        board.Remove(f); removed.append(f); changed = True
        print('dropped OSHW logo')

# The longer copyright line is centred where the old one was and would run
# past the top edge; keep it 1.5 mm inside the outline.
COPYRIGHT_Y = pcb.FromMM(58.0)
for d in board.GetDrawings():
    if d.GetClass() == 'PCB_TEXT' and d.GetText() == REPLACE['Copyright ©2020 Ross Bamford & Contributors']:
        if d.GetPosition().y != COPYRIGHT_Y:
            d.SetPosition(pcb.VECTOR2I(d.GetPosition().x, COPYRIGHT_Y)); changed = True
            print('copyright recentred')

# "PIN 1" and the socket's designator on one line, 0.8/0.12 mm, the designator
# 3 mm to the right of the label: the layout of the solderdemon_m68k cards
# (pin1_mark() in the gpio card's build_card.py).  Printed once: any extra
# "J1" text copy inside the footprint goes.
pin1 = next(d for d in board.GetDrawings() if d.GetClass() == 'PCB_TEXT' and d.GetText() == 'PIN 1')
j1 = board.FindFootprintByReference('J1')
ref = j1.Reference()
want = pcb.VECTOR2I(pin1.GetPosition().x + pcb.FromMM(3.0), pin1.GetPosition().y)
if (ref.GetPosition() != want or ref.GetTextSize().x != pcb.FromMM(0.8) or not ref.IsVisible()
        or ref.GetLayer() != pcb.F_SilkS):
    ref.SetVisible(True); ref.SetLayer(pcb.F_SilkS)
    ref.SetTextSize(pcb.VECTOR2I(pcb.FromMM(0.8), pcb.FromMM(0.8))); ref.SetTextThickness(pcb.FromMM(0.12))
    ref.SetHorizJustify(pcb.GR_TEXT_H_ALIGN_CENTER); ref.SetVertJustify(pcb.GR_TEXT_V_ALIGN_CENTER)
    ref.SetTextAngle(pcb.EDA_ANGLE(0, pcb.DEGREES_T)); ref.SetMirrored(False)
    ref.SetPosition(want); changed = True
    print('J1 designator beside PIN 1')
for g in list(j1.GraphicalItems()):
    if g.GetClass() == 'PCB_TEXT' and g.GetText() in ('J1', '${REFERENCE}'):
        j1.Remove(g); removed.append(g); changed = True
        print('dropped extra J1 text on', g.GetLayerName())

if changed:
    pcb.SaveBoard(str(board_path), board)
    print('saved')
else:
    print('already clean')
