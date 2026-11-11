"""Garry's Mod's own jumps on an fpbody GMod-mode player model.

  python3 -I add_jumps.py <in.mdl> <out.mdl> <m_anm_gmod.mdl> [--base <fpbody model.mdl>]

Garry's Mod jumps with jump_<hold type>: the same leap, the arms as the
weapon is held (jump_smg1, jump_shotgun, ...; empty hands - the "normal" hold -
jump_slam). This puts them in the model:

  jump, long_jump      Garry's Mod's jump_slam (what you see with no weapon,
                       and in third person / other games' views)
  gm_jump_<hold>       slam melee knife revolver pistol shotgun smg1 ar2 rpg
                       grenade crossbow physgun: the client plays the one for
                       the weapon in your hands while you are in the air
                       (cl_dll/fpbody_anim.cpp, FPAnim_SwimHold)

--base: for a model made with hls_body.py --own-skeleton (Decay's women), the
skeleton it was made from (see add_idle.py). The result contains Valve's
animation data: keep it local.
"""
import os
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from srcmdl import SourceModel                              # noqa: E402
from goldsrc import GoldSrcModel                            # noqa: E402
from add_cz import existing_sequences, textures_last         # noqa: E402
from add_freeman import PackRetargeter, source_anim, STAND, make_seq  # noqa: E402
from compact import compact                                 # noqa: E402

HOLDS = ('slam', 'melee', 'knife', 'revolver', 'pistol', 'shotgun', 'smg1', 'ar2', 'rpg', 'grenade',
         'crossbow', 'physgun')


def own_joints(M, B, rt, fr):
    """frames retargeted onto base B, with model M's joints (add_idle.py --base)"""
    rest = M.rest_local()
    mapped = [i for i in rt.src_of if M.bones[i]['parent'] in rt.src_of]
    fr[:, mapped, :3] = rest[mapped, :3]
    _, Tm = M.world(rest)
    _, Tb = B.world(B.rest_local())
    pel, ft = M.bone_by_name['Bip01 Pelvis'], M.bone_by_name['Bip01 L Foot']
    k = (Tm[pel][2] - Tm[ft][2]) / (Tb[pel][2] - Tb[ft][2])
    r = fr[:, rt.root, :3]
    r[:, 2] -= STAND
    r *= k
    r[:, 2] += STAND
    fr[:, rt.root, :3] = r
    return fr


def main(in_path, out_path, gmod, base=None):
    M = GoldSrcModel(in_path)
    seqs = existing_sequences(M)
    g = SourceModel(gmod, gmod[:-4].replace('_gmod', '') + '.ani')
    B = GoldSrcModel(base) if base else M
    rt = PackRetargeter(g, B, g)
    made = {}
    for h in HOLDS:
        a = source_anim(g, 'jump_' + h)
        fr = rt.frames(g.frames(a), STAND)
        if base:
            fr = own_joints(M, B, rt, fr)
        made[h] = (fr, float(a['fps']))
    template = next(s for s in seqs if s['label'] == 'look_idle')
    seqs[:] = [s for s in seqs if not s['label'].startswith('gm_jump_')]
    for s in seqs:
        if s['label'] in ('jump', 'long_jump'):
            fr, fps = made['slam']
            s['frames'] = [fr.copy()]
            s['fps'] = fps
            s['motiontype'] = 0
            s['linearmovement'] = [0, 0, 0]
    for h in HOLDS:
        fr, fps = made[h]
        seqs.append(make_seq('gm_jump_' + h, fr, fps, False, template))
    tmp = out_path + '.tmp'
    M.write(tmp, seqs)
    textures_last(tmp)
    compact(tmp, out_path)
    os.remove(tmp)
    print('wrote', out_path, os.path.getsize(out_path))


if __name__ == '__main__':
    args = sys.argv[1:]
    base = None
    if '--base' in args:
        k = args.index('--base'); base = args[k + 1]; del args[k:k + 2]
    main(*args[:3], base=base)
