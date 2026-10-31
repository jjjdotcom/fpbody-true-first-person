"""Left-hand targets for the HD pack's p_ models (g_handles in cl_dll/fpbody_anim.cpp).

  python3 lefthand_hd.py <folder with the HD p_ models> <out.png>

Poses the classic body in each gun's hold, reaches the left wrist to the target
(in the gun bone's space, as the client does), renders it from the left, from
below and from the eyes, and prints how much of the left hand touches the gun.
The HD egon needs its arm bones renamed first (hd_arm_bones.py).
"""
import sys, math, numpy as np
sys.argv = [sys.argv[0], '/tmp', '0'] + sys.argv[1:]
exec(open('/home/claude/hlsdk/tools/gmod_anims/lefthand_sim.py').read().split("if __name__ == '__main__':")[0])
from goldsrc import GoldSrcModel
import matplotlib.pyplot as plt
BODY = OUT + '/czcs/fpbody__fpbody_classic.mdl'
def pose(M, seq, pitch=0):
    s = M.seqs[M.seq_by_name[seq]]; fr = M.decode(M.seq_by_name[seq])
    if s['numblends'] > 1:
        w = np.clip((-pitch - s['blendstart'][0]) / (s['blendend'][0] - s['blendstart'][0]), 0, 1)
        a = fr[0][0] * (1 - w) + fr[1][0] * w
    else: a = fr[0][0].copy()
    g = M.decode(M.seq_by_name['deep_idle'])[0][0]; sp = M.bone_by_name['Bip01 Spine']; a[:sp] = g[:sp]
    return M.world(a)
def run(cases, out):
    M, btris = load_tris(BODY); hs = head_set(M)
    fig, axes = plt.subplots(len(cases), 3, figsize=(19, 6 * len(cases)))
    axes = np.atleast_2d(axes)
    for row, (nm, seq, gp, bn, w) in enumerate(cases):
        R0, T0 = pose(M, seq)
        rb = M.bone_by_name[bn]
        res = [('before', R0, T0)]
        if w is not None:
            tgt = R0[rb] @ np.array(w) + T0[rb]
            R, T, miss = reach(M, R0, T0, tgt); print(nm, 'miss %.2f' % miss); res.append(('IK %s' % (w,), R, T))
        for col, (lab, RR, TT) in enumerate(res):
            body = [(np.array([RR[b[i]] @ v[i] + TT[b[i]] for i in range(3)]), c) for b, v, c in btris]
            H_['ortho'](axes[row][col], body + merged_weapon(gp, M, RR, TT), np.array([-0.3, 1.0, -0.2]), '%s: %s' % (nm, lab))
            axes[row][col].set_xlim(-15, 40); axes[row][col].set_ylim(5, 45)
        RR, TT = res[-1][1], res[-1][2]
        body = [(np.array([RR[b[i]] @ v[i] + TT[b[i]] for i in range(3)]), c) for b, v, c in btris if not any(x in hs for x in b)]
        eye = TT[M.bone_by_name['Bip01 Head']] + np.array([4, 0, 3])
        render(axes[row][2], body + merged_weapon(gp, M, RR, TT), eye, 15, 0, nm + ': eye view')
    plt.tight_layout(); plt.savefig(out, dpi=55)

