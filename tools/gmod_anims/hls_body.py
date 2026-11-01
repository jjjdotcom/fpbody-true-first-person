"""Put a Garry's Mod playermodel (Source, ValveBiped skeleton) on an fpbody
GMod-mode player model, with the skeleton re-proportioned to fit it.

  python3 -I hls_body.py <base.mdl> <source.mdl> <out.mdl> <ref m_anm_gmod.mdl> \
        [--roots dir,dir,...] [--body part=index,...]

<base.mdl> is a converted fpbody model with the Garry's Mod animations
(fpbody/models/player.mdl, fpbody_suit.mdl ...): its bones, sequences,
hitboxes and attachments are kept. Its animations were retargeted from Garry's
Mod's player skeleton (retarget.py: each Bip01 bone turns like its ValveBiped
counterpart, but keeps Half-Life's bone lengths). Playermodels such as the
Half-Life: Source / Blue Shift / Opposing Force ones are skinned to that same
ValveBiped skeleton, so this:

  1. gives every mapped Bip01 bone the ValveBiped bone's offset from its parent
     (in the frame the retargeted animations turn it in), and undoes the height
     scale on the root, in every sequence - the skeleton now has Garry's Mod's
     proportions and the animations play as they did in Garry's Mod;
  2. binds the mesh to it: each vertex to its heaviest bone (Half-Life has one
     bone per vertex), in the bind pose, which is the reference rest pose;
  3. converts the materials (VMT/VTF) to 8-bit textures, every skin family.

--body picks one submodel per body part (e.g. Armor=1,Helmet=1); empty
submodels are dropped. --head <model> [--head-body ...] takes the head from
another playermodel on the same skeleton (the triangles skinned to the head
replace the main model's), and --tint <hue> recolours the main model's orange
(an HEV suit) to that hue in degrees (215 blue, 95 olive green). The result contains the playermodel's data: keep it
local.
"""
import argparse
import struct
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from goldsrc import GoldSrcModel                  # noqa: E402
from srcmdl import SourceModel, quat_to_mat, euler_to_quat   # noqa: E402
from srcmesh import SourceMesh                    # noqa: E402
from add_cz import existing_sequences, textures_last   # noqa: E402
from add_freeman import PackRetargeter            # noqa: E402
import retarget                                   # noqa: E402

ZOFF = -36.0
STUDIO_NF_CHROME = 2
STUDIO_NF_MASKED = 0x40


def emat(e):
    return quat_to_mat(euler_to_quat(*e))


def build_skeleton(P, ref):
    """New local positions and the bind pose (world R, T) of P's bones."""
    rt = PackRetargeter(ref, P, ref)
    rest = P.rest_local()
    n = P.numbones
    tgt_of_src = {}
    for ti, si in rt.pairs:
        tgt_of_src[si] = ti
    W = np.zeros((n, 3, 3)); X = np.zeros((n, 3))
    newpos = rest[:, :3].copy()
    root, pelvis = rt.root, rt.pelvis_t
    for i, b in enumerate(P.bones):
        p = b['parent']
        if i == root:
            W[i] = rt.Rt0[i]
            X[i] = rt.Ts0[rt.pelvis_s] + np.array([0, 0, ZOFF])
            continue
        if i in rt.src_of:
            W[i] = rt.C[i] @ rt.Rt0[i]
            if p in rt.src_of:
                newpos[i] = W[p].T @ (rt.Ts0[rt.src_of[i]] - rt.Ts0[rt.src_of[p]])
        else:
            W[i] = W[p] @ emat(rest[i, 3:6])
        X[i] = W[p] @ newpos[i] + X[p]
    return rt, newpos, W, X


def resequence(P, seqs, rt, newpos):
    """Every sequence on the re-proportioned skeleton."""
    mapped = [i for i in rt.src_of if P.bones[i]['parent'] in rt.src_of]
    for s in seqs:
        s['linearmovement'] = [v / rt.scale for v in s['linearmovement']]
        for arr in s['frames']:
            arr[:, mapped, :3] = newpos[mapped]
            r = arr[:, rt.root, :3]
            r[:, 2] -= ZOFF
            r /= rt.scale
            r[:, 2] += ZOFF
            arr[:, rt.root, :3] = r
    for i in mapped:
        P.bones[i]['value'][:3] = newpos[i]
        bo = P.boneindex + i * 112
        struct.pack_into('<3f', P.d, bo + 64, *newpos[i])


