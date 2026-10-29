"""Mock-up render of holstered weapons on the fpbody player (for discussion)."""
import json, math, struct, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
sys.path.insert(0, '/home/claude/gmodconv')
from goldsrc import GoldSrcModel


def load_tris(path, bodyparts=None):
    """-> (model, list of (bone, local verts[3], colour)) for body 0 of every part"""
    M = GoldSrcModel(path); d = bytes(M.d)
    ntex, ti = struct.unpack_from('<2i', d, 180)
    nsr, nsf, si = struct.unpack_from('<3i', d, 192)
    skins = struct.unpack_from('<%dh' % nsr, d, si) if nsr else ()
    tex = []
    for t in range(ntex):
        flags, w, h, idx = struct.unpack_from('<4i', d, ti + t * 80 + 64)
        pix = np.frombuffer(d[idx:idx + w * h], np.uint8).reshape(h, w)
        pal = np.frombuffer(d[idx + w * h:idx + w * h + 768], np.uint8).reshape(256, 3)
        tex.append((w, h, pal[pix]))
    out = []
    nbp, bpi = struct.unpack_from('<2i', d, 204)
    for bp in range(nbp):
        if bodyparts is not None and bp not in bodyparts:
            continue
        nm, _, mi = struct.unpack_from('<3i', d, bpi + bp * 76 + 64)
        nummesh, meshindex, numverts, vinfo, vindex = struct.unpack_from('<5i', d, mi + 72)
        vb = d[vinfo:vinfo + numverts]
        vv = np.frombuffer(d[vindex:vindex + numverts * 12], '<f4').reshape(-1, 3).astype(float)
        for m in range(nummesh):
            numtris, triindex, skinref, _, _ = struct.unpack_from('<5i', d, meshindex + m * 20)
            tx = tex[skins[skinref]] if ntex else None
            o = triindex
            while True:
                c = struct.unpack_from('<h', d, o)[0]; o += 2
                if c == 0:
                    break
                fan = c < 0; c = abs(c)
                vs = [struct.unpack_from('<4h', d, o + k * 8) for k in range(c)]; o += c * 8
                for k in range(2, c):
                    if fan: a, b, e = vs[0], vs[k - 1], vs[k]
                    elif k % 2: a, b, e = vs[k - 1], vs[k - 2], vs[k]
                    else: a, b, e = vs[k - 2], vs[k - 1], vs[k]
                    col = (0.7, 0.7, 0.7)
                    if tx:
                        s = (a[2] + b[2] + e[2]) / 3; t = (a[3] + b[3] + e[3]) / 3
                        col = tx[2][int(np.clip(t, 0, tx[1] - 1)), int(np.clip(s, 0, tx[0] - 1))] / 255.0
                    out.append(([vb[a[0]], vb[b[0]], vb[e[0]]], np.array([vv[a[0]], vv[b[0]], vv[e[0]]]), col))
    return M, out


def posed_world_tris(M, tris, R, T):
    return [(np.array([R[b[i]] @ v[i] + T[b[i]] for i in range(3)]), col) for b, v, col in tris]


def gun_world_tris(path, place, only_bones=None):
    """Weapon triangles in its right-hand space, placed by place(points)->points"""
    G, tris = load_tris(path)
    R, T = G.world(G.decode(0)[0][0])
    hi = G.bone_by_name.get('Bip01 R Hand')
    out = []
    for b, v, col in tris:
        if only_bones is not None and not all(x in only_bones for x in b):
            continue
        if hi is None:      # p_egon: a backpack on the spine bones
            P = np.array([R[b[i]] @ v[i] + T[b[i]] for i in range(3)])
        else:
            P = np.array([R[hi].T @ (R[b[i]] @ v[i] + T[b[i]] - T[hi]) for i in range(3)])
        out.append((place(P), col))
    return out


def frame_from(axis, up_hint):
    x = np.array(axis, float); x /= np.linalg.norm(x)
    z = np.array(up_hint, float); z -= x * (z @ x); z /= np.linalg.norm(z)
    return np.stack([x, np.cross(z, x), z], 1)     # columns: barrel, side, up


def placer(info, barrel_dir, up_dir, pos):
    """map weapon (hand space) so its barrel axis points along barrel_dir, its
    'up' along up_dir and its centroid sits at pos"""
    A = frame_from(info['axis'], [0, 0, 1])          # gun frame in hand space
    B = frame_from(barrel_dir, up_dir)                # wanted frame in world
    c = np.array(info['center'])
    Rm = B @ A.T
    return lambda P: (P - c) @ Rm.T + pos