def run2(cases, out, views=((np.array([-0.3, -1.0, -0.3]), 'left'), (np.array([0.1, 0.3, -1.0]), 'below'))):
    M, btris = load_tris(BODY)
    L = set(i for i in range(len(M.bones)) if M.bones[i]['name'].startswith('Bip01 L Hand') or M.bones[i]['name'].startswith('Bip01 L Finger'))
    fig, axes = plt.subplots(len(cases), len(views) + 1, figsize=(7 * len(views) + 7, 6 * len(cases)))
    axes = np.atleast_2d(axes)
    for row, (nm, seq, gp, bn, w) in enumerate(cases):
        R, T = pose(M, seq); rb = M.bone_by_name[bn]
        if w is not None:
            tgt = R[rb] @ np.array(w) + T[rb]; R, T, miss = reach(M, R, T, tgt); print(nm, w, 'miss %.2f' % miss)
        body = [(np.array([R[b[i]] @ v[i] + T[b[i]] for i in range(3)]), (1, 0, 0) if any(x in L for x in b) else c) for b, v, c in btris]
        g = merged_weapon(gp, M, R, T)
        ctr = T[M.bone_by_name['Bip01 R Hand']]
        for col, (vd, vn) in enumerate(views):
            ax = axes[row][col]
            H_['ortho'](ax, body + g, vd, '%s %s %s' % (nm, w, vn))
            v = vd / np.linalg.norm(vd); upw = np.array([0, 0, 1.0]) if abs(v[2]) < 0.9 else np.array([1.0, 0, 0])
            rt = np.cross(v, H_['up'] if abs(v[2]) < 0.9 else upw); rt /= np.linalg.norm(rt); uv = np.cross(rt, v)
            cx, cy = ctr @ rt, ctr @ uv
            ax.set_xlim(cx - 18, cx + 18); ax.set_ylim(cy - 15, cy + 15)
        hs = head_set(M)
        bodyn = [(np.array([R[b[i]] @ v[i] + T[b[i]] for i in range(3)]), (1, 0, 0) if any(x in L for x in b) else c) for b, v, c in btris if not any(x in hs for x in b)]
        eye = T[M.bone_by_name['Bip01 Head']] + np.array([4, 0, 3])
        render(axes[row][len(views)], bodyn + g, eye, 20, 0, nm + ' eye')
    plt.tight_layout(); plt.savefig(out, dpi=55)

def sample(tris, n=4):
    out = []
    for P, c in tris:
        for i in range(n + 1):
            for j in range(n + 1 - i):
                a, b = i / n, j / n
                out.append(P[0] + a * (P[1] - P[0]) + b * (P[2] - P[0]))
    return np.array(out)

def contact(seq, gp, bn, w, gun_bones=None):
    M, btris = load_tris(BODY)
    L = set(i for i in range(len(M.bones)) if M.bones[i]['name'].startswith('Bip01 L Hand') or M.bones[i]['name'].startswith('Bip01 L Finger'))
    R, T = pose(M, seq); rb = M.bone_by_name[bn]
    miss = 0
    if w is not None:
        tgt = R[rb] @ np.array(w) + T[rb]; R, T, miss = reach(M, R, T, tgt)
    hand = sample([(np.array([R[b[i]] @ v[i] + T[b[i]] for i in range(3)]), c) for b, v, c in btris if all(x in L for x in b)])
    gun = sample(merged_weapon(gp, M, R, T))
    from scipy.spatial import cKDTree
    d, _ = cKDTree(gun).query(hand)
    return miss, d.min(), np.mean(d < 1.0)


if __name__ == '__main__':
    P = sys.argv[-2].rstrip('/') + '/'
    CASES = [('M16', 'cs_ref_aim_rifle', P + 'p_9mmar.mdl', 'Bip01 R Hand', [13.5, 4.5, 3.0]),
             ('Crossbow', 'ref_aim_rifle', P + 'p_crossbow.mdl', 'Bip01 R Hand', [9.5, 4.0, 0.5]),
             ('Pistol', 'ref_aim_onehanded', P + 'p_9mmhandgun.mdl', 'Bip01 R Hand', [3.0, 4.5, -1.0]),
             ('357', 'ref_aim_onehanded', P + 'p_357.mdl', 'Bip01 R Hand', [3.0, 4.5, -1.0]),
             ('Gluon gun (own hold)', 'ref_aim_egon', P + 'p_egon.mdl', 'Bip01 R Arm2', None)]
    for c in CASES:
        print(c[0], 'miss %.2f, closest %.2f, hand on gun %.0f%%' % (lambda r: (r[0], r[1], r[2] * 100))(contact(*c[1:])))
    run2(CASES, sys.argv[-1])
