"""Eye-view render of every held weapon, as the fpbody camera sees it (classic mode).

  python3 -I eye_sheet.py <outdir> [pitch]
"""
import math, os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
sys.path.insert(0, '/home/claude/gmodconv')
G_ = {}
exec(open('/home/claude/gmodconv/holster_mock.py').read().split("HD = json.load")[0], G_)
load_tris = G_['load_tris']

OUT = '/home/claude/gmodconv/out'
HL_P = '/home/claude/gmodconv/src/final_p/'
OP_P = '/home/claude/gmodconv/src/final_p/'
HFOV, VFOV = 106.26, 73.74          # fov 90 at 4:3, widened to 16:9 like the Steam version


def player_pose(M, ext, pitch):
    seq = 'ref_aim_' + ext
    if seq not in M.seq_by_name:
        a = M.decode(0)[0][0].copy()          # what the game does: falls back to sequence 0
    else:
        s = M.seqs[M.seq_by_name[seq]]
        fr = M.decode(M.seq_by_name[seq])
        if s['numblends'] > 1:
            # classic: the aim blend follows the whole view pitch
            w = np.clip((-pitch - s['blendstart'][0]) / (s['blendend'][0] - s['blendstart'][0]), 0, 1)
            a = fr[0][0] * (1 - w) + fr[1][0] * w
        else:
            a = fr[0][0].copy()
    g = M.decode(M.seq_by_name['deep_idle'])[0][0]
    sp = M.bone_by_name['Bip01 Spine']
    a[:sp] = g[:sp]
    return M.world(a)


def merged_weapon(path, M, R, T):
    """engine StudioMergeBones: bones named like the player's copy the player's,
    the rest hang off their (merged) parent with the weapon's own local pose"""
    W, tris = load_tris(path)
    Rw, Tw = W.world(W.decode(0)[0][0])
    Rn, Tn = [None] * len(W.bones), [None] * len(W.bones)
    for i, b in enumerate(W.bones):
        j = M.bone_by_name.get(b['name'])
        p = b['parent']
        if j is not None:
            Rn[i], Tn[i] = R[j], T[j]
        elif p < 0:
            Rn[i], Tn[i] = Rw[i], Tw[i]
        else:
            Rl = Rw[p].T @ Rw[i]; tl = Rw[p].T @ (Tw[i] - Tw[p])
            Rn[i], Tn[i] = Rn[p] @ Rl, Tn[p] + Rn[p] @ tl
    return [(np.array([Rn[b[k]] @ v[k] + Tn[b[k]] for k in range(3)]), col) for b, v, col in tris]


def head_set(M):
    out = set()
    for i in range(len(M.bones)):
        j = i
        while j >= 0:
            if M.bones[j]['name'] == 'Bip01 Head':
                out.add(i); break
            j = M.bones[j]['parent']
    return out


def render(ax, tris, eye, pitch, floor_z, title):
    p = math.radians(pitch)
    f = np.array([math.cos(p), 0, -math.sin(p)]); up = np.array([0, 0, 1.0])
    r = np.cross(f, up); r /= np.linalg.norm(r); u = np.cross(r, f)
    kh = 1 / math.tan(math.radians(HFOV) / 2); kv = 1 / math.tan(math.radians(VFOV) / 2)
    # sky / floor
    hy = math.tan(p) * kv if abs(pitch) < 89 else 9
    ax.add_patch(plt.Rectangle((-1, hy), 2, 3, color=(0.62, 0.66, 0.70), zorder=0))
    ax.add_patch(plt.Rectangle((-1, -3), 2, 3 + hy, color=(0.40, 0.38, 0.35), zorder=0))
    polys, cols, depth = [], [], []
    light = np.array([0.3, -0.4, 0.85]); light /= np.linalg.norm(light)
    for P, col in tris:
        rel = P - eye; z = rel @ f
        if (z < 1.5).any():
            continue
        n = np.cross(P[1] - P[0], P[2] - P[0]); nl = np.linalg.norm(n)
        if nl < 1e-9:
            continue
        n /= nl
        if n @ (P.mean(0) - eye) < 0:
            continue
        x = (rel @ r) / z * kh; y = (rel @ u) / z * kv
        polys.append(np.stack([x, y], 1))
        cols.append(np.clip(np.array(col) * (0.55 + 0.45 * abs(n @ light)), 0, 1))
        depth.append(-z.mean())
    o = np.argsort(depth)
    ax.add_collection(PolyCollection([polys[i] for i in o], facecolors=[cols[i] for i in o],
                                     edgecolors='none', zorder=1))
    ax.set_xlim(-1, 1); ax.set_ylim(-1, 1); ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(title, fontsize=10)
    # crosshair
    ax.plot([0], [0], marker='+', color=(1, 0.85, 0.2), markersize=8, zorder=2)


