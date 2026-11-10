"""Recolour the orange of an HEV suit in a GoldSrc model's textures.

  python3 -I tint_mdl.py <in.mdl> <out.mdl> <hue> [sat] [--only name,name]

Works on a model with its own textures or on a texture file (<name>T.mdl).
Only the palettes change (8-bit textures): entries that are orange (hue 8-50,
saturated, not dark - the same test as hls_body.py --tint) get the new hue and
their saturation scaled by sat; skin, greys and dark parts stay.

Used for the pickups that replace Barney's helmet and vest (blue, 215) and
Opposing Force's batteries (green, 80 / 0.5): w_suit.mdl + w_suitT.mdl copied
as w_suit_<colour>.mdl + w_suit_<colour>T.mdl. The result contains Valve's
model data: keep it local.
"""
import colorsys
import struct
import sys


def tint_palette(pal, hue, sat):
    out = bytearray(pal)
    for i in range(256):
        r, g, b = pal[i * 3:i * 3 + 3]
        h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        if 8 <= h * 360 <= 50 and s * 255 > 90 and v * 255 > 40:
            nr, ng, nb = colorsys.hsv_to_rgb(hue / 360.0, min(1.0, s * sat), v)
            out[i * 3:i * 3 + 3] = bytes((round(nr * 255), round(ng * 255), round(nb * 255)))
    return bytes(out)


def main(src, dst, hue, sat=1.0, only=None):
    """only: texture names to recolour (default all), e.g. the PS2 hands ("leg") on Decay's Gina"""
    d = bytearray(open(src, 'rb').read())
    ntex, ti = struct.unpack_from('<2i', d, 180)
    for t in range(ntex):
        o = ti + t * 80
        if only and d[o:o + 64].split(b'\0')[0].decode('latin-1') not in only:
            continue
        w, h, idx = struct.unpack_from('<3i', d, o + 68)
        p = idx + w * h
        d[p:p + 768] = tint_palette(bytes(d[p:p + 768]), float(hue), float(sat))
    open(dst, 'wb').write(d)
    return ntex


if __name__ == '__main__':
    a = sys.argv[1:]
    only = None
    if '--only' in a:
        k = a.index('--only'); only = a[k + 1].split(','); del a[k:k + 2]
    print(main(*a[:4], only=only), 'textures tinted')
