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
    while anc >= 0 and target_name(N.bones[anc]['name']) not in P.bone_by_name:
        anc = N.bones[anc]['parent']
    if anc < 0:
        anc = 0
    bone_map[i] = (P.bone_by_name[target_name(N.bones[anc]['name'])], anc)
unmapped = [N.bones[i]['name'] for i in bone_map if bone_map[i][1] != i]
print('rigid-attached to an ancestor:', unmapped)

Rn, Tn = N.world(N.rest_local())
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
    Y = X
    tex_hdr = struct.unpack_from('<6i', N.d, 180)
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
