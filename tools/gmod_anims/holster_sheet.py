"""Renders every fpbody player outfit with all of its game's weapons holstered.

  python3 -I holster_sheet.py <outdir>
"""
import glob, json, math, os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection

sys.path.insert(0, '/home/claude/gmodconv')
G = {}
exec(open('/home/claude/gmodconv/holster_mock.py').read().split("HD = json.load")[0], G)
load_tris, posed_world_tris, gun_world_tris, frame_from = (G['load_tris'], G['posed_world_tris'],
                                                           G['gun_world_tris'], G['frame_from'])

SRC = '/home/claude/gmodconv/src'
OUT = '/home/claude/gmodconv/out'
HL_P = SRC + '/final_p/'   # the p_ models the mods ship (VAPW + converted viewmodels + originals)
OP_P = SRC + '/final_p/'
MM_P = SRC + '/mmod_p/'   # Half-Life MMod replacements (glock)
TABLE = {}
for f in (OUT + '/weapons_hd.json', OUT + '/weapons_op4.json'):
    for k, v in json.load(open(f)).items():
        if v:
            TABLE[k] = v


def info(path, only_bones=None):
    pts = np.concatenate([P for P, _ in gun_world_tris(path, lambda P: P, only_bones)])
    c = (pts.min(0) + pts.max(0)) / 2
    _, _, vt = np.linalg.svd(pts - pts.mean(0)); ax = vt[0]
    name = os.path.basename(path)
    if name in TABLE and '/mmod_p/' not in path:
        ax = np.array(TABLE[name]['axis'])
    if ax[np.argmax(abs(ax))] < 0:
        ax = -ax
    return c, ax


up = np.array([0, 0, 1.0]); fwd = np.array([1.0, 0, 0]); left = np.array([0, 1.0, 0])


def n(v):
    v = np.array(v, float); return v / np.linalg.norm(v)


def put(path, barrel, upd, pos, only_bones=None, roll=None):
    c, ax = info(path, only_bones)
    A = frame_from(ax, [0, 0, 1]); Bm = frame_from(barrel, upd)
    Rm = Bm @ A.T
    return gun_world_tris(path, lambda P: (P - c) @ Rm.T + pos, only_bones)


def layout(J, op4):
    """J: joint positions. Returns triangle lists of the holstered weapons."""
    pel, sp1, sp2, sp3 = J['Bip01 Pelvis'], J['Bip01 Spine1'], J['Bip01 Spine2'], J['Bip01 Spine3']
    rthigh = J['Bip01 R Leg'] * 0.55 + J['Bip01 R Leg1'] * 0.45 - left * 4.5
    lthigh = J['Bip01 L Leg'] * 0.55 + J['Bip01 L Leg1'] * 0.45 + left * 4.5
    rcalf = J['Bip01 R Leg1'] * 0.6 + J['Bip01 R Foot'] * 0.4 - left * 3.5
    back = -fwd
    L = []
    # back: outer layer, over the shoulders
    L.append(put(HL_P + 'p_rpg.mdl', n(up * 0.8 - left * 0.6), back, sp2 - fwd * 11 + up * 2))
    L.append(put(HL_P + 'p_crossbow.mdl', n(up * 0.8 + left * 0.6), back, sp2 - fwd * 10.5 + up * 1))
    # back: MP5 and shotgun crossed
    L.append(put(HL_P + 'p_9mmar.mdl', n(up * 0.6 - left * 0.8), back, sp2 - fwd * 8.5 - up * 1))
    L.append(put(HL_P + 'p_shotgun.mdl', n(up * 0.6 + left * 0.8), back, sp2 - fwd * 8.5 - up * 1))
    # against the body
    L.append(put(HL_P + 'p_gauss.mdl', n(-left), back, sp3 - fwd * 9.5 + up * 1.5))
    L.append(put(HL_P + 'p_crowbar.mdl', n(-up * 0.9 + left * 0.3), back, sp3 - fwd * 7.5 + left * 5 - up * 3))
    # egon pack + nozzle
    eg = HL_P + 'p_egon.mdl'
    c, _ = info(eg, {3, 6})
    L.append(gun_world_tris(eg, lambda P: P - c + (sp1 - fwd * 11 + up * 1 - left * 3), {3, 6}))
    c2, _ = info(eg, {8, 9})
    Rh = np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]], float)
    L.append(gun_world_tris(eg, lambda P: (P - c2) @ Rh.T + (pel - fwd * 9 + left * 9 + up * 4), {8, 9}))
    # belt and legs
    L.append(put(HL_P + 'p_357.mdl', n(-up * 0.95 + fwd * 0.15), fwd, rthigh))
    L.append(put(HL_P + 'p_9mmhandgun.mdl', n(-up * 0.95 + fwd * 0.15), fwd, rthigh + fwd * 3.5 - up * 1))
    L.append(put(HL_P + 'p_tripmine.mdl', up, left, lthigh + fwd * 0.5))
    L.append(put(HL_P + 'p_grenade.mdl', up, left, pel + left * 6.5 + fwd * 1.5 + up * 1.0))
    L.append(put(HL_P + 'p_hgun.mdl', n(-up), -left, pel + left * 8.5 - fwd * 2 - up * 3))
    L.append(put(HL_P + 'p_squeak.mdl', up, -left, pel - left * 6.5 + fwd * 1.0 + up * 1.5))
    L.append(put(HL_P + 'p_satchel.mdl', up, back, pel - fwd * 6 - left * 3 - up * 1))
    if op4:
        # long guns on the outer layer of the back
        L.append(put(OP_P + 'p_m40a1.mdl', n(up * 0.75 + left * 0.66), back, sp2 - fwd * 13 + up * 3))
        L.append(put(OP_P + 'p_saw.mdl', n(-left * 0.95 + up * 0.3), back, sp1 - fwd * 13 - up * 2))
        L.append(put(OP_P + 'p_spore_launcher.mdl', n(up * 0.8 - left * 0.6), back, sp2 - fwd * 14 - left * 4))
        L.append(put(OP_P + 'p_shock.mdl', n(-up * 0.6 - left * 0.8), back, sp1 - fwd * 12 + left * 6 - up * 4))
        L.append(put(OP_P + 'p_displacer.mdl', n(left), back, pel - fwd * 12 + up * 2))
        L.append(put(OP_P + 'p_pipe_wrench.mdl', n(-up * 0.9 - left * 0.3), back, sp3 - fwd * 7.5 - left * 5 - up * 3))
        # belt and legs
        L.append(put(OP_P + 'p_desert_eagle.mdl', n(-up * 0.95 + fwd * 0.15), fwd, lthigh + left * 0.5 - up * 3))
        L.append(put(OP_P + 'p_knife.mdl', n(-up), -left, rcalf))
        L.append(put(OP_P + 'p_bgrap.mdl', n(-up), left, pel - left * 9 - fwd * 1 - up * 3))
        L.append(put(OP_P + 'p_penguin.mdl', up, left, pel + left * 7 + fwd * 4 + up * 0.5))
    return [t for it in L for t in it]


