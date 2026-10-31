"""Add Sven Co-op's third-person reload animations to an fpbody classic player model.

  python3 -I add_sven.py <sven player.mdl> <in.mdl> <out.mdl>

Sven Co-op's player model uses the Half-Life player skeleton (same bone names)
and Half-Life's two pitch blends, so its rotations copy across bone by bone.
Added as sv_ref_reload_<set> / sv_crouch_reload_<set> for the client, which
plays them (or Condition Zero's) when the gun reloads; see cl_fpbody_reloads.
"""
import struct
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from goldsrc import GoldSrcModel                          # noqa: E402
from add_cz import existing_sequences, textures_last      # noqa: E402

SETS = ('mp5', 'shotgun', 'onehanded', 'python', 'bow', 'sniper', 'saw', 'rpg')


def main(sven_path, in_path, out_path):
    S = GoldSrcModel(sven_path)
    M = GoldSrcModel(in_path)
    seqs = existing_sequences(M)
    if any(s['label'].startswith('sv_') for s in seqs):
        seqs = [s for s in seqs if not s['label'].startswith('sv_')]
    base = M.decode(M.seq_by_name['look_idle'])[0][0]
    smap = {M.bone_by_name[b['name']]: i for i, b in enumerate(S.bones) if b['name'] in M.bone_by_name}
    template = next(s for s in seqs if s['label'] == 'ref_aim_mp5')
    added = 0
    for name in SETS:
        for st in ('ref', 'crouch'):
            src = '%s_reload_%s' % (st, name)
            q = S.seqs[S.seq_by_name[src]]
            frames = []
            for arr in S.decode(S.seq_by_name[src]):
                f = np.repeat(base[None], arr.shape[0], axis=0)
                for mi, si in smap.items():
                    f[:, mi, 3:6] = arr[:, si, 3:6]
                frames.append(f)
            raw = bytearray(template['raw'])
            struct.pack_into('<2i', raw, 48, 0, 0)
            struct.pack_into('<2i', raw, 60, 0, 0)
            struct.pack_into('<6i', raw, 152, 0, 0, 0, 0, 0, 0)
            seqs.append(dict(label='sv_' + src, fps=q['fps'], flags=0, activity=0, actweight=0, motiontype=0,
                             motionbone=0, linearmovement=[0, 0, 0], blendtype=q['blendtype'],
                             blendstart=q['blendstart'], blendend=q['blendend'], frames=frames, raw=bytes(raw)))
            added += 1
    M.write(out_path, seqs)
    textures_last(out_path)
    return len(seqs), added


if __name__ == '__main__':
    print(main(*sys.argv[1:4]))
