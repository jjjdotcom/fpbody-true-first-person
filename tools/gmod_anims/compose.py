"""Compose a player model for fpbody from pieces of other Half-Life models.

The skeleton, sequences, hitboxes and attachments come from the converted
fpbody player model; the body parts are built from meshes of any GoldSrc
models (NPCs included), rebound to the player skeleton bone by bone, with
optional triangle filters (e.g. "only the head") and texture recolouring.

Used as a library by outfits.py.
"""
import colorsys
import struct

import numpy as np

from goldsrc import GoldSrcModel


def target_name(name):
    t = (name.replace('Thigh', 'Leg').replace('Calf', 'Leg1').replace('Clavicle', 'Arm')
         .replace('UpperArm', 'Arm1').replace('Forearm', 'Arm2'))
    for s in 'LR':
        for f in ('2', '3', '4'):
            t = t.replace('%s Finger%s' % (s, f), '%s Finger1' % s)
    return t


class Source:
    """A GoldSrc model (+ optional external texture model) to take meshes from."""

    def __init__(self, path, tex_path=None):
        self.m = GoldSrcModel(path)
        self.d = bytes(self.m.d)
        self.t = open(tex_path, 'rb').read() if tex_path else self.d
        ntex, ti = struct.unpack_from('<2i', self.t, 180)
        nsr, nsf, si = struct.unpack_from('<3i', self.t, 192)
        self.skins = struct.unpack_from('<%dh' % nsr, self.t, si) if nsr else ()
        self.textures = []
        for k in range(ntex):
            o = ti + k * 80
            name = self.t[o:o + 64].split(b'\0')[0]
            flags, w, h, idx = struct.unpack_from('<4i', self.t, o + 64)
            pix = self.t[idx:idx + w * h]
            pal = self.t[idx + w * h:idx + w * h + 768]
            self.textures.append(dict(name=name, flags=flags, w=w, h=h, pix=pix, pal=pal))
        self.R, self.T = self.m.world(self.m.rest_local())

    def model(self, bodypart, index=0):
        d = self.d
        nbp, bpi = struct.unpack_from('<2i', d, 204)
        nm, _, mi = struct.unpack_from('<3i', d, bpi + bodypart * 76 + 64)
        assert index < nm
        mo = mi + index * 112
        name = d[mo:mo + 64].split(b'\0')[0]
        (nummesh, meshindex, numverts, vinfo, vindex,
         numnorms, ninfo, nindex) = struct.unpack_from('<8i', d, mo + 72)
        vb = list(d[vinfo:vinfo + numverts])
        vv = np.frombuffer(d[vindex:vindex + numverts * 12], '<f4').reshape(-1, 3).astype(float)
        nb = list(d[ninfo:ninfo + numnorms])
        nv = np.frombuffer(d[nindex:nindex + numnorms * 12], '<f4').reshape(-1, 3).astype(float)
        meshes = []
        for m in range(nummesh):
            numtris, triindex, skinref, _, _ = struct.unpack_from('<5i', d, meshindex + m * 20)
            tris = []
            o = triindex
            while True:
                c = struct.unpack_from('<h', d, o)[0]; o += 2
                if c == 0:
                    break
                fan = c < 0; c = abs(c)
                vs = [struct.unpack_from('<4h', d, o + k * 8) for k in range(c)]; o += c * 8
                for k in range(2, c):
                    if fan:
                        tri = (vs[0], vs[k - 1], vs[k])
                    elif k % 2:
                        tri = (vs[k - 1], vs[k - 2], vs[k])
                    else:
                        tri = (vs[k - 2], vs[k - 1], vs[k])
                    tris.append(tri)
            tex = self.skins[skinref] if self.skins else skinref
            meshes.append(dict(tex=tex, tris=tris))
        return dict(src=self, name=name, vb=vb, vv=vv, nb=nb, nv=nv, meshes=meshes)


def bone_names(model):
    m = model['src'].m
    return [m.bones[b]['name'] for b in range(m.numbones)]


def keep_tris(model, pred):
    """Keep only triangles whose three vertex bone names satisfy pred(names)."""
    names = bone_names(model)
    for mesh in model['meshes']:
        mesh['tris'] = [t for t in mesh['tris'] if pred([names[model['vb'][v[0]]] for v in t])]
    return model


