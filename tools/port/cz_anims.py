"""Player animation sets for the Condition Zero animations (fpbody classic models).

  python3 cz_anims.py <sdk folder>

Sets each weapon's player animation extension (the last DefaultDeploy argument,
used as ref_aim_<ext> / ref_shoot_<ext> / crouch_...): the classic player models
carry Condition Zero's mp5, shotgun, onehanded, rifle, m249, knife, grenade and
c4 sets, and "tau" (Half-Life's shotgun hold) for the Tau Cannon. The 9mmAR (an M16 in the HD
weapon models) holds like a rifle; the client plays the Counter-Strike 1.6
rifle set on it (fpbody_anim.cpp). Weapons not listed keep Half-Life's own
animations.
"""
import os
import re
import sys

EXT = {
    'p_357': 'onehanded', 'p_9mmar': 'rifle', 'p_crossbow': 'rifle', 'p_crowbar': 'knife', 'p_grenade': 'grenade',
    'p_squeak': 'grenade', 'p_satchel': 'c4', 'p_tripmine': 'c4', 'p_gauss': 'tau',
    'p_knife': 'knife', 'p_pipe_wrench': 'knife', 'p_saw': 'm249', 'p_m40a1': 'rifle', 'p_penguin': 'grenade',
}
CALL = re.compile(r'(DefaultDeploy\s*\(\s*"models/v_\w+\.mdl"\s*,\s*"models/(p_\w+)\.mdl"\s*,\s*\w+\s*,\s*)"(\w+)"')


def main(sdk):
    changed = 0
    for root, _, files in os.walk(os.path.join(sdk, 'dlls')):
        for f in files:
            if not f.endswith('.cpp'):
                continue
            p = os.path.join(root, f)
            s = open(p, encoding='latin-1', newline='').read()
            s2 = CALL.sub(lambda m: m.group(1) + '"%s"' % EXT.get(m.group(2).lower(), m.group(3)), s)
            if f.lower() == 'satchel.cpp':     # the satchel sets its extension by hand too (radio keeps "hive")
                s2 = re.sub(r'(strcpy\s*\(\s*m_pPlayer->m_szAnimExtention\s*,\s*)"trip"', r'\1"c4"', s2)
            if s2 != s:
                open(p, 'w', encoding='latin-1', newline='').write(s2)
                changed += 1
                print('patched', p)
    return changed


if __name__ == '__main__':
    main(sys.argv[1])
