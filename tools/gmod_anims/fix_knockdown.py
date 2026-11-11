"""fm_knockdown without the half turn.

  python3 -I fix_knockdown.py <in.mdl> <out.mdl> [sequence ...]

The Freeman mod's knockdown (thrown back by a big enemy) spins the body half
way round as it falls and gets up facing backwards: in first person the body
turned away under the camera and the view went "backwards". This takes the
spin out: each frame is turned about the vertical so the hips face the way
they do on the first frame (the fall, the lying and the getting up stay).
Default sequence: fm_knockdown. The result contains the model's data: keep it
local.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goldsrc import GoldSrcModel, mat_to_euler            # noqa: E402
from srcmdl import euler_to_quat, quat_to_mat              # noqa: E402
from add_cz import existing_sequences, textures_last        # noqa: E402
from compact import compact                                 # noqa: E402


def heading(M, f):
    """the way the hips face, as an angle about z (from the left-right hip axis)"""
    _, T = M.world(f)
    T = np.array(T)
    p = T[:, :3, 3] if T.ndim == 3 else T
    l, r = M.bone_by_name['Bip01 L Leg'], M.bone_by_name['Bip01 R Leg']
    a = p[l] - p[r]                     # points left
    return np.arctan2(a[1], a[0]) - np.pi / 2


def rotz(t):
    c, s = np.cos(t), np.sin(t)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def unspin(M, fr):
    fr = fr.copy()
    h = np.unwrap([heading(M, fr[k]) for k in range(len(fr))])
    d = h - h[0]
    # smooth, so a moment where the hips point up doesn't jerk the body round
    if len(d) > 5:
        kern = np.ones(5) / 5
        d = np.convolve(np.pad(d, 2, mode='edge'), kern, mode='valid')
    root = [i for i, b in enumerate(M.bones) if b['parent'] < 0]
    for k in range(len(fr)):
        R = rotz(-d[k])
        for i in root:
            fr[k, i, :3] = R @ fr[k, i, :3]
            m = R @ quat_to_mat(euler_to_quat(*fr[k, i, 3:6]))
            fr[k, i, 3:6] = mat_to_euler(m)
    return fr, np.degrees(d)


def main(src, out, names=('fm_knockdown',)):
    M = GoldSrcModel(src)
    seqs = existing_sequences(M)
    done = []
    for s in seqs:
        if s['label'] in names:
            fr = np.array(s['frames'][0])
            fr2, d = unspin(M, fr)
            s['frames'] = [fr2]
            done.append('%s (turn taken out: %.0f..%.0f deg)' % (s['label'], d.min(), d.max()))
    if not done:
        print('no', names, 'in', src)
        return
    tmp = out + '.tmp'
    M.write(tmp, seqs)
    textures_last(tmp)
    compact(tmp, out)
    os.remove(tmp)
    print('wrote', out, '; '.join(done))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], tuple(sys.argv[3:]) or ('fm_knockdown',))
