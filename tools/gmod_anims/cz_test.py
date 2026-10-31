import sys, math, numpy as np
sys.argv = ['x', '/tmp', '0']
exec(open('/home/claude/gmodconv/eye_sheet.py').read().split("outdir = sys.argv[1]")[0])
import matplotlib.pyplot as plt
H_ = {}; exec(open('/home/claude/gmodconv/holster_sheet.py').read().split("outdir = sys.argv[1]")[0], H_)
from compose import target_name
from goldsrc import GoldSrcModel
CZ = '/mnt/user-data/uploads/Half-Life/czero/models/player/gsg9/gsg9.mdl'
C, ctris = load_tris(CZ)
M, btris = load_tris(OUT + '/classic/fpbody_classic.mdl')
rest = M.decode(M.seq_by_name['look_idle'])[0][0].copy()
cmap = {}
for i, b in enumerate(C.bones):
    t = target_name(b['name'])
    if t in M.bone_by_name: cmap[M.bone_by_name[t]] = i
hC = C.world(C.decode(C.seq_by_name['idle1'])[0][0])[1][C.bone_by_name['Bip01 Head']][2] - C.world(C.decode(C.seq_by_name['idle1'])[0][0])[1][C.bone_by_name['Bip01 Pelvis']][2]
R0, T0 = M.world(rest); hM = T0[M.bone_by_name['Bip01 Head']][2] - T0[M.bone_by_name['Bip01 Pelvis']][2]
scale = hM / hC


def cz_local(seq, frame=0, blend=None):
    fr = C.decode(C.seq_by_name[seq])
    if blend is None: return fr[0][frame]
    nb = len(fr); w = blend * (nb - 1); i = int(min(w, nb - 2)); t = w - i
    return fr[i][frame] * (1 - t) + fr[i + 1][frame] * t


def retarget(cl):
    a = rest.copy()
    for mi, ci in cmap.items():
        a[mi][3:6] = cl[ci][3:6]                 # rotation from Condition Zero
        if M.bones[mi]['parent'] < 0 or M.bones[mi]['name'] == 'Bip01':
            a[mi][0:3] = cl[ci][0:3] * scale     # root motion, scaled to the height
    return a


def draw(ax, model, tris, a, gun, title, view=np.array([-1.0, 0.9, -0.15])):
    R, T = model.world(a)
    body = [(np.array([R[b[i]] @ v[i] + T[b[i]] for i in range(3)]), c) for b, v, c in tris]
    if gun: body += merged_weapon(gun, model, R, T)
    H_['ortho'](ax, body, view, title); ax.set_xlim(-30, 30); ax.set_ylim(-40, 45)


if __name__ == '__main__':
    gun = '/home/claude/gmodconv/src/final_p/p_9mmar.mdl'
    shots = [('ref_aim_mp5', 0, 0.5, 'aim'), ('ref_shoot_mp5', 2, 0.5, 'fire'),
             ('ref_reload_mp5', 8, None, 'reload'), ('ref_reload_mp5', 22, None, 'reload'), ('ref_reload_mp5', 36, None, 'reload')]
    fig, axes = plt.subplots(2, len(shots), figsize=(4.2 * len(shots), 9.5))
    for k, (seq, fr, bl, lab) in enumerate(shots):
        cl = cz_local(seq, fr, bl)
        draw(axes[0][k], C, ctris, cl.copy(), None, 'Condition Zero: %s (frame %d)' % (lab, fr))
        draw(axes[1][k], M, btris, retarget(cl), gun, 'Gordon: %s (frame %d)' % (lab, fr))
    plt.suptitle('Condition Zero MP5 animations moved onto Gordon (top: original, bottom: converted)', fontsize=14)
    plt.tight_layout(); plt.savefig('/home/claude/gmodconv/eyeview/cz_mp5.png', dpi=65); print('ok', scale)
