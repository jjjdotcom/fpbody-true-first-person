"""Give a view model the sequence order of another game's model, so that the
other game's weapon code (which plays sequences by number) plays the right
animations on it.

  python3 -I match_seqs.py <source.mdl> <template.mdl> <out.mdl>

Each of the template's sequences takes the source's sequence of the same
label; repeated labels take the source's numbered variants in turn ("shoot"
x3 -> shoot_1, shoot_2, shoot_3), or the same sequence again ("deploy" x2).
A "holster" the source lacks is its "deploy" played backwards. Events stay
with their sequences (none on a reversed one). The result contains the
models' data: keep it local.
"""
import re
import struct
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from goldsrc import GoldSrcModel                          # noqa: E402
from add_cz import existing_sequences, textures_last, clone   # noqa: E402
from compact import compact                              # noqa: E402


def labels(path):
    d = open(path, 'rb').read()
    n, i = struct.unpack_from('<2i', d, 164)
    return [d[i + k * 176:i + k * 176 + 32].split(b'\0')[0].decode('latin-1') for k in range(n)]


def main(src, template, out):
    M = GoldSrcModel(src)
    seqs = existing_sequences(M)
    want = labels(template)
    have = [s['label'].lower() for s in seqs]
    used = {}
    res = []
    for lab in want:
        l = lab.lower()
        k = used.get(l, 0); used[l] = k + 1
        cands = [i for i, h in enumerate(have) if h == l] + \
                [i for i, h in enumerate(have) if re.fullmatch(re.escape(l) + r'_?\d+', h)]
        if cands:
            s = clone(seqs[cands[min(k, len(cands) - 1)]], lab)
            s['activity'] = seqs[cands[min(k, len(cands) - 1)]]['activity']
            raw = bytearray(s['raw']); struct.pack_into('<i', raw, 40, s['activity']); s['raw'] = bytes(raw)
        elif l == 'holster' and 'deploy' in have:
            s = clone(seqs[have.index('deploy')], lab)
            s['frames'] = [f[::-1].copy() for f in s['frames']]
            raw = bytearray(s['raw']); struct.pack_into('<2i', raw, 48, 0, 0); s['raw'] = bytes(raw)
        else:
            sys.exit('%s: no sequence for "%s" (has %s)' % (src, lab, have))
        res.append(s)
    tmp = out + '.tmp'
    M.write(tmp, res)
    textures_last(tmp)
    compact(tmp, out)
    import os
    os.remove(tmp)
    print('wrote', out, [s['label'] for s in res])


if __name__ == '__main__':
    main(*sys.argv[1:4])
