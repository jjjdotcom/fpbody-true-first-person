import sys, math, numpy as np
sys.argv = [sys.argv[0], '/tmp', '0'] + sys.argv[1:]
exec(open('/home/claude/gmodconv/eye_sheet.py').read().split("outdir = sys.argv[1]")[0])
import matplotlib.pyplot as plt
H_ = {}; exec(open('/home/claude/gmodconv/holster_sheet.py').read().split("outdir = sys.argv[1]")[0], H_)
E_ = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float)
# wrist targets, world-aligned offsets (x fwd, y left, z up) from the gun's bone, -> stored in bone frame
# the Gluon gun and Displacer keep Half-Life's own hold (no IK); the Tau Cannon uses the shotgun hold
CASES = [('Tau Cannon (MMod)', 'shotgun', '/home/claude/gmodconv/src/mmod_p/p_gauss.mdl', 'Bip01 R Hand', np.eye(3), np.array([16.3, 8.0, 2.5])),
         ('Gluon gun (VAPW)', 'egon', '/home/claude/gmodconv/src/final_p/p_egon.mdl', 'Bip01 R Arm2', E_, np.array([20.8, 8.5, 4.7])),
         ('Displacer', 'egon', '/home/claude/gmodconv/src/final_p/p_displacer.mdl', 'Bip01 R Hand', np.eye(3), np.array([11.0, 10.5, 4.2]))]


def rot_between(a, b):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b)
    v = np.cross(a, b); s = np.linalg.norm(v); c = a @ b
    if s < 1e-9: return np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * ((1 - c) / s ** 2)


def subtree(M, root):
    out = []
    for i in range(len(M.bones)):
        j = i
        while j >= 0:
            if j == root: out.append(i); break
            j = M.bones[j]['parent']
    return out


def reach(M, R, T, tgt):
    B = M.bone_by_name; R = [r.copy() for r in R]; T = [t.copy() for t in T]
    s, e, h = B['Bip01 L Arm1'], B['Bip01 L Arm2'], B['Bip01 L Hand']
    S, E, H = T[s], T[e], T[h]
    a, b = np.linalg.norm(E - S), np.linalg.norm(H - E)
    d = np.clip(np.linalg.norm(tgt - S), abs(a - b) + 0.1, a + b - 0.1)
    # elbow stays in its current bend plane
    n = np.cross(E - S, H - E); n /= np.linalg.norm(n)
    dirt = (tgt - S) / np.linalg.norm(tgt - S)
    ang = math.acos(np.clip((a * a + d * d - b * b) / (2 * a * d), -1, 1))
    perp = np.cross(n, dirt); 
    if perp @ (E - S) < 0: perp = -perp
    E2 = S + a * (math.cos(ang) * dirt + math.sin(ang) * perp)
    for (piv, frm, to, root) in ((S, E - S, E2 - S, s),):
        Rr = rot_between(frm, to)
        for i in subtree(M, root):
            R[i] = Rr @ R[i]; T[i] = Rr @ (T[i] - piv) + piv
    H1 = T[h]; Rr = rot_between(H1 - E2, (S + d * dirt) - E2)
    for i in subtree(M, e):
        R[i] = Rr @ R[i]; T[i] = Rr @ (T[i] - E2) + E2
    return R, T, np.linalg.norm(T[h] - tgt)


if __name__ == '__main__':
    M, btris = load_tris(OUT + '/classic/fpbody_classic.mdl'); hs = head_set(M)
    fig, axes = plt.subplots(3, 3, figsize=(19, 17))
    for row, (nm, ext, gp, bn, Mx, w) in enumerate(CASES):
        R0, T0 = player_pose(M, ext, 0)
        rb = M.bone_by_name[bn]; tgt = R0[rb] @ (Mx.T @ w) + T0[rb]
        R, T, miss = reach(M, R0, T0, tgt)
        print(nm, 'miss %.2f' % miss)
        for col, (lab, RR, TT) in enumerate((('before', R0, T0), ('left hand on handle', R, T))):
            body = [(np.array([RR[b[i]] @ v[i] + TT[b[i]] for i in range(3)]), c) for b, v, c in btris]
            H_['ortho'](axes[row][col], body + merged_weapon(gp, M, RR, TT), np.array([-0.7, 1.0, -0.35]), '%s: %s' % (nm, lab))
            axes[row][col].set_xlim(-25, 30); axes[row][col].set_ylim(-5, 45)
        R2, T2 = player_pose(M, ext, 30); tgt2 = R2[rb] @ (Mx.T @ w) + T2[rb]; R2, T2, _ = reach(M, R2, T2, tgt2)
        body = [(np.array([R2[b[i]] @ v[i] + T2[b[i]] for i in range(3)]), c) for b, v, c in btris if not any(x in hs for x in b)]
        eye = T2[M.bone_by_name['Bip01 Head']] + np.array([4 + 8 * math.sin(math.radians(30)), 0, 3])
        render(axes[row][2], body + merged_weapon(gp, M, R2, T2), eye, 30, 0, nm + ': eye view, 30° down')
    plt.tight_layout(); plt.savefig('/home/claude/gmodconv/eyeview/lefthand.png', dpi=60)
