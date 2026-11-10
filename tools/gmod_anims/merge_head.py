"""Put another fpbody model's head on a body (both on the fpbody skeleton).

  python3 -I merge_head.py <body.mdl> <head.mdl> <out.mdl> [head submodel] [corners]

[head submodel] picks the head model's submodel (default 0; Half-Life's
multiplayer models keep the full-detail mesh in 1). [corners] (default 2) is
how many corners on the head make a triangle the head's: 1 also swaps the
neck (strips joining the head to the collar), for a helmet. [part] "hands"
swaps the hands (both hand bones and the fingers) instead of the head: the
PS2 hands of the fpbody suits onto another outfit.

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


def tris(path, sub=0):
    """-> skeleton bone names, textures, [(local verts, local normals, st, texture, bones)] of submodel sub"""
    G = GoldSrcModel(path)
    d = bytes(G.d)
    nsr, nsf, si = struct.unpack_from('<3i', d, 192)
    skins = struct.unpack_from('<%dh' % nsr, d, si)
    out = []
    nbp, bpi = struct.unpack_from('<2i', d, 204)
    for bp in range(nbp):
        nm, _, mi = struct.unpack_from('<3i', d, bpi + bp * 76 + 64)
        mi += min(sub, nm - 1) * 112
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


PART = ('Bip01 Head',)


def head_set(names, parents):
    h = {names.index(n) for n in PART if n in names}
    for i, p in enumerate(parents):
        if p in h:
            h.add(i)
    return h


class _Tex:
    def __init__(self, t):
        self.textures = t


def main(body_path, head_path, out_path, sub='0', corners='2', part='head'):
    global PART
    PART = ('Bip01 L Hand', 'Bip01 R Hand') if part == 'hands' else ('Bip01 Head',)
    sub, corners = int(sub), int(corners)
    bn, bp, btex, btris = tris(body_path)
    hn, hp, htex, htris = tris(head_path, sub)
    bh, hh = head_set(bn, bp), head_set(hn, hp)
    keep = [t for t in btris if sum(1 for b in t[4] if b in bh) < corners]
    # head bones by name onto the body's skeleton
    remap = {i: bn.index(n) for i, n in enumerate(hn) if n in bn}
    add = [(P, N, st, tex + len(btex), [remap.get(b, bn.index('Bip01 Head')) for b in bones])
           for P, N, st, tex, bones in htris if sum(1 for b in bones if b in hh) >= corners]
    used = sorted({t[3] for t in keep + add})
    alltex = btex + htex
    idx = {k: i for i, k in enumerate(used)}
    out = [(P, N, st, idx[tex], bones) for P, N, st, tex, bones in keep + add]
    info = write_skinned(body_path, out, _Tex([alltex[k] for k in used]), out_path)
    print('wrote', out_path, 'kept', len(keep), 'body triangles, added', len(add), 'head triangles;', info)


if __name__ == '__main__':
    main(*sys.argv[1:7])
