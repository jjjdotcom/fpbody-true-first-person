"""Put another Half-Life model's mesh on the fpbody player skeleton.

  python3 -I build_outfit.py <player.mdl> <mesh.mdl> <meshT.mdl|-> <out.mdl>

<player.mdl> is the converted fpbody player model: its skeleton, sequences
(GMod + procedural-ready), hitboxes and attachments are kept as they are.
<mesh.mdl> (e.g. Blue Shift's gordon_scientist.mdl, an NPC with a
differently named Biped skeleton) provides the body parts and, with its
T model, the textures. Every vertex and normal is moved from its own bone's
rest frame to the matching player bone: the offset from the joint keeps its
world-space direction and length, and follows the player's joint position, so
each limb segment stays attached to the joint it bends around.
"""
import struct
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from goldsrc import GoldSrcModel   # noqa: E402

player_path, mesh_path, tex_path, out_path = sys.argv[1:5]
# --blend: move each vertex by the joints' moves blended along the bones near it
# (instead of rigidly with its own joint), so a mesh made for other proportions
# (a Half-Life player on the Garry's Mod-proportioned skeleton) stretches to fit
# with no dents or gaps where body parts meet (hips, shoulders)
BLEND = '--blend' in sys.argv[5:]
# --hips <s>: with --blend, the hips and thighs' depth (front to back) scaled
# to s (full at the hips, none at the knees and the waist)
# --hipback <u> / --torso <u>: with --blend, the hips moved back and the torso
# moved forward by u units (fading out toward the knees / the waist and neck),
# for a Half-Life mesh whose torso sits behind its hips on the Garry's
# Mod-proportioned skeleton (whose spine is further back)
HIPS = float(sys.argv[sys.argv.index('--hips') + 1]) if '--hips' in sys.argv else 1.0
HIPBACK = float(sys.argv[sys.argv.index('--hipback') + 1]) if '--hipback' in sys.argv else 0.0
TORSO = float(sys.argv[sys.argv.index('--torso') + 1]) if '--torso' in sys.argv else 0.0
P = GoldSrcModel(player_path)
N = GoldSrcModel(mesh_path)


def target_name(name):
    t = (name.replace('Thigh', 'Leg').replace('Calf', 'Leg1').replace('Clavicle', 'Arm')
         .replace('UpperArm', 'Arm1').replace('Forearm', 'Arm2'))
    for s in 'LR':
        t = t.replace(s + ' Finger2', s + ' Finger1')
        t = t.replace(s + ' Finger3', s + ' Finger1').replace(s + ' Finger4', s + ' Finger1')
    return t


# mesh bone -> (player bone, mesh bone whose joint it is measured from)
bone_map = {}
for i, b in enumerate(N.bones):
    j, anc = i, i
    # only Biped bones match by name: helper bones (Dummy05, Bone02...) mean
    # different things in different models (the HD scientist's jaw hangs off its
    # Dummy05, the player's Dummy05 is somewhere else entirely)
    while anc >= 0 and (not N.bones[anc]['name'].startswith('Bip01') or
                        target_name(N.bones[anc]['name']) not in P.bone_by_name):
        anc = N.bones[anc]['parent']
    if anc < 0:
        anc = 0
    bone_map[i] = (P.bone_by_name[target_name(N.bones[anc]['name'])], anc)
unmapped = [N.bones[i]['name'] for i in bone_map if bone_map[i][1] != i]
print('rigid-attached to an ancestor:', unmapped)

Rn, Tn = N.world(N.rest_local())
# --pose <seq>: bones the player skeleton doesn't have (a jaw, a tie...) are
# placed as in that sequence's first frame, relative to the bone they ride on,
# instead of in their rest pose (the HD scientist's jaw rests wide open)
if '--pose' in sys.argv:
    _pr, _pt = N.world(N.decode(N.seq_by_name[sys.argv[sys.argv.index('--pose') + 1]])[0][0])
    for _i, _b in enumerate(N.bones):
        _a = _i
        while _a >= 0 and (not N.bones[_a]['name'].startswith('Bip01') or
                           target_name(N.bones[_a]['name']) not in P.bone_by_name):
            _a = N.bones[_a]['parent']
        if _a >= 0 and _a != _i:
            _k = Rn[_a] @ _pr[_a].T
            Rn[_i] = _k @ _pr[_i]
            Tn[_i] = Tn[_a] + _k @ (_pt[_i] - _pt[_a])
Rp, Tp = P.world(P.rest_local())

base = bytearray(P.d)
mesh = bytearray(N.d)
texm = bytearray(open(tex_path, 'rb').read()) if tex_path != '-' else mesh


def align(buf):
    while len(buf) % 16:
        buf.append(0)


# ---------------------------------------------------------------- rebind mesh
nbp, bpi = struct.unpack_from('<2i', mesh, 204)
models = []
for bp in range(nbp):
    nm, _, mi = struct.unpack_from('<3i', mesh, bpi + bp * 76 + 64)
    models += [mi + k * 112 for k in range(nm)]

# joint moves (player joint - mesh joint, world rest pose) and the bone segments
mapped = [i for i in bone_map if bone_map[i][1] == i]
move = {i: Tp[bone_map[i][0]] - Tn[i] for i in mapped}
segs = []
for i in mapped:
    kids = [c for c in mapped if N.bones[c]['parent'] == i]
    for c in kids:
        segs.append((i, c))
    if not kids:
        segs.append((i, i))


