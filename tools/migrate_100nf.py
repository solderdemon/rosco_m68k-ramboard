"""Migrate this legacy RAM board's nine 100 nF capacitors to 5.08 mm pitch.

Run once on the original 2.54 mm board with KiCad's Python.  The board predates
the workspace build-card generator, so this script records its migration.
"""
from pathlib import Path
import sys
import pcbnew as pcb
import wx

wx.Log.EnableLogging(False)
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'tools' / 'capacitors'))
from replace import replace_100nf

board_path = root / 'design' / 'roscram01.kicad_pcb'
board = pcb.LoadBoard(str(board_path))
refs, removed = replace_100nf(board)
if refs:
    assert set(refs) == {f'C{i}' for i in range(1, 10)}, refs
    # C1 faces the data bus; its second pad must face away from those tracks.
    cap = board.FindFootprintByReference('C1')
    pin1 = next(p for p in cap.Pads() if p.GetNumber() == '1').GetPosition()
    cap.SetOrientationDegrees(180)
    cap.SetPosition(cap.GetPosition() + pin1 - next(p for p in cap.Pads() if p.GetNumber() == '1').GetPosition())
    offsets = {'C1': (0, 1.2), 'C2': (-2, -1.2), 'C3': (0, -1),
               'C4': (-2, -1.2), 'C5': (0, -1), 'C6': (-2, -1.2),
               'C8': (-2, -1.2), 'C9': (0, -1.2)}
    for ref, (dx, dy) in offsets.items():
        board.FindFootprintByReference(ref).Reference().Move(
            pcb.VECTOR2I(pcb.FromMM(dx), pcb.FromMM(dy)))
    pcb.ZONE_FILLER(board).Fill(board.Zones())
    pcb.SaveBoard(str(board_path), board)
    print('migrated', ', '.join(sorted(refs)))
else:
    print('already migrated')

# Label positions are owned by align_capacitors.py (designators inside the outline).

sch = root / 'design' / 'roscram01.sch'
source = sch.read_text(encoding='utf-8')
if 'rosco_m68k:C2.5-3' in source:
    assert source.count('rosco_m68k:C2.5-3') == 9
    sch.write_text(source.replace('rosco_m68k:C2.5-3', 'SolderDemonCaps:C_Radial_5.08mm'), encoding='utf-8')

table = root / 'design' / 'fp-lib-table'
source = table.read_text(encoding='utf-8')
if '(name SolderDemonCaps)' not in source:
    source = source.replace('\n)', '\n  (lib (name SolderDemonCaps)(type KiCad)(uri ${KIPRJMOD}/../tools/capacitors/SolderDemonCaps.pretty)(options "")(descr "5.08 mm radial capacitor"))\n)')
    table.write_text(source, encoding='utf-8')

bom = root / 'design' / 'roscram01.csv'
source = bom.read_text(encoding='utf-8')
if 'C2.5-3' in source:
    assert source.count('C2.5-3') == 1
    bom.write_text(source.replace('C2.5-3', 'C_Radial_5.08mm'), encoding='utf-8')
