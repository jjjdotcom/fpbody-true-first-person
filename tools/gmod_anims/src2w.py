"""Turn a Source (Garry's Mod) weapon world model into a Half-Life one.

  python3 -I src2w.py <source w_model.mdl> <reference GoldSrc w_model.mdl> <out.mdl> [material root ...]

The Source model's triangles (body 0 of every body part, LOD 0) are fitted onto
the reference world model - the one the game uses now - with a uniform scale,
rotation and translation (tried from all 24 orientations of the principal
axes, refined by ICP), so the new model lies where and how the old one did.
It is written with the reference's skeleton and sequences, every vertex on its
first bone, with the Source materials converted to 8-bit textures.
The result contains the Source model's data: keep it local.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from srcmesh import SourceMesh                     # noqa: E402
from hls_body import convert_textures              # noqa: E402
from vm2p import ref_hand_points, sample, fit   # noqa: E402
import struct
from goldsrc import GoldSrcModel                   # noqa: E402


def rest_tris(G):
    """the reference's triangles in its rest pose"""
    d = bytes(G.d)
    R, T = G.world(G.rest_local())
    out = []
    nbp, bpi = struct.unpack_from('<2i', d, 204)
    for bp in range(nbp):
        _, _, mi = struct.unpack_from('<3i', d, bpi + bp * 76 + 64)
        nummesh, meshindex, numverts, vinfo, vindex = struct.unpack_from('<5i', d, mi + 72)
        vbn = d[vinfo:vinfo + numverts]
        vv = np.frombuffer(d[vindex:vindex + numverts * 12], '<f4').reshape(-1, 3).astype(float)
        for m in range(nummesh):
            numtris, triindex = struct.unpack_from('<2i', d, meshindex + m * 20)
            o = triindex
            while True:
                c = struct.unpack_from('<h', d, o)[0]; o += 2
                if c == 0:
                    break
                fan = c < 0; c = abs(c)
                vs = [struct.unpack_from('<4h', d, o + k * 8)[0] for k in range(c)]; o += c * 8
                for k in range(2, c):
                    idx = (vs[0], vs[k - 1], vs[k]) if fan else (vs[k - 2], vs[k - 1], vs[k])
                    out.append(np.array([R[vbn[i]] @ vv[i] + T[vbn[i]] for i in idx]))
    return out


class _Tex:
    """the texture list vm2p.write expects"""
    def __init__(self, conv):
        self.textures = [dict(name=n.encode('latin-1')[:63], flags=f, w=w, h=h, pix=p, pal=pal)
                         for n, f, w, h, p, pal in conv]


def source_tris(S):
    """-> [(3 verts, 3 normals, 3 (u, v), material, 3 bones)] of body 0 of every body part (bind pose)"""
    out = []
    for mat, tris, bp, m in S.meshes:
        if m != 0:
            continue
        for t in tris:
            V = [S.vertices[i] for i in t]
            out.append((np.array([v['pos'] for v in V], float), np.array([v['normal'] for v in V], float),
                        [tuple(v['uv']) for v in V], mat,
                        [max(v['bones'], key=lambda bw: bw[1])[0] for v in V]))
    return out