def blended(p):
    best = []
    for a, b in segs:
        A, B = Tn[a], Tn[b]
        ab = B - A
        L = float(ab @ ab)
        t = 0.0 if L < 1e-6 else float(np.clip((p - A) @ ab / L, 0.0, 1.0))
        d = float(np.linalg.norm(p - (A + t * ab)))
        best.append((d, (1 - t) * move[a] + t * move[b]))
    dmin = min(d for d, _ in best)
    ws = np.array([np.exp(-(d - dmin) / 1.5) for d, _ in best])
    return sum(w * m for w, (_, m) in zip(ws, best)) / ws.sum()


arms = set()
for i, b in enumerate(N.bones):
    if target_name(b['name']) in ('Bip01 L Arm', 'Bip01 R Arm') or b['parent'] in arms:
        arms.add(i)
_pz = Tn[[i for i in mapped if target_name(N.bones[i]['name']) == 'Bip01 Pelvis'][0]][2]
_kz = Tn[[i for i in mapped if target_name(N.bones[i]['name']) == 'Bip01 L Leg1'][0]][2]


def hip_weight(z):
    lo, hi = _kz + 2.0, _pz + 7.0                     # knees .. waist
    if z <= lo or z >= hi:
        return 0.0
    if z < _pz - 6.0:
        return (z - lo) / (_pz - 6.0 - lo)
    if z > _pz + 3.0:
        return (hi - z) / (hi - _pz - 3.0)
    return 1.0


_nz = Tn[[i for i in mapped if target_name(N.bones[i]['name']) == 'Bip01 Neck'][0]][2]


def torso_weight(z):
    lo, top = _pz + 3.0, _nz                         # above the hips .. the neck
    if z <= lo or z >= top:
        return 0.0
    return min(1.0, (z - lo) / 9.0, (top - z) / 4.0)


for mo in models:
    (nummesh, meshindex, numverts, vinfo, vindex,
     numnorms, ninfo, nindex) = struct.unpack_from('<8i', mesh, mo + 72)
    for arr_info, arr, count, is_norm in ((vinfo, vindex, numverts, False), (ninfo, nindex, numnorms, True)):
        for k in range(count):
            nb = mesh[arr_info + k]
            pb, anc = bone_map[nb]
            v = np.array(struct.unpack_from('<3f', mesh, arr + k * 12))
            if is_norm:
                w = Rn[nb] @ v
                out = Rp[pb].T @ w
            elif BLEND:
                pw = Rn[nb] @ v + Tn[nb]               # world rest position
                q = pw + blended(pw)
                if nb not in arms:
                    q[1] *= 1.0 - (1.0 - HIPS) * hip_weight(pw[2])
                    # the rest pose faces -y: forward is -y
                    q[1] += HIPBACK * hip_weight(pw[2]) - TORSO * torso_weight(pw[2])
                out = Rp[pb].T @ (q - Tp[pb])
            else:
                w = Rn[nb] @ v + Tn[nb] - Tn[anc]    # offset from the joint, world space
                out = Rp[pb].T @ w
            struct.pack_into('<3f', mesh, arr + k * 12, *out)
            mesh[arr_info + k] = pb

# ---------------------------------------------------------------- relocate + append
align(base)
X = len(base)
for bp in range(nbp):
    o = bpi + bp * 76
    nm, b, mi = struct.unpack_from('<3i', mesh, o + 64)
    struct.pack_into('<i', mesh, o + 72, mi + X)
for mo in models:
    f = list(struct.unpack_from('<8i', mesh, mo + 72))
    for k in (1, 3, 4, 6, 7):
        if f[k]:
            f[k] += X
    nummesh, meshindex = f[0], f[1] - X
    for m in range(nummesh):
        so = meshindex + m * 20
        numtris, triindex, skinref, nn, normindex = struct.unpack_from('<5i', mesh, so)
        struct.pack_into('<5i', mesh, so, numtris, triindex + X, skinref, nn, normindex + X)
    groupindex = struct.unpack_from('<i', mesh, mo + 108)[0]
    struct.pack_into('<8i', mesh, mo + 72, *f)
    if groupindex:
        struct.pack_into('<i', mesh, mo + 108, groupindex + X)
base += mesh

if texm is mesh:
    # the textures came along with the mesh: their pixel data moved by X too
    Y = X
    tex_hdr = struct.unpack_from('<6i', N.d, 180)
    ntex, ti = tex_hdr[0], tex_hdr[1]
    for t in range(ntex):
        o = X + ti + t * 80 + 76
        struct.pack_into('<i', base, o, struct.unpack_from('<i', base, o)[0] + X)
else:
    align(base)
    Y = len(base)
    tex_hdr = struct.unpack_from('<6i', texm, 180)
    ntex, ti = tex_hdr[0], tex_hdr[1]
    for t in range(ntex):
        o = ti + t * 80 + 76
        struct.pack_into('<i', texm, o, struct.unpack_from('<i', texm, o)[0] + Y)
    base += texm

ntex, ti, tdi, nsr, nsf, si = tex_hdr
struct.pack_into('<6i', base, 180, ntex, ti + Y, tdi + Y, nsr, nsf, si + Y)
struct.pack_into('<2i', base, 204, nbp, bpi + X)
struct.pack_into('<i', base, 72, len(base))
name = b'fpbody_scientist.mdl'
base[8:72] = name + bytes(64 - len(name))
open(out_path, 'wb').write(base)
print('wrote', out_path, len(base), 'bytes;', len(models), 'models,', ntex, 'textures')