def recolour(src, tex_names, hue_to, sat_min=0.25, hue_range=(0.0, 0.14), sat_scale=1.0, val_scale=1.0):
    """Move the orange HEV colours of the named textures to another hue
    (0..1, e.g. 0.6 blue, 0.33 green)."""
    for t in src.textures:
        if t['name'].decode('latin-1').lower() not in [n.lower() for n in tex_names]:
            continue
        pal = bytearray(t['pal'])
        for i in range(256):
            r, g, b = (pal[i * 3 + k] / 255.0 for k in range(3))
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            if s >= sat_min and (hue_range[0] <= h <= hue_range[1] or h >= 0.97):
                r, g, b = colorsys.hsv_to_rgb(hue_to, min(1.0, s * sat_scale), min(1.0, v * val_scale))
                pal[i * 3:i * 3 + 3] = bytes(int(round(c * 255)) for c in (r, g, b))
        t['pal'] = bytes(pal)


def compose(player_path, bodyparts, out_path, name='fpbody_outfit.mdl'):
    """bodyparts: list of (bodypart name, [models]); each model is a list of
    pieces from Source.model() (merged into one studio model)."""
    P = GoldSrcModel(player_path)
    Rp, Tp = P.world(P.rest_local())
    base = bytearray(P.d)

    textures = []        # merged texture list
    tex_key = {}

    def tex_index(src, k):
        key = (id(src), k)
        if key not in tex_key:
            tex_key[key] = len(textures)
            textures.append(src.textures[k])
        return tex_key[key]

    SPINE = [P.bone_by_name[n] for n in ('Bip01 Spine', 'Bip01 Spine1', 'Bip01 Spine2', 'Bip01 Spine3')]

    def rebind(src):
        """-> (bone map, warp function). bone map: mesh bone -> player bone
        (nearest mapped ancestor). warp: rest-pose world position of the mesh
        -> rest-pose world position on the player, interpolated from the
        displacement of corresponding joints (plus floor anchors)."""
        m = src.m
        def mapped(i):
            n = m.bones[i]['name']
            return n.startswith('Bip01') and target_name(n) in P.bone_by_name
        bm = {}
        src.anc = {}
        for i in range(m.numbones):
            anc = i
            while anc >= 0 and not mapped(anc):
                anc = m.bones[anc]['parent']
            src.anc[i] = max(anc, 0)
            bm[i] = P.bone_by_name[target_name(m.bones[max(anc, 0)]['name'])]
        full_spine = 'Bip01 Spine2' in m.bone_by_name and 'Bip01 Spine3' in m.bone_by_name
        src_pts, dsp = [], []
        for i in range(m.numbones):
            if not mapped(i):
                continue
            n = m.bones[i]['name']
            if not full_spine and n in ('Bip01 Spine1', 'Bip01 Spine2', 'Bip01 Spine3'):
                continue
            j = P.bone_by_name[target_name(n)]
            src_pts.append(src.T[i]); dsp.append(Tp[j] - src.T[i])
            if 'Foot' in n:      # floor under the ankle stays on the floor
                src_pts.append(np.array([src.T[i][0], src.T[i][1], 0.0]))
                dsp.append(np.array([dsp[-1][0], dsp[-1][1], 0.0]))
        src_pts = np.array(src_pts); dsp = np.array(dsp)

        def warp(p):
            d2 = np.sum((src_pts - p) ** 2, axis=1)
            w = 1.0 / (d2 * d2 + 1e-3)
            return p + (w[:, None] * dsp).sum(0) / w.sum()
        return bm, warp

    def place(bm, warp, src, b, v):
        if getattr(src, 'mode', 'warp') == 'local':
            # same Biped bone conventions: keep the vertex in its bone's own frame
            # (bones with no counterpart: expressed in their mapped ancestor's frame)
            a = src.anc[b]
            return bm[b], src.R[a].T @ (src.R[b] @ v + src.T[b] - src.T[a])
        p = warp(src.R[b] @ v + src.T[b])
        pb = bm[b]
        if pb in SPINE:                       # split the torso over the player's spine bones
            pb = SPINE[0]
            for sb in SPINE:
                if Tp[sb][2] <= p[2]:
                    pb = sb
        return pb, Rp[pb].T @ (p - Tp[pb])

    built = []   # per bodypart: list of studio models (dict with arrays)
    for bpname, models in bodyparts:
        mlist = []
        for pieces in models:
            verts, vbones, norms, nbones, meshes = [], [], [], [], []
            for pc in pieces:
                src = pc['src']
                bm, warp = rebind(src)
                vmap, nmap = {}, {}
                for mesh in pc['meshes']:
                    if not mesh['tris']:
                        continue
                    tris = []
                    for tri in mesh['tris']:
                        out = []
                        for vi, ni, s, t in tri:
                            if vi not in vmap:
                                pb, v = place(bm, warp, src, pc['vb'][vi], pc['vv'][vi])
                                vmap[vi] = len(verts); verts.append(v); vbones.append(pb)
                            if ni not in nmap:
                                # normals follow the bone their vertex ended up on
                                b = pc['nb'][ni]
                                pb = vbones[vmap[vi]]
                                if getattr(src, 'mode', 'warp') == 'local':
                                    nrm = src.R[src.anc[b]].T @ (src.R[b] @ pc['nv'][ni])
                                else:
                                    nrm = Rp[pb].T @ (src.R[b] @ pc['nv'][ni])
                                nmap[ni] = len(norms); norms.append(nrm)
                                nbones.append(pb)
                            out.append((vmap[vi], nmap[ni], s, t))
                        tris.append(out)
                    meshes.append(dict(tex=tex_index(src, mesh['tex']), tris=tris))
            mlist.append(dict(name=pieces[0]['name'] if pieces else b'blank', verts=verts, vbones=vbones,
                              norms=norms, nbones=nbones, meshes=meshes))
        built.append((bpname, mlist))

    # --------------------------------------------------------------- write
    def align():
        while len(base) % 4:
            base.append(0)

    def put(b):
        align(); o = len(base); base.extend(b); return o

    # texture headers and skin table here; the pixel data goes last (below),
    # because the engine keeps the model only up to texturedataindex
    tex_hdr_off = put(bytes(80 * len(textures)))
    skin_off = put(struct.pack('<%dh' % len(textures), *range(len(textures))))

    bp_off = put(bytes(76 * len(built)))
    for bi, (bpname, mlist) in enumerate(built):
        models_off = put(bytes(112 * len(mlist)))
        for mi, md in enumerate(mlist):
            nv, nn = len(md['verts']), len(md['norms'])
            vinfo = put(bytes(md['vbones']))
            ninfo = put(bytes(md['nbones']))
            vindex = put(np.array(md['verts'], '<f4').tobytes() if nv else b'')
            nindex = put(np.array(md['norms'], '<f4').tobytes() if nn else b'')
            mesh_off = put(bytes(20 * len(md['meshes'])))
            for k, mesh in enumerate(md['meshes']):
                cmds = bytearray()
                for tri in mesh['tris']:
                    cmds += struct.pack('<h', 3)
                    for v in tri:
                        cmds += struct.pack('<4h', *v)
                cmds += struct.pack('<h', 0)
                tri_off = put(bytes(cmds))
                struct.pack_into('<5i', base, mesh_off + k * 20, len(mesh['tris']), tri_off, mesh['tex'],
                                 nn, nindex)
            radius = float(np.max(np.linalg.norm(np.array(md['verts']), axis=1))) if nv else 0.0
            nm = md['name'][:63]
            struct.pack_into('<64sif8i2i', base, models_off + mi * 112, nm + bytes(64 - len(nm)), 0, radius,
                             len(md['meshes']), mesh_off, nv, vinfo, vindex, nn, ninfo, nindex, 0, 0)
        nm = bpname.encode()[:63]
        base_mul = 1
        for _, ml in built[:bi]:
            base_mul *= len(ml)
        struct.pack_into('<64s3i', base, bp_off + bi * 76, nm + bytes(64 - len(nm)), len(mlist), base_mul,
                         models_off)
    struct.pack_into('<2i', base, 204, len(built), bp_off)

    align()
    tex_data_off = len(base)
    for k, t in enumerate(textures):
        data_off = put(t['pix'] + t['pal'])
        nm = t['name'][:63]
        struct.pack_into('<64s4i', base, tex_hdr_off + k * 80, nm + bytes(64 - len(nm)),
                         t['flags'], t['w'], t['h'], data_off)
    struct.pack_into('<6i', base, 180, len(textures), tex_hdr_off, tex_data_off, len(textures), 1, skin_off)
    struct.pack_into('<i', base, 72, len(base))
    n = name.encode()[:63]
    base[8:72] = n + bytes(64 - len(n))
    open(out_path, 'wb').write(base)
    return len(base), len(textures)
