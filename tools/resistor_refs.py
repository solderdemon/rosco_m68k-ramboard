"""Resistor designators inside the body outline, as on the SolderDemon cards.

The upstream ``rosco_m68k:R-0207_10`` footprint prints ``Rn`` beside the body
at 1.2 mm; the SolderDemon standard (``tools/brand/identity.py``,
``refs_inside``) puts it in the middle of the body at 1.0/0.15 mm, centred.
This footprint carries no F.Fab ``${REFERENCE}`` for that routine to use, so
the label is placed here: at the footprint origin, running along the body
(all five resistors stand vertically; the body is 6.35 x 2.3 mm, so ``Rn``
at 1.0 mm fits lengthwise with more than 2 mm to spare and would touch the
outline upright).

Run with KiCad's Python; re-running changes nothing.
"""
from pathlib import Path
import pcbnew as pcb
import wx

wx.Log.EnableLogging(False)
root = Path(__file__).resolve().parents[1]
board_path = root / 'design' / 'roscram01.kicad_pcb'
board = pcb.LoadBoard(str(board_path))
MM = pcb.FromMM
changed = False

for f in board.GetFootprints():
    if f.GetFPIDAsString() != 'rosco_m68k:R-0207_10':
        continue
    ref = f.Reference()
    want = pcb.VECTOR2I(f.GetPosition())
    a = f.GetOrientationDegrees() % 360   # along the body, reading left-to-right
    angle = pcb.EDA_ANGLE(a - 180 if 90 < a <= 270 else a, pcb.DEGREES_T)   # or bottom-to-top
    if (ref.GetPosition() == want and ref.GetTextAngleDegrees() % 360 == angle.AsDegrees() % 360
            and ref.GetTextSize().x == MM(1.0) and ref.GetTextThickness() == MM(0.15)):
        continue
    ref.SetTextSize(pcb.VECTOR2I(MM(1.0), MM(1.0)))
    ref.SetTextThickness(MM(0.15))
    ref.SetHorizJustify(pcb.GR_TEXT_H_ALIGN_CENTER)
    ref.SetVertJustify(pcb.GR_TEXT_V_ALIGN_CENTER)
    ref.SetPosition(want)
    ref.SetTextAngle(angle)
    changed = True
    print(f'{f.GetReference()}: label inside the outline')

if changed:
    pcb.SaveBoard(str(board_path), board)
    print('saved')
else:
    print('already inside')
