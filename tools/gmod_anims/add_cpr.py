"""Half-Life's CPR scene (a scientist reviving a security guard) on fpbody's
models, for the downed / revive mechanic (dlls/fpbody_buddy.inl).

  python3 -I add_cpr.py player <scientist.mdl> <barney.mdl> <in.mdl> <out.mdl>
  python3 -I add_cpr.py buddy  <scientist.mdl> <barney.mdl> <in.mdl> <out.mdl>

player: fm_down     the guard on his back, being revived (cprbarney, looping)
        fm_down_up  the guard getting up (cprbarneyrevive)
        fm_cpr      the scientist giving CPR (cprscientist, looping)
        fm_cpr_up   the scientist helping him up after (cprscientistrevive)
buddy:  cprscientist, cprscientistrevive  (the companion already has the guard's cprbarney /
        cprbarneyrevive: he's a Barney)
Half-Life's Biped and fpbody's share the bone axes (see vanilla_jump.py): each
bone takes the stock animation's rotation and keeps the model's length; the
root moves as in the stock animation (from its standing idle), scaled to the
model's legs. The scientist's Bip02 is read as Bip01. The result contains
Valve's animation data: keep it local.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goldsrc import GoldSrcModel                            # noqa: E402
from add_cz import existing_sequences, textures_last         # noqa: E402
from add_freeman import make_seq                             # noqa: E402
from compact import compact                                  # noqa: E402

LOOP = 1   # STUDIO_LOOPING


def bname(n):
    return n.replace('Bip02', 'Bip01')


def leg(M):
    by = {bname(b['name']): i for i, b in enumerate(M.bones)}
    _, T = M.world(M.rest_local())
    T = np.array(T)
    p = T[:, :3, 3] if T.ndim == 3 else T
    return abs(p[by['Bip01 Pelvis']][2] - p[by['Bip01 L Foot']][2])


def idle_frame(M, names):
    for n in names:
        if n in M.seq_by_name:
            return M.decode(M.seq_by_name[n])[0][0]
    return M.decode(0)[0][0]


# the old Biped's names (Half-Life's) -> the newer Biped's (the HD companion)
NEWER = {' L Leg': ' L Thigh', ' R Leg': ' R Thigh', ' L Leg1': ' L Calf', ' R Leg1': ' R Calf',
         ' L Arm': ' L Clavicle', ' R Arm': ' R Clavicle', ' L Arm1': ' L UpperArm', ' R Arm1': ' R UpperArm',
         ' L Arm2': ' L Forearm', ' R Arm2': ' R Forearm'}


def retarget(V, label, M, base, vbase, drift=True):
    """V's sequence `label` on M's skeleton (drift False: the root stays where
    it starts across the floor, it only goes up and down)"""
    vmap = {}
    for ci, b in enumerate(V.bones):
        n = bname(b['name'])
        if n not in M.bone_by_name:
            for old, new in NEWER.items():
                if n.endswith(old):
                    n = n[:-len(old)] + new
                    break
        if n in M.bone_by_name:
            vmap[M.bone_by_name[n]] = ci
    roots = [i for i, b in enumerate(M.bones) if b['parent'] < 0]
    k = leg(M) / leg(V)
    vi = V.seq_by_name[label]
    src = V.decode(vi)[0]
    f = np.repeat(base[None], src.shape[0], axis=0)
    for mi, ci in vmap.items():
        f[:, mi, 3:6] = src[:, ci, 3:6]
    for r in roots:
        ci = vmap.get(r, 0)
        f[:, r, :3] = base[r, :3] + ( src[:, ci, :3] - vbase[ci, :3] ) * k
        if not drift:
            f[:, r, :2] = f[0, r, :2]
    return f, float(V.seqs[vi]['fps'])


def main(kind, sci, bar, in_path, out_path):
    S, B, M = GoldSrcModel(sci), GoldSrcModel(bar), GoldSrcModel(in_path)
    seqs = existing_sequences(M)
    names = [s['label'] for s in seqs]
    if kind == 'player':
        base = idle_frame(M, ['look_idle', 'idle'])
        want = [('fm_down', B, 'cprbarney', True), ('fm_down_up', B, 'cprbarneyrevive', False),
                ('fm_cpr', S, 'cprscientist', True), ('fm_cpr_up', S, 'cprscientistrevive', False)]
        template = seqs[names.index('look_idle')] if 'look_idle' in names else seqs[0]
    else:
        base = idle_frame(M, ['idle1', 'idle'])
        want = [('cprscientist', S, 'cprscientist', True), ('cprscientistrevive', S, 'cprscientistrevive', False)]
        template = seqs[names.index('cprbarney')] if 'cprbarney' in names else seqs[0]
    seqs[:] = [s for s in seqs if s['label'] not in [w[0] for w in want]]
    for label, V, src, loop in want:
        vbase = idle_frame(V, ['idle1', 'idle'])
        # helping him up, the scientist walks round to the guard's head: kept
        # in place here (the game doesn't move the body's origin with it)
        f, fps = retarget(V, src, M, base, vbase, drift=(src != 'cprscientistrevive'))
        s = make_seq(label, f, fps, loop, template)
        s['activity'] = 0
        s['actweight'] = 0
        seqs.append(s)
    tmp = out_path + '.tmp'
    M.write(tmp, seqs)
    textures_last(tmp)
    compact(tmp, out_path)
    os.remove(tmp)
    print('wrote', out_path, [w[0] for w in want])


if __name__ == '__main__':
    main(*sys.argv[1:6])
