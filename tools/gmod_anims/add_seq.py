"""Add one animation from another Half-Life model (Biped skeleton) to an fpbody
player model, under a new name.

  python3 -I add_seq.py <src.mdl> <src label> <new label> <in.mdl> <out.mdl> [Bone=Target ...]

For NPC animations the player plays as a move (fm_retina: Barney's "retina",
leaning in to a retinal scanner). The two skeletons' bones point the same way
but their local axes can differ, so each bone takes the source bone's turn in
world space away from a standing reference (the animation's first frame / the
model's look_idle): world(target) = turn * world(target standing).
The Clavicle/UpperArm/Forearm/Thigh/Calf names map to Half-Life's
Arm/Arm1/Arm2/Leg/Leg1, extra fingers to Finger1; more with Bone=Target, e.g.
"Helper=Bip01 Spine2". Bones the source doesn't have keep their standing
local pose. The root moves as in the source from its reference, scaled to the
leg length. If <new label> already exists it is replaced.
The result contains the models' animation data: keep it local.
"""
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from goldsrc import GoldSrcModel, mat_to_euler           # noqa: E402
from srcmdl import euler_to_quat, quat_to_mat            # noqa: E402
from add_cz import existing_sequences, textures_last, clone   # noqa: E402
from compose import target_name                          # noqa: E402


def leg(G, thigh, calf, foot):
    r = G.rest_local()
    return np.linalg.norm(r[G.bone_by_name[calf], :3]) + np.linalg.norm(r[G.bone_by_name[foot], :3])


def main(src_path, src_label, new_label, in_path, out_path, *extra):
    S, M = GoldSrcModel(src_path), GoldSrcModel(in_path)
    more = dict(e.split('=', 1) for e in extra)
    base = M.decode(M.seq_by_name['look_idle'])[0][0].copy()
    smap = {}
    for i, b in enumerate(S.bones):
        t = more.get(b['name']) or target_name(b['name'])
        if t in M.bone_by_name:
            smap[M.bone_by_name[t]] = i
    roots = [i for i, b in enumerate(M.bones) if b['parent'] < 0]
    k = leg(M, 'Bip01 L Leg', 'Bip01 L Leg1', 'Bip01 L Foot') / leg(S, 'Bip01 L Thigh', 'Bip01 L Calf', 'Bip01 L Foot') \
        if 'Bip01 L Calf' in S.bone_by_name else 1.0
    si = S.seq_by_name[src_label]
    src = S.decode(si)[0]
    sref = src[0]                   # the animation's own first frame: standing
    Rs0, Ts0 = S.world(sref)
    Rt0, Tt0 = M.world(base)
    f = np.repeat(base[None], src.shape[0], axis=0)
    for n in range(src.shape[0]):
        Rs, Ts = S.world(src[n])
        Rt = np.zeros_like(Rt0)
        for i, b in enumerate(M.bones):
            p = b['parent']
            ci = smap.get(i)
            if ci is not None:
                Rt[i] = ( Rs[ci] @ Rs0[ci].T ) @ Rt0[i]
                loc = Rt[i] if p < 0 else Rt[p].T @ Rt[i]
                f[n, i, 3:6] = mat_to_euler(loc)
            else:
                r = quat_to_mat(euler_to_quat(*base[i, 3:6]))
                Rt[i] = r if p < 0 else Rt[p] @ r
        for r in roots:
            ci = smap.get(r)
            if ci is not None:
                f[n, r, :3] = base[r, :3] + (Ts[ci] - Ts0[ci]) * k
    seqs = existing_sequences(M)
    by = {s['label']: i for i, s in enumerate(seqs)}
    new = clone(seqs[by['look_idle']], new_label)
    new['frames'] = [f]
    new['fps'] = S.seqs[si]['fps']
    new['flags'] = 0                                    # plays once
    new['blendtype'], new['blendstart'], new['blendend'] = [0, 0], [0, 0], [1.0, 0]
    new['linearmovement'] = [0, 0, 0]
    if new_label in by:
        seqs[by[new_label]] = new
    else:
        seqs.append(new)
    M.write(out_path, seqs)
    textures_last(out_path)
    print('wrote', out_path, new_label, '%d frames at %g fps' % (len(f), new['fps']), 'mapped', len(smap), 'bones')


if __name__ == '__main__':
    main(*sys.argv[1:])
