"""Put the HD pack's HEV gloves (from a view model) on an fpbody body.

  python3 -I hd_hands.py <HD v_ model> <body.mdl> <out.mdl> [size]

size (default 1.2) scales the gloves on top of the hand-length match (the
view model's hands are slimmer than the bodies' forearms).

The body's own hand triangles (two or more corners on a hand or finger bone)
are dropped. The view model's glove triangles (the hand and finger bones, the
glove textures; not the gun or the sleeves) are placed on the body's hands:
each corner is taken relative to the view model's hand in its rest pose,
scaled by the hand lengths, and put on the body's matching bone. The view
model has five finger chains and the player skeleton two (thumb, fingers),
so fingers 1-4 all ride on the body's Finger1 chain. The result contains the
models' data: keep it local.
"""
import struct
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from goldsrc import GoldSrcModel        # noqa: E402
from merge_head import tris, textures   # noqa: E402
from src2w import write_skinned         # noqa: E402

GLOVE_TEX = ('rubberglove', 'gordon_glove', 'glove', 'hand')


def is_hand(name):
    return ' Hand' in name or ' Finger' in name


def target_bone(name):
    """view-model bone name -> player bone name"""
    if name.endswith(' Hand'):
        return name
    side = name[len('Bip01 '):len('Bip01 ') + 1]
    k = name.split('Finger')[1]           # '0', '01', '2', '21' ...
    chain, joint = k[0], k[1:]
    return 'Bip01 %s Finger%s%s' % (side, '0' if chain == '0' else '1', joint)


def hand_len(G, side):
    r = G.rest_local()
    b = G.bone_by_name['Bip01 %s Finger1' % side]
    return np.linalg.norm(r[b, :3])


class _Tex:
    def __init__(self, t):
        self.textures = t


def main(v_path, body_path, out_path, size=1.2):
    size = float(size)
    V, B = GoldSrcModel(v_path), GoldSrcModel(body_path)
    Rv, Tv = V.world(V.rest_local())
    Rb, Tb = B.world(B.rest_local())
    vn, _, vtex, vtris = tris(v_path)
    bn, bpar, btex, btris = tris(body_path)
    bh = {i for i, n in enumerate(bn) if is_hand(n)}
    keep = [t for t in btris if sum(1 for b in t[4] if b in bh) < 2]

    add = []
    for P, N, st, tx, bones in vtris:
        names = [vn[b] for b in bones]
        tname = vtex[tx]['name'].decode('latin-1').lower()
        if not all(is_hand(n) for n in names) or not any(g in tname for g in GLOVE_TEX):
            continue
        side = names[0][len('Bip01 ')]
        vh, mh = V.bone_by_name['Bip01 %s Hand' % side], B.bone_by_name['Bip01 %s Hand' % side]
        s = hand_len(B, side) / hand_len(V, side) * size
        newP, newN, newB = [], [], []
        for p, n, b, name in zip(P, N, bones, names):
            w = Rv[b] @ p + Tv[b]                         # view model, world
            hl = Rv[vh].T @ (w - Tv[vh]) * s               # relative to its hand
            wb = Rb[mh] @ hl + Tb[mh]                      # onto the body's hand
            tb = B.bone_by_name[target_bone(name)]
            newP.append(Rb[tb].T @ (wb - Tb[tb]))
            nw = Rb[mh] @ (Rv[vh].T @ (Rv[b] @ n))
            newN.append(Rb[tb].T @ nw)
            newB.append(tb)
        add.append((np.array(newP), np.array(newN), st, tx + len(btex), newB))

    alltex = btex + vtex
    used = sorted({t[3] for t in keep + add})
    idx = {k: i for i, k in enumerate(used)}
    out = [(P, N, st, idx[tx], bones) for P, N, st, tx, bones in keep + add]
    info = write_skinned(body_path, out, _Tex([alltex[k] for k in used]), out_path)
    print('wrote', out_path, 'dropped', len(btris) - len(keep), 'hand triangles, added', len(add), 'glove triangles;', info)


if __name__ == '__main__':
    main(*sys.argv[1:5])
