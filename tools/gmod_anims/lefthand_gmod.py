"""Left-hand targets for the GMod-mode holds (g_gmHandles in cl_dll/fpbody_anim.cpp).

  python3 lefthand_gmod.py <player.mdl (GMod mode)> <p_ model> <hold ext> <bone> [x0 x1 y0 y1 z0 z1]

Poses the body in ref_aim_<ext> (level aim), and for every wrist target on a
grid in the space of the bone the gun hangs from, reaches the left arm to it
(as the client does) and measures how much of the left hand touches the gun.
Prints the best targets: in front of the right hand, on the barrel / handguard.
"""
import sys
import numpy as np
argv = sys.argv[1:]
sys.argv = [sys.argv[0], '/tmp', '0']
exec(open('/home/claude/hlsdk/tools/gmod_anims/lefthand_sim.py').read().split("if __name__ == '__main__':")[0])
from scipy.spatial import cKDTree


def pose_level(M, seq):
    s = M.seqs[M.seq_by_name[seq]]
    fr = M.decode(M.seq_by_name[seq])
    a = (fr[0][0] + fr[1][0]) * 0.5 if s['numblends'] > 1 else fr[0][0].copy()
    return M.world(a)


def sample(tris, n=3):
    out = []
    for P, c in tris:
        for i in range(n + 1):
            for j in range(n + 1 - i):
                a, b = i / n, j / n
                out.append(P[0] + a * (P[1] - P[0]) + b * (P[2] - P[0]))
    return np.array(out)


def main(body, gun, ext, bone, box):
    M, btris = load_tris(body)
    L = set(i for i in range(len(M.bones)) if M.bones[i]['name'].startswith(('Bip01 L Hand', 'Bip01 L Finger')))
    R0, T0 = pose_level(M, 'ref_aim_' + ext)
    rb = M.bone_by_name[bone]
    gpts = sample(merged_weapon(gun, M, R0, T0))
    tree = cKDTree(gpts)
    hand_tris = [(b, v) for b, v, c in btris if all(x in L for x in b)]
    # gun extent along the bone's x (barrel)
    loc = (gpts - T0[rb]) @ R0[rb]
    x0, x1, y0, y1, z0, z1 = box or (4, float(loc[:, 0].max()) - 3, -4, 14, -8, 10)
    res = []
    for x in np.arange(x0, x1, 1.5):
        for y in np.arange(y0, y1, 0.75):
            for z in np.arange(z0, z1, 1.5):
                # the wrist outside the gun's left side at that point along it, so the
                # hand wraps the barrel / handguard instead of sinking into it
                sl = loc[np.abs(loc[:, 0] - x) < 1.5]
                if len(sl) == 0 or y < sl[:, 1].max() + 1.0 or y > sl[:, 1].max() + 3.5 or \
                        z < sl[:, 2].min() - 1.0 or z > sl[:, 2].max():
                    continue
                tgt = R0[rb] @ np.array([x, y, z]) + T0[rb]
                R, T, miss = reach(M, R0, T0, tgt)
                if miss > 0.5:
                    continue
                hp = sample([(np.array([R[b[i]] @ v[i] + T[b[i]] for i in range(3)]), None) for b, v in hand_tris], 2)
                d, _ = tree.query(hp)
                inside = np.mean(d < 1.2)
                res.append((inside, -d.min(), x, y, z))
    # prefer a hold well out along the gun (the barrel / handguard) among the good ones
    best = max(r[0] for r in res) if res else 0
    res = [r for r in res if r[0] >= best - 0.08]
    res.sort(key=lambda r: (-r[2], -r[0]))
    for r in res[:6]:
        print('contact %3.0f%%  min %.2f  wrist (%.1f, %.1f, %.1f)' % (r[0] * 100, -r[1], r[2], r[3], r[4]))
    return res[0] if res else None


if __name__ == '__main__':
    box = tuple(float(v) for v in argv[4:10]) if len(argv) >= 10 else None
    main(argv[0], argv[1], argv[2], argv[3], box)
