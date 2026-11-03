"""Make a battle-damaged copy of an HEV suit model (texture work only).

  python3 -I damage_suit.py <in.mdl> <out.mdl> [strength] [seed] [nowrap]

nowrap: comma-separated texture names that get no bandage (on the HL:S
body PLAYER_Legs1 is the waist, where a wrap comes out stretched).

Every suit texture (PLAYER_*, the HL:S "leg" sheet; not the head, face, glasses
or the chrome) gets, in its own pixel space so it lands the same on every
model that shares the texture:
  grime      dirt worked into the surface (soft noise, darker and browner)
  scorches   burnt patches, black at the heart with a brown edge
  scrapes    short streaks where the orange paint is worn to bare metal
  tears      ragged holes through to the dark under-suit, with a frayed edge
  cracks     branching splits through the orange armour plates
  bandages   dirty, blood-stained gauze wrapped round arms and legs
  blood      dried smears, spatter and runs
strength (default 1) scales how much of each; seed picks the layout.
Atlas textures (128 texels or more on a side: one sheet for the torso or the
legs, as on Source-converted suits) get the effects sized to a 64-texel part,
and their bandages are placed on the mesh instead (WRAPS: a long wrap round
the left upper arm, one round the right thigh). The
texture is requantized to its own 256-colour palette; the mesh is untouched.
The result contains the model's data: keep it local.
"""
import struct
import sys
import zlib

import numpy as np
from PIL import Image

SKIP = ('chrome', 'face', 'sci', 'glasses', 'grim', 'teeth', 'tounge', 'tongue', 'footbtm', 'hand-', 'inmouth')


def is_suit(name):
    n = name.lower()
    if any(s in n for s in SKIP):
        return False
    return n.startswith('player_') or n in ('leg', 'leg.bmp', 'torso')


def fbm(w, h, rng, octaves=4, base=4):
    """smooth value noise 0..1, tiling-agnostic"""
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        n = max(2, base * 2 ** o)
        g = rng.random((n + 1, n + 1)).astype(np.float32)
        img = Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        out += amp * np.asarray(img, np.float32) / 255.0
        tot += amp
        amp *= 0.5
    return out / tot


def blob_mask(w, h, rng, cx, cy, r, rough, aspect=1.0, ang=0.0):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = xx - cx, yy - cy
    u = dx * np.cos(ang) + dy * np.sin(ang)
    v = -dx * np.sin(ang) + dy * np.cos(ang)
    d = np.sqrt((u / aspect) ** 2 + (v * aspect) ** 2) / max(r, 1.0)
    n = fbm(w, h, rng, 3, max(3, int(min(w, h) / (max(r, 1.0) * 1.5))))
    return np.clip(1.0 - d - (n - 0.5) * rough, 0.0, 1.0)


