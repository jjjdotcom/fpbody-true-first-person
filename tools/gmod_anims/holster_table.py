"""Generates cl_dll/fpbody_holsters.h: where each carried weapon sits on the
body. Same layout as holster_sheet.py (the approved mock-up)."""
import sys, os, struct, numpy as np
sys.path.insert(0, '/home/claude/gmodconv')
exec(open('/home/claude/gmodconv/holster_sheet.py').read().split("def layout(J, op4):")[0])
from goldsrc import GoldSrcModel

# reference pose (the one the mock-ups were drawn in)
M = GoldSrcModel(OUT + '/classic/fpbody_classic.mdl')
spine = M.bone_by_name['Bip01 Spine']
a = M.decode(M.seq_by_name['look_idle'])[0][0].copy(); g = M.decode(M.seq_by_name['deep_idle'])[0][0]
a[:spine] = g[:spine]
R, T = M.world(a)
J = {b['name']: T[i] for i, b in enumerate(M.bones)}
RB = {b['name']: (R[i], T[i]) for i, b in enumerate(M.bones)}

def model_to_world_put(path, barrel, upd, pos, only_bones=None):
    """affine (Rw, tw) taking the p_ model's frame-0 model space to the reference world"""
    c, ax = info(path, only_bones)
    A = frame_from(ax, [0, 0, 1]); Bm = frame_from(barrel, upd); Rm = Bm @ A.T
    G_ = GoldSrcModel(path); Rg, Tg = G_.world(G_.decode(0)[0][0])
    hi = G_.bone_by_name.get('Bip01 R Hand')
    if hi is None:
        Rh, Th = np.eye(3), np.zeros(3)
    else:
        Rh, Th = Rg[hi], Tg[hi]
    # world = Rm (Rh^T (P - Th) - c) + pos
    Rw = Rm @ Rh.T
    tw = pos - Rm @ c - Rw @ Th
    return Rw, tw

rows = []
def add(weapons, path, anchor, Rw, tw, keep=None, note=''):
    RA, TA = RB[anchor]
    Rl = RA.T @ Rw; tl = RA.T @ (tw - TA)
    mask = 0 if keep is None else sum(1 << b for b in keep)
    length = struct.unpack_from('<i', open(path, 'rb').read(), 72)[0]
    rows.append((weapons, 'models/' + os.path.basename(path), anchor, Rl, tl, mask, note, path, length))

def P(weapons, path, anchor, barrel, upd, pos, note=''):
    Rw, tw = model_to_world_put(path, barrel, upd, pos)
    add(weapons, path, anchor, Rw, tw, note=note)

