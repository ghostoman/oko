"""FaceTracker printable parts (build123d). Every part is modelled in the WORLD frame
at the neutral pose (pan 0, tilt 0). See ft_params.py for the frame."""
import math
from build123d import (Box, Cylinder, Pos, Rot, Plane, Location, Polygon, RegularPolygon,
                       extrude, chamfer, Axis, Compound, Part)
from ft_params import *


# ------------------------------------------------------------------ helpers
def bx(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def cz(x, y, r, z0, z1):
    return Pos(x, y, (z0 + z1) / 2) * Cylinder(r, z1 - z0)


def cx(y, z, r, x0, x1):
    return Pos((x0 + x1) / 2, y, z) * (Rot(0, 90, 0) * Cylinder(r, x1 - x0))


def cy(x, z, r, y0, y1):
    return Pos(x, (y0 + y1) / 2, z) * (Rot(90, 0, 0) * Cylinder(r, y1 - y0))


def _ccw(pts):
    a = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    return list(pts) if a > 0 else list(reversed(pts))


def pz(pts_xy, z0, z1):
    return Pos(0, 0, z0) * extrude(Polygon(*_ccw(pts_xy), align=None), z1 - z0)


def px(pts_yz, x0, x1):
    s = extrude(Polygon(*_ccw(pts_yz), align=None), x1 - x0)
    return Location(Plane(origin=(x0, 0, 0), x_dir=(0, 1, 0), z_dir=(1, 0, 0))) * s


def py(pts_xz, y0, y1):
    s = extrude(Polygon(*_ccw(pts_xz), align=None), y1 - y0)
    return Location(Plane(origin=(0, y1, 0), x_dir=(1, 0, 0), z_dir=(0, -1, 0))) * s


def cham(shape, edges, d):
    try:
        return chamfer(edges, d)
    except Exception as e:      # keep the plain shape if OCC refuses
        print('  chamfer skipped:', str(e)[:60])
        return shape


def cut_all(s, cutters):
    for c in cutters:
        s = s - c
    return s


def fuse_all(s, adds):
    for a in adds:
        s = s + a
    return s


NEON = {}


def neon(s, part, x0, x1, y0, y1, z0, z1, loc=None):
    """Cut a channel for a 1.75 mm filament strand and remember the strand for the preview."""
    c = bx(x0, x1, y0, y1, z0, z1)
    NEON.setdefault(part, []).append(c if loc is None else loc * c)
    return s - c


# ------------------------------------------------------------------ 1. housing
DOVE_X = 16.0
DOVE_D = 2.5
NEON_Z = -8.6
RAIL_T, RAIL_WING, RAIL_LIP, RAIL_C = 3.0, 1.6, 1.0, 0.15   # L-rail: stem, hook wing (-X), slot lip, clearance
DOVE_ZTOP = -4.0
COL_Z0, COL_Z1 = -24.0, -17.5         # cover screw columns
SERVO_Y0, SERVO_Y1 = YP - MG['W'] / 2, YP + MG['W'] / 2
PORT = (-24.0, -9.0, YI1, -44.0)      # cable port in the deck (x0, x1, y0, y1)


def housing():
    NEON['housing'] = []
    body = bx(-HWO, HWO, YI1, YF, Z_BOT, Z_TOP)
    body = cham(body, body.edges().filter_by(Axis.Y), 2.0)
    cav = bx(-HWI, HWI, YI1 - 1, YI0, Z_BOT_I, Z_SLAB)
    s = body - cav
    # ---- pan servo cradle (servo slides in from the rear, tabs run in grooves, no screws)
    zc0 = ZM - MG['tab_t'] - 2.2
    front = SERVO_Y1 + CLR
    rear = SERVO_Y0 - 0.2
    xl0, xl1 = -14.0, -MG['shaft_off'] - CLR
    xr0, xr1 = MG['L'] - MG['shaft_off'] + CLR, 25.0
    s = s + bx(xl0, xr1, front, YI0 + 0.1, zc0, Z_SLAB + 0.1)
    s = s + bx(xl0, xl1, rear, front, zc0, Z_SLAB + 0.1) + bx(xr0, xr1, rear, front, zc0, Z_SLAB + 0.1)
    gz0, gz1 = ZM - MG['tab_t'] - 0.25, ZM + 0.2
    tab = (MG['tab_L'] - MG['L']) / 2 + 0.35
    s = s - bx(xl1 - tab, xl1 + 0.1, rear - 0.1, front, gz0, gz1) - bx(xr0 - 0.1, xr0 + tab, rear - 0.1, front, gz0, gz1)
    # ---- deck: horn hole, boss tunnel and spline slit so the servo can come in from the rear
    s = s - cz(0, YP, 6.3, Z_SLAB - 0.1, Z_TOP + 1)
    zr = ZM + MG_BOSS + 1.2                                  # roof of the boss tunnel
    s = s - bx(-6.3, BOSS2_X1, YI1 - 1, YP, Z_SLAB - 0.1, zr)   # wide on +X: the MG90S has a second bump next to the shaft boss
    s = s - bx(0, BOSS2_X1, YP - 0.1, YP + MG['boss2_r'] + 0.9, Z_SLAB - 0.1, zr)   # ...and it needs room at the end position too
    s = s - bx(-2.8, 2.8, YI1 - 1, YP, ZM + MG_BOSS, Z_TOP + 1)
    # ---- thrust ring for the yoke
    ring = cz(0, YP, RING_R1, Z_TOP - 0.1, Z_TOP + RING_H) - cz(0, YP, RING_R0, Z_TOP - 1, Z_TOP + 1)
    ring = ring & bx(-HWO, HWO, YI1, YF, 0, 10)
    ring = ring - bx(-2.8, 2.8, YI1 - 1, YP, 0, 10)
    s = s + ring
    # ---- cable port (rear-left of the deck, closed by the cover)
    s = s - bx(PORT[0], PORT[1], PORT[2] - 1, PORT[3], Z_SLAB - 0.1, Z_TOP + 1)
    # ---- cover screw columns
    for sx in (-1, 1):
        xa, xb = sorted((sx * 22.0, sx * (HWI + 0.1)))
        s = s + bx(xa, xb, YI1, YI0 + 0.1, COL_Z0, COL_Z1)
        s = s - cy(sx * 25.0, (COL_Z0 + COL_Z1) / 2, PILOT / 2, YI1 - 1, YI1 + 13)
    # ---- ESP32 seat: 4 corner pads, 2 top stops, 2 lips at the USB end
    ez0, ez1 = ESP_ZC - ESP_W / 2 - 0.1, ESP_ZC + ESP_W / 2 + 0.1
    for sx in (-1, 1):
        xa, xb = (HWI - 4.0, HWI + 0.1) if sx > 0 else (-HWI - 0.1, -HWI + 4.0)
        s = s + bx(xa, xb, ESP_Y_TOP, YI0 + 0.1, ez1 - 3.6, ez1) + bx(xa, xb, ESP_Y_TOP, YI0 + 0.1, Z_BOT_I - 0.1, ez0 + 3.6)
        s = s + bx(xa, xb, ESP_Y_TOP - 3.2, YI0 + 0.1, ez1 + 0.15, ez1 + 2.0)       # top stop
    yb = ESP_Y_TOP - 1.6 - 0.2                                                        # behind the PCB
    for zz in (ez1 - 4.0, ez0 + 1.0):
        lip = px([(yb, zz), (yb - 1.9, zz), (yb - 1.9, zz + 3.0), (yb, zz + 3.0)], HWI - 1.3, HWI + 0.1)
        s = s + lip
    # ---- micro-USB opening (right wall)
    uy = ESP_Y_TOP + 1.4
    s = s - bx(HWI - 0.5, HWO + 1, uy - 4.25, uy + 4.25, ESP_ZC - 6.25, ESP_ZC + 6.25)
    # ---- L-slots for the lid clip rails (open at the bottom, closed at the top: gravity locks the clip)
    for sx in (-1, 1):
        x = sx * DOVE_X
        s = s - bx(x - RAIL_T / 2 - RAIL_C, x + RAIL_T / 2 + RAIL_C, YF - DOVE_D, YF + 0.01, Z_BOT - 1, DOVE_ZTOP)
        s = s - bx(x - RAIL_T / 2 - RAIL_WING - RAIL_C, x - RAIL_T / 2, YF - DOVE_D, YF - RAIL_LIP, Z_BOT - 1, DOVE_ZTOP)
        xe = x + RAIL_T / 2 + RAIL_C
        s = s - pz([(xe - 0.05, YF - DOVE_D), (xe + DOVE_D, YF + 0.01), (xe - 0.05, YF + 0.01)], Z_BOT - 1, DOVE_ZTOP)
    # ---- neon channels on the side walls (continue across the cover)
    for sx in (-1, 1):
        xa, xb = sorted((sx * (HWO - NEON_D), sx * (HWO + 0.5)))
        s = neon(s, 'housing', xa, xb, YI1 - 0.01, YF + 0.01, NEON_Z - NEON_W / 2, NEON_Z + NEON_W / 2)
        s = neon(s, 'housing', xa, xb, YI1 - 0.01, YI1 + 16.0, -47.0 - NEON_W / 2, -47.0 + NEON_W / 2)
    return s


# ------------------------------------------------------------------ 2. housing cover
def cover():
    plate = bx(-HWO, HWO, YR, YI1, Z_BOT, Z_TOP)
    plate = cham(plate, plate.edges().filter_by(Axis.Y), 2.0)
    s = plate
    rim = bx(-HWI + 0.25, HWI - 0.25, YI1 - 0.1, YI1 + 3.0, Z_BOT_I + 0.25, Z_SLAB - 0.25) - \
        bx(-HWI + 1.85, HWI - 1.85, YI1 - 1, YI1 + 4, Z_BOT_I + 1.85, Z_SLAB - 1.85)
    for sx in (-1, 1):                                    # clear the screw columns
        rim = rim - bx(min(sx * 21.5, sx * 29), max(sx * 21.5, sx * 29), YI1 - 1, YI1 + 4, COL_Z0 - 0.4, COL_Z1 + 0.4)
    rim = rim - bx(HWI - 3, HWI + 1, YI1 - 1, YI1 + 4, ESP_ZC - 8, ESP_ZC + 8)   # USB plug side
    s = s + rim
    # PCB hold-down post (antenna end, between the pin rows) and pan-servo retainer
    yb = ESP_Y_TOP - 1.6 - 0.25
    s = s + bx(-27.2, -23.9, YI1 - 0.1, yb, ESP_ZC - 4.2, ESP_ZC + 4.2)
    s = s + bx(2.0, 9.0, YI1 - 0.1, SERVO_Y0 - 0.3, -21.5, -13.0)
    for sx in (-1, 1):
        s = s - cy(sx * 25.0, (COL_Z0 + COL_Z1) / 2, CLEAR / 2, YR - 1, YI1 + 1)
    # slanted vent slits (cyberpunk louvres) over the ESP32
    slits = []
    for i in range(7):
        x = -15.0 + i * 5.6
        slits.append(Pos(x, YI1 - 1, -41.0) * (Rot(0, 35, 0) * Box(2.2, 6, 20.0)))
    s = s - Compound(children=slits)
    # hex cluster next to the servo
    for (x, z) in ((-14.0, -17.0), (-8.6, -20.1), (-14.0, -23.2), (-19.4, -20.1)):
        s = s - Pos(x, YI1 + 1, z) * (Rot(90, 0, 0) * extrude(RegularPolygon(2.7, 6), COVER_T + 2))
    NEON['cover'] = []
    s = neon(s, 'cover', -HWO - 0.5, HWO + 0.5, YR - 0.5, YR + NEON_D, NEON_Z - NEON_W / 2, NEON_Z + NEON_W / 2)
    s = neon(s, 'cover', HWO - 13.0, HWO + 0.5, YR - 0.5, YR + NEON_D, -47.0 - NEON_W / 2, -47.0 + NEON_W / 2)
    s = neon(s, 'cover', -HWO - 0.5, -HWO + 13.0, YR - 0.5, YR + NEON_D, -47.0 - NEON_W / 2, -47.0 + NEON_W / 2)
    return s


# ------------------------------------------------------------------ 3. lid clip
def lid_clip():
    y_r, y_s, y_f, y_o = YF, S0, S1, S1 + LIP_T
    prof = [(y_r, CP_Z), (y_s, CP_Z), (y_s + 0.4, CP_Z + 1.0), (y_s + 0.4, CP_Z + 4.0), (y_s, CP_Z + 5.0),
            (y_s, 0), (y_f, 0), (y_f, -LIP_H + 1.0), (y_f + 0.7, -LIP_H), (y_o, -LIP_H),
            (y_o, BR_T - 1.2), (y_o - 1.2, BR_T), (y_r, BR_T)]
    s = px(prof, -HWO, HWO)
    # notch in the lip for the laptop's own webcam / mics (45 deg sides: prints without support)
    s = s - py([(-9, 0.0), (9, 0.0), (15, -LIP_H - 0.1), (-15, -LIP_H - 0.1)], y_f - 0.05, y_o + 1)
    # L-shaped rails (hook towards -X = upwards when printed on the +X end: no overhang at all)
    d = DOVE_D - 0.15
    for sx in (-1, 1):
        x = sx * DOVE_X
        s = s + bx(x - RAIL_T / 2, x + RAIL_T / 2, YF - d, YF + 0.05, CP_Z, DOVE_ZTOP - 0.05)
        s = s + bx(x - RAIL_T / 2 - RAIL_WING, x - RAIL_T / 2 + 0.05, YF - d, YF - RAIL_LIP - RAIL_C, CP_Z, DOVE_ZTOP - 0.05)
        s = s + pz([(x + RAIL_T / 2 - 0.05, YF - d), (x + RAIL_T / 2 + d, YF + 0.05), (x + RAIL_T / 2 - 0.05, YF + 0.05)], CP_Z, DOVE_ZTOP - 0.05)
    # top corner chamfers to match the housing
    for sx in (-1, 1):
        s = s - py([(sx * HWO, BR_T - 2.0), (sx * HWO, BR_T + 1), (sx * (HWO - 3.0), BR_T + 1)], y_r - 1, y_o + 1)
    return s


# ------------------------------------------------------------------ 4. yoke (pan-rotating fork)
def yoke():
    zt_l, zt_r = ZA + 10.5, ZA + 12.0
    g = 4.0
    prof = [(ARM_L_OUT + 1.5, YOKE_Z0), (ARM_R_OUT - 1.5, YOKE_Z0), (ARM_R_OUT, YOKE_Z0 + 1.5),
            (ARM_R_OUT, zt_r - 1.5), (ARM_R_OUT - 1.5, zt_r), (ARM_R_IN, zt_r),
            (ARM_R_IN, YOKE_Z1 + g), (ARM_R_IN - g, YOKE_Z1), (ARM_L_IN + g, YOKE_Z1), (ARM_L_IN, YOKE_Z1 + g),
            (ARM_L_IN, zt_l), (ARM_L_OUT + 1.5, zt_l), (ARM_L_OUT, zt_l - 1.5), (ARM_L_OUT, YOKE_Z0 + 1.5)]
    s = py(prof, -YOKE_HW, YOKE_HW)
    # tilt servo: window + two inner bosses for the tab screws
    zc = ZA - MG_XC
    for dz in (-MG['hole_dx'] / 2, MG['hole_dx'] / 2):
        z = zc + dz
        zb0, zb1 = (z - 3.0, z + 2.0) if dz < 0 else (z - 2.0, z + 3.0)
        s = s + bx(ARM_R_IN - 2.5, ARM_R_IN + 0.1, -5.0, 5.0, zb0, zb1)
        s = s - cx(0, z, PILOT_SERVO / 2, ARM_R_IN - 3, ARM_R_OUT + 1)
    s = s - bx(ARM_R_IN - 3, ARM_R_OUT + 1, -MG['W'] / 2 - 0.2, MG['W'] / 2 + 0.2, zc - MG['L'] / 2 - 0.2, zc + MG['L'] / 2 + 0.2)
    # left pivot hole
    r = TRUN_R + TRUN_C
    s = s - cx(0, ZA, r, ARM_L_OUT - 1, ARM_L_IN + 1)
    # roof of the hole as a cut-off teardrop (towards +Y = up on the bed): no sagging arc, the pivot never bears there
    q, yt = r * math.sqrt(0.5), r + 0.6
    s = s - px([(q, ZA - q), (yt, ZA - (2 * q - yt)), (yt, ZA + (2 * q - yt)), (q, ZA + q)], ARM_L_OUT - 1, ARM_L_IN + 1)
    # pan horn pocket (horn dropped in from the top, arms keep the yoke from lifting off)
    hl, hw = MG['horn_L'] / 2 + 0.4, MG['horn_w'] / 2 + 0.3
    s = s - bx(-hl, hl, -hw, hw, YOKE_FLOOR, YOKE_Z1 + 1)
    s = s - cz(0, 0, MG['horn_hub_d'] / 2 + 0.4, YOKE_FLOOR, YOKE_Z1 + 1)
    s = s - cz(0, 0, MG['horn_hub_d'] / 2 + 0.3, YOKE_Z0 - 1, YOKE_Z1 + 1)
    s = s - px([(hw - 0.05, YOKE_Z1 - 1.9), (hw - 0.05, YOKE_Z1 + 0.1), (hw + 2.0, YOKE_Z1 + 0.1)], -hl, hl)   # print-side chamfer
    # faceted arm tops and beam edges (45 deg: printable lying on the rear face)
    for (x0, x1, zt) in ((ARM_L_OUT - 1, ARM_L_IN + 1, zt_l), (ARM_R_IN - 3, ARM_R_OUT + 1, zt_r)):
        for sy in (-1, 1):
            s = s - px([(sy * (YOKE_HW - 5.0), zt + 0.1), (sy * (YOKE_HW + 0.1), zt + 0.1), (sy * (YOKE_HW + 0.1), zt - 5.0)], x0, x1)
    for sy in (-1, 1):
        s = s - px([(sy * (YOKE_HW - 1.5), YOKE_Z0 - 0.1), (sy * (YOKE_HW + 0.1), YOKE_Z0 - 0.1), (sy * (YOKE_HW + 0.1), YOKE_Z0 + 1.5)], ARM_L_OUT - 1, ARM_R_OUT + 1)
    # truss window in the left stand (apex towards +Y: self-supporting when printed on the rear face)
    zw = ZA - TRUN_R - 4.0
    s = s - px([(-6.0, 15.0), (-6.0, zw), ((zw - 15.0) / 2 - 6.0, (zw + 15.0) / 2)], ARM_L_OUT - 1, ARM_L_IN + 1)
    # neon channel along the front of the beam
    loc = Pos(0, YP, 0); NEON['yoke'] = []
    s = neon(s, 'yoke', -22.0, 32.0, YOKE_HW - NEON_D, YOKE_HW + 0.5, 6.0, 6.0 + NEON_W, loc)
    # zip-tie slots for the tilt servo cable (rear edge of the beam)
    for x in (12.0, 29.0):
        s = s - bx(x - 1.8, x + 1.8, -YOKE_HW + 2.2, -YOKE_HW + 4.0, YOKE_Z0 - 1, YOKE_Z1 + 1)
    return Pos(0, YP, 0) * s


# ------------------------------------------------------------------ 5. head (tilting part)
RAIL_Y = 13.0
PIN_X1 = CB_PIN0 + 7 * 2.54          # last pin of a row
SCREW_XL, SCREW_XR = (-CHEEK_X0 + FING_L) / 2, 18.0


def head():
    s = bx(-CHEEK_X0, CHEEK_X0, FIN_Y0, FIN_Y1, FIN_Z0, FIN_Z1)
    s = s + bx(-CHEEK_X0, FING_L, FIN_Y0, FIN_Y1, FING_Z0, FIN_Z0 + 0.1) + bx(FING_R, CHEEK_X0, FIN_Y0, FIN_Y1, FING_Z0, FIN_Z0 + 0.1)
    ck = [(-5, -16.5), (-2, -19.5), (12, -19.5), (15, -16.5), (15, 15), (12, 18), (-5, 18)]
    s = s + px(ck, CHEEK_X0 - 0.1, CHEEK_X1) + px(ck, -CHEEK_X1, -CHEEK_X0 + 0.1)
    # right cheek: horn pocket (horn pressed in, then the servo slides into it from outside)
    hl, hw = MG['horn_L'] / 2 + 0.4, MG['horn_w'] / 2 + 0.3
    xp = CHEEK_X1 - HORN_POCKET
    s = s - bx(xp, CHEEK_X1 + 1, -hw, hw, -hl, hl)
    s = s - cx(0, 0, MG['horn_hub_d'] / 2 + 0.4, xp, CHEEK_X1 + 1)
    s = s - cx(0, 0, 2.6, xp - 1.4, CHEEK_X1 + 1)
    s = s - pz([(xp + 0.5, hw - 0.05), (CHEEK_X1 + 0.1, hw - 0.05), (CHEEK_X1 + 0.1, hw + 1.6)], -hl, hl)
    # left trunnion
    # It is printed lying on the bed (rear face of the head). A plain cylinder would touch the bed along a line and come out
    # egg-shaped, so it is cut by the bed plane (flat 8 mm wide, the arc above starts at a 50 deg overhang) and the two
    # edges of the flat get a small 45 deg chamfer: first-layer squish and brim stay inside the bearing circle.
    tr = cx(0, 0, TRUN_R, -CHEEK_X1 - 5.0, -CHEEK_X1 + 0.1) & bx(-CHEEK_X1 - 6, -CHEEK_X1 + 1, FIN_Y0, TRUN_R + 1, -TRUN_R - 1, TRUN_R + 1)
    c = math.sqrt(TRUN_R ** 2 - FIN_Y0 ** 2)
    for sz in (-1, 1):
        tr = tr - px([(FIN_Y0 - 0.1, sz * (c - 0.5)), (FIN_Y0 - 0.1, sz * (c + 3.5)), (FIN_Y0 + 3.9, sz * (c + 3.5))], -CHEEK_X1 - 6, -CHEEK_X1 + 1)
    s = s + tr
    # guides for the webcam clip plate on top of the fin
    g = CLIP_W / 2 + 0.3
    for sx in (-1, 1):
        s = s + px([(FIN_Y0, FIN_Z1 - 0.1), (FIN_Y1, FIN_Z1 - 0.1), (FIN_Y1 - 1.0, FIN_Z1 + 1.6), (FIN_Y0, FIN_Z1 + 1.6)],
                   min(sx * g, sx * CHEEK_X0), max(sx * g, sx * CHEEK_X0))
        # rail for the camera pod on the inner face of each cheek (45 deg underside for printing)
        xw, xt = sx * (CHEEK_X0 + 0.1), sx * (CHEEK_X0 - 0.9)
        s = s + pz([(xw, RAIL_Y - 1.5), (xt, RAIL_Y - 0.6), (xt, RAIL_Y + 0.6), (xw, RAIL_Y + 0.6)], -19.5, SH_Z1 - 0.5)
    # pocket for the unused (upper) pin row of the ESP32-CAM
    zr = CB_Z1 - CB_ROW
    s = s - bx(CB_PIN0 - 2.3, PIN_X1 + 2.3, FIN_Y1 - 4.8, FIN_Y1 + 0.1, zr - 2.0, zr + 2.0)
    # four stand-offs under the corners of the ESP32-CAM
    for (xa, xb) in ((-CB_L / 2, CB_PIN0 - 2.1), (14.0, CB_L / 2)):
        s = s + bx(xa, xb, FIN_Y1 - 0.1, CB_Y0, CB_Z1 - 3.4, CB_Z1)
    s = s + bx(-CB_L / 2, FING_L, FIN_Y1 - 0.1, CB_Y0, CB_Z0, CB_Z0 + 3.6) + bx(16.5, CB_L / 2, FIN_Y1 - 0.1, CB_Y0, CB_Z0, CB_Z0 + 3.6)
    # pilots for the pod screws (from below into the fingers)
    for x in (SCREW_XL, SCREW_XR):
        s = s - cz(x, -0.5, PILOT / 2, FING_Z0 - 1, FING_Z0 + 10)
    # grip grooves on the back of the fin where the webcam flap rests
    for z in (-12.0, -8.0, -4.0, 0.0, 4.0):
        s = s - px([(FIN_Y0 - 0.1, z - 0.6), (FIN_Y0 + 0.5, z), (FIN_Y0 - 0.1, z + 0.6)], -18.0, 18.0)
    return Pos(0, YP, ZA) * s


# ------------------------------------------------------------------ 6. camera pod (cover of the ESP32-CAM)
def shroud():
    s = bx(-SH_HW, SH_HW, SH_Y0, SH_Y1, SH_Z0, SH_Z1)
    iw = SH_HW - 2.05
    s = s - bx(-iw, iw, SH_Y0 - 1, SH_Y1 - 2.0, SH_Z0 + 1.6, SH_Z1 - 1.6)
    pf = CB_Y0 + CB_T + 0.15                                   # PCB front face
    for (xa, xb, za, zb) in ((-iw - 0.1, CB_PIN0 - 2.0, CB_Z1 - 3.4, SH_Z1 - 1.5), (14.0, iw + 0.1, CB_Z1 - 3.4, SH_Z1 - 1.5),
                             (-iw - 0.1, CB_PIN0 - 2.0, SH_Z0 + 1.5, CB_Z0 + 3.4), (5.5, 11.0, SH_Z0 + 1.5, CB_Z0 + 2.6)):
        s = s + bx(xa, xb, pf, SH_Y1 - 1.9, za, zb)            # front stops on the PCB corners
    # facets (front face lies on the bed)
    s = s - px([(SH_Y1 - 2.0, SH_Z0 - 0.1), (SH_Y1 + 0.1, SH_Z0 - 0.1), (SH_Y1 + 0.1, SH_Z0 + 2.0)], -SH_HW - 1, SH_HW + 1)
    s = s - px([(SH_Y1 - 2.0, SH_Z1 + 0.1), (SH_Y1 + 0.1, SH_Z1 + 0.1), (SH_Y1 + 0.1, SH_Z1 - 2.0)], -SH_HW - 1, SH_HW + 1)
    for sx in (-1, 1):
        s = s - pz([(sx * (SH_HW - 2.0), SH_Y1 + 0.1), (sx * (SH_HW + 0.1), SH_Y1 + 0.1), (sx * (SH_HW + 0.1), SH_Y1 - 2.0)], SH_Z0 - 1, SH_Z1 + 1)
        xw, xg = sx * (SH_HW + 0.1), sx * (SH_HW - 1.0)
        s = s - pz([(xw, RAIL_Y - 1.7), (xg, RAIL_Y - 1.7), (xg, RAIL_Y + 0.9), (xw, RAIL_Y + 0.9)], SH_Z0 - 1, SH_Z1 + 1)
    # flanges under the fin fingers + screw holes (45 deg gusset: prints without support)
    for (xa, xb, xs) in ((-SH_HW, FING_L - 0.1, SCREW_XL), (14.0, SH_HW, SCREW_XR)):
        s = s + bx(xa, xb, -3.0, SH_Y0 + 0.1, FLANGE_Z0, FING_Z0 - 0.05)
        s = s + px([(SH_Y0, FLANGE_Z0), (SH_Y0 + 4.0, FLANGE_Z0), (SH_Y0 + 5.6, SH_Z0 + 0.5), (SH_Y0, SH_Z0 + 0.5)], xa, xb)
        s = s - cz(xs, -0.5, CLEAR / 2, FLANGE_Z0 - 1, FING_Z0 + 1)
    # camera window (the square OV2640 head sits in it) and flash LED window
    s = s - bx(CB_LENS_X - 4.7, CB_LENS_X + 4.7, SH_Y1 - 3, SH_Y1 + 1, CB_LENS_Z - 4.7, CB_LENS_Z + 4.7)
    s = s - bx(CB_LED[0] - 2.4, CB_LED[0] + 2.4, SH_Y1 - 3, SH_Y1 + 1, CB_LED[1] - 1.2, CB_LED[1] + 2.4)
    # engraved target brackets around the eye and slashes (0.4 deep, on the bed face)
    e = 0.4
    fr = bx(CB_LENS_X - 7.6, CB_LENS_X + 7.6, SH_Y1 - e, SH_Y1 + 1, CB_LENS_Z - 7.6, CB_LENS_Z + 7.6) - \
        bx(CB_LENS_X - 6.6, CB_LENS_X + 6.6, SH_Y1 - 1, SH_Y1 + 2, CB_LENS_Z - 6.6, CB_LENS_Z + 6.6)
    fr = fr - bx(CB_LENS_X - 3.2, CB_LENS_X + 3.2, SH_Y1 - 1, SH_Y1 + 2, CB_LENS_Z - 9, CB_LENS_Z + 9) - bx(CB_LENS_X - 9, CB_LENS_X + 9, SH_Y1 - 1, SH_Y1 + 2, CB_LENS_Z - 3.2, CB_LENS_Z + 3.2)
    s = s - fr
    for i in range(4):
        s = s - Pos(4.0 + i * 3.4, SH_Y1, CB_LENS_Z + 1.5) * (Rot(0, 35, 0) * Box(1.0, 2 * e, 11.0))
    NEON['shroud'] = []
    s = neon(s, 'shroud', -2.0, SH_HW + 0.5, SH_Y1 - NEON_D, SH_Y1 + 0.5, SH_Z1 - 4.6, SH_Z1 - 4.6 + NEON_W, Pos(0, YP, ZA))
    return Pos(0, YP, ZA) * s


# ------------------------------------------------------------------ 6b. tilt servo cap (cosmetic, push fit)
def servo_cap():
    zc = ZA - MG_XC
    x0 = ARM_R_OUT + 0.2
    xb = ARM_R_OUT + MG_TAB_TOP            # servo bottom (outer end)
    x1 = xb + 2.0
    zt0, zt1 = zc - MG['tab_L'] / 2 - 1.3, zc + MG['tab_L'] / 2 + 1.3
    zb0, zb1 = zc - MG['L'] / 2 - 2.0, zc + MG['L'] / 2 + 2.0
    xs = ARM_R_OUT + 6.0                   # end of the tab / screw-head zone
    k = zb0 - zt0
    prof = [(x0, zt0), (xs, zt0), (xs + k, zb0), (x1 - 1.5, zb0), (x1, zb0 + 1.5), (x1, zb1 - 1.5), (x1 - 1.5, zb1),
            (xs + k, zb1), (xs, zt1), (x0, zt1)]
    hw = MG['W'] / 2 + 0.2 + 1.8
    s = py(prof, -hw, hw)
    for sy in (-1, 1):                     # facet the long outer edges
        s = s - pz([(x1 - 2.0, sy * (hw + 0.1)), (x1 + 0.1, sy * (hw + 0.1)), (x1 + 0.1, sy * (hw - 2.0))], zt0 - 1, zt1 + 1)
    iw = MG['W'] / 2 + 0.2
    s = s - bx(x0 - 1, xb + 0.2, -iw, iw, zc - MG['L'] / 2 - 0.2, zc + MG['L'] / 2 + 0.2)          # body
    s = s - bx(x0 - 1, xs - 1.6, -iw, iw, zt0 + 1.3 - 0.3, zt1 - 1.3 + 0.3)                        # tabs + screw heads
    for sy in (-1, 1):                     # crush ribs gripping the servo body
        for z in (zc - 6.0, zc + 6.0):
            s = s + bx(xs + 1.0, xb, sy * iw - (0.25 if sy > 0 else 0), sy * iw + (0.25 if sy < 0 else 0), z - 0.6, z + 0.6)
    # cable slots, open to the rim. The lead leaves the end face of the servo near the case bottom, so the cap can only be
    # pushed on if the lead can run along a slot the whole way. Both ends are slotted: the cap goes on either way round.
    for (za, zb) in ((zc + MG['L'] / 2 + 0.1, zt1 + 1), (zt0 - 1, zc - MG['L'] / 2 - 0.1)):
        s = s - bx(x0 - 1, xb + 0.2, -4.1, 4.1, za, zb)
    loc = Pos(0, YP, 0); NEON['servo_cap'] = []
    s = neon(s, 'servo_cap', x1 - 1.2, x1 + 0.5, -hw - 0.5, hw + 0.5, zc - NEON_W / 2, zc + NEON_W / 2, loc)
    for dz in (-7.0, 7.0):                 # louvre slits
        s = s - bx(x1 - 0.5, x1 + 1, -3.5, 3.5, zc + dz - 0.5, zc + dz + 0.5)
    return Pos(0, YP, 0) * s


# ------------------------------------------------------------------ 7. desk foot
FOOT_T = 3.0
FOOT_WALL = 7.0


def desk_foot():
    z0, z1 = Z_BOT - FOOT_T, Z_BOT
    yc = (YR + YF) / 2
    hx, hy, c = 52.0, 46.0, 14.0
    oct_ = [(-hx + c, yc - hy), (hx - c, yc - hy), (hx, yc - hy + c), (hx, yc + hy - c),
            (hx - c, yc + hy), (-hx + c, yc + hy), (-hx, yc + hy - c), (-hx, yc - hy + c)]
    s = pz(oct_, z0, z1)
    ring = bx(-HWO - 0.25 - 2.4, HWO + 0.25 + 2.4, YR - 0.25 - 2.4, YF + 0.25 + 2.4, z1 - 0.1, z1 + FOOT_WALL) - \
        bx(-HWO - 0.25, HWO + 0.25, YR - 0.25, YF + 0.25, z1 - 1, z1 + FOOT_WALL + 1)
    s = s + ring
    # the clip rails / plate pass in front: open the front wall between the rails
    s = s - bx(-DOVE_X - 7, DOVE_X + 7, YF, YF + 4, z1 + 0.01, z1 + FOOT_WALL + 1)
    # neon channels on the plate + truss cut-outs
    NEON['desk_foot'] = []
    for sx in (-1, 1):
        s = neon(s, 'desk_foot', sx * 41 - NEON_W / 2, sx * 41 + NEON_W / 2, yc - 28, yc + 28, z1 - NEON_D, z1 + 0.5)
        s = s - pz([(sx * 34.0, yc + 39), (sx * 20.0, yc + 39), (sx * 34.0, yc + 25)], z0 - 1, z1 + 1)
        s = s - pz([(sx * 34.0, yc - 39), (sx * 20.0, yc - 39), (sx * 34.0, yc - 25)], z0 - 1, z1 + 1)
    return s


# ------------------------------------------------------------------ 8. shims
def shim(t):
    s = cz(0, 0, RING_R1 - 0.3, 0, t) - cz(0, 0, MG['horn_hub_d'] / 2 + 0.6, -1, t + 1)
    return Pos(0, YP, Z_TOP + RING_H) * s


# ------------------------------------------------------------------ reference (non printed) bodies
def servo_ref():
    """MG90S in its own frame: shaft axis = Z through the origin, mount plane z = 0, body along +X."""
    p = MG
    body = bx(-p['shaft_off'], p['L'] - p['shaft_off'], -p['W'] / 2, p['W'] / 2, -MG_TAB_TOP, MG_CASE)
    tabs = bx(MG_XC - p['tab_L'] / 2, MG_XC + p['tab_L'] / 2, -p['W'] / 2, p['W'] / 2, -p['tab_t'], 0)
    boss = cz(0, 0, p['boss_d'] / 2, MG_CASE, MG_BOSS) + bx(0, p['boss2_off'], -p['boss2_r'], p['boss2_r'], MG_CASE, MG_BOSS) + \
        cz(p['boss2_off'], 0, p['boss2_r'], MG_CASE, MG_BOSS)
    spl = cz(0, 0, p['spline_d'] / 2, MG_BOSS, MG_TIP)
    horn = bx(-p['horn_L'] / 2, p['horn_L'] / 2, -p['horn_w'] / 2, p['horn_w'] / 2, MG_HORN_ARM0, MG_HORN_FACE) + \
        cz(0, 0, p['horn_hub_d'] / 2, MG_BOSS + 0.3, MG_HORN_FACE)
    return body + tabs + boss + spl, horn


def pan_servo_ref():
    b, h = servo_ref()
    loc = Pos(0, YP, ZM)
    return loc * b, loc * h


def tilt_servo_ref():
    """Shaft along -X (pointing at the head), body hanging down from the tilt axis."""
    b, h = servo_ref()
    # servo +Z -> world -X ; servo +X -> world -Z ; servo +Y -> world +Y  (proper rotation)
    loc = Location(Plane(origin=(ARM_R_OUT, YP, ZA), x_dir=(0, 0, -1), z_dir=(-1, 0, 0)))
    return loc * b, loc * (Rot(0, 0, 0) * h)


def esp32_ref():
    yt = ESP_Y_TOP
    pcb = bx(-ESP_L / 2, ESP_L / 2, yt - 1.6, yt, ESP_ZC - ESP_W / 2, ESP_ZC + ESP_W / 2)
    mod = bx(-ESP_L / 2 + 0.5, -ESP_L / 2 + 26, yt, yt + 3.1, ESP_ZC - 9, ESP_ZC + 9)
    usb = bx(ESP_L / 2 - 5, ESP_L / 2 + 0.7, yt, yt + 2.7, ESP_ZC - 3.9, ESP_ZC + 3.9)
    pins = None
    for sz in (-1, 1):
        r = bx(-23.5, 23.5, yt - 1.6 - (ESP_STACK - 1.6 - 3.1), yt - 1.6, ESP_ZC + sz * 11.43 - 1.27, ESP_ZC + sz * 11.43 + 1.27)
        pins = r if pins is None else pins + r
    return pcb + mod + usb, pins


def espcam_ref():
    """ESP32-CAM in the pod: (board + ESP-32S can + SD slot), camera head, (pin rows + 4 plugged Dupont housings)."""
    yf = CB_Y0 + CB_T
    pcb = bx(-CB_L / 2, CB_L / 2, CB_Y0, yf, CB_Z0, CB_Z1)
    can = bx(-4.0, CB_L / 2 - 0.3, CB_Y0 - 3.6, CB_Y0, CB_LENS_Z - 9.0, CB_LENS_Z + 9.0)
    sd = bx(-CB_L / 2 + 0.3, -5.0, yf, yf + 1.9, CB_LENS_Z - 7.5, CB_LENS_Z + 7.5)
    led = bx(CB_LED[0] - 1.75, CB_LED[0] + 1.75, yf, yf + 1.4, CB_LED[1] - 1.75, CB_LED[1] + 1.75)
    cam = bx(CB_LENS_X - 4.25, CB_LENS_X + 4.25, yf + 1.9, yf + 5.4, CB_LENS_Z - 4.25, CB_LENS_Z + 4.25) + \
        cy(CB_LENS_X, CB_LENS_Z, 3.7, yf + 5.3, yf + 8.4)
    pins = None
    for zr in (CB_Z0 + CB_ROW, CB_Z1 - CB_ROW):
        r = bx(CB_PIN0 - 1.27, PIN_X1 + 1.27, CB_Y0 - 8.5, CB_Y0, zr - 1.27, zr + 1.27)
        pins = r if pins is None else pins + r
    zr = CB_Z0 + CB_ROW
    for i in (0, 3, 5, 6):                                  # 3V3, GND, U0R, U0T
        x = CB_PIN0 + i * 2.54
        pins = pins + bx(x - 1.27, x + 1.27, CB_Y0 - 16.5, CB_Y0 - 2.5, zr - 1.27, zr + 1.27)
    loc = Pos(0, YP, ZA)
    return loc * (pcb + can + sd + led), loc * cam, loc * pins


def webcam_ref():
    """Brio 100 sitting on the fin with its own clip (approximate, for the preview and clearance)."""
    zt = FIN_Z1
    plate = bx(-CLIP_W / 2, CLIP_W / 2, FIN_Y1 - 26.0, FIN_Y1 + 2.0, zt, zt + 3.0)
    lip = bx(-CLIP_W / 2, CLIP_W / 2, FIN_Y1 + 0.1, FIN_Y1 + 2.0, zt - LIP_DROP, zt + 0.1)
    neck = bx(-9, 9, FIN_Y1 - 12.0, FIN_Y1 - 2.0, zt + 2.9, zt + 5.6)
    zb = zt + 5.5
    yb0 = FIN_Y1 - 16.0
    body = bx(-CAM_W / 2 + CAM_H / 2, CAM_W / 2 - CAM_H / 2, yb0, yb0 + CAM_D, zb, zb + CAM_H) + \
        cy(-CAM_W / 2 + CAM_H / 2, zb + CAM_H / 2, CAM_H / 2, yb0, yb0 + CAM_D) + \
        cy(CAM_W / 2 - CAM_H / 2, zb + CAM_H / 2, CAM_H / 2, yb0, yb0 + CAM_D)
    lens = cy(-14.0, zb + CAM_H / 2, 6.5, yb0 + CAM_D - 0.1, yb0 + CAM_D + 0.8)
    # rear flap folded down against the back of the fin
    flap = px([(FIN_Y1 - 26.0, zt + 1.5), (FIN_Y1 - 23.0, zt + 1.5), (FIN_Y0 - 0.2, zt - 30.0), (FIN_Y0 - 3.2, zt - 30.0)], -FLAP_W / 2, FLAP_W / 2)
    loc = Pos(0, YP, ZA)
    return loc * (plate + lip + neck + flap), loc * body, loc * lens


def lid_ref():
    return bx(-110, 110, -LID_T, 0, -150, 0)


PARTS = dict(housing=housing, cover=cover, lid_clip=lid_clip, yoke=yoke, head=head, shroud=shroud, servo_cap=servo_cap, desk_foot=desk_foot)
