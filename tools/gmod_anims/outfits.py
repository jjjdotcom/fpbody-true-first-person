"""Build the fpbody outfit models for the expansions.

  python3 -I outfits.py bshift <player.mdl> <hl player.mdl> <hl playerT.mdl> <barney.mdl> <barneyT.mdl> <outdir>

Blue Shift:
  fpbody_presuit.mdl  Barney in his guard uniform (HD NPC mesh)
  fpbody_suit.mdl     a blue HEV suit with Barney's head
"""
import os
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from compose import Source, compose, keep_tris, recolour   # noqa: E402

HEV_FACE = {'player_faceside1.bmp', 'player_face1.bmp', 'player_facetop1.bmp', 'player_inmouth1.bmp',
            'player_teeth1.bmp'}


def hev_texture_names(src):
    return [t['name'].decode() for t in src.textures if t['name'].decode().lower() not in HEV_FACE]


def head_only(names):
    return all(n in ('Bip01 Head', 'Bip01 Neck') or not n.startswith('Bip01') for n in names) and \
        any(n == 'Bip01 Head' or not n.startswith('Bip01') for n in names)


if sys.argv[1] == 'bshift':
    player, hl, hlT, barney, barneyT, outdir = sys.argv[2:8]
    B = Source(barney, barneyT)
    body = B.model(0, 0)
    print('presuit', compose(player, [('body', [[body]])], os.path.join(outdir, 'fpbody_presuit.mdl'),
                             'fpbody_presuit.mdl'))

    H = Source(hl, hlT)
    recolour(H, hev_texture_names(H), hue_to=0.60, sat_scale=1.05)       # blue
    suit = H.model(0, 0)
    head = keep_tris(Source(barney, barneyT).model(0, 0), head_only)
    print('suit', compose(player, [('body', [[suit]]), ('head', [[head]])],
                          os.path.join(outdir, 'fpbody_suit.mdl'), 'fpbody_suit.mdl'))