def layout_rows():
    pel, sp1, sp2, sp3 = J['Bip01 Pelvis'], J['Bip01 Spine1'], J['Bip01 Spine2'], J['Bip01 Spine3']
    rthigh = J['Bip01 R Leg'] * 0.55 + J['Bip01 R Leg1'] * 0.45 - left * 4.5
    lthigh = J['Bip01 L Leg'] * 0.55 + J['Bip01 L Leg1'] * 0.45 + left * 4.5
    rcalf = J['Bip01 R Leg1'] * 0.6 + J['Bip01 R Foot'] * 0.4 - left * 3.5
    back = -fwd
    P('weapon_rpg', HL_P + 'p_rpg.mdl', 'Bip01 Spine2', n(up * 0.8 - left * 0.6), back, sp2 - fwd * 11 + up * 2, 'back, over the right shoulder')
    P('weapon_crossbow', HL_P + 'p_crossbow.mdl', 'Bip01 Spine2', n(up * 0.8 + left * 0.6), back, sp2 - fwd * 10.5 + up * 1, 'back, over the left shoulder')
    P('weapon_9mmAR weapon_mp5', HL_P + 'p_9mmar.mdl', 'Bip01 Spine2', n(up * 0.6 - left * 0.8), back, sp2 - fwd * 8.5 - up * 1, 'back, crossed')
    P('weapon_shotgun', HL_P + 'p_shotgun.mdl', 'Bip01 Spine2', n(up * 0.6 + left * 0.8), back, sp2 - fwd * 8.5 - up * 1, 'back, crossed')
    P('weapon_gauss', HL_P + 'p_gauss.mdl', 'Bip01 Spine3', n(-left), back, sp3 - fwd * 9.5 + up * 1.5, 'across the shoulders')
    P('weapon_crowbar', HL_P + 'p_crowbar.mdl', 'Bip01 Spine3', n(-up * 0.9 + left * 0.3), back, sp3 - fwd * 7.5 + left * 5 - up * 3, 'back, upright left')
    eg = HL_P + 'p_egon.mdl'
    pk, nz = egon_keep(eg)
    c, _ = info(eg, pk); add('weapon_egon', eg, 'Bip01 Spine1', np.eye(3), (sp1 - fwd * 11 + up * 1 - left * 3) - c, keep=pk, note='pack, lower back')
    c2, _ = info(eg, nz); Rh = np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]], float)
    add('weapon_egon', eg, 'Bip01 Pelvis', Rh, (pel - fwd * 9 + left * 9 + up * 4) - Rh @ c2, keep=nz, note='nozzle, left side')
    P('weapon_357 weapon_python', HL_P + 'p_357.mdl', 'Bip01 R Leg', n(-up * 0.95 + fwd * 0.15), fwd, rthigh, 'right thigh')
    P('weapon_9mmhandgun weapon_glock', HL_P + 'p_9mmhandgun.mdl', 'Bip01 R Leg', n(-up * 0.95 + fwd * 0.15), fwd, rthigh + fwd * 3.5 - up * 1, 'right thigh, front')
    P('weapon_tripmine', HL_P + 'p_tripmine.mdl', 'Bip01 L Leg', up, left, lthigh + fwd * 0.5, 'left thigh')
    P('weapon_handgrenade', HL_P + 'p_grenade.mdl', 'Bip01 Pelvis', up, left, pel + left * 6.5 + fwd * 1.5 + up * 1.0, 'left hip')
    P('weapon_hornetgun', HL_P + 'p_hgun.mdl', 'Bip01 Pelvis', n(-up), -left, pel + left * 8.5 - fwd * 2 - up * 3, 'left hip, hanging')
    P('weapon_snark', HL_P + 'p_squeak.mdl', 'Bip01 Pelvis', up, -left, pel - left * 6.5 + fwd * 1.0 + up * 1.5, 'right hip')
    P('weapon_satchel', HL_P + 'p_satchel.mdl', 'Bip01 Pelvis', up, back, pel - fwd * 6 - left * 3 - up * 1, 'lower back')
    # Opposing Force
    P('weapon_sniperrifle', OP_P + 'p_m40a1.mdl', 'Bip01 Spine2', n(up * 0.75 + left * 0.66), back, sp2 - fwd * 13 + up * 3, 'back, over the left shoulder')
    P('weapon_m249', OP_P + 'p_saw.mdl', 'Bip01 Spine1', n(-left * 0.95 + up * 0.3), back, sp1 - fwd * 13 - up * 2, 'across the back')
    P('weapon_sporelauncher', OP_P + 'p_spore_launcher.mdl', 'Bip01 Spine2', n(up * 0.8 - left * 0.6), back, sp2 - fwd * 14 - left * 4, 'back, over the right shoulder')
    P('weapon_shockrifle', OP_P + 'p_shock.mdl', 'Bip01 Spine1', n(-up * 0.6 - left * 0.8), back, sp1 - fwd * 12 + left * 6 - up * 4, 'back, hanging left')
    P('weapon_displacer', OP_P + 'p_displacer.mdl', 'Bip01 Pelvis', n(left), back, pel - fwd * 12 + up * 2, 'waist, behind')
    P('weapon_pipewrench', OP_P + 'p_pipe_wrench.mdl', 'Bip01 Spine3', n(-up * 0.9 - left * 0.3), back, sp3 - fwd * 7.5 - left * 5 - up * 3, 'back, upright right')
    P('weapon_eagle', OP_P + 'p_desert_eagle.mdl', 'Bip01 L Leg', n(-up * 0.95 + fwd * 0.15), fwd, lthigh + left * 0.5 - up * 3, 'left thigh')
    P('weapon_knife', OP_P + 'p_knife.mdl', 'Bip01 R Leg1', n(-up), -left, rcalf, 'right calf')
    P('weapon_grapple', OP_P + 'p_bgrap.mdl', 'Bip01 Pelvis', n(-up), left, pel - left * 9 - fwd * 1 - up * 3, 'right hip, hanging')
    P('weapon_penguin', OP_P + 'p_penguin.mdl', 'Bip01 Pelvis', up, left, pel + left * 7 + fwd * 4 + up * 0.5, 'left hip')


