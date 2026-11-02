"""Turn a Source (Garry's Mod) weapon world model into a Half-Life one.

  python3 -I src2w.py <source w_model.mdl> <reference GoldSrc w_model.mdl> <out.mdl> [material root ...]

The Source model's triangles (body 0 of every body part, LOD 0) are fitted onto
the reference world model - the one the game uses now - with a uniform scale,
rotation and translation (tried from all 24 orientations of the principal
axes, refined by ICP), so the new model lies where and how the old one did.
It is written with the reference's skeleton and sequences, every vertex on its
first bone, with the Source materials converted to 8-bit textures.
The result contains the Source model's data: keep it local.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from srcmesh import SourceMesh                     # noqa: E402
from hls_body import convert_textures              # noqa: E402
from vm2p import ref_hand_points, sample, fit, write   # noqa: E402
from goldsrc import GoldSrcModel                   # noqa: E402


class _Tex:
    """the texture list vm2p.write expects"""
    def __init__(self, conv):
        self.textures = [dict(name=n.encode('latin-1')[:63], flags=f, w=w, h=h, pix=p, pal=pal)
                         for n, f, w, h, p, pal in conv]


def source_tris(S):
    """-> [(3 verts, 3 normals, 3 (u, v), material)] of body 0 of every body part"""
    out = []
    for mat, tris, bp, m in S.meshes:
        if m != 0:
            continue
        for t in tris:
            V = [S.vertices[i] for i in t]
            out.append((np.array([v['pos'] for v in V], float), np.array([v['normal'] for v in V], float),
                        [tuple(v['uv']) for v in V], mat))
    return out


def convert(src_path, ref_path, out_path, roots=()):
    S = SourceMesh(src_path, list(roots))
    tris = source_tris(S)
    used = sorted({t[3] for t in tris})
    conv = convert_textures(S, skip=set(range(len(S.materials))) - set(used))
    T = _Tex(conv)
    # reference in its first bone's frame (world models: one bone, usually at the origin)
    G, _, rtris = ref_hand_points(ref_path)
    R, Tt = G.world(G.decode(0)[0][0])
    rtris = [(P - Tt[0]) @ R[0] for P in rtris]
    src = sample([t[0] for t in tris])
    ref = sample(rtris)
    err, s, Rm, t = fit(src, ref)
    size = float(np.linalg.norm(ref.max(0) - ref.min(0)))
    out = []
    for P, N, uv, mat in tris:
        w, h = T.textures[mat]['w'], T.textures[mat]['h']
        st = [(int(round(u * w)), int(round(v * h))) for u, v in uv]
        out.append((s * P @ Rm.T + t, N @ Rm.T, st, mat))
    info = write(ref_path, None, out, T, out_path)
    return dict(err=round(err, 3), rel=round(err / size, 4), scale=round(s, 3), size=round(size, 1),
                verts=info[0], tris=info[1], textures=info[2], bytes=info[3])


if __name__ == '__main__':
    print(convert(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]))
