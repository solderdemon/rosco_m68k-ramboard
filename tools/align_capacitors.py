"""Line the capacitors up with the chips they decouple.

The 5.08 mm migration (``migrate_100nf.py``) kept pad 1 where the old 2.54 mm
pad was, which left every 100 nF body 1.3-1.5 mm off the axis of its SRAM, C1
4 mm off U1 and turned around, and C9 1.4 mm off IC1.  This script puts each
body on the centre line of its chip (same row height as before) and reattaches
the tracks: parallel ones are shortened, perpendicular ones get a 45 degree
entry, the rest keep their geometry behind a short lead.

C1 and C2 could not be centred as drawn: the data bus bends down to U1 and U2
right there.  So the bend of D0-D7 (B.Cu) is carried 1.7 mm to the right, and
D8/D9 (F.Cu) are led between the two pads of C2 instead of under its VCC pad;
U2 pin 32 gets its own via onto the bottom VCC run.  C10 and C11 stand on the
IC1/C9 axis, centred on the end pin rows of U1 and U2; the redundant F.Cu GND
link from C1 to the J1 corner is dropped because it ran exactly where C10's
VCC pad now sits (GND stays on both pours and on the B.Cu run).  Designators
of the 100 nF parts go inside the body outline.

Run with KiCad's Python; re-running changes nothing.
"""
from pathlib import Path
import pcbnew as pcb
import wx

wx.Log.EnableLogging(False)
root = Path(__file__).resolve().parents[1]
board_path = root / 'design' / 'roscram01.kicad_pcb'
board = pcb.LoadBoard(str(board_path))
MM, mm = pcb.FromMM, pcb.ToMM
TOL = MM(0.05)
F, B = pcb.F_Cu, pcb.B_Cu
W_SIG, W_PWR = MM(0.1524), MM(0.254)
removed = []          # SWIG: keep deleted items alive until the board is saved
changed = False


def fp(ref):
    f = board.FindFootprintByReference(ref)
    assert f, ref
    return f


def pad(ref, number):
    return next(p for p in fp(ref).Pads() if p.GetNumber() == number)


def chip_axis(ref):
    xs = sorted({p.GetPosition().x for p in fp(ref).Pads()})
    return (xs[0] + xs[-1]) // 2


def V(x, y):
    return pcb.VECTOR2I(int(round(x)), int(round(y)))


def P(x, y):
    """Point from millimetres."""
    return V(MM(x), MM(y))


def near(a, b, tol=TOL):
    return (a - b).EuclideanNorm() <= tol


def copy(v):
    # SWIG hands out references into the track for GetStart()/GetEnd(); a point
    # kept across a SetStart()/SetEnd() has to be a copy.
    return V(v.x, v.y)


def start(t):
    return copy(t.GetStart())


def end(t):
    return copy(t.GetEnd())


def segments():
    return [t for t in board.GetTracks() if t.GetClass() == 'PCB_TRACK']


def net(name):
    n = board.FindNet(name)
    assert n, name
    return n


def ends_at(p, net_, layer=None):
    return [t for t in segments() if t.GetNetCode() == net_.GetNetCode()
            and (layer is None or t.GetLayer() == layer)
            and (near(start(t), p) or near(end(t), p))]


def other_end(t, p):
    return end(t) if near(start(t), p) else start(t)


def set_end(t, p_old, p_new):
    if near(start(t), p_old):
        t.SetStart(p_new)
    else:
        t.SetEnd(p_new)


def add_segment(a, b, layer, net_, width):
    if near(a, b):
        return
    t = pcb.PCB_TRACK(board)
    t.SetStart(a); t.SetEnd(b); t.SetLayer(layer); t.SetWidth(width); t.SetNet(net_)
    board.Add(t)


# ------------------------------------------------------------ explicit re-routing
def seg(layer, netname, a, b, tol=MM(0.02)):
    n = net(netname)
    for t in segments():
        if t.GetLayer() == layer and t.GetNetCode() == n.GetNetCode():
            s, e = start(t), end(t)
            if (near(s, a, tol) and near(e, b, tol)) or (near(s, b, tol) and near(e, a, tol)):
                return t
    return None


def kill(layer, netname, a, b):
    t = seg(layer, netname, a, b)
    assert t is not None, ('missing', netname, mm(a.x), mm(a.y), mm(b.x), mm(b.y))
    board.Remove(t); removed.append(t)


