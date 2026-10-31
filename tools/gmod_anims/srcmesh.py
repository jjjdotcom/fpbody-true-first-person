"""Source engine model meshes and textures (MDL v44-49 + VVD + VTX, VMT/VTF).

  m = SourceMesh('models/player/hl1/player.mdl', material_roots)
  m.bind_world()          -> per-bone (R, T) of the bind pose (from poseToBone)
  m.vertices              -> list of dicts: pos, normal, uv, bones [(index, weight)]
  m.meshes                -> list of (material index, triangles [(a, b, c) vertex ids])
  m.materials             -> names; m.load_texture(i) -> PIL RGBA image or None

Layouts follow the Source SDK 2013 (studio.h, optimize.h); only LOD 0 is read.
"""
import os
import re
import struct

import numpy as np


def cstr(d, o):
    e = d.index(b'\0', o)
    return d[o:e].decode('latin-1')


class SourceMesh:
    def __init__(self, mdl_path, material_roots=()):
        self.path = mdl_path
        self.d = d = open(mdl_path, 'rb').read()
        assert d[:4] == b'IDST'
        self.version = struct.unpack_from('<i', d, 4)[0]
        self.roots = list(material_roots)
        base = mdl_path[:-4]
        self.vvd = open(base + '.vvd', 'rb').read()
        vtx = None
        for ext in ('.dx90.vtx', '.vtx', '.dx80.vtx', '.sw.vtx'):
            if os.path.exists(base + ext):
                vtx = open(base + ext, 'rb').read()
                break
        assert vtx, 'no .vtx for ' + mdl_path
        self.vtx = vtx
        self._bones()
        self._textures()
        self._vvd()
        self._geometry()

    # ------------------------------------------------------------ skeleton
    def _bones(self):
        d = self.d
        n, bi = struct.unpack_from('<ii', d, 156)
        self.bones = []
        for i in range(n):
            o = bi + i * 216
            nameoff, parent = struct.unpack_from('<ii', d, o)
            m = np.array(struct.unpack_from('<12f', d, o + 96)).reshape(3, 4)
            self.bones.append(dict(name=cstr(d, o + nameoff), parent=parent, pose_to_bone=m))
        self.bone_by_name = {b['name']: i for i, b in enumerate(self.bones)}

    def bind_world(self):
        """World rotation and position of each bone in the bind pose."""
        R = np.zeros((len(self.bones), 3, 3)); T = np.zeros((len(self.bones), 3))
        for i, b in enumerate(self.bones):
            m = b['pose_to_bone']
            R[i] = m[:, :3].T
            T[i] = -R[i] @ m[:, 3]
        return R, T

    # ------------------------------------------------------------ materials
    def _textures(self):
        d = self.d
        nt, ti = struct.unpack_from('<ii', d, 204)
        ncd, cdi = struct.unpack_from('<ii', d, 212)
        nsr, nsf, si = struct.unpack_from('<3i', d, 220)
        self.materials = []
        for k in range(nt):
            o = ti + k * 64
            self.materials.append(cstr(d, o + struct.unpack_from('<i', d, o)[0]))
        self.cdtextures = [cstr(d, struct.unpack_from('<i', d, cdi + k * 4)[0]) for k in range(ncd)]
        self.skins = [list(struct.unpack_from('<%dh' % nsr, d, si + f * nsr * 2)) for f in range(nsf)]

    def find_vmt(self, k):
        name = self.materials[k].replace('\\', '/').lower()
        for cd in self.cdtextures + ['']:
            cd = cd.replace('\\', '/').strip('/').lower()
            rel = (cd + '/' + name if cd else name) + '.vmt'
            for r in self.roots:
                p = _find_ci(r, 'materials/' + rel)
                if p:
                    return p
        return None

    def material_info(self, k):
        """(vtf path or None, {vmt keys})"""
        vmt = self.find_vmt(k)
        if not vmt:
            return None, {}
        txt = open(vmt, 'rb').read().decode('latin-1')
        keys = {m.group(1).lower(): m.group(2) for m in
                re.finditer(r'"?(\$\w+)"?\s+"?([^"\n\r]*)"?', txt)}
        base = keys.get('$basetexture')
        if not base:
            return None, keys
        base = base.replace('\\', '/').lower()
        for r in self.roots:
            p = _find_ci(r, 'materials/' + base + '.vtf')
            if p:
                return p, keys
        return None, keys

    def load_texture(self, k):
        p, keys = self.material_info(k)
        if not p:
            return None, keys
        return read_vtf(p), keys

    # ------------------------------------------------------------ vertices
    def _vvd(self):
        v = self.vvd
        assert v[:4] == b'IDSV'
        numlods = struct.unpack_from('<i', v, 12)[0]
        nlodv = struct.unpack_from('<8i', v, 16)
        nfix, fixstart, vstart = struct.unpack_from('<3i', v, 48)

        def vert(i):
            o = vstart + i * 48
            w = struct.unpack_from('<3f', v, o)
            b = struct.unpack_from('<3B', v, o + 12)
            nb = v[o + 15]
            pos = struct.unpack_from('<3f', v, o + 16)
            nrm = struct.unpack_from('<3f', v, o + 28)
            uv = struct.unpack_from('<2f', v, o + 40)
            return dict(pos=np.array(pos), normal=np.array(nrm), uv=uv,
                        bones=[(b[j], w[j]) for j in range(nb)])
        if nfix:
            order = []
            for f in range(nfix):
                lod, src, cnt = struct.unpack_from('<3i', v, fixstart + f * 12)
                if lod >= 0:
                    order += range(src, src + cnt)
            self.vertices = [vert(i) for i in order]
        else:
            self.vertices = [vert(i) for i in range(nlodv[0])]

    # ------------------------------------------------------------ triangles
    def _geometry(self):
        d, x = self.d, self.vtx
        nbp, bpi = struct.unpack_from('<ii', d, 232)
        xv = struct.unpack_from('<i', x, 0)[0]
        xnbp, xbpo = struct.unpack_from('<ii', x, 28)
        assert xv == 7 and xnbp == nbp
        self.meshes = []           # (material, [(a, b, c)], bodypart, model)
        self.bodyparts = []
        for bp in range(nbp):
            bo = bpi + bp * 16
            nameoff, nm, base, mi = struct.unpack_from('<4i', d, bo)
            self.bodyparts.append((cstr(d, bo + nameoff), nm))
            xb = xbpo + bp * 8
            xnm, xmo = struct.unpack_from('<ii', x, xb)
            for m in range(nm):
                mo = bo + mi + m * 148
                nmesh, meshi, nverts, vidx = struct.unpack_from('<4i', d, mo + 72)
                vstart = vidx // 48
                xm = xb + xmo + m * 8
                nlod, lodo = struct.unpack_from('<ii', x, xm)
                xl = xm + lodo                               # LOD 0
                xnmesh, xmesho = struct.unpack_from('<ii', x, xl)
                for k in range(nmesh):
                    me = mo + meshi + k * 116
                    mat, _, mnv, mvoff = struct.unpack_from('<4i', d, me)
                    xme = xl + xmesho + k * 9
                    nsg, sgo = struct.unpack_from('<ii', x, xme)
                    tris = []
                    sgsize = self._sg_size(xme + sgo, nsg)
                    for g in range(nsg):
                        sg = xme + sgo + g * sgsize
                        nv, vo, ni, io, ns, so = struct.unpack_from('<6i', x, sg)
                        verts = [struct.unpack_from('<H', x, sg + vo + j * 9 + 4)[0] for j in range(nv)]
                        idx = struct.unpack_from('<%dH' % ni, x, sg + io)
                        ssize = 35 if sgsize == 33 else 27
                        for s in range(ns):
                            st = sg + so + s * ssize
                            sni, sio, snv, svo = struct.unpack_from('<4i', x, st)
                            flags = x[st + 18]
                            ii = idx[sio:sio + sni]
                            if flags & 2:             # strip
                                tl = []
                                for j in range(len(ii) - 2):
                                    t = (ii[j], ii[j + 1], ii[j + 2]) if j % 2 == 0 else (ii[j + 1], ii[j], ii[j + 2])
                                    tl.append(t)
                            else:
                                tl = [ii[j:j + 3] for j in range(0, len(ii) - 2, 3)]
                            for t in tl:
                                a, b, c = (vstart + mvoff + verts[q] for q in t)
                                if a != b and b != c and a != c:
                                    tris.append((a, b, c))
                    self.meshes.append((mat, tris, bp, m))

    def _sg_size(self, o, n):
        """25-byte strip groups (most models) or 33 (with topology, MDL v49 flexes)."""
        x = self.vtx
        if n <= 1:
            # check that the strip offsets make sense with 25
            nv, vo, ni, io, ns, so = struct.unpack_from('<6i', x, o)
            return 25 if so == io + ni * 2 or so > 0 and ns < 1000 else 33
        nxt = struct.unpack_from('<i', x, o + 25)[0]
        return 25 if 0 <= nxt < 100000 else 33