def damage(img, name, strength, seed, nowrap=(), atlas=False):
    h, w, _ = img.shape
    # one texture per body part: effects sized to the texture; an atlas (one
    # sheet for the whole torso or legs, Source-style): sized to a 64-texel part
    U = 64.0 if atlas else min(w, h)
    F = max(1, int(round(min(w, h) / U)))     # noise detail to match
    rng = np.random.default_rng((zlib.crc32(name.lower().encode()) + seed) & 0xffffffff)
    a = img.astype(np.float32)
    area = w * h / 4096.0                      # 64x64 = 1
    s = strength

    # grime: darker, browner in the noise's low spots
    g = fbm(w, h, rng, 4, 3 * F)
    dirt = np.clip((0.62 - g) * 2.2, 0, 1)[..., None] * 0.55 * s
    a = a * (1 - dirt) + np.array([48, 38, 28], np.float32) * dirt
    a *= (0.9 + 0.1 * fbm(w, h, rng, 2, 8 * F))[..., None]

    # scrapes: short streaks of bare grey metal, mostly along one direction
    nscr = int(round(rng.uniform(1.5, 3.5) * area * s))
    ang0 = rng.uniform(0, np.pi)
    for _ in range(nscr):
        x0, y0 = rng.uniform(0, w), rng.uniform(0, h)
        ang = ang0 + rng.normal(0, 0.35)
        ln = rng.uniform(0.08, 0.25) * U
        for t in np.linspace(0, 1, int(ln * 2) + 2):
            x = int(x0 + np.cos(ang) * ln * t) % w
            y = int(y0 + np.sin(ang) * ln * t) % h
            k = 0.4 * (1 - abs(t - 0.5) * 1.6)
            a[y, x] = a[y, x] * (1 - k) + np.array([120, 112, 100], np.float32) * k

    # scorches
    nsc = max(1 if area >= 0.5 else 0, int(round(rng.uniform(0.6, 1.6) * area * s)))
    for _ in range(nsc):
        r = rng.uniform(0.12, 0.28) * U
        m = blob_mask(w, h, rng, rng.uniform(0, w), rng.uniform(0, h), r, 0.9)
        core = np.clip(m * 1.6, 0, 1)[..., None]
        edge = np.clip(m * 2.5, 0, 1)[..., None] - core
        a = a * (1 - core * 0.9) + np.array([14, 11, 9], np.float32) * core * 0.9
        a = a * (1 - edge * 0.5) + np.array([70, 40, 18], np.float32) * edge * 0.5

    # tears: holes to the dark under-suit with a light frayed rim
    ntr = int(round(rng.uniform(0.3, 1.1) * area * s))
    for _ in range(ntr):
        r = rng.uniform(0.05, 0.11) * U
        m = blob_mask(w, h, rng, rng.uniform(0, w), rng.uniform(0, h), r, 2.2,
                      rng.uniform(1.8, 3.5), rng.uniform(0, np.pi))
        hole = (m > 0.4).astype(np.float32)[..., None]
        rim = ((m > 0.3) & (m <= 0.4)).astype(np.float32)[..., None]
        under = np.array([34, 32, 30], np.float32) * (0.8 + 0.4 * fbm(w, h, rng, 2, 6 * F))[..., None]
        a = a * (1 - hole) + under * hole
        a = a * (1 - rim * 0.55) + np.array([95, 55, 25], np.float32) * rim * 0.55

    # cracks: branching splits through the orange armour plates
    orig = img.astype(np.float32)
    armour = np.clip((orig[..., 0] - orig[..., 2] - 60) / 80.0, 0, 1) * np.clip((orig[..., 0] - 90) / 60.0, 0, 1)
    ncr = int(round(rng.uniform(2.0, 4.0) * area * s))
    dark, lit = np.array([22, 15, 10], np.float32), np.array([215, 160, 95], np.float32)

    def crack(x, y, ang, ln, depth):
        steps = int(ln)
        for i in range(steps):
            ang += rng.normal(0, 0.45)
            x += np.cos(ang); y += np.sin(ang)
            xi, yi = int(x) % w, int(y) % h
            k = armour[yi, xi] * (1 - 0.5 * i / max(steps, 1))
            if k <= 0.05:
                continue
            a[yi, xi] = a[yi, xi] * (1 - 0.85 * k) + dark * 0.85 * k
            xo, yo = (xi + 1) % w, (yi + 1) % h		# a chipped light edge beside it
            a[yo, xo] = a[yo, xo] * (1 - 0.25 * k) + lit * 0.25 * k
            if depth < 2 and rng.random() < 0.08:
                crack(x, y, ang + rng.choice([-1, 1]) * rng.uniform(0.5, 1.1), ln * rng.uniform(0.3, 0.6), depth + 1)

    for _ in range(ncr):
        ys, xs = np.nonzero(armour > 0.5)
        if not len(xs):
            break
        j = rng.integers(len(xs))
        crack(float(xs[j]), float(ys[j]), rng.uniform(0, 2 * np.pi), rng.uniform(0.25, 0.6) * U, 0)

    blood = np.array([62, 10, 8], np.float32)

    # bandages: a wrap of dirty gauze round arms and legs, stained through
    lname = name.lower()
    # (not the HL:S 'leg' sheet: its band lands round the waist, stretched)
    limb = not atlas and any(k in lname for k in ('forearm', 'bicep', 'calf', 'legs1')) and lname not in nowrap
    bicep = 'bicep' in lname
    if limb and h >= 24 and ( bicep or rng.random() < 0.7 * min(1.0, s) ):
        # the upper arm gets a long wrap (most of its length), the others a band
        bh = max(5, int(h * ( rng.uniform(0.38, 0.48) if bicep else rng.uniform(0.12, 0.2) )))
        cy = rng.uniform(bh, h - bh) if h > 2 * bh else h / 2
        tilt = rng.uniform(-0.12, 0.12)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        edge_noise = (fbm(w, h, rng, 3, 8 * F) - 0.5) * 3.0
        dist = np.abs(yy - (cy + tilt * (xx - w / 2))) + edge_noise
        band = np.clip((bh / 2 - dist) / 1.5, 0, 1)
        gauze = np.array([196, 186, 160], np.float32) * (0.8 + 0.25 * fbm(w, h, rng, 3, 6 * F))[..., None]
        wraps = 0.85 + 0.15 * np.cos((yy - tilt * xx) * 2.2 + xx * 0.35)[..., None]	# the layers of the wrap
        stain = np.clip((fbm(w, h, rng, 3, 4 * F) - 0.55) * 4, 0, 1)[..., None]
        gauze = gauze * wraps * (1 - stain * 0.6) + blood * 1.6 * stain * 0.6
        dirt2 = np.clip((0.5 - fbm(w, h, rng, 2, 5 * F)) * 2, 0, 1)[..., None] * 0.35
        gauze = gauze * (1 - dirt2) + np.array([90, 75, 55], np.float32) * dirt2
        a = a * (1 - band[..., None]) + gauze * band[..., None]
        # blood soaked through the wrap
        bx = rng.uniform(0.2, 0.8) * w
        m = blob_mask(w, h, rng, bx, cy, bh * 0.6, 1.5, 1.6, 0.0) * band
        b = np.clip(m * 2.0, 0, 1)[..., None] * 0.85
        a = a * (1 - b) + blood * (1.1 + 0.6 * fbm(w, h, rng, 2, 6 * F))[..., None] * b
        # tied ends hanging off one side
        tx = rng.uniform(0.15, 0.85) * w
        tail = np.clip((2.0 - np.abs(xx - tx - (yy - cy) * 0.3)) / 2.0, 0, 1) * ((yy > cy) & (yy < cy + bh * 1.6))
        a = a * (1 - tail[..., None] * 0.9) + gauze * tail[..., None] * 0.9

    # dried blood: smears, spatter and runs
    nbl = int(round(rng.uniform(0.6, 1.6) * area * s)) + ( 1 if area >= 1.0 else 0 )
    for _ in range(nbl):
        cx, cy = rng.uniform(0, w), rng.uniform(0, h)
        r = rng.uniform(0.04, 0.1) * U
        m = blob_mask(w, h, rng, cx, cy, r, 1.8, rng.uniform(1.0, 2.2), rng.uniform(0, np.pi))
        b = np.clip(m * 1.6, 0, 1)[..., None] * 0.8
        tone = blood * (0.7 + 0.5 * fbm(w, h, rng, 2, 6 * F))[..., None]
        a = a * (1 - b) + tone * b
        for _ in range(rng.integers(3, 9)):			# spatter
            sx, sy = int(cx + rng.normal(0, r * 1.6)) % w, int(cy + rng.normal(0, r * 1.6)) % h
            a[sy, sx] = a[sy, sx] * 0.25 + blood * 0.75
        for _ in range(rng.integers(0, 3)):			# runs
            x = int(cx + rng.uniform(-r, r)) % w
            for i in range(int(rng.uniform(0.1, 0.3) * (U if atlas else h))):
                y = int(cy + i) % h
                k = 0.7 * (1 - i / (0.3 * (U if atlas else h)))
                a[y, x] = a[y, x] * (1 - k) + blood * k

    return np.clip(a, 0, 255).astype(np.uint8)