def add(layer, netname, a, b, width=None):
    add_segment(a, b, layer, net(netname), width or (W_PWR if netname in ('VCC', 'GND') else W_SIG))


def retarget(layer, netname, a, b, a_new):
    """Move the ``a`` end of segment (a, b) to ``a_new``."""
    t = seg(layer, netname, a, b)
    assert t is not None, ('missing', netname, mm(a.x), mm(a.y), mm(b.x), mm(b.y))
    set_end(t, a, a_new)


def add_via(netname, p):
    v = pcb.PCB_VIA(board)
    v.SetPosition(p)
    v.SetViaType(pcb.VIATYPE_THROUGH)
    v.SetLayerPair(F, B)
    v.SetDrill(MM(0.381))
    try:
        v.SetWidth(pcb.PADSTACK.ALL_LAYERS, MM(0.635))
    except Exception:
        v.SetWidth(MM(0.635))
    v.SetNet(net(netname))
    board.Add(v)


def shift_u1_fan():
    """D0-D7 bend down to U1 exactly where C1's GND pad has to be.  Carry the
    whole bend (runs' left ends, diagonals, verticals, vias, the F.Cu stubs that
    start at the vias) 1.7 mm to the right; everything moves together, so the
    6 mil spacing inside the fan is untouched."""
    if seg(B, 'D7', P(176.111, 35.471), P(172.657, 35.471)) is None:
        return False
    dx = MM(1.7)
    x0, x1, y0, y1 = MM(165.0), MM(174.0), MM(35.0), MM(53.0)
    codes = {net(f'D{i}').GetNetCode() for i in range(8)}

    def inside(p):
        return x0 <= p.x < x1 and y0 <= p.y <= y1

    for t in list(board.GetTracks()):
        if t.GetNetCode() not in codes:
            continue
        if t.GetClass() == 'PCB_VIA':
            p = copy(t.GetPosition())
            if inside(p):
                t.SetPosition(V(p.x + dx, p.y))
        elif t.GetClass() == 'PCB_TRACK':
            s, e = start(t), end(t)
            if inside(s):
                t.SetStart(V(s.x + dx, s.y))
            if inside(e):
                t.SetEnd(V(e.x + dx, e.y))
    print('U1: D0-D7 bend moved 1.7 mm right')
    return True


def unlink_c1():
    """Old C1 leads; the F.Cu GND run to the J1 corner goes too (see unlink_c10)."""
    if seg(F, 'VCC', P(165.26, 36.132), P(167.78, 36.106)) is None:
        return False
    kill(F, 'VCC', P(165.26, 36.132), P(167.78, 36.106))
    kill(F, 'VCC', P(165.26, 36.132), P(167.78, 38.651))
    kill(F, 'VCC', P(167.78, 38.651), P(167.78, 38.773))
    kill(B, 'VCC', P(165.26, 36.132), P(164.18, 35.027))
    kill(B, 'GND', P(170.32, 36.106), P(169.062, 37.363))
    return True


def link_c1():
    p1, p2 = copy(pad('C1', '1').GetPosition()), copy(pad('C1', '2').GetPosition())
    j = P(167.78, 36.106)                       # legacy VCC junction on F.Cu
    add(F, 'VCC', p1, j)
    k = V(j.x, p1.y + (j.x - p1.x))             # 45 degrees down to the via column
    add(F, 'VCC', p1, k)
    add(F, 'VCC', k, P(167.78, 38.773))
    r = V(p1.x - (p1.y - MM(35.027)), MM(35.027))
    add(B, 'VCC', p1, r)
    retarget(B, 'VCC', P(164.18, 35.027), P(147.015, 35.027), r)
    g = V(p2.x - (MM(37.363) - p2.y), MM(37.363))
    add(B, 'GND', p2, g)
    retarget(B, 'GND', P(169.062, 37.363), P(153.924, 37.363), g)


