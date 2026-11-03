"""Textured software render of a GoldSrc model (front / back / side), for checks.

  python3 -I render_tex.py <model.mdl> <out.png> [seq[:frame]] [size]
"""
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from goldsrc import GoldSrcModel   # noqa: E402


def load(path):
    M = GoldSrcModel(path)
    d = bytes(M.d)
    ntex, ti = struct.unpack_from('<2i', d, 180)
    nsr, nsf, si = struct.unpack_from('<3i', d, 192)
    skins = struct.unpack_from('<%dh' % nsr, d, si)
    tex = []
    for t in range(ntex):
        o = ti + t * 80
        flags, w, h, idx = struct.unpack_from('<4i', d, o + 64)
        pix = np.frombuffer(d[idx:idx + w * h], np.uint8).reshape(h, w)
        pal = np.frombuffer(d[idx + w * h:idx + w * h + 768], np.uint8).reshape(256, 3)
        tex.append((pal[pix].astype(np.float32), flags))
    tris = []
    nbp, bpi = struct.unpack_from('<2i', d, 204)
    for bp in range(nbp):
        nm, _, mi = struct.unpack_from('<3i', d, bpi + bp * 76 + 64)
        nummesh, meshindex, numverts, vinfo, vindex = struct.unpack_from('<5i', d, mi + 72)
        vb = np.frombuffer(d[vinfo:vinfo + numverts], np.uint8)
        vv = np.frombuffer(d[vindex:vindex + numverts * 12], '<f4').reshape(-1, 3).astype(float)
        for m in range(nummesh):
            numtris, triindex, skinref, _, _ = struct.unpack_from('<5i', d, meshindex + m * 20)
            t = skins[skinref]
            o = triindex
            while True:
                c = struct.unpack_from('<h', d, o)[0]; o += 2
                if c == 0:
                    break
                fan = c < 0; c = abs(c)
                vs = [struct.unpack_from('<4h', d, o + k * 8) for k in range(c)]; o += c * 8
                for k in range(2, c):
                    if fan:
                        a, b, e = vs[0], vs[k - 1], vs[k]
                    elif k % 2:
                        a, b, e = vs[k - 1], vs[k - 2], vs[k]
                    else:
                        a, b, e = vs[k - 2], vs[k - 1], vs[k]
                    tris.append(([vb[a[0]], vb[b[0]], vb[e[0]]], [vv[a[0]], vv[b[0]], vv[e[0]]],
                                 [(a[2], a[3]), (b[2], b[3]), (e[2], e[3])], t))
    return M, tex, tris


def render(M, tex, tris, R, T, vdir, size=(420, 640), span=(-24, 24, -40, 36)):
    W, H = size
    img = np.full((H, W, 3), 235, np.float32)
    zb = np.full((H, W), -1e9, np.float32)
    vdir = np.array(vdir, float)
    right = np.cross(vdir, [0, 0, 1]); right /= np.linalg.norm(right)
    up = np.array([0, 0, 1.0])
    x0, x1, y0, y1 = span
    for bones, verts, uvs, t in tris:
        P = np.array([R[bones[i]] @ verts[i] + T[bones[i]] for i in range(3)])
        n = np.cross(P[1] - P[0], P[2] - P[0])
        nl = np.linalg.norm(n)
        if nl < 1e-9:
            continue
        shade = 0.35 + 0.65 * abs(np.dot(n / nl, vdir))
        sx = (P @ right - x0) / (x1 - x0) * W
        sy = (1 - (P @ up - y0) / (y1 - y0)) * H
        z = -(P @ vdir)
        minx, maxx = int(max(0, np.floor(sx.min()))), int(min(W - 1, np.ceil(sx.max())))
        miny, maxy = int(max(0, np.floor(sy.min()))), int(min(H - 1, np.ceil(sy.max())))
        if minx > maxx or miny > maxy:
            continue
        yy, xx = np.mgrid[miny:maxy + 1, minx:maxx + 1].astype(np.float32) + 0.5
        d = (sy[1] - sy[2]) * (sx[0] - sx[2]) + (sx[2] - sx[1]) * (sy[0] - sy[2])
        if abs(d) < 1e-9:
            continue
        l0 = ((sy[1] - sy[2]) * (xx - sx[2]) + (sx[2] - sx[1]) * (yy - sy[2])) / d
        l1 = ((sy[2] - sy[0]) * (xx - sx[2]) + (sx[0] - sx[2]) * (yy - sy[2])) / d
        l2 = 1 - l0 - l1
        inside = (l0 >= -1e-4) & (l1 >= -1e-4) & (l2 >= -1e-4)
        if not inside.any():
            continue
        zz = l0 * z[0] + l1 * z[1] + l2 * z[2]
        sub = zb[miny:maxy + 1, minx:maxx + 1]
        ok = inside & (zz > sub)
        if not ok.any():
            continue
        timg = tex[t][0]
        th, tw = timg.shape[:2]
        u = l0 * uvs[0][0] + l1 * uvs[1][0] + l2 * uvs[2][0]
        v = l0 * uvs[0][1] + l1 * uvs[1][1] + l2 * uvs[2][1]
        col = timg[np.clip(v.astype(int), 0, th - 1), np.clip(u.astype(int), 0, tw - 1)] * shade
        sub[ok] = zz[ok]
        img[miny:maxy + 1, minx:maxx + 1][ok] = col[ok]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def main(path, out, spec='look_idle:0', scale=1.0):
    M, tex, tris = load(path)
    seq, fr = (spec.split(':') + ['0'])[:2]
    R, T = M.world(M.decode(M.seq_by_name[seq])[0][int(fr)])
    s = float(scale)
    views = [render(M, tex, tris, R, T, v, (int(420 * s), int(640 * s))) for v in ([1, 0, 0], [-1, 0, 0], [0, -1, 0])]
    W = sum(v.width for v in views)
    sheet = Image.new('RGB', (W, views[0].height), (235, 235, 235))
    x = 0
    for v in views:
        sheet.paste(v, (x, 0)); x += v.width
    sheet.save(out)


if __name__ == '__main__':
    main(*sys.argv[1:5])