HL_W = [('Crowbar', HL_P + 'p_crowbar.mdl', 'crowbar'), ('Glock', HL_P + 'p_9mmhandgun.mdl', 'onehanded'),
        ('.357 Magnum', HL_P + 'p_357.mdl', 'python'), ('MP5', HL_P + 'p_9mmar.mdl', 'mp5'),
        ('Shotgun', HL_P + 'p_shotgun.mdl', 'shotgun'), ('Crossbow', HL_P + 'p_crossbow.mdl', 'bow'),
        ('RPG', HL_P + 'p_rpg.mdl', 'rpg'), ('Gauss', HL_P + 'p_gauss.mdl', 'gauss'),
        ('Gluon (Egon)', HL_P + 'p_egon.mdl', 'egon'), ('Hivehand', HL_P + 'p_hgun.mdl', 'hive'),
        ('Hand grenade', HL_P + 'p_grenade.mdl', 'crowbar'), ('Satchel', HL_P + 'p_satchel.mdl', 'trip'),
        ('Satchel radio', HL_P + 'p_satchel_radio.mdl', 'hive'), ('Tripmine', HL_P + 'p_tripmine.mdl', 'trip'),
        ('Snarks', HL_P + 'p_squeak.mdl', 'squeak')]
OP_W = HL_W + [('Pipe wrench', OP_P + 'p_pipe_wrench.mdl', 'crowbar'), ('Knife', OP_P + 'p_knife.mdl', 'crowbar'),
               ('Desert Eagle', OP_P + 'p_desert_eagle.mdl', 'onehanded'), ('M249', OP_P + 'p_saw.mdl', 'mp5'),
               ('Sniper rifle', OP_P + 'p_m40a1.mdl', 'bow'), ('Shock roach', OP_P + 'p_shock.mdl', 'bow'),
               ('Spore launcher', OP_P + 'p_spore_launcher.mdl', 'rpg'), ('Displacer', OP_P + 'p_displacer.mdl', 'egon'),
               ('Barnacle grapple', OP_P + 'p_bgrap.mdl', 'gauss'), ('Penguin', OP_P + 'p_penguin.mdl', 'penguin')]

GAMES = [('Half-Life', 'Gordon, HEV suit', OUT + '/classic/fpbody_classic.mdl', HL_W),
         ('Blue Shift', 'Barney, blue HEV suit', OUT + '/classic/bs/fpbody_classic_suit.mdl', HL_W),
         ('Opposing Force', 'Shephard, green HEV suit', OUT + '/classic/op4/fpbody_classic_suit.mdl', OP_W)]

outdir = sys.argv[1]
pitch = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
for game, who, path, weapons in GAMES:
    M, btris = load_tris(path)
    hs = head_set(M)
    btris = [t for t in btris if not any(b in hs for b in t[0])]
    cols = 5
    rows = (len(weapons) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 4.2, rows * 2.6))
    for k, ax in enumerate(axes.flat):
        if k >= len(weapons):
            ax.axis('off'); continue
        name, wpath, ext = weapons[k]
        R, T = player_pose(M, ext, pitch)
        body = [(np.array([R[b[i]] @ v[i] + T[b[i]] for i in range(3)]), col) for b, v, col in btris]
        gun = merged_weapon(wpath, M, R, T)
        head = T[M.bone_by_name['Bip01 Head']]
        down = max(0.0, math.sin(math.radians(pitch)))
        eye = head + np.array([4 + 8 * down, 0, 3])
        floor_z = min(P[:, 2].min() for P, _ in body)
        render(ax, body + gun, eye, pitch, floor_z, name)
    fig.suptitle('%s eye view: %s, looking %s' % (game, who, 'straight ahead' if pitch == 0 else '%d° down' % pitch),
                 fontsize=14)
    plt.tight_layout()
    out = os.path.join(outdir, 'eyeview_%s_%d.png' % (game.lower().replace(' ', '_'), pitch))
    plt.savefig(out, dpi=80); plt.close(fig)
    print('saved', out)
