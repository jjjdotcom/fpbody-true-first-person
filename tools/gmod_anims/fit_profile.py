"""Reshape a body's torso to another body's proportions (same skeleton).

  python3 -I fit_profile.py <body.mdl> <ref.mdl> <out.mdl> [zlo zhi] [--lowerback u] [--belly u]

In the rest pose, every horizontal slice of the body between zlo and zhi
(heights relative to "Bip01 Pelvis"; default -4 .. 18, the hips to the chest)
is stretched side to side and front to back so that its outline spans what
the reference body's does at that height (both measured without the arms),
fading out over 4 units at both ends. For a Half-Life mesh on the Garry's
Mod-proportioned skeleton, whose waist comes out sunken next to the HL:S
bodies'. --lowerback pushes the back of the waist out by up to u units
(most 9 units above the pelvis, none at 2 and 16), filling a sway-back
curve the outline match leaves; --belly pushes the front of the lower torso out
the same way (most 6 units above the pelvis, none at 0 and 13). Vertices stay
on their bones.
"""
import struct
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from goldsrc import GoldSrcModel   # noqa: E402

WIN = 1.5      # half height of the slice an outline is measured over
FADE = 4.0
MAXMOVE = 4.0
BE_MID, BE_HALF = 6.0, 6.5   # --belly: the front of the lower torso
LB_MID, LB_HALF = 9.0, 7.0   # --lowerback: most 9 units above the pelvis, none 7 above / below that


def arm_bones(M):
    arms = set()
    for i, b in enumerate(M.bones):
        if b['name'] in ('Bip01 L Arm', 'Bip01 R Arm') or b['parent'] in arms:
            arms.add(i)
    return arms


def body_verts(M):
    """-> [(vinfo, vindex, numverts)], surface samples of the rest-pose body (no arms), R, T, arms"""
    d = bytes(M.d)
    R, T = M.world(M.rest_local())
    arms = arm_bones(M)
    nbp, bpi = struct.unpack_from('<2i', d, 204)
    models, tris = [], []
    for bp in range(nbp):
        nm, _, mi = struct.unpack_from('<3i', d, bpi + bp * 76 + 64)
        mo = mi                                    # body 0 of every part
        nummesh, meshindex, numverts, vinfo, vindex = struct.unpack_from('<5i', d, mo + 72)
        for k in range(nm):
            nv_, vi_, vx_ = struct.unpack_from('<3i', d, mi + k * 112 + 80)
            models.append((vi_, vx_, nv_))
        vb = d[vinfo:vinfo + numverts]
        vv = np.frombuffer(d[vindex:vindex + numverts * 12], '<f4').reshape(-1, 3)
        W = np.array([R[vb[i]] @ vv[i] + T[vb[i]] for i in range(numverts)])
        for m in range(nummesh):
            _, o = struct.unpack_from('<2i', d, meshindex + m * 20)
            while True:
                c = struct.unpack_from('<h', d, o)[0]; o += 2
                if c == 0:
                    break
                fan = c < 0; c = abs(c)
                vs = [struct.unpack_from('<h', d, o + j * 8)[0] for j in range(c)]; o += c * 8
                for j in range(2, c):
                    t = [vs[0], vs[j - 1], vs[j]] if fan else [vs[j - 2], vs[j - 1], vs[j]]
                    if not any(vb[i] in arms for i in t):
                        tris.append(W[t])
    tris = np.array(tris)
    a = 0.5 * np.linalg.norm(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1) + 1e-6
    rng = np.random.default_rng(1)
    pick = rng.choice(len(tris), 60000, p=a / a.sum())
    u, v = rng.random(60000), rng.random(60000)
    f = u + v > 1; u[f], v[f] = 1 - u[f], 1 - v[f]
    t = tris[pick]
    pts = t[:, 0] + u[:, None] * (t[:, 1] - t[:, 0]) + v[:, None] * (t[:, 2] - t[:, 0])
    return models, pts, R, T, arms


def extents(P, z):
    s = P[np.abs(P[:, 2] - z) <= WIN]
    if len(s) < 3:
        return None
    return s[:, 0].min(), s[:, 0].max(), s[:, 1].min(), s[:, 1].max()


def main(body, ref, out, zlo=-4.0, zhi=18.0, lowerback=0.0, belly=0.0):
    B, Rf = GoldSrcModel(body), GoldSrcModel(ref)
    bm, bp_, R, T, arms = body_verts(B)
    _, rp, _, _, _ = body_verts(Rf)
    pz = pz0 = T[B.bone_by_name['Bip01 Pelvis']][2]
    zlo, zhi = pz + float(zlo), pz + float(zhi)

    def remap(p):
        z = p[2]
        w = min(1.0, max(0.0, (z - (zlo - FADE)) / FADE), max(0.0, (zhi + FADE - z) / FADE))
        if w <= 0.0:
            return p
        a, b = extents(bp_, z), extents(rp, z)
        if not a or not b:
            return p
        q = p.copy()
        for ax, (lo0, hi0, lo1, hi1) in ((0, (a[0], a[1], b[0], b[1])), (1, (a[2], a[3], b[2], b[3]))):
            if hi0 - lo0 < 0.5:
                continue
            t = (p[ax] - lo0) / (hi0 - lo0)
            dv = float(np.clip((lo1 + t * (hi1 - lo1)) - p[ax], -MAXMOVE, MAXMOVE))
            q[ax] = p[ax] + w * dv
        return q

    d = B.d
    for vinfo, vindex, n in bm:
        for i in range(n):
            b = d[vinfo + i]
            if b in arms:
                continue
            v = np.array(struct.unpack_from('<3f', d, vindex + i * 12))
            p = R[b] @ v + T[b]
            q = remap(p)
            if belly:
                # the front is -y
                z = p[2] - pz0
                wz = max(0.0, 1.0 - abs(z - BE_MID) / BE_HALF)
                sl = bp_[np.abs(bp_[:, 2] - p[2]) <= WIN]
                if wz > 0 and len(sl):
                    cy, ymin = (sl[:, 1].min() + sl[:, 1].max()) / 2, sl[:, 1].min()
                    f = float(np.clip((cy - p[1]) / max(cy - ymin, 0.5), 0.0, 1.0))
                    q[1] -= float(belly) * wz * f
            if lowerback:
                # the rest pose faces -y: the back is +y
                z = p[2] - pz0
                wz = max(0.0, 1.0 - abs(z - LB_MID) / LB_HALF)
                sl = bp_[np.abs(bp_[:, 2] - p[2]) <= WIN]
                if wz > 0 and len(sl):
                    cy, ymax = (sl[:, 1].min() + sl[:, 1].max()) / 2, sl[:, 1].max()
                    f = float(np.clip((p[1] - cy) / max(ymax - cy, 0.5), 0.0, 1.0))
                    q[1] += float(lowerback) * wz * f
            struct.pack_into('<3f', d, vindex + i * 12, *(R[b].T @ (q - T[b])))
    open(out, 'wb').write(d)
    print('wrote', out)


if __name__ == '__main__':
    a = sys.argv[1:]
    opt = {}
    for k in ('--lowerback', '--belly'):
        if k in a:
            i = a.index(k); opt[k[2:]] = float(a[i + 1]); del a[i:i + 2]
    main(*a, **opt)
