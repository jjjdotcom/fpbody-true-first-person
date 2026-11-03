"""Move an outfit's hips and thighs back so they don't stick out in front of
the torso (seen when looking down in first person).

  python3 -I shift_hips.py <in.mdl> <out.mdl> <units> [full_top fade_top fade_bottom]

Every vertex on the pelvis or a thigh ("Bip01 Pelvis", "Bip01 L/R Leg") is
moved <units> backwards in look_idle's first frame, the full amount between
the heights fade_bottom..full_top relative to the pelvis joint, fading out
to none at fade_top above it (the waist, where the shirt is) and to none at
the knee below (defaults 2, 9 and the knee height). The skeleton and
everything else is kept. The result contains the model's data: keep it local.
"""
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from goldsrc import GoldSrcModel        # noqa: E402
from merge_head import tris, textures   # noqa: E402
from src2w import write_skinned         # noqa: E402


class _Tex:
    def __init__(self, t):
        self.textures = t


def main(src, dst, units, full_top=2.0, fade_top=9.0, fade_bottom=None):
    units, full_top, fade_top = float(units), float(full_top), float(fade_top)
    G = GoldSrcModel(src)
    R, T = G.world(G.decode(G.seq_by_name['look_idle'])[0][0])
    names, _, texs, tl = tris(src)
    bones = {names.index(n) for n in ('Bip01 Pelvis', 'Bip01 L Leg', 'Bip01 R Leg') if n in names}
    pz = T[names.index('Bip01 Pelvis')][2]
    knee = min(T[names.index(n)][2] for n in ('Bip01 L Leg1', 'Bip01 R Leg1') if n in names) - pz
    fade_bottom = float(fade_bottom) if fade_bottom is not None else knee
    moved = 0
    out = []
    for P, N, st, tx, bs in tl:
        P = P.copy()
        for i, b in enumerate(bs):
            if b not in bones:
                continue
            w = R[b] @ P[i] + T[b]
            z = w[2] - pz
            if z >= full_top:
                k = np.clip((fade_top - z) / max(fade_top - full_top, 1e-3), 0, 1)
            else:
                k = np.clip((z - fade_bottom) / max(-fade_bottom, 1e-3), 0, 1)
            if k > 0:
                w[0] -= units * k
                P[i] = R[b].T @ (w - T[b])
                moved += 1
        out.append((P, N, st, tx, bs))
    info = write_skinned(src, out, _Tex(texs), dst)
    print('wrote', dst, 'moved', moved, 'corners; knee at', round(knee, 1), info)


if __name__ == '__main__':
    main(*sys.argv[1:7])