HD = json.load(open('/home/claude/gmodconv/out/weapons_hd.json'))

body_path = '/home/claude/gmodconv/out/classic/fpbody_classic.mdl'
M, btris = load_tris(body_path)
spine = M.bone_by_name['Bip01 Spine']
a = M.decode(M.seq_by_name['ref_aim_9mmhandgun' if 'ref_aim_9mmhandgun' in M.seq_by_name else 'ref_aim_onehanded'])[0][0].copy()
a = (M.decode(M.seq_by_name['ref_aim_onehanded'])[0][0] + M.decode(M.seq_by_name['ref_aim_onehanded'])[1][0]) / 2
g = M.decode(M.seq_by_name['deep_idle'])[0][0]
a[:spine] = g[:spine]
R, T = M.world(a)
B = M.bone_by_name
world = posed_world_tris(M, btris, R, T)

# body frame from the pelvis / spine (model faces +x)
pel = T[B['Bip01 Pelvis']]; sp1 = T[B['Bip01 Spine1']]; sp2 = T[B['Bip01 Spine2']]; sp3 = T[B['Bip01 Spine3']]
rleg = T[B['Bip01 R Leg']]; rknee = T[B['Bip01 R Leg1']]; lleg = T[B['Bip01 L Leg']]
fwd = np.array([1.0, 0, 0]); left = np.array([0, 1.0, 0]); up = np.array([0, 0, 1.0])

import glob, os
FULL = {}
for p_ in sorted(glob.glob('/home/claude/gmodconv/src/hd_p/*.mdl')):
    pts = np.concatenate([P for P, _ in gun_world_tris(p_, lambda P: P)])
    c = pts.mean(0); _, _, vt = np.linalg.svd(pts - c); ax_ = vt[0]
    if ax_[np.argmax(abs(ax_))] < 0: ax_ = -ax_
    if os.path.basename(p_) in HD and HD[os.path.basename(p_)]:
        ax_ = np.array(HD[os.path.basename(p_)]['axis'])          # muzzle direction
        if ax_[0] < 0: ax_ = -ax_
    FULL[os.path.basename(p_)] = dict(center=c, axis=ax_)

def put(name, barrel, upd, pos):
    info = FULL[name]
    A = frame_from(info['axis'], [0, 0, 1]); Bm = frame_from(barrel, upd)
    Rm = Bm @ A.T; c = info['center']
    return gun_world_tris('/home/claude/gmodconv/src/hd_p/' + name, lambda P: (P - c) @ Rm.T + pos)

def n(v): v = np.array(v, float); return v / np.linalg.norm(v)
items = []
GR, GT = R, T
hand = B['Bip01 R Hand']
items.append(gun_world_tris('/home/claude/gmodconv/src/hd_p/p_9mmhandgun.mdl', lambda P: P @ GR[hand].T + GT[hand]))
back = -fwd
# back, outer layer: RPG over the right shoulder, crossbow over the left
items.append(put('p_rpg.mdl', n(up * 0.8 - left * 0.6), back, sp2 - fwd * 11 + up * 2))
items.append(put('p_crossbow.mdl', n(up * 0.8 + left * 0.6), back, sp2 - fwd * 10.5 + up * 1))
# back, middle: MP5 and shotgun crossed in an X
items.append(put('p_9mmar.mdl', n(up * 0.6 - left * 0.8), back, sp2 - fwd * 8.5 - up * 1))
items.append(put('p_shotgun.mdl', n(up * 0.6 + left * 0.8), back, sp2 - fwd * 8.5 - up * 1))
# back, against the body: gauss gun upright in the middle, crowbar beside it
items.append(put('p_gauss.mdl', n(-left), back, sp3 - fwd * 9.5 + up * 1.5))      # across the shoulders
items.append(put('p_crowbar.mdl', n(-up * 0.9 + left * 0.3), back, sp3 - fwd * 7.5 + left * 5 - up * 3))
# lower back: hivehand across the waist
items.append(put('p_hgun.mdl', n(-up), -left, pel + left * 8.5 - fwd * 2 - up * 3))   # hanging on the left hip
# egon: its own backpack model, worn as it is in the game
EG = '/home/claude/gmodconv/src/hd_p/p_egon.mdl'
_ep = np.concatenate([P for P, _ in gun_world_tris(EG, lambda P: P, only_bones={3})])
_ec = (_ep.min(0) + _ep.max(0)) / 2
egon_items = [gun_world_tris(EG, lambda P: P - _ec + (sp1 - fwd * 11 + up * 1 - left * 3), only_bones={3})]     # pack
_gp = np.concatenate([P for P, _ in gun_world_tris(EG, lambda P: P, only_bones={8, 9})])
_gc = (_gp.min(0) + _gp.max(0)) / 2
_c, _s = 0.0, 1.0      # rotate the nozzle 90 degrees to hang down beside the pack
def _hang(P):
    Q = P - _gc
    Q = Q @ np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]], float).T
    return Q + (pel - fwd * 9 + left * 9 + up * 4)
