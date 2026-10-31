"""Turn a weapon viewmodel (v_*.mdl) into a player world model (p_*.mdl).

  python3 -I vm2p.py <v_model> <reference p_model> <out p_model>

1. keeps the weapon's triangles (drops the arms: hand / skin / glove / sleeve
   textures), with every submodel taken at its fullest variant
2. freezes the weapon in the viewmodel's idle pose
3. fits it onto the reference world model (the one the game shipped for this
   weapon), so it sits in the player's hand where the player animations expect:
   uniform scale + rotation + translation, tried from all 24 axis orientations
   of its principal axes and refined by ICP, scored by surface distance
4. writes a p_ model with the reference's skeleton and sequence, every vertex
   on the reference's right-hand bone, textures copied from the viewmodel
"""
import itertools
import struct
import sys

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from compose import Source            # noqa: E402
from goldsrc import GoldSrcModel     # noqa: E402

ARM_TEX = {'hand.bmp', 'skin.bmp', 'fatigues.bmp', 'gordon_glove.bmp', 'gordon_sleeve.bmp',
           'rubberglovechrome.bmp'}


def idle_pose(m):
    for want in ('idle1', 'idle', 'slowidle', 'breathe'):
        for i, s in enumerate(m.seqs):
            if s['label'].lower() == want:
                return m.decode(i)[0][0]
    return m.decode(0)[0][0]


def weapon_tris(S):
    """-> list of (3 world verts, 3 world normals, 3 (s,t), texture index)"""
    R, T = S.m.world(idle_pose(S.m))
    d = S.d
    nbp = struct.unpack_from('<i', d, 204)[0]
    out = []
    for bp in range(nbp):
        bpi = struct.unpack_from('<i', d, 208)[0]
        nm = struct.unpack_from('<i', d, bpi + bp * 76 + 64)[0]
        best = None
        for k in range(nm):
            mdl = S.model(bp, k)
            tris = []
            for mesh in mdl['meshes']:
                if S.textures[mesh['tex']]['name'].decode('latin-1').lower() in ARM_TEX:
                    continue
                for tri in mesh['tris']:
                    P = np.array([R[mdl['vb'][v[0]]] @ mdl['vv'][v[0]] + T[mdl['vb'][v[0]]] for v in tri])
                    N = np.array([R[mdl['nb'][v[1]]] @ mdl['nv'][v[1]] for v in tri])
                    tris.append((P, N, [(v[2], v[3]) for v in tri], mesh['tex']))
            if best is None or len(tris) > len(best):
                best = tris
        out += best or []
    return out


def ref_hand_points(path):
    """reference p_ model triangles in its right-hand bone frame (= hand-bone local coords)"""
    G = GoldSrcModel(path)
    d = bytes(G.d)
    R, T = G.world(G.decode(0)[0][0])
    hi = G.bone_by_name.get('Bip01 R Hand')
    tris = []
    nbp, bpi = struct.unpack_from('<2i', d, 204)
    for bp in range(nbp):
        _, _, mi = struct.unpack_from('<3i', d, bpi + bp * 76 + 64)
        nummesh, meshindex, numverts, vinfo, vindex = struct.unpack_from('<5i', d, mi + 72)
        vb = d[vinfo:vinfo + numverts]
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
                    P = np.array([R[vb[i]] @ vv[i] + T[vb[i]] for i in idx])
                    if hi is not None:
                        P = (P - T[hi]) @ R[hi]
                    tris.append(P)
    return G, hi, tris


def sample(tris, n=4000, seed=1):
    """area-weighted surface samples"""
    tris = np.array(tris)
    a = 0.5 * np.linalg.norm(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1)
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(tris), n, p=a / a.sum())
    u, v = rng.random(n), rng.random(n)
    flip = u + v > 1; u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
    t = tris[pick]
    return t[:, 0] + u[:, None] * (t[:, 1] - t[:, 0]) + v[:, None] * (t[:, 2] - t[:, 0])


def frame(pts):
    c = pts.mean(0)
    _, s, vt = np.linalg.svd(pts - c, full_matrices=False)
    return c, vt, s


