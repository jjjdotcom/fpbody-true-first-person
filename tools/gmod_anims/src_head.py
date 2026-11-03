"""Put the head of a Source model on a Half-Life Biped skeleton (Bip01 bones)
onto an fpbody body.

  python3 -I src_head.py <body.mdl> <source.mdl> <out.mdl> [--roots dir,...]
        [--body part=index,...] [--scale s] [--shift x,y,z]
        [--rot deg] [--minx x] [--corners n]

For Source ports of Half-Life's NPCs that keep the original Biped skeleton
(the "PS2 HD Model Fix" scientist, whose "heads" part 0 is Walter): the
triangles skinned to "Bip01 Head" or a bone under it (two or more corners)
(--corners, default 2)
are taken from the chosen submodels, each vertex kept in the head bone's own
bind frame (both skeletons are 3ds Max Bipeds, so the head's axes match),
scaled by s (default 1), turned by --rot degrees about the head's side axis
(a nod: the two Bipeds' heads can rest at different angles), moved by the
shift (head bone frame), triangles reaching below --minx along the neck
dropped (strips stretched to the collar), and put on
the body's "Bip01 Head"; their other corners (the neck's base) go on the body's\nbone of the same name,
at their offset from the head joint. The body's own head triangles are dropped. The
textures are converted from the VMT/VTF materials under the roots.
The result contains the models' data: keep it local.
"""
import argparse
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from srcmesh import SourceMesh                   # noqa: E402
from merge_head import tris, head_set            # noqa: E402
from hls_body import convert_textures            # noqa: E402
from src2w import write_skinned                  # noqa: E402


class _Tex:
    def __init__(self, t):
        self.textures = t


def src_head_set(S):
    h = {S.bone_by_name['Bip01 Head']}
    for i, b in enumerate(S.bones):
        if b['parent'] in h:
            h.add(i)
    return h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('body'); ap.add_argument('source'); ap.add_argument('out')
    ap.add_argument('--roots', default='')
    ap.add_argument('--body', dest='choose', default='')
    ap.add_argument('--scale', type=float, default=1.0)
    ap.add_argument('--shift', default='0,0,0')
    ap.add_argument('--rot', type=float, default=0.0)
    ap.add_argument('--minx', type=float, default=-1e9)
    ap.add_argument('--corners', type=int, default=2)
    a = ap.parse_args()
    choose = {k.lower(): int(v) for k, v in (kv.split('=') for kv in filter(None, a.choose.split(',')))}
    shift = np.array([float(x) for x in a.shift.split(',')])
    c, s_ = np.cos(np.radians(a.rot)), np.sin(np.radians(a.rot))
    Rz = np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1]])
    S = SourceMesh(a.source, [r for r in a.roots.split(',') if r])
    R, T = S.bind_world()
    hb = src_head_set(S)
    h = S.bone_by_name['Bip01 Head']

    bn, bp, btex, btris = tris(a.body)
    bh = head_set(bn, bp)
    keep = [t for t in btris if sum(1 for b in t[4] if b in bh) < 2]
    target = bn.index('Bip01 Head')
    # neck vertices: on the body's neck, kept at their offset from the head
    # joint (so the neck stays joined to the head whatever the neck length)
    from goldsrc import GoldSrcModel
    G = GoldSrcModel(a.body)
    Rb, Tb = G.world(G.rest_local())

    def heavy(v):
        return max(S.vertices[v]['bones'], key=lambda bw: bw[1])[0]

    texs = convert_textures(S)
    texd = [dict(name=n.encode('latin-1')[:63], flags=f, w=w, h=hh, pix=bytes(p), pal=bytes(pl))
            for n, f, w, hh, p, pl in texs]
    add = []
    for bpi, (bpname, nm) in enumerate(S.bodyparts):
        sub = choose.get(bpname.lower(), 0)
        for mat, ts, b, m in S.meshes:
            if b != bpi or m != sub:
                continue
            for t in ts:
                if sum(1 for v in t if heavy(v) in hb) < a.corners:
                    continue
                P, N, B = [], [], []
                for v in t:
                    sv = S.vertices[v]
                    sb = heavy(v)
                    if sb in hb or S.bones[sb]['name'] not in bn:
                        P.append(Rz @ (R[h].T @ (sv['pos'] - T[h])) * a.scale + shift)
                        N.append(Rz @ R[h].T @ sv['normal']); B.append(target)
                    else:
                        tb = bn.index(S.bones[sb]['name'])
                        hj = Rb[tb].T @ (Tb[target] - Tb[tb])        # the body's head joint, in that bone's frame
                        P.append(R[sb].T @ (sv['pos'] - T[h]) * a.scale + hj)
                        N.append(R[sb].T @ sv['normal']); B.append(tb)
                P, N = np.array(P), np.array(N)
                if min(p[0] for p, b in zip(P, B) if b == target) < a.minx:
                    continue
                uv = np.array([S.vertices[v]['uv'] for v in t])
                uv -= np.floor(uv.min(axis=0) + 1e-4)       # Half-Life doesn't repeat textures
                w, hh = texd[mat]['w'], texd[mat]['h']
                st = [(int(round(u * w)), int(round(vv * hh))) for u, vv in uv]
                add.append((P, N, st, len(btex) + mat, B))
    alltex = btex + texd
    used = sorted({t[3] for t in keep + add})
    idx = {k: i for i, k in enumerate(used)}
    out = [(P, N, st, idx[tx], bones) for P, N, st, tx, bones in keep + add]
    info = write_skinned(a.body, out, _Tex([alltex[k] for k in used]), a.out)
    print('wrote', a.out, 'kept', len(keep), 'body triangles, added', len(add), 'head triangles;', info)


if __name__ == '__main__':
    main()