def ortho(ax, tris, vdir, title):
    vdir = vdir / np.linalg.norm(vdir)
    right = np.cross(vdir, up); right /= np.linalg.norm(right); upv = np.cross(right, vdir)
    polys, cols, depth = [], [], []
    for P, col in tris:
        nn = np.cross(P[1] - P[0], P[2] - P[0]); nl = np.linalg.norm(nn)
        if nl < 1e-9: continue
        nn /= nl
        if nn @ vdir < 0: continue
        polys.append(np.stack([P @ right, P @ upv], 1))
        cols.append(np.clip(np.array(col) * (0.45 + 0.55 * abs(nn @ vdir)), 0, 1))
        depth.append(-(P @ vdir).mean())
    o = np.argsort(depth)
    ax.add_collection(PolyCollection([polys[i] for i in o], facecolors=[cols[i] for i in o], edgecolors='none'))
    ax.set_xlim(-34, 34); ax.set_ylim(-40, 44); ax.set_aspect('equal'); ax.axis('off'); ax.set_title(title, fontsize=11)


def player_tris(path, op4):
    M, btris = load_tris(path)
    spine = M.bone_by_name['Bip01 Spine']
    a = M.decode(M.seq_by_name['look_idle'])[0][0].copy()
    g = M.decode(M.seq_by_name['deep_idle'])[0][0]
    a[:spine] = g[:spine]
    R, T = M.world(a)
    J = {b['name']: T[i] for i, b in enumerate(M.bones)}
    return posed_world_tris(M, btris, R, T) + layout(J, op4)


GAMES = [
    ('Half-Life', False, [('Gordon, HEV suit', OUT + '/classic/fpbody_classic.mdl'),
                          ('Gordon, lab coat', OUT + '/classic/hl/fpbody_classic_presuit.mdl')]),
    ('Blue Shift', False, [('Barney, guard uniform', OUT + '/classic/bs/fpbody_classic_presuit.mdl'),
                           ('Barney, blue HEV suit', OUT + '/classic/bs/fpbody_classic_suit.mdl')]),
    ('Opposing Force', True, [('Shephard, before the PCV', OUT + '/classic/op4/fpbody_classic_presuit.mdl'),
                              ('Shephard, green HEV suit', OUT + '/classic/op4/fpbody_classic_suit.mdl')]),
]

outdir = sys.argv[1]
for game, op4, players in GAMES:
    fig, axes = plt.subplots(1, 4, figsize=(18, 7.2))
    for k, (label, path) in enumerate(players):
        tris = player_tris(path, op4)
        ortho(axes[k * 2], tris, np.array([1.0, 0.45, -0.15]), label + ' (back)')
        ortho(axes[k * 2 + 1], tris, np.array([-1.0, 0.5, -0.1]), label + ' (front)')
    fig.suptitle(game + ': every weapon holstered', fontsize=15)
    plt.tight_layout()
    out = os.path.join(outdir, 'holster_%s.png' % game.lower().replace(' ', '_'))
    plt.savefig(out, dpi=90)
    plt.close(fig)
    print('saved', out)