def reroute_u2_fan():
    """D8 and D9 came down under C2's VCC pad; lead them between the two pads.
    C2's F.Cu VCC path up to U2 pin 32 went through the same spot: pin 32 gets
    a via of its own onto the bottom VCC run instead."""
    if seg(F, 'D8', P(166.851, 127.898), P(166.851, 131.9)) is None:
        return False
    # D8
    kill(F, 'D8', P(166.851, 127.898), P(166.851, 131.9))
    kill(F, 'D8', P(166.851, 131.9), P(167.729, 132.779))
    # The runs sit exactly 0.3048 mm apart: keep their y to the micron.
    retarget(F, 'D8', P(167.729, 132.7785), P(195.072, 132.7785), P(169.779, 132.7785))
    add(F, 'D8', P(166.851, 127.898), P(168.9, 129.947))
    add(F, 'D8', P(168.9, 129.947), P(168.9, 131.9))
    add(F, 'D8', P(168.9, 131.9), P(169.779, 132.7785))
    # D9
    kill(F, 'D9', P(166.304, 128.922), P(166.304, 128.473))
    kill(F, 'D9', P(166.304, 128.926), P(166.306, 128.924))
    kill(F, 'D9', P(166.304, 131.785), P(166.304, 128.926))
    kill(F, 'D9', P(166.306, 128.924), P(166.304, 128.922))
    kill(F, 'D9', P(167.603, 133.083), P(166.304, 131.785))
    retarget(F, 'D9', P(167.603, 133.0833), P(195.198, 133.0833), P(169.633, 133.0833))
    add(F, 'D9', P(166.304, 128.473), P(168.3, 130.469))
    add(F, 'D9', P(168.3, 130.469), P(168.3, 131.75))
    add(F, 'D9', P(168.3, 131.75), P(169.633, 133.0833))
    # C2 VCC: old F.Cu path pad -> pin 32, old B.Cu diagonal, hidden stubs
    kill(F, 'VCC', P(162.192, 125.006), P(161.811, 125.006))
    kill(F, 'VCC', P(167.437, 125.006), P(161.811, 125.006))
    kill(F, 'VCC', P(168.3, 125.87), P(167.437, 125.006))
    kill(F, 'VCC', P(168.3, 129.958), P(168.3, 125.87))
    kill(F, 'VCC', P(168.288, 129.971), P(168.3, 129.958))
    kill(F, 'VCC', P(168.288, 131.102), P(168.288, 129.971))
    kill(F, 'VCC', P(168.0, 131.102), P(168.288, 131.102))
    kill(B, 'VCC', P(168.0, 131.102), P(168.288, 131.102))
    kill(B, 'VCC', P(166.51, 132.88), P(168.288, 131.102))
    add(F, 'VCC', P(161.811, 125.006), P(161.811, 131.6))
    add_via('VCC', P(161.811, 131.6))
    add(B, 'VCC', P(161.811, 131.6), P(163.091, 132.88))
    # C2 GND: old leads on both layers
    kill(B, 'GND', P(173.08, 131.102), P(170.828, 131.102))
    kill(B, 'GND', P(173.08, 131.102), P(173.08, 128.85))
    kill(B, 'GND', P(173.215, 128.714), P(173.08, 128.85))
    kill(F, 'GND', P(173.08, 131.102), P(173.321, 130.861))
    print('U2: D8/D9 led between the C2 pads, pin 32 via added')
    return True


def link_c2():
    p1, p2 = copy(pad('C2', '1').GetPosition()), copy(pad('C2', '2').GetPosition())
    add(B, 'VCC', p1, V(p1.x - (MM(132.88) - p1.y), MM(132.88)))
    add(B, 'GND', P(170.828, 131.102), p2)
    k = V(p2.x, MM(128.714) + (MM(173.215) - p2.x))
    add(B, 'GND', p2, k)
    add(B, 'GND', k, P(173.215, 128.714))
    d = MM(131.102) - MM(130.861)
    e = V(p2.x + d, MM(130.861))
    add(F, 'GND', p2, e)
    retarget(F, 'GND', P(173.321, 130.861), P(183.68, 130.861), e)


