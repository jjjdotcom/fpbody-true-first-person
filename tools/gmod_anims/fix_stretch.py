"""Clean up badly stretched triangles at the crotch / hips of a body model.

  python3 -I fix_stretch.py <in.mdl> <out.mdl> [min_stretch]

Half-Life's classic player mesh maps the crotch with two long, thin slivers
of PLAYER_LegBck1: on a body the texture's pixels smear across them in
streaks. Every triangle on the pelvis whose surface is over min_stretch
(default 2) times its texture area gets its texture coordinates moved onto
the darkest small patch of its own texture (the black rubber under-suit), so
it reads as one even colour. The mesh is untouched otherwise.
"""
import struct
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from goldsrc import GoldSrcModel        # noqa: E402
from merge_head import tris, textures   # noqa: E402
from src2w import write_skinned         # noqa: E402


class _Tex:
    def __init__(self, t):
        self.textures = t


def dark_patch(t, k=4):
    w, h = t['w'], t['h']
    pix = np.frombuffer(t['pix'], np.uint8).reshape(h, w)
    pal = np.frombuffer(t['pal'], np.uint8).reshape(256, 3).astype(float)
    lum = pal[pix].sum(2)
    best, at = 1e9, (0, 0)
    for y in range(0, h - k):
        for x in range(0, w - k):
            v = lum[y:y + k, x:x + k].mean()
            if v < best:
                best, at = v, (x, y)
    x, y = at
    return [(x + 1, y + 1), (x + k - 1, y + 1), (x + 1, y + k - 1)]


def main(src, dst, min_stretch=2.0):
    min_stretch = float(min_stretch)
    M = GoldSrcModel(src)
    R, T = M.world(M.rest_local())
    names, parents, tex, T3 = tris(src)
    pelvis = M.bone_by_name['Bip01 Pelvis']
    out, n, patches = [], 0, {}
    for P, N, st, tx, bones in T3:
        if tex[tx]['flags'] & 2 or pelvis not in bones:
            out.append((P, N, st, tx, bones)); continue
        W = np.array([R[b] @ p + T[b] for p, b in zip(P, bones)])
        A = np.linalg.norm(np.cross(W[1] - W[0], W[2] - W[0])) / 2
        U = np.array(st, float); e1, e2 = U[1] - U[0], U[2] - U[0]
        Au = abs(e1[0] * e2[1] - e1[1] * e2[0]) / 2
        if A / (Au + 0.5) > min_stretch:
            if tx not in patches:
                patches[tx] = dark_patch(tex[tx])
            st = patches[tx]
            n += 1
        out.append((P, N, st, tx, bones))
    info = write_skinned(src, out, _Tex(tex), dst)
    print('wrote', dst, '-', n, 'stretched triangles cleaned;', info)


if __name__ == '__main__':
    main(*sys.argv[1:4])
