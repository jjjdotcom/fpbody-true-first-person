"""Give a model's textures back from another model with the same textures (by name).

  python3 -I retexture.py <broken.mdl> <source.mdl> <out.mdl>

For upscaled weapon models whose texture data came out blank (Opposing
Force's upscaled displacer: a 512x512 skin that is all one black colour,
with the mesh's texture coordinates scaled 4x from the original's). Every
texture of <broken.mdl> whose name matches one in <source.mdl> (ignoring
case and ".bmp") gets the source's picture, resized smoothly to its own size
and requantized to a 256-colour palette; the mesh and everything else is
kept. The result contains the models' data: keep it local.
"""
import struct
import sys

import numpy as np
from PIL import Image


def key(name):
    n = name.split(b'\0')[0].decode('latin-1').lower()
    return n[:-4] if n.endswith('.bmp') else n


def textures(d):
    ntex, ti = struct.unpack_from('<2i', d, 180)
    out = {}
    for k in range(ntex):
        o = ti + k * 80
        flags, w, h, idx = struct.unpack_from('<4i', d, o + 64)
        out[key(d[o:o + 64])] = (k, flags, w, h, idx)
    return out


def main(broken, source, out):
    d = bytearray(open(broken, 'rb').read())
    s = open(source, 'rb').read()
    src = textures(s)
    for name, (k, flags, w, h, idx) in textures(d).items():
        if name not in src:
            print('no source for', name)
            continue
        _, _, sw, sh, sidx = src[name]
        pix = np.frombuffer(s[sidx:sidx + sw * sh], np.uint8).reshape(sh, sw)
        pal = np.frombuffer(s[sidx + sw * sh:sidx + sw * sh + 768], np.uint8).reshape(256, 3)
        img = Image.fromarray(pal[pix]).resize((w, h), Image.LANCZOS)
        q = img.quantize(colors=256, method=Image.MEDIANCUT, dither=Image.NONE)
        qpal = np.zeros(768, np.uint8)
        p = np.array(q.getpalette()[:768], np.uint8)
        qpal[:len(p)] = p
        d[idx:idx + w * h] = np.array(q, np.uint8).tobytes()
        d[idx + w * h:idx + w * h + 768] = qpal.tobytes()
        print('retextured', name, '%dx%d <- %dx%d' % (w, h, sw, sh))
    open(out, 'wb').write(d)


if __name__ == '__main__':
    main(*sys.argv[1:4])