def unlink_c10(x_new):
    """C10 moves 3.1 mm left onto the IC1 axis.  Its pads were the F/B links of
    VCC and GND to the J1 corner; the links stay on the pads, the tracks follow.
    The F.Cu GND diagonal from C1's run passed exactly through the new VCC pad
    and cannot be led around (JP1-JP3 wall, VCC diagonal), so it is dropped
    together with the run it fed; both are duplicates of the B.Cu GND run."""
    if seg(F, 'GND', P(187.744, 44.056), P(179.794, 36.106)) is None:
        return False
    kill(F, 'GND', P(187.744, 44.056), P(179.794, 36.106))
    kill(F, 'GND', P(179.794, 36.106), P(170.32, 36.106))
    y_bend = MM(34.874) + (x_new - MM(181.102))
    retarget(F, 'VCC', P(187.744, 41.516), P(181.102, 34.874), V(x_new, y_bend))
    kill(F, 'VCC', P(187.744, 40.869), P(187.744, 41.516))
    kill(B, 'VCC', P(187.744, 40.869), P(187.744, 41.516))
    retarget(B, 'VCC', P(187.744, 41.516), P(190.97, 44.742), P(187.097, 40.869))
    retarget(F, 'GND', P(187.744, 44.056), P(179.032, 44.056), V(x_new - (MM(44.056) - MM(43.409)), MM(44.056)))
    kill(F, 'GND', P(187.744, 43.409), P(187.744, 44.056))
    kill(B, 'GND', P(187.744, 43.409), P(187.744, 44.056))
    kill(B, 'GND', P(187.744, 44.069), P(187.744, 44.056))
    print('C10: links re-hung on the new pad positions')
    return True


def link_c10():
    p1, p2 = copy(pad('C10', '1').GetPosition()), copy(pad('C10', '2').GetPosition())
    add(F, 'VCC', V(p1.x, MM(34.874) + (p1.x - MM(181.102))), p1)
    add(B, 'VCC', p1, P(187.097, 40.869))
    add(F, 'GND', V(p2.x - (MM(44.056) - p2.y), MM(44.056)), p2)
    k = V(p2.x + (MM(44.069) - p2.y), MM(44.069))
    add(B, 'GND', p2, k)
    add(B, 'GND', k, P(187.744, 44.069))


def unlink_c11():
    if seg(B, 'VCC', P(179.121, 132.88), P(187.846, 124.155)) is None:
        return False
    kill(B, 'VCC', P(179.121, 132.88), P(187.846, 124.155))
    kill(B, 'VCC', P(183.528, 119.837), P(187.846, 124.155))
    kill(B, 'VCC', P(187.744, 123.736), P(187.846, 124.155))
    kill(F, 'GND', P(183.68, 130.861), P(187.846, 126.695))
    kill(F, 'GND', P(187.744, 126.276), P(187.846, 126.695))
    kill(B, 'GND', P(186.068, 120.142), P(189.776, 123.85))
    kill(B, 'GND', P(189.776, 123.85), P(189.776, 124.765))
    kill(B, 'GND', P(189.776, 124.765), P(187.846, 126.695))
    kill(B, 'GND', P(187.744, 126.276), P(187.846, 126.695))
    print('C11: links re-hung on the new pad positions')
    return True


def link_c11():
    p1, p2 = copy(pad('C11', '1').GetPosition()), copy(pad('C11', '2').GetPosition())
    # VCC from C9's column: extend the vertical, 45 degrees onto the pad
    k = V(MM(183.528), p1.y - (p1.x - MM(183.528)))
    add(B, 'VCC', P(183.528, 119.837), k)
    add(B, 'VCC', k, p1)
    # VCC from the bottom run: up at x 182, 45 degrees onto the pad, clear of the GND pad
    a = P(182.0, 132.88 - (182.0 - 179.121))
    b = V(MM(182.0), p1.y + (p1.x - MM(182.0)))
    add(B, 'VCC', P(179.121, 132.88), a)
    add(B, 'VCC', a, b)
    add(B, 'VCC', b, p1)
    # GND: the F.Cu run along the bottom turns up into the pad
    run = [t for t in ends_at(P(183.68, 130.861), net('GND'), F)]
    assert len(run) == 1, len(run)
    set_end(run[0], P(183.68, 130.861), V(p2.x, MM(130.861)))
    add(F, 'GND', V(p2.x, MM(130.861)), p2)
    # GND from C9's column: down, then 45 degrees onto the pad
    g = V(MM(186.068), p2.y - (MM(186.068) - p2.x))
    add(B, 'GND', P(186.068, 120.142), g)
    add(B, 'GND', g, p2)


