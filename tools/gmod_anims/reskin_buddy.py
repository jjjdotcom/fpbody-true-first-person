"""Give the fpbody companion (make_buddy.py's model) another character's body:
Half-Life: Decay's Colette (models/player/dm_colette/dm_colette.mdl) as the
companion of fpbody_decay (dlls/fpbody_buddy.inl, FPB_DECAY).

  python3 -I reskin_buddy.py <fpbody_buddy.mdl> <mesh.mdl> <out.mdl>

<mesh.mdl> is a model on Half-Life's player skeleton (Bip01 L Leg / Arm
names, like the companion's): its body parts (all of them, e.g. body + head)
become the companion's first body part; the companion's skeleton, sequences
(the guard's and the MP5 ones), hitboxes, attachments and gun body part (the
holstered / drawn revolver, the MP5) are kept. Each vertex keeps its place in
its bone's own frame (both skeletons are 3ds Max Biped: the same axes), on the
companion's bone of that name; bones the companion lacks (fingers, the
mouth) ride on the nearest ancestor it has. The result contains both models' data: keep it
local.
"""
import struct
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from goldsrc import GoldSrcModel               # noqa: E402
from merge_head import textures                # noqa: E402


def mesh_tris(d, bodyparts=None):
    """-> [(local verts, local normals, st, texture, bones)] of every body part's submodel 0"""
    nsr, nsf, si = struct.unpack_from('<3i', d, 192)
    skins = struct.unpack_from('<%dh' % nsr, d, si)
    out = []
    nbp, bpi = struct.unpack_from('<2i', d, 204)
    for bp in range(nbp):
        if bodyparts is not None and bp not in bodyparts:
            continue
        _, _, mi = struct.unpack_from('<3i', d, bpi + bp * 76 + 64)
        nummesh, meshindex, numverts, vinfo, vindex, numnorms, ninfo, nindex = struct.unpack_from('<8i', d, mi + 72)
        vb = d[vinfo:vinfo + numverts]
        nb = d[ninfo:ninfo + numnorms]
        vv = np.frombuffer(d[vindex:vindex + numverts * 12], '<f4').reshape(-1, 3).astype(float)
        nv = np.frombuffer(d[nindex:nindex + numnorms * 12], '<f4').reshape(-1, 3).astype(float)
        for m in range(nummesh):
            numtris, triindex, skinref, _, _ = struct.unpack_from('<5i', d, meshindex + m * 20)
            tex = skins[skinref]
            o = triindex
            while True:
                c = struct.unpack_from('<h', d, o)[0]; o += 2
                if c == 0:
                    break
                fan = c < 0; c = abs(c)
                vs = [struct.unpack_from('<4h', d, o + k * 8) for k in range(c)]; o += c * 8
                for k in range(2, c):
                    if fan:
                        t = (vs[0], vs[k - 1], vs[k])
                    elif k % 2:
                        t = (vs[k - 1], vs[k - 2], vs[k])
                    else:
                        t = (vs[k - 2], vs[k - 1], vs[k])
                    out.append((np.array([vv[v[0]] for v in t]), np.array([nv[v[1]] for v in t]),
                                [(v[2], v[3]) for v in t], tex, [vb[v[0]] for v in t]))
    return out


