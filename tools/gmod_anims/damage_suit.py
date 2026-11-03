"""Make a battle-damaged copy of an HEV suit model (texture work only).

  python3 -I damage_suit.py <in.mdl> <out.mdl> [strength] [seed]

Every suit texture (PLAYER_*, the HL:S "leg" sheet; not the head, face, glasses
or the chrome) gets, in its own pixel space so it lands the same on every
model that shares the texture:
  grime      dirt worked into the surface (soft noise, darker and browner)
  scorches   burnt patches, black at the heart with a brown edge
  scrapes    short streaks where the orange paint is worn to bare metal
  tears      ragged holes through to the dark under-suit, with a frayed edge
  blood      a few dried dark-red smears
strength (default 1) scales how much of each; seed picks the layout. The
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
    n = fbm(w, h, rng, 3, 3)
    return np.clip(1.0 - d - (n - 0.5) * rough, 0.0, 1.0)


def damage(img, name, strength, seed):
    h, w, _ = img.shape
    rng = np.random.default_rng((zlib.crc32(name.lower().encode()) + seed) & 0xffffffff)
    a = img.astype(np.float32)
    area = w * h / 4096.0                      # 64x64 = 1
    s = strength

    # grime: darker, browner in the noise's low spots
    g = fbm(w, h, rng, 4, 3)
    dirt = np.clip((0.62 - g) * 2.2, 0, 1)[..., None] * 0.55 * s
    a = a * (1 - dirt) + np.array([48, 38, 28], np.float32) * dirt
    a *= (0.9 + 0.1 * fbm(w, h, rng, 2, 8))[..., None]

    # scrapes: short streaks of bare grey metal, mostly along one direction
    nscr = int(round(rng.uniform(1.5, 3.5) * area * s))
    ang0 = rng.uniform(0, np.pi)
    for _ in range(nscr):
        x0, y0 = rng.uniform(0, w), rng.uniform(0, h)
        ang = ang0 + rng.normal(0, 0.35)
        ln = rng.uniform(0.08, 0.25) * min(w, h)
        for t in np.linspace(0, 1, int(ln * 2) + 2):
            x = int(x0 + np.cos(ang) * ln * t) % w
            y = int(y0 + np.sin(ang) * ln * t) % h
            k = 0.4 * (1 - abs(t - 0.5) * 1.6)
            a[y, x] = a[y, x] * (1 - k) + np.array([120, 112, 100], np.float32) * k

    # scorches
    nsc = max(1 if area >= 0.5 else 0, int(round(rng.uniform(0.6, 1.6) * area * s)))
    for _ in range(nsc):
        r = rng.uniform(0.12, 0.28) * min(w, h)
        m = blob_mask(w, h, rng, rng.uniform(0, w), rng.uniform(0, h), r, 0.9)
        core = np.clip(m * 1.6, 0, 1)[..., None]
        edge = np.clip(m * 2.5, 0, 1)[..., None] - core
        a = a * (1 - core * 0.9) + np.array([14, 11, 9], np.float32) * core * 0.9
        a = a * (1 - edge * 0.5) + np.array([70, 40, 18], np.float32) * edge * 0.5

    # tears: holes to the dark under-suit with a light frayed rim
    ntr = int(round(rng.uniform(0.3, 1.1) * area * s))
    for _ in range(ntr):
        r = rng.uniform(0.05, 0.11) * min(w, h)
        m = blob_mask(w, h, rng, rng.uniform(0, w), rng.uniform(0, h), r, 2.2,
                      rng.uniform(1.8, 3.5), rng.uniform(0, np.pi))
        hole = (m > 0.4).astype(np.float32)[..., None]
        rim = ((m > 0.3) & (m <= 0.4)).astype(np.float32)[..., None]
        under = np.array([34, 32, 30], np.float32) * (0.8 + 0.4 * fbm(w, h, rng, 2, 6))[..., None]
        a = a * (1 - hole) + under * hole
        a = a * (1 - rim * 0.55) + np.array([95, 55, 25], np.float32) * rim * 0.55

    # blood: a couple of dried smears on the bigger sheets
    if area >= 1.0 and rng.random() < 0.55 * s:
        r = rng.uniform(0.06, 0.12) * min(w, h)
        m = blob_mask(w, h, rng, rng.uniform(0, w), rng.uniform(0, h), r, 1.6)
        b = np.clip(m * 1.4, 0, 1)[..., None] * 0.75
        a = a * (1 - b) + np.array([70, 12, 10], np.float32) * b

    return np.clip(a, 0, 255).astype(np.uint8)


def main(src, dst, strength=1.0, seed=0):
    strength, seed = float(strength), int(seed)
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
        out = damage(pal[pix], name.rsplit('.', 1)[0], strength, seed)
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
    main(*sys.argv[1:5])