# one set of rows per weapon-model folder (HD and LD); identical files collapse
DIRS = sys.argv[2:] or [SRC + '/final_p/', SRC + '/ld_p/']
for d_ in DIRS:
    HL_P = OP_P = d_
    layout_rows()
seen, uniq = set(), []
for r in rows:
    key = (r[0], r[1], r[5], r[8])
    if key not in seen:
        seen.add(key); uniq.append(r)
rows = uniq

out = ['// fpbody_holsters.h - generated by tools/gmod_anims/holster_table.py',
       '// Where each carried weapon sits on the body: weapon class names, p_ model,',
       '// body bone, and the matrix taking the p_ model (frame 0) into that bone\'s space.',
       '// keep: bitmask of the p_ model\'s bones to draw (0 = all).',
       '', 'struct fpholster_def_t', '{', '\tconst char *weapons;\t// space separated class names',
       '\tconst char *model;', '\tconst char *bone;', '\tfloat local[ 3 ][ 4 ];', '\tunsigned int keep;', '\tint length;\t\t// the p_ model file\'s header length: picks the LD or HD row', '};', '',
       'static const fpholster_def_t g_holsterDefs[] =', '{']
for w, m, b, Rl, tl, mask, note, path, length in rows:
    mat = ', '.join('{ %s }' % ', '.join('%.5ff' % x for x in list(Rl[r]) + [tl[r]]) for r in range(3))
    out.append('\t{ "%s", "%s", "%s", { %s }, 0x%x, %d },\t// %s (%s)' % (w, m, b, mat, mask, length, note, 'Sven Co-op' if 'sven_p' in path else 'HD' if 'final_p' in path else 'LD'))
out += ['};', '']
open(sys.argv[1], 'w').write('\n'.join(out))
print(len(rows), 'holsters')

# self-check: reproduce the mock-up positions from the table
for w, m, b, Rl, tl, mask, note, path, length in rows[:3]:
    RA, TA = RB[b]
    print(w, 'world translation', np.round(RA @ tl + TA, 2))

# verify: model-space vertices through anchor * local must land where the mock-up put them
import re
maxerr = 0
for w, m, b, Rl, tl, mask, note, path, length in rows:
    keep = None if mask == 0 else {i for i in range(32) if mask >> i & 1}
    Gm = GoldSrcModel(path); Rg, Tg = Gm.world(Gm.decode(0)[0][0])
    _, tris = load_tris(path)
    RA, TA = RB[b]
    pts = []
    for bb, v, col in tris:
        if keep is not None and not all(x in keep for x in bb): continue
        for i in range(3):
            pm = Rg[bb[i]] @ v[i] + Tg[bb[i]]
            pts.append(RA @ (Rl @ pm + tl) + TA)
    pts = np.array(pts)
    print('%-28s centre %s' % (w, np.round((pts.min(0) + pts.max(0)) / 2, 1)))
