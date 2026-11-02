"""Put another fpbody model's head on a body (both on the fpbody skeleton).

  python3 -I merge_head.py <body.mdl> <head.mdl> <out.mdl>

The body's triangles on the head (two or more corners skinned to "Bip01 Head"
or a bone under it) are dropped and the head model's are added, with their
textures; the body's skeleton, sequences, hitboxes and attachments are kept.
Vertices are kept in their bone's own space, so the head fits either skeleton
(Half-Life's or the Garry's Mod-proportioned one). Used for Echoes: Walter's
head (from the HL:S scientist) on the lab coat and the suit.
The result contains the models' data: keep it local.
"""
import struct
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from goldsrc import GoldSrcModel        # noqa: E402
from src2w import write_skinned         # noqa: E402


def textures(d):
    ntex, ti = struct.unpack_from('<2i', d, 180)
    out = []
    for k in range(ntex):
        o = ti + k * 80
        name = d[o:o + 64].split(b'\0')[0]
        flags, w, h, idx = struct.unpack_from('<4i', d, o + 64)
        out.append(dict(name=name, flags=flags, w=w, h=h, pix=d[idx:idx + w * h], pal=d[idx + w * h:idx + w * h + 768]))
    return out


def tris(path):
    """-> skeleton bone names, textures, [(local verts, local normals, st, texture, bones)] of body 0"""
    G = GoldSrcModel(path)
    d = bytes(G.d)
    nsr, nsf, si = struct.unpack_from('<3i', d, 192)
    skins = struct.unpack_from('<%dh' % nsr, d, si)
    out = []
    nbp, bpi = struct.unpack_from('<2i', d, 204)
    for bp in range(nbp):
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
    return [b['name'] for b in G.bones], [b['parent'] for b in G.bones], textures(d), out


def head_set(names, parents):
    h = {names.index('Bip01 Head')}
    for i, p in enumerate(parents):
        if p in h:
            h.add(i)
    return h


class _Tex:
    def __init__(self, t):
        self.textures = t


def main(body_path, head_path, out_path):
    bn, bp, btex, btris = tris(body_path)
    hn, hp, htex, htris = tris(head_path)
    bh, hh = head_set(bn, bp), head_set(hn, hp)
    keep = [t for t in btris if sum(1 for b in t[4] if b in bh) < 2]
    # head bones by name onto the body's skeleton
    remap = {i: bn.index(n) for i, n in enumerate(hn) if n in bn}
    add = [(P, N, st, tex + len(btex), [remap.get(b, bn.index('Bip01 Head')) for b in bones])
           for P, N, st, tex, bones in htris if sum(1 for b in bones if b in hh) >= 2]
    used = sorted({t[3] for t in keep + add})
    alltex = btex + htex
    idx = {k: i for i, k in enumerate(used)}
    out = [(P, N, st, idx[tex], bones) for P, N, st, tex, bones in keep + add]
    info = write_skinned(body_path, out, _Tex([alltex[k] for k in used]), out_path)
    print('wrote', out_path, 'kept', len(keep), 'body triangles, added', len(add), 'head triangles;', info)


if __name__ == '__main__':
    main(*sys.argv[1:4])
