"""Add fm_knockdown to an fpbody player model: knocked flat on the back by a
big enemy (zombies, bullsquids, gargantuas ...), a moment on the ground, then
getting back up.

  python3 -I add_knockdown.py <in.mdl> <out.mdl>

It is made from two animations the model already has: Half-Life's own
die_backwards1 (the fall) and fm_standup_back (the Freeman mod's get-up,
add_freeman.py). The get-up was made facing the other way and somewhere else,
so it is turned round and moved to lie where the fall ends; the model holds
the last frame of the fall, then eases into the get-up, which drifts back to
where the player stands so the end meets the normal stance. The client plays
it when the server knocks the player down (FPM_KNOCK, cl_dll/fpbody_anim.cpp).
If fm_knockdown is already there it is replaced; a model without the two
source animations is copied unchanged. The result contains the models'
animation data: keep it local.
"""
import shutil
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from goldsrc import GoldSrcModel, mat_to_euler             # noqa: E402
from srcmdl import euler_to_quat, quat_to_mat              # noqa: E402
from add_cz import existing_sequences, textures_last, clone  # noqa: E402
from compact import compact                                # noqa: E402

LABEL = 'fm_knockdown'
FALL, UP = 'die_backwards1', 'fm_standup_back'
HOLD = 12           # frames lying still after the fall
EASE = 10           # frames easing from the fall's last pose into the get-up's first
FPS = 30.0


def quat(e):
    return np.array(euler_to_quat(*e))


def slerp(a, b, t):
    if np.dot(a, b) < 0:
        b = -b
    d = np.clip(np.dot(a, b), -1, 1)
    if d > 0.9995:
        q = a + t * (b - a)
    else:
        th = np.arccos(d)
        q = (np.sin((1 - t) * th) * a + np.sin(t * th) * b) / np.sin(th)
    return q / np.linalg.norm(q)


def lerp_pose(p, q, t, quat_of):
    out = p.copy()
    out[:, :3] = p[:, :3] + t * (q[:, :3] - p[:, :3])
    for b in range(len(p)):
        out[b, 3:] = mat_to_euler(quat_to_mat(slerp(quat_of(p[b, 3:]), quat_of(q[b, 3:]), t)))
    return out


def main(in_path, out_path):
    M = GoldSrcModel(in_path)
    if FALL not in M.seq_by_name or UP not in M.seq_by_name:
        shutil.copyfile(in_path, out_path)
        print('copied', out_path, '(no', FALL, 'or', UP + ')')
        return
    seqs = [s for s in existing_sequences(M) if s['label'] != LABEL]
    by = {s['label']: s for s in seqs}
    root = [i for i, b in enumerate(M.bones) if b['parent'] < 0][0]
    fall = by[FALL]['frames'][0].copy()
    up = by[UP]['frames'][0].copy()

    # the get-up, turned round (180 degrees about the vertical)
    rz = np.diag([-1.0, -1.0, 1.0])
    for f in range(len(up)):
        up[f, root, :3] = rz @ up[f, root, :3]
        up[f, root, 3:] = mat_to_euler(rz @ quat_to_mat(quat(up[f, root, 3:])))
    # ... lying where the fall ends at its start, standing where the fall started at its end
    start_off = fall[-1, root, :2] - up[0, root, :2]
    end_off = fall[0, root, :2] - up[-1, root, :2]
    n = len(up)
    for f in range(n):
        t = f / max(1, n - 1)
        t = t * t * (3 - 2 * t)
        up[f, root, :2] += (1 - t) * start_off + t * end_off

    frames = list(fall)
    frames += [fall[-1].copy() for _ in range(HOLD)]
    for k in range(1, EASE + 1):
        t = k / (EASE + 1)
        frames.append(lerp_pose(fall[-1], up[0], t * t * (3 - 2 * t), quat))
    frames += list(up)

    s = clone(by[UP], LABEL)
    s['frames'] = [np.array(frames)]
    s['fps'] = FPS
    s['flags'] &= ~1                # plays once
    s['linearmovement'] = [0.0, 0.0, 0.0]
    seqs.append(s)
    tmp = out_path + '.tmp'
    M.write(tmp, seqs)
    textures_last(tmp)
    compact(tmp, out_path)
    import os
    os.remove(tmp)
    print('wrote', out_path, LABEL, len(frames), 'frames, %.2f s' % ((len(frames) - 1) / FPS))


if __name__ == '__main__':
    main(*sys.argv[1:3])