def write_skinned(ref_path, tris_out, S, out_path):
    """vm2p.write with a bone per vertex: tris_out = [(P, N, st, tex, bones)]"""
    G = GoldSrcModel(ref_path)
    base = bytearray(G.d)
    # cut the reference's own textures / bodyparts: rebuild from the header's
    # bone/sequence data, which compose-style writes leave in place
    texmap, textures = {}, []
    verts, norms, meshes = [], [], {}
    vkey, nkey = {}, {}
    vbone, nbone = [], []
    for P, N, st, tex, bones in tris_out:
        if tex not in texmap:
            texmap[tex] = len(textures); textures.append(S.textures[tex])
        tri = []
        for k in range(3):
            key = (bones[k],) + tuple(np.round(P[k], 4))
            if key not in vkey:
                vkey[key] = len(verts); verts.append(P[k]); vbone.append(bones[k])
            nk = (bones[k],) + tuple(np.round(N[k], 4))
            if nk not in nkey:
                nkey[nk] = len(norms); norms.append(N[k]); nbone.append(bones[k])
            tri.append((vkey[key], nkey[nk], int(st[k][0]), int(st[k][1])))
        meshes.setdefault(texmap[tex], []).append(tri)

    def align():
        while len(base) % 4:
            base.append(0)

    def put(b):
        align(); o = len(base); base.extend(b); return o

    tex_hdr_off = put(bytes(80 * len(textures)))
    skin_off = put(struct.pack('<%dh' % len(textures), *range(len(textures))))
    bp_off = put(bytes(76))
    model_off = put(bytes(112))
    vinfo = put(bytes(vbone))
    ninfo = put(bytes(nbone))
    vindex = put(np.array(verts, '<f4').tobytes())
    nindex = put(np.array(norms, '<f4').tobytes())
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
    struct.pack_into('<64sif8i2i', base, model_off, b'weapon'.ljust(64, b'\0'), 0, radius,
                     len(meshes), mesh_off, len(verts), vinfo, vindex, len(norms), ninfo, nindex, 0, 0)
    struct.pack_into('<64s3i', base, bp_off, b'studio'.ljust(64, b'\0'), 1, 1, model_off)
    struct.pack_into('<2i', base, 204, 1, bp_off)
    align()
    tex_data_off = len(base)
    for k, t in enumerate(textures):
        data_off = put(t['pix'] + t['pal'])
        nm = t['name'][:63]
        struct.pack_into('<64s4i', base, tex_hdr_off + k * 80, nm + bytes(64 - len(nm)),
                         t['flags'], t['w'], t['h'], data_off)
    struct.pack_into('<6i', base, 180, len(textures), tex_hdr_off, tex_data_off, len(textures), 1, skin_off)
    struct.pack_into('<i', base, 72, len(base))
    n = out_path.rsplit('/', 1)[-1].encode()[:63]
    base[8:72] = n + bytes(64 - len(n))
    open(out_path, 'wb').write(base)
    return len(verts), sum(len(t) for t in meshes.values()), len(textures), len(base)


def convert(src_path, ref_path, out_path, roots=()):
    S = SourceMesh(src_path, list(roots))
    tris = source_tris(S)
    used = sorted({t[3] for t in tris})
    conv = convert_textures(S, skip=set(range(len(S.materials))) - set(used))
    # a material the model names but doesn't ship (it shows as the missing-texture
    # checkerboard in Garry's Mod): a plain dark one instead of the converter's grey
    for k in used:
        im, _ = S.load_texture(k)
        if im is None:
            n = conv[k][0]
            conv[k] = (n, 0, 8, 8, bytes(64), bytes([34, 34, 36] * 256))
            print('  no texture for', n, '- dark')
    T = _Tex(conv)
    G = GoldSrcModel(ref_path)
    gb = {b['name'].lower(): i for i, b in enumerate(G.bones)}
    sb = [gb.get(b['name'].lower(), -1) for b in S.bones]
    skinned = len(S.bones) > 1 and sum(1 for x in sb if x >= 0) * 2 >= len(S.bones)
    if skinned:
        # same skeleton (a port of the same model): fit in the rest pose and keep
        # each vertex on its bone, so the reference's animations still move it
        R0, T0 = G.world(G.rest_local())
        rtris = rest_tris(G)
    else:
        # a static mesh: fit onto the reference's first frame, all on its first bone
        _, _, rtris = ref_hand_points(ref_path)
        R0, T0 = G.world(G.decode(0)[0][0])
        rtris = [(P - T0[0]) @ R0[0] for P in rtris]
    src = sample([t[0] for t in tris])
    ref = sample(rtris)
    err, s, Rm, t = fit(src, ref)
    size = float(np.linalg.norm(ref.max(0) - ref.min(0)))
    out = []
    for P, N, uv, mat, vb in tris:
        w, h = T.textures[mat]['w'], T.textures[mat]['h']
        st = [(int(round(u * w)), int(round(v * h))) for u, v in uv]
        P2, N2 = s * P @ Rm.T + t, N @ Rm.T
        if skinned:
            bones = [sb[b] if sb[b] >= 0 else 0 for b in vb]
            P2 = np.array([R0[b].T @ (P2[k] - T0[b]) for k, b in enumerate(bones)])
            N2 = np.array([R0[b].T @ N2[k] for k, b in enumerate(bones)])
        else:
            bones = [0, 0, 0]
        out.append((P2, N2, st, mat, bones))
    info = write_skinned(ref_path, out, T, out_path)
    return dict(err=round(err, 3), rel=round(err / size, 4), scale=round(s, 3), size=round(size, 1),
                verts=info[0], tris=info[1], textures=info[2], bytes=info[3])


if __name__ == '__main__':
    print(convert(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]))
