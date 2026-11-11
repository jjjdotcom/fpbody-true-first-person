"""The fpbody companion from a Half-Life Barney replacement model that carries
its own gun: the "Minigunner" of the HEV Barney Automatic Weapons Pack (an HEV
Barney with a minigun; its LD version for most games, the HD version for
Echoes). The model keeps its own skeleton, sequences (its firing stance
standing_mp5_fullauto is Barney's ACT_RANGE_ATTACK1) and minigun - the gun
body part's submodel 1 (drawn), which dlls/fpbody_buddy.inl shows. Made into
one file the game loads as models/fpbody_buddy.mdl:

  python3 -I make_minigun_buddy.py <barney.mdl> <out.mdl>

  - the sequence groups (barney01.mdl ...) and the T file (barneyT.mdl) are
    folded into the one file;
  - the gun body part is moved to body part 1 (fpbody_buddy.inl's
    FPB_GUN_GROUP), the others' body values following.
The result contains the model's data: keep it local.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goldsrc import GoldSrcModel                          # noqa: E402
from add_cz import existing_sequences, textures_last      # noqa: E402
from compact import compact                               # noqa: E402


def fold_textures(path, src_path):
    """copy the T file's textures and skin table into the model at path"""
    d = bytearray(open(path, 'rb').read())
    if struct.unpack_from('<i', d, 180)[0]:
        return 0
    base = src_path[:-4]
    t = next((p for p in (base + 'T.mdl', base + 't.mdl') if os.path.exists(p)), None)
    if t is None:
        sys.exit('no textures in %s and no T file' % src_path)
    td = open(t, 'rb').read()
    ntex, ti = struct.unpack_from('<2i', td, 180)
    nsr, nsf, si = struct.unpack_from('<3i', td, 192)

    def put(b):
        while len(d) % 4:
            d.append(0)
        o = len(d); d.extend(b); return o
    hdr = put(bytes(80 * ntex))
    first = None
    for k in range(ntex):
        o = ti + k * 80
        h = bytearray(td[o:o + 80])
        flags, w, hh, idx = struct.unpack_from('<4i', h, 64)
        off = put(td[idx:idx + w * hh + 768])
        first = off if first is None else first
        struct.pack_into('<i', h, 76, off)
        d[hdr + k * 80:hdr + k * 80 + 80] = h
    skins = put(td[si:si + nsr * nsf * 2])
    struct.pack_into('<3i', d, 180, ntex, hdr, first)
    struct.pack_into('<3i', d, 192, nsr, nsf, skins)
    struct.pack_into('<i', d, 72, len(d))
    open(path, 'wb').write(d)
    return ntex


def gun_part_first(path, name=b'gun'):
    """body parts reordered so 'gun' is body part 1; each part's base (its
    multiplier in pev->body) recomputed"""
    d = bytearray(open(path, 'rb').read())
    nbp, bpi = struct.unpack_from('<2i', d, 204)
    parts = [bytearray(d[bpi + k * 76:bpi + k * 76 + 76]) for k in range(nbp)]
    gi = next((k for k, p in enumerate(parts) if p[:64].split(b'\0')[0] == name), None)
    if gi is None:
        sys.exit('no gun body part')
    if gi != 1:
        parts.insert(1, parts.pop(gi))
    base = 1
    for p in parts:
        struct.pack_into('<i', p, 68, base)
        base *= struct.unpack_from('<i', p, 64)[0]
    for k, p in enumerate(parts):
        d[bpi + k * 76:bpi + k * 76 + 76] = p
    open(path, 'wb').write(d)
    return gi


def main(src, out):
    M = GoldSrcModel(src)
    seqs = existing_sequences(M)
    tmp = out + '.tmp'
    M.write(tmp, seqs)                              # every sequence in the one file
    nt = fold_textures(tmp, src)
    gi = gun_part_first(tmp)
    textures_last(tmp)
    compact(tmp, out)
    os.remove(tmp)
    d = bytearray(open(out, 'rb').read())
    o = 4 + 4 + 64 + 4 + 12 * 5 + 4 + 32            # numseqgroups: just this file
    if struct.unpack_from('<i', d, o)[0] > 1:
        struct.pack_into('<i', d, o, 1)
        open(out, 'wb').write(d)
    print('wrote', out, len(seqs), 'sequences;', 'textures from the T file: %d;' % nt if nt else '',
          'gun body part was %d, now 1' % gi)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