# ------------------------------------------------------------ generic moves
def merge_colinear(t, p_near):
    """Absorb colinear continuations beyond the far end of ``t``."""
    while True:
        q = other_end(t, p_near)
        u = q - p_near
        nxt = [s for s in ends_at(q, t.GetNet(), t.GetLayer()) if s.m_Uuid != t.m_Uuid]
        if len(nxt) != 1:
            return
        s = nxt[0]
        w = other_end(s, q) - q
        if abs(u.x * w.y - u.y * w.x) > TOL * max(u.EuclideanNorm(), 1) or u.Dot(w) <= 0:
            return
        set_end(t, q, other_end(s, q))
        board.Remove(s); removed.append(s)


def reattach(p_old, p_new, net_):
    """Tracks that ended at ``p_old`` now have to reach ``p_new``."""
    global changed
    d = p_new - p_old
    L = d.EuclideanNorm()
    segs = ends_at(p_old, net_)
    if not segs or L <= TOL:
        return
    changed = True
    stubs = set()

    def stub(t):
        if t.GetLayer() not in stubs:
            stubs.add(t.GetLayer())
            add_segment(p_new, p_old, t.GetLayer(), net_, t.GetWidth())

    if L <= MM(0.75):                        # hidden under the pad anyway
        for t in segs:
            stub(t)
        return
    assert abs(d.y) <= MM(0.1), ('only horizontal moves are handled', mm(d.x), mm(d.y))
    sx = 1 if d.x > 0 else -1
    for t in segs:
        merge_colinear(t, p_old)
        q = other_end(t, p_old)
        u = q - p_old
        length = u.EuclideanNorm()
        layer, width = t.GetLayer(), t.GetWidth()
        if abs(u.y) <= TOL:                  # parallel to the move: just shorten/extend
            set_end(t, p_old, p_new)
        elif abs(u.x) <= TOL:                # perpendicular: 45 degree entry
            if length >= L + TOL:
                sy = 1 if u.y > 0 else -1
                j = V(p_old.x, p_new.y + sy * L)
                set_end(t, p_old, j)
                add_segment(p_new, j, layer, net_, width)
            else:
                stub(t)
        elif u.x * sx > 0:                   # heads the way the pad went
            t_len = L / (abs(u.x) / length)
            if t_len <= length - TOL:        # shorten, then a straight connector
                r = V(p_old.x + u.x * t_len / length, p_old.y + u.y * t_len / length)
                set_end(t, p_old, r)
                add_segment(p_new, r, layer, net_, width)
            else:                            # translate if a horizontal run continues
                cont = [s for s in ends_at(q, net_, layer) if s.m_Uuid != t.m_Uuid
                        and abs((other_end(s, q) - q).y) <= TOL]
                if cont:
                    q2 = V(q.x + d.x, q.y)       # the run stays level; the diagonal takes the row offset
                    set_end(t, p_old, p_new); set_end(t, q, q2)
                    for s in cont:
                        set_end(s, q, q2)
                else:
                    stub(t)
        else:                                # heads away: keep it behind a short lead
            stub(t)


def move(ref, x, y, rot):
    """Move a two-pad capacitor and keep its tracks attached."""
    global changed
    f = fp(ref)
    target = V(x, y)
    if near(copy(f.GetPosition()), target, MM(0.005)) and abs(f.GetOrientationDegrees() - rot) < 1e-6:
        return False
    before = {p.GetNumber(): (copy(p.GetPosition()), p.GetNet()) for p in f.Pads()}
    p1, p2 = before['1'][0], before['2'][0]
    pitch = p2 - p1
    # Where the 2.54 mm pad 2 stood before the migration (GND tracks still end there).
    legacy_p2 = V(p1.x + pitch.x / 2, p1.y + pitch.y / 2) if pitch.EuclideanNorm() > MM(5) else None
    f.SetOrientationDegrees(rot)
    f.SetPosition(target)
    after = {p.GetNumber(): copy(p.GetPosition()) for p in f.Pads()}
    for n in ('1', '2'):
        candidates = [before[n][0]]
        if n == '2' and legacy_p2 is not None:
            candidates.append(legacy_p2)
        for c in candidates:
            if any(near(c, p) for p in after.values()):
                continue
            reattach(c, after[n], before[n][1])
    changed = True
    print(f'{ref}: centre {mm(f.GetPosition().x):.3f},{mm(f.GetPosition().y):.3f} rot {rot:g}')
    return True


