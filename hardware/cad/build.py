"""Build all parts, validate, export world-frame STLs (for preview/checks)."""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(__file__))
from build123d import export_stl, export_step
import ft_parts as F
OUT = os.path.join(os.path.dirname(__file__), '..', 'out')
os.makedirs(OUT + '/world', exist_ok=True)
only = sys.argv[1:]
info = {}
shapes = {}
for name, fn in F.PARTS.items():
    if only and name not in only: continue
    t = time.time(); s = fn(); shapes[name] = s
    bb = s.bounding_box()
    info[name] = dict(valid=bool(s.is_valid), vol=round(s.volume / 1000, 2), solids=len(s.solids()),
                      bb=[round(v, 2) for v in (bb.min.X, bb.max.X, bb.min.Y, bb.max.Y, bb.min.Z, bb.max.Z)])
    export_stl(s, f'{OUT}/world/{name}.stl', tolerance=0.03, angular_tolerance=0.25)
    print(f'{name:10s} valid={info[name]["valid"]} solids={info[name]["solids"]} vol={info[name]["vol"]}cm3 bb={info[name]["bb"]} {time.time()-t:.1f}s')
