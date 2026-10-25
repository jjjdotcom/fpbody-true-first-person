"""Measure Half-Life p_ weapon models in the right-hand bone's frame:
barrel axis (principal axis of the gun mesh), centre line point, front/back
extent, and attachments. Output feeds the client's aim/off-hand IK table."""
import struct, sys, glob, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goldsrc import GoldSrcModel

def cstr(b): return b.split(b'\0')[0].decode('latin-1')

def analyse(path):
    m = GoldSrcModel(path)
    d = bytes(m.d)
    numbp, bpi, numatt, atti = struct.unpack_from('<4i', d, 204)
    fr = m.decode(0)[0][0]
    R, T = m.world(fr)
    if 'Bip01 R Hand' not in m.bone_by_name:
        return None
    hi = m.bone_by_name['Bip01 R Hand']
    # bones in the hand's subtree
    sub = {hi}
    for i, b in enumerate(m.bones):
        if b['parent'] in sub: sub.add(i)
    pts = []
    for p in range(numbp):
        o = bpi + p * 76
        nummodels, base, modelindex = struct.unpack_from('<3i', d, o + 64)
        for k in range(nummodels):
            mo = modelindex + k * 112
            numverts, vinfo, vidx = struct.unpack_from('<3i', d, mo + 64 + 16)
            bones = d[vinfo:vinfo + numverts]
            for v in range(numverts):
                b = bones[v]
                if b in sub:
                    pv = np.array(struct.unpack_from('<3f', d, vidx + v * 12))
                    w = R[b] @ pv + T[b]
                    pts.append(R[hi].T @ (w - T[hi]))     # into hand-local space
    atts = []
    for a in range(numatt):
        o = atti + a * 88
        bone = struct.unpack_from('<i', d, o + 36)[0]
        org = np.array(struct.unpack_from('<3f', d, o + 40))
        w = R[bone] @ org + T[bone]
        atts.append(R[hi].T @ (w - T[hi]))
    pts = np.array(pts)
    if len(pts) < 4:
        return None
    c = pts.mean(axis=0)
    u, s, vt = np.linalg.svd(pts - c)
    axis = vt[0]
    proj = (pts - c) @ axis
    # point the axis toward the muzzle: the end farther from the hand origin
    if abs(proj.max()) < abs(proj.min()):
        axis = -axis; proj = -proj
    # where the hand origin projects on the axis
    hand_t = (-c) @ axis
    return dict(axis=axis.round(4).tolist(), center=c.round(2).tolist(), front=float(proj.max().round(2)),
                back=float(proj.min().round(2)), hand_t=round(float(hand_t), 2), npts=len(pts),
                sv=(s[:3] / np.sqrt(len(pts))).round(2).tolist(), atts=[a.round(2).tolist() for a in atts])

res = {}
for p in sorted(glob.glob(sys.argv[1] + '/p_*.mdl')):
    r = analyse(p)
    name = os.path.basename(p).lower()
    res[name] = r
    if r:
        print(f"{name:20s} axis={r['axis']} centre={r['center']} front={r['front']} back={r['back']} hand_t={r['hand_t']} sv={r['sv']} n={r['npts']} atts={r['atts']}")
    else:
        print(name, 'no hand geometry')
json.dump(res, open('out/weapons.json', 'w'), indent=1)
