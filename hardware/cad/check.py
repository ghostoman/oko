"""Collision / clearance report for the FaceTracker assembly."""
import sys, os, math
sys.path.insert(0, os.path.dirname(__file__))
from build123d import Pos, Rot, Location, Axis
import ft_parts as F
from ft_params import *

def tilt(s, deg):   # + = look up
    return Pos(0, YP, ZA) * (Rot(deg, 0, 0) * (Pos(0, -YP, -ZA) * s))
def pan(s, deg):
    return Pos(0, YP, 0) * (Rot(0, 0, deg) * (Pos(0, -YP, 0) * s))
def iv(a, b):
    try:
        c = a & b
        return 0.0 if c is None else round(c.volume, 2)
    except Exception as e:
        return 0.0

P = {k: f() for k, f in F.PARTS.items()}
ps_b, ps_h = F.pan_servo_ref(); ts_b, ts_h = F.tilt_servo_ref()
esp, pins = F.esp32_ref(); ov_pcb, ov_lens, ov_hdr = F.espcam_ref()
wc_clip, wc_body, wc_lens = F.webcam_ref(); lid = F.lid_ref()
R = dict(pan_servo=ps_b, pan_horn=ps_h, tilt_servo=ts_b, tilt_horn=ts_h, esp=esp, esp_pins=pins,
         ov_pcb=ov_pcb, ov_lens=ov_lens, ov_hdr=ov_hdr, wc_clip=wc_clip, wc_body=wc_body, lid=lid)
print('== neutral pose: printed vs printed')
names = [n for n in P if n != 'desk_foot']
for i, a in enumerate(names):
    for b in names[i + 1:]:
        v = iv(P[a], P[b])
        if v > 0.02: print(f'  {a} x {b}: {v} mm3')
print('== neutral pose: printed vs reference bodies')
for a in P:
    for b in R:
        v = iv(P[a], R[b])
        if v > 0.02: print(f'  {a} x {b}: {v} mm3')
print('== refs vs refs')
rn = list(R)
for i, a in enumerate(rn):
    for b in rn[i + 1:]:
        v = iv(R[a], R[b])
        if v > 0.02: print(f'  {a} x {b}: {v} mm3')
print('== desk foot'); 
for a in ('housing', 'cover', 'lid_clip'):
    print('  foot x', a, iv(P['desk_foot'], P[a]))
head_grp = [P['head'], P['shroud'], ov_pcb, ov_lens, ov_hdr, wc_clip, wc_body, ts_h]
yoke_grp = [P['yoke'], ts_b, ps_h, P['servo_cap']]
base_grp = [P['housing'], P['cover'], P['lid_clip'], lid]
print('== tilt sweep (head group vs yoke group and base)')
for t in (-25, -15, 15, 30, 45):
    tot = 0
    for h in head_grp:
        ht = tilt(h, t)
        for y in yoke_grp + base_grp: tot += iv(ht, y)
    print(f'  tilt {t:+d}: {round(tot,2)} mm3')
print('== pan sweep (yoke+head at tilt -25/0/+45 vs base)')
for p in (-90, -60, -30, 30, 60, 90):
    for t in (-25, 45):
        tot = 0
        for y in yoke_grp: 
            yp = pan(y, p)
            for b in base_grp: tot += iv(yp, b)
        for h in head_grp:
            hp = pan(tilt(h, t), p)
            for b in base_grp: tot += iv(hp, b)
        print(f'  pan {p:+d} tilt {t:+d}: {round(tot,2)} mm3')