def quantize(im, masked):
    from PIL import Image
    w, h = im.size
    if w > 512 or h > 512:
        k = 512.0 / max(w, h)
        im = im.resize((max(8, int(w * k)), max(8, int(h * k))), Image.LANCZOS)
        w, h = im.size
    # GoldSrc uploads only textures whose sides are multiples of 4 ("GL_Upload16: s&3")
    w4 = max(8, (w + 3) // 4 * 4); h4 = max(8, (h + 3) // 4 * 4)
    if (w4, h4) != (w, h):
        im = im.resize((w4, h4), Image.NEAREST if w < 8 or h < 8 else Image.LANCZOS)
        w, h = w4, h4
    rgb = im.convert('RGB')
    if masked:
        q = rgb.quantize(255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        pix = np.array(q, np.uint8)
        a = np.array(im.split()[3])
        pix[a < 128] = 255
        pal = (q.getpalette() + [0] * 768)[:765] + [0, 0, 255]
    else:
        q = rgb.quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        pix = np.array(q, np.uint8)
        pal = (q.getpalette() + [0] * 768)[:768]
    return w, h, pix.tobytes(), bytes(pal)


def tint(im, hue, sat=1.0):
    """Orange (an HEV suit) -> another hue; skin, greys and dark parts stay."""
    from PIL import Image
    a = im.split()[3]
    hsv = np.array(im.convert('RGB').convert('HSV')).astype(float)
    h = hsv[..., 0] * 360.0 / 255.0
    m = (h >= 8) & (h <= 50) & (hsv[..., 1] > 90) & (hsv[..., 2] > 40)
    hsv[..., 0][m] = hue * 255.0 / 360.0
    hsv[..., 1][m] = np.clip(hsv[..., 1][m] * sat, 0, 255)
    out = Image.fromarray(hsv.astype(np.uint8), 'HSV').convert('RGBA')
    out.putalpha(a)
    return out


def convert_textures(S, hue=None, sat=1.0, skip=()):
    from PIL import Image
    out = []
    for k, name in enumerate(S.materials):
        if k in skip:
            out.append((name, 0, 8, 8, bytes(64), bytes(768)))      # not used by any triangle
            continue
        im, keys = S.load_texture(k)
        if im is not None and hue is not None:
            im = tint(im, hue, sat)
        flags = 0
        if im is None and '$envmap' in keys:
            # chrome without a base texture: the environment map as Half-Life chrome
            env = keys['$envmap'].replace('\\', '/').lower()
            from srcmesh import _find_ci, read_vtf
            for r in S.roots:
                p = _find_ci(r, 'materials/' + env + '.vtf')
                if p:
                    try:
                        im = read_vtf(p)
                    except Exception:
                        im = None
                    break
            flags |= STUDIO_NF_CHROME
        if im is None:
            print('  no texture for', name, '- grey')
            im = Image.new('RGBA', (8, 8), (128, 128, 128, 255))
        alpha = np.array(im.split()[3])
        masked = (keys.get('$alphatest', '0').strip() not in ('0', '') or
                  keys.get('$translucent', '0').strip() not in ('0', '')) and (alpha < 128).any()
        if masked:
            flags |= STUDIO_NF_MASKED
        w, h, pix, pal = quantize(im, masked)
        out.append((name, flags, w, h, pix, pal))
    return out


def head_bones(S):
    h = S.bone_by_name[retarget.VB + 'Head1']
    out = set()
    for i, b in enumerate(S.bones):
        j = i
        while j >= 0 and j != h:
            j = S.bones[j]['parent']
        if j == h:
            out.add(i)
    return out


def subtree_bones(S, names):
    """bones at or under any of the named ValveBiped bones"""
    roots = {S.bone_by_name[retarget.VB + n] for n in names if retarget.VB + n in S.bone_by_name}
    out = set()
    for i in range(len(S.bones)):
        j = i
        while j >= 0 and j not in roots:
            j = S.bones[j]['parent']
        if j >= 0:
            out.add(i)
    return out


HAND_ROOTS = ('L_Hand', 'R_Hand')


def is_head_tri(S, hb, t):
    n = sum(1 for v in t if max(S.vertices[v]['bones'], key=lambda bw: bw[1])[0] in hb)
    return n >= 2


def build_mesh(S, P, W, X, rt, choose, keep='all', matoff=0, partnames=None):
    """GoldSrc body parts: [(name, vertices, vertex bones, normals, normal bones, meshes)]
    keep: 'all', 'nohead' (drop the triangles skinned to the head) or 'head' (only those),
    or a function (S, triangle) -> keep it."""
    hb = head_bones(S)
    Rs, Ts = S.bind_world()
    tgt_by_srcname = {retarget.VB + sn: P.bone_by_name[tn] for tn, sn in retarget.MAP}
    # Source bone -> (GoldSrc bone, the Source bone whose joint it hangs from)
    bmap = {}
    # Half-Life's hands have a thumb and one finger: the index, ring and little
    # fingers bend with it (the middle finger's joints), instead of staying stiff
    alias = {}
    for side in ('L', 'R'):
        for f in ('1', '3', '4'):
            for k in ('', '1', '2'):
                alias[retarget.VB + '%s_Finger%s%s' % (side, f, k)] = retarget.VB + '%s_Finger2%s' % (side, k)
    for i, b in enumerate(S.bones):
        al = alias.get(b['name'])
        if al and al in tgt_by_srcname and al in S.bone_by_name:
            bmap[i] = (tgt_by_srcname[al], S.bone_by_name[al])
            continue
        j = i
        while j >= 0 and S.bones[j]['name'] not in tgt_by_srcname:
            j = S.bones[j]['parent']
        bmap[i] = (tgt_by_srcname[S.bones[j]['name']], j) if j >= 0 else (rt.pelvis_t, S.bone_by_name[retarget.VB + 'Pelvis'])
    textures = {}
    parts = []
    for bp, (bpname, nm) in enumerate(S.bodyparts):
        sub = choose.get(bpname.lower(), 0)
        meshes = [(mat, tris) for mat, tris, b, m in S.meshes if b == bp and m == sub and tris]
        if callable(keep):
            meshes = [(mat, [t for t in tris if keep(S, t)]) for mat, tris in meshes]
            meshes = [(mat, tris) for mat, tris in meshes if tris]
        elif keep != 'all':
            want = keep == 'head'
            meshes = [(mat, [t for t in tris if is_head_tri(S, hb, t) == want]) for mat, tris in meshes]
            meshes = [(mat, tris) for mat, tris in meshes if tris]
        if not meshes:
            continue
        vid = {}
        verts, vbones, norms, nbones = [], [], [], []
        gmeshes = []
        for mat, tris in meshes:
            cmds = []
            for t in tris:
                cmd = []
                for v in t:
                    if v not in vid:
                        sv = S.vertices[v]
                        sb = max(sv['bones'], key=lambda bw: bw[1])[0]
                        gb, anc = bmap[sb]
                        # offset from the joint the vertex hangs from, in that bone's bind frame
                        off = sv['pos'] - Ts[anc]
                        verts.append(W[gb].T @ off)
                        vbones.append(gb)
                        norms.append(W[gb].T @ sv['normal'])
                        nbones.append(gb)
                        vid[v] = len(verts) - 1
                    cmd.append((vid[v], S.vertices[v]['uv']))
                cmds.append(cmd)
            gmeshes.append((mat + matoff, cmds))
        parts.append(((partnames or bpname), np.array(verts), vbones, np.array(norms), nbones, gmeshes))
        assert len(verts) <= 2048, 'too many vertices in ' + bpname
    return parts


def write_model(P, base_path, out_path, parts, textures, skins):
    d = bytearray(open(base_path, 'rb').read())
    tex_hdr_names = [t[0] for t in textures]

    def align(buf):
        while len(buf) % 4:
            buf.append(0)
    align(d)
    # textures: header table, skin table (data goes last)
    ti = len(d)
    for name, flags, w, h, pix, pal in textures:
        nb = name.encode('latin-1')[:63]
        d += nb + bytes(64 - len(nb)) + struct.pack('<4i', flags, w, h, 0)
    align(d)
    si = len(d)
    nsr = len(textures)
    for fam in skins:
        row = list(fam) + list(range(len(fam), nsr))
        d += struct.pack('<%dh' % nsr, *row[:nsr])
    align(d)
    # body parts
    bpi = len(d)
    d += bytes(76 * len(parts))
    for k, (name, verts, vb, norms, nb, meshes) in enumerate(parts):
        align(d)
        mo = len(d)
        d += bytes(112)
        vinfo = len(d); d += bytes(vb); align(d)
        vidx = len(d)
        for v in verts:
            d += struct.pack('<3f', *v)
        ninfo = len(d); d += bytes(nb); align(d)
        nidx = len(d)
        for v in norms:
            d += struct.pack('<3f', *v)
        meshi = len(d)
        d += bytes(20 * len(meshes))
        for m, (mat, cmds) in enumerate(meshes):
            align(d)
            tri = len(d)
            _, _, w, h, _, _ = textures[mat]
            for cmd in cmds:
                d += struct.pack('<h', 3)
                # Source repeats textures; Half-Life doesn't: move each triangle into the 0-1 tile
                du = np.floor(min(uv[0] for _, uv in cmd) + 1e-4)
                dv = np.floor(min(uv[1] for _, uv in cmd) + 1e-4)
                for vi, (u, v) in cmd:
                    u -= du; v -= dv
                    s = int(round(u * w)); t = int(round(v * h))
                    s = max(-32000, min(32000, s)); t = max(-32000, min(32000, t))
                    d += struct.pack('<4h', vi, vi, s, t)
            d += struct.pack('<h', 0)
            struct.pack_into('<5i', d, meshi + m * 20, len(cmds), tri, mat, len(cmds) * 3, 0)
        radius = float(np.max(np.linalg.norm(verts, axis=1))) if len(verts) else 0.0
        mn = name.encode('latin-1')[:63]
        d[mo:mo + 64] = mn + bytes(64 - len(mn))
        struct.pack_into('<if8i2i', d, mo + 64, 0, radius, len(meshes), meshi, len(verts), vinfo, vidx,
                         len(norms), ninfo, nidx, 0, 0)
        bn = name.encode('latin-1')[:63]
        o = bpi + k * 76
        d[o:o + 64] = bn + bytes(64 - len(bn))
        struct.pack_into('<3i', d, o + 64, 1, 1, mo)
    # texture data, last (the engine keeps the file only up to it)
    align(d)
    tdi = len(d)
    for k, (name, flags, w, h, pix, pal) in enumerate(textures):
        struct.pack_into('<i', d, ti + k * 80 + 76, len(d))
        d += pix + pal
    struct.pack_into('<6i', d, 180, len(textures), ti, tdi, nsr, len(skins), si)
    struct.pack_into('<2i', d, 204, len(parts), bpi)
    struct.pack_into('<i', d, 72, len(d))
    nm = out_path.replace('\\', '/').split('/')[-1].encode()[:63]
    d[8:72] = nm + bytes(64 - len(nm))
    open(out_path, 'wb').write(d)
    return len(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('base'); ap.add_argument('source'); ap.add_argument('out'); ap.add_argument('ref')
    ap.add_argument('--roots', default='')
    ap.add_argument('--body', default='')
    ap.add_argument('--head', default='')
    ap.add_argument('--head-body', default='')
    ap.add_argument('--hands', default='')
    ap.add_argument('--hands-body', default='')
    ap.add_argument('--tint', type=float, default=None)
    ap.add_argument('--sat', type=float, default=1.0)
    a = ap.parse_args()

    def parse(txt):
        out = {}
        for kv in filter(None, txt.split(',')):
            k, v = kv.split('=')
            out[k.lower()] = int(v)
        return out
    choose = parse(a.body)
    P = GoldSrcModel(a.base)
    ref = SourceModel(a.ref, a.ref[:-4].replace('_gmod', '') + '.ani')
    S = SourceMesh(a.source, [r for r in a.roots.split(',') if r])

    rt, newpos, W, X = build_skeleton(P, ref)
    seqs = existing_sequences(P)
    resequence(P, seqs, rt, newpos)
    tmp = a.out + '.tmp'
    P.write(tmp, seqs)
    roots = [r for r in a.roots.split(',') if r]
    if a.head or a.hands:
        # the main model, minus the head and / or hands taken from other models
        def region(Mdl, bones):
            return lambda _S, t: sum(1 for v in t if max(_S.vertices[v]['bones'], key=lambda bw: bw[1])[0] in bones) >= 2
        sh = head_bones(S) if a.head else set()
        sg = subtree_bones(S, HAND_ROOTS) if a.hands else set()
        parts = build_mesh(S, P, W, X, rt, choose, keep=lambda _S, t: not region(S, sh)(_S, t) and not region(S, sg)(_S, t))
        srcs = [(S, parts, a.tint)]
        matoff = len(S.materials)
        if a.head:
            H = SourceMesh(a.head, roots)
            hparts = build_mesh(H, P, W, X, rt, parse(a.head_body), keep='head', matoff=matoff, partnames='head')
            srcs.append((H, hparts, None)); matoff += len(H.materials)
        if a.hands:
            G = SourceMesh(a.hands, roots)
            gb = subtree_bones(G, HAND_ROOTS)
            gparts = build_mesh(G, P, W, X, rt, parse(a.hands_body), keep=region(G, gb), matoff=matoff, partnames='hands')
            srcs.append((G, gparts, a.tint)); matoff += len(G.materials)
        textures = []
        parts = []
        off = 0
        for Mdl, ps, tn in srcs:
            used = {m - off for p in ps for m, _ in p[5]}
            textures += convert_textures(Mdl, tn, a.sat if tn is not None else 1.0, skip=set(range(len(Mdl.materials))) - used)
            parts += ps
            off += len(Mdl.materials)
        skins = [list(range(len(textures)))]
    else:
        parts = build_mesh(S, P, W, X, rt, choose)
        textures = convert_textures(S, a.tint, a.sat)
        skins = S.skins
    n = write_model(P, tmp, a.out, parts, textures, skins)
    import os
    os.remove(tmp)
    print('wrote', a.out, n, 'bytes;', len(parts), 'body parts,', sum(len(p[1]) for p in parts), 'vertices,',
          len(textures), 'textures,', len(skins), 'skins; height scale undone', round(1 / rt.scale, 3))


if __name__ == '__main__':
    main()