def chamfer(A, B, tb):
    da, _ = tb.query(A)
    db, _ = cKDTree(A).query(B)
    return 0.5 * (np.mean(da) + np.mean(db))


def fit(src, ref):
    """similarity transform (s, R, t) taking src samples onto ref samples"""
    tb = cKDTree(ref)
    cs, Vs, _ = frame(src)
    cr, Vr, _ = frame(ref)
    best = None
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((1, -1), repeat=3):
            M = np.zeros((3, 3))
            for i in range(3):
                M[i, perm[i]] = signs[i]
            if np.linalg.det(M) < 0:
                continue
            Rm = Vr.T @ M @ Vs                     # src principal frame -> ref principal frame
            ps, pr = (src - cs) @ Rm.T, ref - cr
            s = np.sqrt((pr ** 2).sum(1).mean() / (ps ** 2).sum(1).mean())
            R_, t_, s_ = Rm, cr - s * Rm @ cs, s
            for _ in range(30):                   # ICP with uniform scale (Umeyama)
                cur = s_ * src @ R_.T + t_
                _, j = tb.query(cur)
                tgt = ref[j]
                mu_s, mu_t = src.mean(0), tgt.mean(0)
                X, Y = src - mu_s, tgt - mu_t
                U, D, Wt = np.linalg.svd(Y.T @ X / len(src))
                S_ = np.eye(3)
                if np.linalg.det(U) * np.linalg.det(Wt) < 0:
                    S_[2, 2] = -1
                R_ = U @ S_ @ Wt
                s_ = np.trace(np.diag(D) @ S_) / (X ** 2).sum(1).mean()
                t_ = mu_t - s_ * R_ @ mu_s
            err = chamfer(s_ * src @ R_.T + t_, ref, tb)
            if best is None or err < best[0]:
                best = (err, s_, R_, t_)
    return best


def write(ref_path, hi, tris_out, S, out_path):
    """p_ model: reference skeleton + sequence, one bodypart, all verts on the hand bone"""
    G = GoldSrcModel(ref_path)
    base = bytearray(G.d)
    # cut the reference's own textures / bodyparts: rebuild from the header's
    # bone/sequence data, which compose-style writes leave in place
    texmap, textures = {}, []
    verts, norms, meshes = [], [], {}
    vkey, nkey = {}, {}
    for P, N, st, tex in tris_out:
        if tex not in texmap:
            texmap[tex] = len(textures); textures.append(S.textures[tex])
        tri = []
        for k in range(3):
            key = tuple(np.round(P[k], 4))
            if key not in vkey:
                vkey[key] = len(verts); verts.append(P[k])
            nk = tuple(np.round(N[k], 4))
            if nk not in nkey:
                nkey[nk] = len(norms); norms.append(N[k])
            tri.append((vkey[key], nkey[nk], int(st[k][0]), int(st[k][1])))
        meshes.setdefault(texmap[tex], []).append(tri)

    def align():
        while len(base) % 4:
            base.append(0)

    def put(b):
        align(); o = len(base); base.extend(b); return o

    hb = 0 if hi is None else hi
    tex_hdr_off = put(bytes(80 * len(textures)))
    skin_off = put(struct.pack('<%dh' % len(textures), *range(len(textures))))
    bp_off = put(bytes(76))
    model_off = put(bytes(112))
    vinfo = put(bytes([hb] * len(verts)))
    ninfo = put(bytes([hb] * len(norms)))
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


def convert(v_path, ref_path, out_path):
    S = Source(v_path)
    wt = weapon_tris(S)
    G, hi, rtris = ref_hand_points(ref_path)
    src = sample([t[0] for t in wt])
    ref = sample(rtris)
    err, s, R, t = fit(src, ref)
    size = np.linalg.norm(ref.max(0) - ref.min(0))
    out = [((s * P @ R.T + t), (N @ R.T), st, tex) for P, N, st, tex in wt]
    info = write(ref_path, hi, out, S, out_path)
    return dict(err=err, rel=err / size, scale=s, size=size, verts=info[0], tris=info[1], tex=info[2], bytes=info[3])


if __name__ == '__main__':
    print(convert(*sys.argv[1:4]))
