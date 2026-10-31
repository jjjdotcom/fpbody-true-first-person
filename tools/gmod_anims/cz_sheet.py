import sys, numpy as np
sys.argv = ['x', '/tmp', '0']
exec(open('/home/claude/gmodconv/eye_sheet.py').read().split("outdir = sys.argv[1]")[0])
import matplotlib.pyplot as plt
H_ = {}; exec(open('/home/claude/gmodconv/holster_sheet.py').read().split("outdir = sys.argv[1]")[0], H_)
HD = '/home/claude/gmodconv/src/final_p/'; LD = '/home/claude/gmodconv/src/ld_p/'
W = [('Crowbar', 'p_crowbar', 'knife'), ('Glock', 'p_9mmhandgun', 'onehanded'), ('.357', 'p_357', 'onehanded'),
     ('MP5', 'p_9mmar', 'mp5'), ('Shotgun', 'p_shotgun', 'shotgun'), ('Crossbow', 'p_crossbow', 'rifle'),
     ('RPG', 'p_rpg', 'rpg'), ('Tau Cannon', 'p_gauss', 'tau'), ('Gluon gun', 'p_egon', 'egon'), ('Hivehand', 'p_hgun', 'hive'),
     ('Hand grenade', 'p_grenade', 'grenade'), ('Satchel', 'p_satchel', 'c4'), ('Satchel radio', 'p_satchel_radio', 'hive'),
     ('Tripmine', 'p_tripmine', 'c4'), ('Snarks', 'p_squeak', 'grenade'), ('Pipe wrench', 'p_pipe_wrench', 'knife'),
     ('Knife', 'p_knife', 'knife'), ('Desert Eagle', 'p_desert_eagle', 'onehanded'), ('M249', 'p_saw', 'm249'),
     ('Sniper rifle', 'p_m40a1', 'rifle'), ('Shock roach', 'p_shock', 'bow'), ('Spore launcher', 'p_spore_launcher', 'rpg'),
     ('Displacer', 'p_displacer', 'egon'), ('Barnacle grapple', 'p_bgrap', 'gauss'), ('Penguin', 'p_penguin', 'grenade')]
CZSETS = {'knife', 'onehanded', 'mp5', 'shotgun', 'rifle', 'grenade', 'c4', 'm249'}


def body_gun(M, btris, ext, gun, seq=None, frame=0):
    if seq is None:
        R, T = player_pose(M, ext, 0)
    else:
        a = M.decode(M.seq_by_name[seq])[0][frame].copy()
        g = M.decode(M.seq_by_name['deep_idle'])[0][0]; sp = M.bone_by_name['Bip01 Spine']; a[:sp] = g[:sp]
        R, T = M.world(a)
    body = [(np.array([R[b[i]] @ v[i] + T[b[i]] for i in range(3)]), c) for b, v, c in btris]
    return body + merged_weapon(gun, M, R, T)


if __name__ == '__main__':
    model = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].endswith('.mdl') else '/home/claude/gmodconv/out/cz/fpbody_op4__fpbody_classic_suit.mdl'
    M, btris = load_tris(model)
    for tag, d in (('HD', HD), ('LD', LD)):
        fig, axes = plt.subplots(5, 5, figsize=(19, 21))
        for k, (nm, p, ext) in enumerate(W):
            ax = axes.flat[k]
            H_['ortho'](ax, body_gun(M, btris, ext, d + p + '.mdl'), np.array([-1.0, 0.9, -0.15]),
                        '%s  [%s%s]' % (nm, ext, ', Condition Zero' if ext in CZSETS else ', Half-Life'))
            ax.set_xlim(-28, 30); ax.set_ylim(-8, 42)
        fig.suptitle('Every weapon held with the Condition Zero animation sets (%s weapon models)' % tag, fontsize=16)
        plt.tight_layout(); plt.savefig('/home/claude/gmodconv/eyeview/cz_all_%s.png' % tag, dpi=62); plt.close(fig)
    # reloads
    R5 = [('MP5', 'p_9mmar', 'mp5'), ('Shotgun', 'p_shotgun', 'shotgun'), ('Glock', 'p_9mmhandgun', 'onehanded'),
          ('Crossbow', 'p_crossbow', 'rifle'), ('M249', 'p_saw', 'm249')]
    fig, axes = plt.subplots(5, 4, figsize=(16, 21))
    for r, (nm, p, ext) in enumerate(R5):
        s = M.seqs[M.seq_by_name['ref_reload_' + ext]]; nf = s['numframes']
        for c, f in enumerate(np.linspace(0, nf - 1, 4).astype(int)):
            ax = axes[r][c]
            H_['ortho'](ax, body_gun(M, btris, ext, HD + p + '.mdl', 'ref_reload_' + ext, f), np.array([-1.0, 0.9, -0.15]),
                        '%s reload, frame %d/%d' % (nm, f, nf - 1))
            ax.set_xlim(-28, 30); ax.set_ylim(-8, 42)
    fig.suptitle('Condition Zero reloads (HD weapon models)', fontsize=16)
    plt.tight_layout(); plt.savefig('/home/claude/gmodconv/eyeview/cz_reloads.png', dpi=62); plt.close(fig)
    print('ok')
