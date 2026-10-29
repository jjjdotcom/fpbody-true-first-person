"""Quick flat-textured render of a GoldSrc model in a few poses (for checks).

  python3 -I render_mdl.py <model.mdl> <out.png> seq[:frame[:blend]] ...
"""
import struct
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt                    # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402
import numpy as np                                  # noqa: E402

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from goldsrc import GoldSrcModel   # noqa: E402

path, out = sys.argv[1:3]
poses = sys.argv[3:] or ['__rest__']
M = GoldSrcModel(path)
d = M.d

ntex, ti = struct.unpack_from('<2i', d, 180)
nsr, nsf, si = struct.unpack_from('<3i', d, 192)
skins = struct.unpack_from('<%dh' % nsr, d, si)
tex = []
for t in range(ntex):
    o = ti + t * 80
    flags, w, h, idx = struct.unpack_from('<4i', d, o + 64)
    pix = np.frombuffer(bytes(d[idx:idx + w * h]), np.uint8).reshape(h, w)
    pal = np.frombuffer(bytes(d[idx + w * h:idx + w * h + 768]), np.uint8).reshape(256, 3)
    tex.append((w, h, pal[pix]))

tris = []   # (vert indices per model, norm, bone, texture, uv)
nbp, bpi = struct.unpack_from('<2i', d, 204)
for bp in range(nbp):
    nm, _, mi = struct.unpack_from('<3i', d, bpi + bp * 76 + 64)
    mo = mi                             # body 0 -> first model of every part
    nummesh, meshindex, numverts, vinfo, vindex = struct.unpack_from('<5i', d, mo + 72)
    vb = np.frombuffer(bytes(d[vinfo:vinfo + numverts]), np.uint8)
    vv = np.frombuffer(bytes(d[vindex:vindex + numverts * 12]), '<f4').reshape(-1, 3).astype(float)
    for m in range(nummesh):
        numtris, triindex, skinref, _, _ = struct.unpack_from('<5i', d, meshindex + m * 20)
        tx = tex[skins[skinref]] if ntex else None
        o = triindex
        while True:
            c = struct.unpack_from('<h', d, o)[0]; o += 2
            if c == 0:
                break
            fan = c < 0; c = abs(c)
            vs = [struct.unpack_from('<4h', d, o + k * 8) for k in range(c)]; o += c * 8
            for k in range(2, c):
                if fan:
                    a, b, e = vs[0], vs[k - 1], vs[k]
                elif k % 2:
                    a, b, e = vs[k - 1], vs[k - 2], vs[k]
                else:
                    a, b, e = vs[k - 2], vs[k - 1], vs[k]
                col = (0.7, 0.7, 0.7)
                if tx:
                    s = (a[2] + b[2] + e[2]) / 3; t = (a[3] + b[3] + e[3]) / 3
                    col = tx[2][int(np.clip(t, 0, tx[1] - 1)), int(np.clip(s, 0, tx[0] - 1))] / 255.0
                tris.append(((vb, vv), (a[0], b[0], e[0]), col))


def pose_world(spec):
    if spec == '__rest__':
        return M.world(M.rest_local())
    parts = spec.split(':')
    si_ = M.seq_by_name[parts[0]]
    fr = int(parts[1]) if len(parts) > 1 else 0
    bl = int(parts[2]) if len(parts) > 2 else 0
    arr = M.decode(si_)[bl]
    return M.world(arr[min(fr, len(arr) - 1)])


views = [('front', np.array([0, -1, 0])), ('side', np.array([1, 0, 0]))]
fig, axes = plt.subplots(len(poses), 2, figsize=(8, 5 * len(poses)), squeeze=False)
for r, spec in enumerate(poses):
    R, T = pose_world(spec)
    for c, (vname, vdir) in enumerate(views):
        polys, cols, depth = [], [], []
        right = np.cross(vdir, [0, 0, 1])
        for (vb, vv), ids, col in tris:
            P = np.array([R[vb[i]] @ vv[i] + T[vb[i]] for i in ids])
            n = np.cross(P[1] - P[0], P[2] - P[0])
            if np.dot(n, vdir) > 0:
                continue   # back face
            shade = 0.45 + 0.55 * abs(np.dot(n / (np.linalg.norm(n) + 1e-9), vdir))
            polys.append(np.stack([P @ right, P[:, 2]], 1))
            cols.append(np.clip(np.array(col) * shade, 0, 1))
            depth.append(-(P @ vdir).mean())
        order = np.argsort(depth)
        ax = axes[r][c]
        ax.add_collection(PolyCollection([polys[i] for i in order], facecolors=[cols[i] for i in order],
                                         edgecolors='none'))
        ax.set_xlim(-40, 40); ax.set_ylim(-45, 70); ax.set_aspect('equal'); ax.axis('off')
        ax.set_title('%s  %s' % (spec, vname))
plt.tight_layout(); plt.savefig(out, dpi=110)
print('saved', out)
