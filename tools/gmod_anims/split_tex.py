"""Give one bone's triangles their own copy of a shared texture.

  python3 -I split_tex.py <in.mdl> <out.mdl> <texture> <bone> <suffix>

Source-converted suits use one texture for both sides of the body (the left
and right arms share texels), so anything painted on it shows on both. This
copies <texture> as "<texture>#<suffix>" and moves the triangles with two or
more corners on <bone> to the copy; damage_suit.py damages a "#" copy exactly
like the original (same seed) and puts the arm wrap only on the copy, so the
bandage goes round that one arm. The result contains the model's data: keep
it local.
"""
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from merge_head import tris          # noqa: E402
from src2w import write_skinned      # noqa: E402


class _Tex:
    def __init__(self, t):
        self.textures = t


def main(src, dst, tex, bone, suffix):
    names, _, texs, tl = tris(src)
    k = next(i for i, t in enumerate(texs) if t['name'].decode('latin-1').lower().split('.')[0] == tex.lower())
    bi = names.index(bone)
    copy = dict(texs[k]); copy['name'] = (texs[k]['name'].decode('latin-1').split('.')[0] + '#' + suffix).encode('latin-1')
    texs = texs + [copy]
    out, moved = [], 0
    for P, N, st, tx, bones in tl:
        if tx == k and sum(1 for b in bones if b == bi) >= 2:
            tx = len(texs) - 1; moved += 1
        out.append((P, N, st, tx, bones))
    info = write_skinned(src, out, _Tex(texs), dst)
    print('wrote', dst, 'moved', moved, 'triangles to', copy['name'].decode(), info)


if __name__ == '__main__':
    main(*sys.argv[1:6])
