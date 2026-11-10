"""Replace an fpbody player model's standing idle with a Garry's Mod idle pack's
(e.g. [xdR] idle Re-animation2 (female), Workshop 3270357830:
models/xdreanims/f_anm_slot_019.mdl + .ani, sequence idle_all_01): the women
of fpbody_decay stand like women.

  python3 -I add_idle.py <in.mdl> <out.mdl> <pack.mdl> <m_anm_gmod.mdl> [labels]

A model without the full player skeleton (the companion, fpbody_colette.mdl:
no fingers or toes, its origin at the feet) gets the bones it has, e.g.
labels idle1,idle2,idle3,idle4.

<labels> (comma-separated, default ref_aim_unarmed,ref_shoot_unarmed,look_idle,idle)
are the sequences that get the idle: each keeps its name, activity, flags and
events; only its frames and frame rate change. The animation is retargeted
(retarget.py) against the Garry's Mod player's rest pose like add_freeman.py's.
The result contains the pack's animation data: keep it local.
"""
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from srcmdl import SourceModel                              # noqa: E402
from goldsrc import GoldSrcModel                            # noqa: E402
from add_cz import existing_sequences, textures_last         # noqa: E402
from add_freeman import PackRetargeter, source_anim, STAND  # noqa: E402
import retarget                                             # noqa: E402

DEFAULT = 'ref_aim_unarmed,ref_shoot_unarmed,look_idle,idle'


def partial_retargeter(g, M, ref):
    """PackRetargeter onto a skeleton without fingers or toes (the companion):
    only the bones it has, feet for the height, the origin at the feet."""
    keep = [(tn, sn) for tn, sn in retarget.MAP if tn in M.bone_by_name]
    dirs = {k: v for k, v in retarget.DIR_CHILD.items() if k in M.bone_by_name and v in M.bone_by_name}
    old = retarget.MAP, retarget.DIR_CHILD
    toe = {}
    for s in 'LR':
        if 'Bip01 %s Toe0' % s not in M.bone_by_name:
            toe['Bip01 %s Toe0' % s] = M.bone_by_name['Bip01 %s Foot' % s]
    M.bone_by_name.update(toe)
    retarget.MAP, retarget.DIR_CHILD = keep, dirs
    import add_freeman
    add_freeman.retarget.MAP, add_freeman.retarget.DIR_CHILD = keep, dirs
    try:
        rt = PackRetargeter(g, M, ref)
    finally:
        retarget.MAP, retarget.DIR_CHILD = old
        for k in toe:
            del M.bone_by_name[k]
    # height scale: pelvis above the feet on both
    vb = retarget.VB
    Rr, Tr = ref.world(np.array([b['pos'] for b in ref.bones]), np.array([b['quat'] for b in ref.bones]))
    tp = rt.Tt0[M.bone_by_name['Bip01 Pelvis']][2] - rt.Tt0[M.bone_by_name['Bip01 L Foot']][2]
    sp = Tr[ref.bone_by_name[vb + 'Pelvis']][2] - Tr[ref.bone_by_name[vb + 'L_Foot']][2]
    rt.scale = tp / sp
    return rt


def main(in_path, out_path, pack, gmod, labels=DEFAULT):
    M = GoldSrcModel(in_path)
    seqs = existing_sequences(M)
    ref = SourceModel(gmod, gmod[:-4].replace('_gmod', '') + '.ani')
    g = SourceModel(pack, pack[:-4] + '.ani')
    full = all(tn in M.bone_by_name for tn, _ in retarget.MAP)
    rt = PackRetargeter(g, M, ref) if full else partial_retargeter(g, M, ref)
    a = source_anim(g, 'idle_all_01' if 'idle_all_01' in g.seq_by_name else list(g.seq_by_name)[0])
    fr = rt.frames(g.frames(a), STAND if full else 0.0)
    want = labels.split(',')
    done = []
    for s in seqs:
        if s['label'] in want:
            s['frames'] = [fr.copy()]
            s['fps'] = float(a['fps'])
            s['linearmovement'] = [0, 0, 0]
            done.append(s['label'])
    import os
    from compact import compact
    tmp = out_path + '.tmp'
    M.write(tmp, seqs)
    textures_last(tmp)
    compact(tmp, out_path)
    os.remove(tmp)
    print('wrote', out_path, '- idle in', done, len(fr), 'frames at', a['fps'], 'fps')


if __name__ == '__main__':
    main(*sys.argv[1:6])
