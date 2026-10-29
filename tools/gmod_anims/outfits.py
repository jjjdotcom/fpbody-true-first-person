"""Build the fpbody outfit models for the expansions.

  python3 -I outfits.py bshift <player.mdl> <hl player.mdl> <hl playerT.mdl> <bshift/models/barney.mdl> <outdir>

Blue Shift:
  fpbody_presuit.mdl  Barney in his guard uniform (original Blue Shift model)
  fpbody_suit.mdl     a blue HEV suit with Barney's head

  python3 -I outfits.py op4 <player.mdl> <hl player.mdl> <hl playerT.mdl> <gearbox/models/player.mdl> <outdir>

Opposing Force:
  fpbody_presuit.mdl  Shephard without the PCV vest (his player model's 2nd body)
  fpbody_suit.mdl     a green HEV suit with Shephard's helmet and gas mask
"""
import os
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from compose import Source, compose, keep_tris, recolour   # noqa: E402

HEV_FACE = {'player_faceside1.bmp', 'player_face1.bmp', 'player_facetop1.bmp', 'player_inmouth1.bmp',
            'player_teeth1.bmp'}


def hev_texture_names(src):
    return [t['name'].decode() for t in src.textures if t['name'].decode().lower() not in HEV_FACE]


def head_bones(src):
    """names of the head bone and everything parented under it"""
    m = src.m
    out = set()
    for i, b in enumerate(m.bones):
        j = i
        while j >= 0:
            if m.bones[j]['name'] == 'Bip01 Head':
                out.add(b['name']); break
            j = m.bones[j]['parent']
    return out


def head_pred(src):
    hb = head_bones(src)
    return lambda names: all(n in hb or n == 'Bip01 Neck' for n in names) and any(n in hb for n in names)


if sys.argv[1] == 'bshift':
    # Barney: the original (SD) Blue Shift model, textures inside the .mdl
    player, hl, hlT, barney, outdir = sys.argv[2:7]
    B = Source(barney)
    B.mode = 'local'
    body = B.model(0, 0)
    print('presuit', compose(player, [('body', [[body]])], os.path.join(outdir, 'fpbody_presuit.mdl'),
                             'fpbody_presuit.mdl'))

    H = Source(hl, hlT)
    H.mode = 'local'
    recolour(H, hev_texture_names(H), hue_to=0.60, sat_scale=1.05)       # blue
    suit = H.model(0, 0)
    B2 = Source(barney)
    B2.mode = 'local'
    head = keep_tris(B2.model(0, 0), head_pred(B2))
    print('suit', compose(player, [('body', [[suit]]), ('head', [[head]])],
                          os.path.join(outdir, 'fpbody_suit.mdl'), 'fpbody_suit.mdl'))

if sys.argv[1] == 'op4':
    player, hl, hlT, shephard, outdir = sys.argv[2:7]
    S = Source(shephard)
    S.mode = 'local'
    body = S.model(0, 1)          # body 1: no PCV vest / backpack
    print('presuit', compose(player, [('body', [[body]])], os.path.join(outdir, 'fpbody_presuit.mdl'),
                             'fpbody_presuit.mdl'))

    H = Source(hl, hlT)
    H.mode = 'local'
    recolour(H, hev_texture_names(H), hue_to=0.33, sat_scale=0.9, val_scale=0.9)   # green
    suit = H.model(0, 0)
    S2 = Source(shephard)
    S2.mode = 'local'
    head = keep_tris(S2.model(0, 0), head_pred(S2))
    print('suit', compose(player, [('body', [[suit]]), ('head', [[head]])],
                          os.path.join(outdir, 'fpbody_suit.mdl'), 'fpbody_suit.mdl'))