egon_items.append(gun_world_tris(EG, _hang, only_bones={8, 9}))
# belt and thighs
thigh = rleg * 0.55 + rknee * 0.45 - left * 4.5
items.append(put('p_357.mdl', n(-up * 0.95 + fwd * 0.15), fwd, thigh))
lthigh = lleg * 0.55 + T[B['Bip01 L Leg1']] * 0.45 + left * 4.5
items.append(put('p_grenade.mdl', up, left, pel + left * 6.5 + fwd * 1.5 + up * 1.0))
items.append(put('p_squeak.mdl', up, -left, pel - left * 6.5 + fwd * 1.0 + up * 1.5))
items.append(put('p_satchel.mdl', up, back, pel - fwd * 6 - left * 3 - up * 1))
items.append(put('p_tripmine.mdl', up, left, lthigh + fwd * 0.5))

base_t = world + [t for it in items for t in it]
egon_t = [t for it in egon_items for t in it]
allt = base_t


def ortho(ax, vdir, title, light=np.array([0.3, -0.4, 0.85])):
    vdir = vdir / np.linalg.norm(vdir)
    right = np.cross(vdir, up); right /= np.linalg.norm(right); upv = np.cross(right, vdir)
    polys, cols, depth = [], [], []
    for P, col in allt:
        n = np.cross(P[1] - P[0], P[2] - P[0]); nl = np.linalg.norm(n)
        if nl < 1e-9: continue
        n /= nl
        if n @ vdir < 0: continue      # GoldSrc triangles wind the other way
        shade = 0.45 + 0.55 * abs(n @ vdir)
        polys.append(np.stack([P @ right, P @ upv], 1)); cols.append(np.clip(np.array(col) * shade, 0, 1))
        depth.append(-(P @ vdir).mean())
    o = np.argsort(depth)
    ax.add_collection(PolyCollection([polys[i] for i in o], facecolors=[cols[i] for i in o], edgecolors='none'))
    ax.set_xlim(-32, 32); ax.set_ylim(-40, 42); ax.set_aspect('equal'); ax.axis('off'); ax.set_title(title)


def perspective(ax, eye, pitch_deg, yaw_deg, title, fov=90):
    p, yv = math.radians(pitch_deg), math.radians(yaw_deg)
    f = np.array([math.cos(p) * math.cos(yv), math.cos(p) * math.sin(yv), -math.sin(p)])
    r = np.cross(f, up); r /= np.linalg.norm(r); u = np.cross(r, f)
    k = 1.0 / math.tan(math.radians(fov) / 2)
    polys, cols, depth = [], [], []
    for P, col in allt:
        rel = P - eye; z = rel @ f
        if (z < 3).any(): continue
        n = np.cross(P[1] - P[0], P[2] - P[0]); nl = np.linalg.norm(n)
        if nl < 1e-9: continue
        n /= nl
        if n @ (P.mean(0) - eye) < 0: continue
        x = (rel @ r) / z * k; y = (rel @ u) / z * k * 16 / 9
        polys.append(np.stack([x, y], 1)); cols.append(np.clip(np.array(col) * (0.5 + 0.5 * abs(n @ f)), 0, 1))
        depth.append(-z.mean())
    o = np.argsort(depth)
    ax.set_facecolor((0.55, 0.53, 0.5))
    ax.add_collection(PolyCollection([polys[i] for i in o], facecolors=[cols[i] for i in o], edgecolors='none'))
    ax.set_xlim(-1, 1); ax.set_ylim(-1, 1); ax.set_xticks([]); ax.set_yticks([]); ax.set_title(title)


fig = plt.figure(figsize=(16, 8))
ax1 = fig.add_subplot(1, 3, 1); ortho(ax1, np.array([1.0, 0.45, -0.15]), 'Back (without the egon)')
allt = base_t + egon_t
ax2 = fig.add_subplot(1, 3, 2); ortho(ax2, np.array([1.0, 0.45, -0.15]), 'Back (egon pack on)')
ax3 = fig.add_subplot(1, 3, 3); ortho(ax3, np.array([-1.0, 0.5, -0.1]), 'Front')
plt.tight_layout()
plt.savefig(sys.argv[1], dpi=100)
print('saved')