def _find_ci(root, rel):
    """Case-insensitive path lookup under root."""
    p = os.path.join(root, rel)
    if os.path.exists(p):
        return p
    cur = root
    for part in rel.split('/'):
        if not os.path.isdir(cur):
            return None
        low = part.lower()
        hit = None
        for e in os.listdir(cur):
            if e.lower() == low:
                hit = e
                break
        if hit is None:
            return None
        cur = os.path.join(cur, hit)
    return cur


# ---------------------------------------------------------------- VTF
_FMT_BPP = {0: 4, 1: 4, 2: 3, 3: 3, 4: 2, 5: 1, 6: 2, 8: 1, 11: 4, 12: 4, 16: 4, 17: 2}


def _size(fmt, w, h):
    if fmt in (13,):
        return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 8
    if fmt in (14, 15):
        return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 16
    return w * h * _FMT_BPP[fmt]


def read_vtf(path):
    from PIL import Image
    v = open(path, 'rb').read()
    assert v[:4] == b'VTF\0', path
    w, h = struct.unpack_from('<HH', v, 16)
    flags = struct.unpack_from('<I', v, 20)[0]
    frames = struct.unpack_from('<H', v, 24)[0]
    fmt = struct.unpack_from('<i', v, 52)[0]
    faces = 6 if flags & 0x4000 else 1
    sz = _size(fmt, w, h)
    o = len(v) - sz * max(1, frames) * faces
    data = v[o:o + sz]
    if fmt == 13:
        im = Image.frombytes('RGBA', (w, h), data, 'bcn', 1)
    elif fmt == 14:
        im = Image.frombytes('RGBA', (w, h), data, 'bcn', 2)
    elif fmt == 15:
        im = Image.frombytes('RGBA', (w, h), data, 'bcn', 3)
    elif fmt == 0:
        im = Image.frombytes('RGBA', (w, h), data)
    elif fmt == 1:
        im = Image.frombytes('RGBA', (w, h), data, 'raw', 'ABGR')
    elif fmt == 2:
        im = Image.frombytes('RGB', (w, h), data).convert('RGBA')
    elif fmt == 3:
        im = Image.frombytes('RGB', (w, h), data, 'raw', 'BGR').convert('RGBA')
    elif fmt == 5:
        im = Image.frombytes('L', (w, h), data).convert('RGBA')
    elif fmt == 6:
        im = Image.frombytes('LA', (w, h), data).convert('RGBA')
    elif fmt == 11:
        im = Image.frombytes('RGBA', (w, h), data, 'raw', 'ARGB')
    elif fmt in (12, 16):
        im = Image.frombytes('RGBA', (w, h), data, 'raw', 'BGRA')
        if fmt == 16:
            im.putalpha(255)
    elif fmt == 4:
        im = Image.frombytes('RGB', (w, h), data, 'raw', 'RGB;16').convert('RGBA')
    elif fmt == 17:
        im = Image.frombytes('RGB', (w, h), data, 'raw', 'BGR;16').convert('RGBA')
    else:
        raise ValueError('VTF format %d not handled (%s)' % (fmt, path))
    return im
