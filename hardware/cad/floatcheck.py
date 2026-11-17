import sys, trimesh, numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
for name in sys.argv[1:]:
    m=trimesh.load(f'/home/claude/ft/out/stl/{name}.stl'); prev=None; n=0
    for k in range(0,int(m.bounds[1][2]/0.2)):
        z=0.1+k*0.2
        s=m.section(plane_origin=[0,0,z],plane_normal=[0,0,1])
        if s is None: continue
        p2,T=s.to_planar(); cur=[]
        for p in p2.polygons_full:
            f=lambda c:(np.c_[np.array(c),np.zeros(len(c)),np.ones(len(c))]@T.T)[:,:2]
            cur.append(Polygon(f(p.exterior.coords),[f(i.coords) for i in p.interiors]).buffer(0))
        if prev is not None:
            u=unary_union(prev).buffer(0.05)
            for c in cur:
                if c.area>0.2 and c.intersection(u).area<0.02:
                    b=c.bounds; n+=1; print(f'{name}: z={z:.1f} island {c.area:.1f} mm2 x[{b[0]:.1f},{b[2]:.1f}] y[{b[1]:.1f},{b[3]:.1f}]')
        prev=cur
    print(name,'islands:',n)
