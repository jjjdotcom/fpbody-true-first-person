"""Add Counter-Strike 1.6 weapon animations to an fpbody classic player model,
next to the Condition Zero ones (see add_cz.py).

  python3 -I add_cs.py <cstrike/models/player.mdl> <in.mdl> <out.mdl>

Counter-Strike 1.6's player animations use the same Biped skeleton and 9 pitch
blends as Condition Zero's, so they go through the same retarget. They are
added as cs_<stance>_<part>_<set> (e.g. cs_ref_aim_mp5); the server plays them
instead of the Condition Zero ones when sv_fpbody_anims is "cs", and the client
plays cs_<stance>_reload_<set> when cl_fpbody_reloads is "cs".
"""
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from goldsrc import GoldSrcModel                                              # noqa: E402
from add_cz import PARTS, CZ_SETS, RELOADS, Retarget, cz_seq, existing_sequences, textures_last  # noqa: E402


def main(cs_path, in_path, out_path):
    M = GoldSrcModel(in_path)
    seqs = [s for s in existing_sequences(M) if not s['label'].startswith('cs_')]
    by = {s['label']: s for s in seqs}
    C = GoldSrcModel(cs_path)
    R = Retarget(C, M)
    added = []
    for name, (aim, shoot) in CZ_SETS.items():
        for p in PARTS:
            src = '%s_%s' % (p, aim if 'aim' in p else shoot)
            added.append(cz_seq(C, R, src, 'cs_%s_%s' % (p, name), by['%s_mp5' % p]))
    for name in RELOADS:
        for st in ('ref', 'crouch'):
            src = '%s_reload_%s' % (st, name)
            added.append(cz_seq(C, R, src, 'cs_' + src, by['ref_aim_mp5']))
    seqs += added
    M.write(out_path, seqs)
    textures_last(out_path)
    return len(seqs), len(added)


if __name__ == '__main__':
    print(main(*sys.argv[1:4]))
