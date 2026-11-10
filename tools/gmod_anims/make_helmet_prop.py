"""The helmet alone, as a prop the hands carry while fp_helmet puts it on or
takes it off (models/fpbody_helmet_prop.mdl, drawn by the client:
FPAnim_HelmetProp in cl_dll/fpbody_anim.cpp).

  python3 -I make_helmet_prop.py <suit_helmet.mdl> <ref.mdl> <out.mdl>

<suit_helmet.mdl> is a make_helmet.py model: its helmet (every triangle with a
corner on the head, collar included, in that game's colours) is cut out,
posed as in its idle, put in the head bone's space and centred
on the helmet, so the prop's origin is the middle of the helmet and its axes
are the head's: the client draws it with the head's turn at the hands. <ref.mdl>
lends the file its bone and sequence (any p_ model: everything is on its first
bone, pre-turned against that bone's pose). The result contains the models'
data: keep it local.
"""
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from goldsrc import GoldSrcModel                  # noqa: E402
from merge_head import tris, head_set, _Tex       # noqa: E402
from src2w import write_skinned                   # noqa: E402


def pose(path):
    M = GoldSrcModel(path)
    sq = M.seq_by_name.get('idle') or list(M.seq_by_name.values())[0]
    fr = M.decode(sq)
    return M.world(fr[0][0])


def main(src, ref, out):
    names, parents, tex, tl = tris(src)
    hs = head_set(names, parents)
    R, T = pose(src)
    hb = names.index('Bip01 Head')
    Rh, Th = R[hb], T[hb]
    sel = [t for t in tl if any(b in hs for b in t[4])]
    pts = []
    res = []
    for P, N, st, tx, bones in sel:
        W = np.array([R[b] @ p + T[b] for p, b in zip(P, bones)])
        WN = np.array([R[b] @ n for n, b in zip(N, bones)])
        H = (W - Th) @ Rh                   # head space: Rh^T (w - Th)
        HN = WN @ Rh
        pts.extend(H)
        res.append([H, HN, st, tx])
    c = (np.min(pts, 0) + np.max(pts, 0)) / 2
    R0, T0 = pose(ref)
    out_t = []
    for H, HN, st, tx in res:
        L = ((H - c) - T0[0]) @ R0[0]       # against the ref's bone 0
        LN = HN @ R0[0]
        out_t.append((L, LN, st, tx, [0, 0, 0]))
    used = sorted({t[3] for t in out_t})
    idx = {k: i for i, k in enumerate(used)}
    out_t = [(P, N, st, idx[t], b) for P, N, st, t, b in out_t]
    info = write_skinned(ref, out_t, _Tex([tex[k] for k in used]), out)
    print('wrote', out, len(out_t), 'triangles; helmet centre in head space', np.round(c, 2), info)


if __name__ == '__main__':
    main(*sys.argv[1:4])
