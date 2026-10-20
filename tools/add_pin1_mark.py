"""Mark pin 1 of the J1 bus socket the way the solderdemon_m68k cards do.

The gpio card draws a filled silkscreen triangle pointing at pad 1 of the bus
socket with a small ``PIN 1`` label behind it (``pin1_mark()`` in its
``build_card.py``).  This legacy board predates the generator, so the marker is
added here, in place, with KiCad's Python.  Pad 1 of J1 is the top pad of the
left column and all pads are round, so the pointer sits above the socket.  The
footprint's own ``J1`` silk text occupies that spot and is moved up above the
label.  Re-running the script is a no-op.
"""
from pathlib import Path
import pcbnew as pcb
import wx

wx.Log.EnableLogging(False)
root = Path(__file__).resolve().parents[1]
board_path = root / 'design' / 'roscram01.kicad_pcb'
board = pcb.LoadBoard(str(board_path))

TIP, BASE, HALF = 1.9, 3.1, 0.7   # mm from pad 1 along the pointer, half width
LABEL_DY, LABEL_SIZE = 4.35, 0.8
REF_DY = 6.0                       # the J1 silk text goes above the label


def v(x, y):
    return pcb.VECTOR2I(pcb.FromMM(x), pcb.FromMM(y))


def already_marked():
    return any(d.GetClass() == 'PCB_TEXT' and d.GetLayer() == pcb.F_SilkS and d.GetText() == 'PIN 1'
               for d in board.GetDrawings())


if already_marked():
    print('already marked')
else:
    j1 = board.FindFootprintByReference('J1')
    pad1 = next(p for p in j1.Pads() if p.GetNumber() == '1')
    x, y = pcb.ToMM(pad1.GetPosition().x), pcb.ToMM(pad1.GetPosition().y)

    tri = pcb.PCB_SHAPE(board, pcb.SHAPE_T_POLY)
    tri.SetPolyPoints(pcb.VECTOR_VECTOR2I([v(x, y - TIP), v(x - HALF, y - BASE), v(x + HALF, y - BASE)]))
    tri.SetFilled(True); tri.SetWidth(0); tri.SetLayer(pcb.F_SilkS)
    board.Add(tri)

    label = pcb.PCB_TEXT(board)
    label.SetText('PIN 1'); label.SetPosition(v(x, y - LABEL_DY))
    label.SetTextSize(v(LABEL_SIZE, LABEL_SIZE)); label.SetTextThickness(pcb.FromMM(LABEL_SIZE * .15))
    label.SetLayer(pcb.F_SilkS)
    board.Add(label)

    for g in j1.GraphicalItems():
        if g.GetClass() == 'PCB_TEXT' and g.GetLayer() == pcb.F_SilkS and g.GetText() == 'J1':
            g.SetPosition(v(pcb.ToMM(g.GetPosition().x), y - REF_DY))

    pcb.SaveBoard(str(board_path), board)
    print(f'marked J1 pin 1 at ({x:.2f}, {y:.2f})')