def mesh_wraps(src, k, img, specs, seed):
    """Bandages placed on the mesh, for atlas textures: each spec is
    (bone, start, end), the stretch of that bone's length (0 = its joint,
    1 = the far end of its vertices) that the gauze covers. Every triangle of
    texture k on that bone is painted where it falls in the stretch."""
    sys.path.insert(0, __file__.rsplit('/', 1)[0])
    from merge_head import tris
    names, _, _, tl = tris(src)
    h, w, _ = img.shape
    a = img.astype(np.float32)
    rng = np.random.default_rng(seed + 77)
    blood = np.array([62, 10, 8], np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    for bone, x0, x1 in specs:
        if bone not in names:
            continue
        bi = names.index(bone)
        mine = [t for t in tl if all(b == bi for b in t[4])]
        if not mine:
            continue
        xs = np.concatenate([t[0][:, 0] for t in mine])
        lo, hi = max(0.0, xs.min()), xs.max()
        mine = [t for t in mine if t[3] == k]
        if not mine:
            continue
        # u along the bone at every texel the triangles cover
        along = np.full((h, w), np.nan, np.float32)
        for P, N, st, tex, bones in mine:
            st = np.array(st, np.float32)
            (ax, ay), (bx, by), (cx, cy) = st
            den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(den) < 1e-6:
                continue
            x_lo, x_hi = int(max(0, np.floor(st[:, 0].min()))), int(min(w - 1, np.ceil(st[:, 0].max())))
            y_lo, y_hi = int(max(0, np.floor(st[:, 1].min()))), int(min(h - 1, np.ceil(st[:, 1].max())))
            if x_hi < x_lo or y_hi < y_lo:
                continue
            X, Y = xx[y_lo:y_hi + 1, x_lo:x_hi + 1] + 0.5, yy[y_lo:y_hi + 1, x_lo:x_hi + 1] + 0.5
            l1 = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / den
            l2 = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / den
            l3 = 1 - l1 - l2
            inside = (l1 >= -0.08) & (l2 >= -0.08) & (l3 >= -0.08)
            u = (l1 * P[0, 0] + l2 * P[1, 0] + l3 * P[2, 0] - lo) / max(hi - lo, 1e-3)
            sub = along[y_lo:y_hi + 1, x_lo:x_hi + 1]
            sub[inside] = u[inside]
        ok = ~np.isnan(along)
        u = np.where(ok, along, -9)
        edge = (fbm(w, h, rng, 3, max(4, w // 16)) - 0.5) * 0.06
        band = np.clip(np.minimum(u - x0, x1 - u) / 0.02 + edge / 0.02, 0, 1) * ok
        gauze = np.array([196, 186, 160], np.float32) * (0.8 + 0.25 * fbm(w, h, rng, 3, max(6, w // 10)))[..., None]
        wraps = 0.85 + 0.15 * np.cos(u * (x1 - x0) * 60.0)[..., None]   # the layers of the wrap
        stain = np.clip((fbm(w, h, rng, 3, max(4, w // 16)) - 0.55) * 4, 0, 1)[..., None]
        gauze = gauze * wraps * (1 - stain * 0.6) + blood * 1.6 * stain * 0.6
        dirt2 = np.clip((0.5 - fbm(w, h, rng, 2, max(5, w // 12))) * 2, 0, 1)[..., None] * 0.35
        gauze = gauze * (1 - dirt2) + np.array([90, 75, 55], np.float32) * dirt2
        a = a * (1 - band[..., None]) + gauze * band[..., None]
        # blood soaked through, round the middle of the wrap
        mid = (x0 + x1) / 2
        soak = np.clip(1 - np.abs(u - mid) / ((x1 - x0) * 0.35), 0, 1) * band
        soak *= np.clip((fbm(w, h, rng, 2, max(4, w // 20)) - 0.45) * 3, 0, 1)
        b = np.clip(soak * 1.8, 0, 1)[..., None] * 0.85
        a = a * (1 - b) + blood * (1.1 + 0.6 * fbm(w, h, rng, 2, max(6, w // 10)))[..., None] * b
    return np.clip(a, 0, 255).astype(np.uint8)


# the wraps on atlas models: a long one round the left upper arm, one round the right thigh
WRAPS = (('Bip01 L Arm1', 0.12, 0.88), ('Bip01 R Leg', 0.45, 0.75))


def main(src, dst, strength=1.0, seed=0, nowrap=''):
    strength, seed = float(strength), int(seed)
    nowrap = tuple(n.strip().lower() for n in nowrap.split(',') if n.strip())
    d = bytearray(open(src, 'rb').read())
    ntex, ti = struct.unpack_from('<2i', d, 180)
    done = []
    for k in range(ntex):
        o = ti + k * 80
        name = bytes(d[o:o + 64]).split(b'\0')[0].decode('latin-1')
        flags, w, h, idx = struct.unpack_from('<4i', d, o + 64)
        if not is_suit(name) or flags & 2 or w * h < 64:
            continue
        pix = np.frombuffer(bytes(d[idx:idx + w * h]), np.uint8).reshape(h, w)
        pal = np.frombuffer(bytes(d[idx + w * h:idx + w * h + 768]), np.uint8).reshape(256, 3)
        atlas = min(w, h) >= 128
        out = damage(pal[pix], name.rsplit('.', 1)[0], strength, seed, nowrap, atlas)
        if atlas:
            out = mesh_wraps(src, k, out, WRAPS, seed)
        q = Image.fromarray(out).quantize(colors=256, method=Image.MEDIANCUT, dither=Image.NONE)
        qp = np.zeros(768, np.uint8)
        p = np.array(q.getpalette()[:768], np.uint8)
        qp[:len(p)] = p
        d[idx:idx + w * h] = np.array(q, np.uint8).tobytes()
        d[idx + w * h:idx + w * h + 768] = qp.tobytes()
        done.append(name)
    open(dst, 'wb').write(d)
    print('damaged', len(done), 'textures:', ', '.join(done))


if __name__ == '__main__':
    main(*sys.argv[1:6])
