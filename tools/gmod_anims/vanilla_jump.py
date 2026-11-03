"""Put Half-Life's own jump animations back into an fpbody player model.

  python3 -I vanilla_jump.py <valve player.mdl> <in.mdl> <out.mdl>

The Garry's Mod-mode models jump with Garry's Mod's jump_smg1 / jump_passive
(arms up holding an SMG, whatever you carry). This copies Half-Life's "jump"
and "long_jump" from the stock player model instead: same Biped skeleton and
bone axes, so each bone takes the stock animation's rotation and keeps the
model's own length; the root moves as in the stock animation, scaled to the
model's leg length. The result contains Valve's animation data: keep it local.
"""
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from goldsrc import GoldSrcModel                       # noqa: E402
from add_cz import existing_sequences, textures_last   # noqa: E402
from add_jobs import leg                               # noqa: E402

LABELS = ('jump', 'long_jump')


def main(src_path, in_path, out_path):
    V, M = GoldSrcModel(src_path), GoldSrcModel(in_path)
    base = M.decode(M.seq_by_name['look_idle'])[0][0].copy()
    vbase = V.decode(V.seq_by_name['look_idle'])[0][0]
    vmap = {M.bone_by_name[b['name']]: i for i, b in enumerate(V.bones) if b['name'] in M.bone_by_name}
    roots = [i for i, b in enumerate(M.bones) if b['parent'] < 0]
    k = leg(M) / leg(V)
    seqs = existing_sequences(M)
    by = {s['label']: i for i, s in enumerate(seqs)}
    for label in LABELS:
        vi = V.seq_by_name[label]
        src = V.decode(vi)[0]
        f = np.repeat(base[None], src.shape[0], axis=0)
        for mi, ci in vmap.items():
            f[:, mi, 3:6] = src[:, ci, 3:6]
        for r in roots:
            ci = vmap[r]
            f[:, r, :3] = base[r, :3] + (src[:, ci, :3] - vbase[ci, :3]) * k
        s = seqs[by[label]]
        s['frames'] = [f]
        s['fps'] = V.seqs[vi]['fps']
        s['blendtype'], s['blendstart'], s['blendend'] = [0, 0], [0, 0], [1.0, 0]
    M.write(out_path, seqs)
    textures_last(out_path)


if __name__ == '__main__':
    main(*sys.argv[1:4])
