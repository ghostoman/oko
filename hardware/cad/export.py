"""Export print-oriented STLs + STEP, and report overhangs per part."""
import os, sys, json, numpy as np, trimesh
sys.path.insert(0, os.path.dirname(__file__))
from build123d import export_stl, export_step, Rot, Pos, Compound
import ft_parts as F
OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'out'))
for d in ('stl', 'step'): os.makedirs(f'{OUT}/{d}', exist_ok=True)
# print orientation: rotation applied to the world-frame part (then dropped onto z=0)
ORIENT = dict(housing=Rot(-90, 0, 0), cover=Rot(90, 0, 0), lid_clip=Rot(0, 90, 0), yoke=Rot(90, 0, 0), head=Rot(90, 0, 0),
              shroud=Rot(-90, 0, 0), servo_cap=Rot(0, 90, 0), desk_foot=Rot(0, 0, 0))
rep = {}
allp = []
for name, fn in F.PARTS.items():
    w = fn(); allp.append(w)
    export_step(w, f'{OUT}/step/{name}.step')
    s = ORIENT[name] * w
    bb = s.bounding_box(); s = Pos(-(bb.min.X + bb.max.X) / 2, -(bb.min.Y + bb.max.Y) / 2, -bb.min.Z) * s
    export_stl(s, f'{OUT}/stl/{name}.stl', tolerance=0.02, angular_tolerance=0.2)
    m = trimesh.load(f'{OUT}/stl/{name}.stl')
    n = m.face_normals; c = m.triangles_center; a = m.area_faces
    ov = (n[:, 2] < -0.75) & (c[:, 2] > 0.25)
    bins = {}
    for z, ar in zip(np.round(c[ov, 2], 0), a[ov]): bins[z] = bins.get(z, 0) + ar
    top = sorted(bins.items(), key=lambda kv: -kv[1])[:6]
    bed = a[(n[:, 2] < -0.99) & (c[:, 2] < 0.05)].sum()
    rep[name] = dict(size=[round(float(v), 1) for v in m.extents], vol=round(float(m.volume) / 1000, 2), watertight=bool(m.is_watertight),
                     bed_area=round(float(bed)), overhang_mm2=round(float(a[ov].sum())), overhang_by_z=[(float(z), round(float(v))) for z, v in top])
    print(name, rep[name])
for t in (0.2, 0.4, 0.6):
    sh = Pos(0, -F.YP, -(F.Z_TOP + F.RING_H)) * F.shim(t)
    export_stl(sh, f'{OUT}/stl/shim_{int(t*10):02d}.stl', tolerance=0.02, angular_tolerance=0.2)
export_step(Compound(children=allp), f'{OUT}/step/FaceTracker_assembly.step')
json.dump(rep, open(f'{OUT}/parts.json', 'w'), indent=1)
