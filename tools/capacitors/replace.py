"""Replace THT 100 nF footprints with the shared 5.08 mm radial footprint.

The pin-1 copper position and both pin numbers/nets are retained. Call this
before routing; moving pin 2 invalidates any tracks attached to its old pad.
"""

from pathlib import Path

import pcbnew as pcb


LIBRARY = Path(__file__).resolve().parent / 'SolderDemonCaps.pretty'
FPID = pcb.LIB_ID('SolderDemonCaps', 'C_Radial_5.08mm')


def replace_100nf(board):
    replaced = []
    removed = []  # Keep SWIG objects alive until the caller saves the board.
    for old in list(board.GetFootprints()):
        if old.GetValue().lower().replace(' ', '') != '100nf':
            continue
        if old.GetFPIDAsString() == 'SolderDemonCaps:C_Radial_5.08mm':
            continue
        pads = {pad.GetNumber(): pad for pad in old.Pads()}
        if set(pads) != {'1', '2'} or any(p.GetAttribute() == pcb.PAD_ATTRIB_SMD for p in pads.values()):
            continue
        new = pcb.FootprintLoad(str(LIBRARY), 'C_Radial_5.08mm')
        assert new is not None, LIBRARY
        new.SetFPID(FPID)
        new.SetReference(old.GetReference())
        new.SetValue(old.GetValue())
        new.SetPath(old.GetPath())
        new.SetOrientationDegrees(old.GetOrientationDegrees())
        new.SetPosition(old.GetPosition())
        pin1 = next(p for p in new.Pads() if p.GetNumber() == '1')
        new.SetPosition(new.GetPosition() + pads['1'].GetPosition() - pin1.GetPosition())
        for pad in new.Pads():
            original = pads[pad.GetNumber()]
            pad.SetNet(original.GetNet())
            pad.SetPinFunction(original.GetPinFunction())
            pad.SetPinType(original.GetPinType())
            pad.SetLocalZoneConnection(original.GetLocalZoneConnection())
        for original, target in ((old.Reference(), new.Reference()), (old.Value(), new.Value())):
            target.SetPosition(original.GetPosition())
            target.SetTextAngleDegrees(original.GetTextAngleDegrees())
            target.SetTextSize(original.GetTextSize())
            target.SetTextThickness(original.GetTextThickness())
            target.SetLayer(original.GetLayer())
            target.SetVisible(original.IsVisible())
        board.Add(new)
        board.Remove(old)
        removed.append(old)
        replaced.append(old.GetReference())
    return replaced, removed