# Row heights: the legacy rows, the top one at C7's height (0.025 mm lower than
# the other three had), which keeps the GND pads 0.18 mm off the B.Cu VCC bus
# at y 35.03-35.05 instead of 0.13.
TOP_Y, BOTTOM_Y = MM(36.1315), MM(131.1021)
AXIS_X = chip_axis('IC1')

did_u1 = shift_u1_fan(); did_c1 = unlink_c1()
did_u2 = reroute_u2_fan()
did_c10 = unlink_c10(AXIS_X)
did_c11 = unlink_c11()
changed = changed or did_u1 or did_c1 or did_u2 or did_c10 or did_c11

for ref, chip in (('C7', 'U7'), ('C5', 'U5'), ('C3', 'U3'), ('C1', 'U1')):
    move(ref, chip_axis(chip), TOP_Y, 0)
for ref, chip in (('C8', 'U8'), ('C6', 'U6'), ('C4', 'U4'), ('C2', 'U2')):
    move(ref, chip_axis(chip), BOTTOM_Y, 0)
move('C9', AXIS_X, fp('C9').GetPosition().y, 0)
move('C10', AXIS_X, pad('U1', '16').GetPosition().y, -90)
move('C11', AXIS_X, pad('U2', '1').GetPosition().y, -90)

if did_c1:
    link_c1()
if did_u2:
    link_c2()
if did_c10:
    link_c10()
if did_c11:
    link_c11()

# The B.Cu VCC run along the top row was drawn at two heights (35.027 and
# 35.052 mm).  Level it, carrying the ends of the tracks that meet it, so every
# GND pad of the row keeps the same 0.18 mm to it.
BUS_Y = MM(35.0266)
for t in segments():
    if t.GetLayerName() != 'B.Cu' or t.GetNetname() != 'VCC':
        continue
    s, e = start(t), end(t)
    if abs(s.y - e.y) > TOL or not MM(35.0) < s.y < MM(35.1) or abs(s.y - BUS_Y) <= MM(0.002):
        continue
    for p_ in (s, e):
        for o in ends_at(p_, t.GetNet(), t.GetLayer()):
            set_end(o, p_, V(p_.x, BUS_Y))
    changed = True
    print(f'levelled VCC run {mm(s.x):.2f}..{mm(e.x):.2f} to y {mm(BUS_Y):.4f}')

# Designators of the 100 nF parts go inside the body outline, as the SolderDemon
# boards print resistors: centred, 1.0/0.15 mm, upright.  The outline is 4.4 x 2.6 mm
# and the pad mask openings start 1.7 mm from the centre, so "Cn" at 1.0 mm fits
# with 0.5 mm to spare.  C10/C11 are round with the pads 2.54 mm apart; no room there.
for f in board.GetFootprints():
    if f.GetFPIDAsString() != 'SolderDemonCaps:C_Radial_5.08mm':
        continue
    ref = f.Reference()
    want = copy(f.GetPosition())
    if (near(copy(ref.GetPosition()), want, MM(0.005)) and ref.GetTextAngleDegrees() == 0
            and ref.GetTextSize().x == MM(1.0) and ref.GetTextThickness() == MM(0.15)):
        continue
    ref.SetTextSize(V(MM(1.0), MM(1.0)))
    ref.SetTextThickness(MM(0.15))
    ref.SetHorizJustify(pcb.GR_TEXT_H_ALIGN_CENTER)
    ref.SetVertJustify(pcb.GR_TEXT_V_ALIGN_CENTER)
    ref.SetPosition(want)
    ref.SetTextAngle(pcb.EDA_ANGLE(0, pcb.DEGREES_T))
    changed = True
    print(f'{f.GetReference()}: label inside the outline')

# C1's GND pad now sits in a strip of F.Cu pour cut up by the VCC run and the
# C1 leads; two of its thermal spokes would land on islands.  Solid connection,
# as route_lib does for starved thermals.
c1_gnd = pad('C1', '2')
if c1_gnd.GetLocalZoneConnection() != pcb.ZONE_CONNECTION_FULL:
    c1_gnd.SetLocalZoneConnection(pcb.ZONE_CONNECTION_FULL)
    changed = True

if changed:
    pcb.ZONE_FILLER(board).Fill(board.Zones())
    pcb.SaveBoard(str(board_path), board)
    print('saved')
else:
    print('already aligned')