def main(buddy_path, mesh_path, out_path):
    B = GoldSrcModel(buddy_path)
    N = GoldSrcModel(mesh_path)
    base = bytearray(B.d)
    nd = bytes(N.d)
    btex, ntex = textures(bytes(base)), textures(nd)
    Rb, Tb = B.world(B.rest_local())
    Rn, Tn = N.world(N.rest_local())

    # mesh bone -> companion bone (itself by name, or its nearest ancestor that is)
    bmap = {}
    for i, b in enumerate(N.bones):
        a = i
        while a >= 0 and N.bones[a]['name'] not in B.bone_by_name:
            a = N.bones[a]['parent']
        bmap[i] = (B.bone_by_name[N.bones[max(a, 0)]['name']], max(a, 0))

    tris = []
    for P, Nn, st, tex, bones in mesh_tris(nd):
        LP, LN, LB = [], [], []
        for p, n, bi in zip(P, Nn, bones):
            tb, anc = bmap[bi]
            # in the matched bone's own frame (both are 3ds Max Biped exports:
            # the same axes); a bone the companion lacks rides on its ancestor
            w = Rn[bi] @ p + Tn[bi]
            LP.append(Rn[anc].T @ (w - Tn[anc]))
            LN.append(Rn[anc].T @ (Rn[bi] @ n))
            LB.append(tb)
        tris.append((np.array(LP), np.array(LN), st, tex + len(btex), LB))

    alltex = btex + ntex
    verts, norms, meshes = [], [], {}
    vkey, nkey, vbone, nbone = {}, {}, [], []
    for P, Nn, st, tex, bones in tris:
        tri = []
        for k in range(3):
            key = (bones[k],) + tuple(np.round(P[k], 4))
            if key not in vkey:
                vkey[key] = len(verts); verts.append(P[k]); vbone.append(bones[k])
            nk = (bones[k],) + tuple(np.round(Nn[k], 4))
            if nk not in nkey:
                nkey[nk] = len(norms); norms.append(Nn[k]); nbone.append(bones[k])
            tri.append((vkey[key], nkey[nk], int(st[k][0]), int(st[k][1])))
        meshes.setdefault(tex, []).append(tri)

    def align():
        while len(base) % 4:
            base.append(0)

    def put(b):
        align(); o = len(base); base.extend(b); return o

    # body parts: the new body, then the companion's own gun part (its data stays where it is)
    nbp, bpi = struct.unpack_from('<2i', base, 204)
    gun = [k for k in range(nbp) if base[bpi + k * 76:bpi + k * 76 + 64].split(b'\0')[0] == b'gun']
    if not gun:
        sys.exit('no gun body part in ' + buddy_path)
    gun_entry = bytearray(base[bpi + gun[0] * 76:bpi + gun[0] * 76 + 76])
    struct.pack_into('<i', gun_entry, 68, 1)              # base: after a one-model body part
    tex_hdr_off = put(bytes(80 * len(alltex)))
    skin_off = put(struct.pack('<%dh' % len(alltex), *range(len(alltex))))
    bp_off = put(bytes(76 * 2))
    model_off = put(bytes(112))
    vinfo = put(bytes(vbone)); ninfo = put(bytes(nbone))
    vindex = put(np.array(verts, '<f4').tobytes()); nindex = put(np.array(norms, '<f4').tobytes())
    mesh_off = put(bytes(20 * len(meshes)))
    for k, (tex, tl) in enumerate(sorted(meshes.items())):
        cmds = bytearray()
        for tri in tl:
            cmds += struct.pack('<h', 3)
            for v in tri:
                cmds += struct.pack('<4h', *v)
        cmds += struct.pack('<h', 0)
        tri_off = put(bytes(cmds))
        struct.pack_into('<5i', base, mesh_off + k * 20, len(tl), tri_off, tex, len(norms), nindex)
    radius = float(np.max(np.linalg.norm(np.array(verts), axis=1)))
    struct.pack_into('<64sif8i2i', base, model_off, b'body'.ljust(64, b'\0'), 0, radius,
                     len(meshes), mesh_off, len(verts), vinfo, vindex, len(norms), ninfo, nindex, 0, 0)
    struct.pack_into('<64s3i', base, bp_off, b'body'.ljust(64, b'\0'), 1, 1, model_off)
    base[bp_off + 76:bp_off + 152] = gun_entry
    struct.pack_into('<2i', base, 204, 2, bp_off)
    align()
    tex_data_off = len(base)
    for k, t in enumerate(alltex):
        data_off = put(t['pix'] + t['pal'])
        nm = t['name'][:63]
        struct.pack_into('<64s4i', base, tex_hdr_off + k * 80, nm + bytes(64 - len(nm)), t['flags'], t['w'], t['h'], data_off)
    struct.pack_into('<6i', base, 180, len(alltex), tex_hdr_off, tex_data_off, len(alltex), 1, skin_off)
    struct.pack_into('<i', base, 72, len(base))
    n = out_path.rsplit('/', 1)[-1].encode()[:63]
    base[8:72] = n + bytes(64 - len(n))
    tmp = out_path + '.tmp'
    open(tmp, 'wb').write(base)
    from compact import compact
    compact(tmp, out_path)
    import os
    os.remove(tmp)
    print('wrote', out_path, len(tris), 'triangles,', len(alltex), 'textures')


if __name__ == '__main__':
    main(*sys.argv[1:4])
