import sys, numpy as np
sys.argv = ['x', '/tmp', '0']
exec(open('/home/claude/gmodconv/eye_sheet.py').read().split("outdir = sys.argv[1]")[0])
import matplotlib.pyplot as plt
H_ = {}; exec(open('/home/claude/gmodconv/holster_sheet.py').read().split("outdir = sys.argv[1]")[0], H_)
from goldsrc import GoldSrcModel
SV = GoldSrcModel('/mnt/user-data/uploads/Sven Co-op/svencoop/models/player.mdl')
M, btris = load_tris('/home/claude/gmodconv/out/cz/fpbody_op4__fpbody_classic_suit.mdl')
base = M.decode(M.seq_by_name['look_idle'])[0][0]
smap = {M.bone_by_name[b['name']]: i for i, b in enumerate(SV.bones) if b['name'] in M.bone_by_name}
HD = '/home/claude/gmodconv/src/final_p/'


def sven_frame(seq, f, blend=0.5):
    fr = SV.decode(SV.seq_by_name[seq]); a = fr[0][f] * (1 - blend) + fr[1][f] * blend if len(fr) > 1 else fr[0][f]
    out = base.copy()
    for mi, si in smap.items():
        out[mi][3:6] = a[si][3:6]
    return out


def cz_frame(seq, f):
    return M.decode(M.seq_by_name[seq])[0][f].copy()


def draw(ax, a, gun, title):
    g = M.decode(M.seq_by_name['deep_idle'])[0][0]; sp = M.bone_by_name['Bip01 Spine']; a = a.copy(); a[:sp] = g[:sp]
    R, T = M.world(a)
    body = [(np.array([R[b[i]] @ v[i] + T[b[i]] for i in range(3)]), c) for b, v, c in btris]
    H_['ortho'](ax, body + merged_weapon(gun, M, R, T), np.array([-1.0, 0.9, -0.15]), title)
    ax.set_xlim(-28, 30); ax.set_ylim(-8, 42)


rows = [('MP5, Condition Zero', 'cz', 'ref_reload_mp5', 'p_9mmar'), ('MP5, Sven Co-op', 'sv', 'ref_reload_mp5', 'p_9mmar'),
        ('Shotgun, Condition Zero', 'cz', 'ref_reload_shotgun', 'p_shotgun'), ('Shotgun, Sven Co-op', 'sv', 'ref_reload_shotgun', 'p_shotgun'),
        ('Glock, Condition Zero', 'cz', 'ref_reload_onehanded', 'p_9mmhandgun'), ('Glock, Sven Co-op', 'sv', 'ref_reload_onehanded', 'p_9mmhandgun'),
        ('.357, Sven Co-op (python)', 'sv', 'ref_reload_python', 'p_357'), ('Crossbow, Sven Co-op (bow)', 'sv', 'ref_reload_bow', 'p_crossbow'),
        ('RPG, Sven Co-op (none in CZ)', 'sv', 'ref_reload_rpg', 'p_rpg'), ('M249, Sven Co-op (saw)', 'sv', 'ref_reload_saw', 'p_saw'),
        ('Sniper rifle, Sven Co-op', 'sv', 'ref_reload_sniper', 'p_m40a1')]
fig, axes = plt.subplots(len(rows), 4, figsize=(15, 4.0 * len(rows)))
for r, (nm, src, seq, gun) in enumerate(rows):
    nf = (SV if src == 'sv' else M).seqs[(SV if src == 'sv' else M).seq_by_name[seq]]['numframes']
    fps = (SV if src == 'sv' else M).seqs[(SV if src == 'sv' else M).seq_by_name[seq]]['fps']
    for c, f in enumerate(np.linspace(0, nf - 1, 4).astype(int)):
        a = sven_frame(seq, f) if src == 'sv' else cz_frame(seq, f)
        draw(axes[r][c], a, HD + gun + '.mdl', '%s  %d/%d (%.1fs)' % (nm, f, nf - 1, (nf - 1) / fps))
plt.tight_layout(); plt.savefig('/home/claude/gmodconv/eyeview/sven_vs_cz.png', dpi=55); print('ok')
for s in ('ref_reload_mp5', 'ref_reload_rpg', 'ref_reload_saw'):
    q = SV.seqs[SV.seq_by_name[s]]; print(s, q['fps'], q['numframes'], q['blendtype'], q['blendstart'], q['blendend'])
