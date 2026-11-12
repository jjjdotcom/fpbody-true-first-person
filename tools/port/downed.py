"""Downed and revived (sv_fpbody_down, dlls/fpbody_buddy.inl's last part).

  python3 downed.py <hlsdk> <sdk dir> [...]          (idempotent)

  dlls/fpbody_buddy.inl   copied from <hlsdk> (the same in every SDK)
  dlls/game.cpp           sv_fpbody_down 1
  dlls/player.cpp         TakeDamage asks FPDown_OnDamage first (a killing
                          blow leaves you down instead)
  LinkUserMessages        registers FPDown (player.cpp or UserMessages.cpp)
"""
import os
import re
import shutil
import sys


def rd(p):
    s = open(p, encoding='latin-1', newline='').read()
    return s.replace('\r\n', '\n'), ('\r\n' if '\r\n' in s else '\n')


def wr(p, s, nl):
    open(p, 'w', encoding='latin-1', newline='').write(s.replace('\n', nl))


hl = sys.argv[1]
for d in sys.argv[2:]:
    if os.path.abspath(d) != os.path.abspath(hl):
        shutil.copy(hl + '/dlls/fpbody_buddy.inl', d + '/dlls/fpbody_buddy.inl')

    p = d + '/dlls/game.cpp'
    s, nl = rd(p)
    if 'sv_fpbody_down' not in s:
        s = re.sub(r'(cvar_t sv_fpbody_buddy_solid = [^\n]*\n)', lambda m: m.group(1) +
                   'cvar_t sv_fpbody_down = { "sv_fpbody_down", "1", FCVAR_ARCHIVE };\t// fpbody: a killing blow leaves you (and the companion) down, to be revived\n', s, count=1)
        s = re.sub(r'(\n(\s*)CVAR_REGISTER\( &sv_fpbody_buddy_solid \);\n)', lambda m: m.group(1) + m.group(2) + 'CVAR_REGISTER( &sv_fpbody_down );\n', s, count=1)
        assert s.count('sv_fpbody_down') == 3, p
    wr(p, s, nl)

    p = d + '/dlls/player.cpp'
    s, nl = rd(p)
    if 'FPDown_OnDamage' not in s:
        old = 'void FPReact_Think( CBasePlayer *pl );\n'
        assert old in s, p
        s = s.replace(old, old + 'bool FPDown_OnDamage( CBasePlayer *pl, entvars_t *pevInflictor, entvars_t *pevAttacker, float flDamage, int bitsDamageType );\t// fpbody_buddy.inl\n', 1)
        if 'FPReact_OnDamage( this, pevInflictor, pevAttacker, damageInfo.damage, damageInfo.type );' in s:
            old = 'FPReact_OnDamage( this, pevInflictor, pevAttacker, damageInfo.damage, damageInfo.type );'
            new = old + '\n\tif ( FPDown_OnDamage( this, pevInflictor, pevAttacker, damageInfo.damage, damageInfo.type ) )\n\t\treturn TakeDamageResult();\t// fpbody: down, not dead'
        else:
            old = 'FPReact_OnDamage( this, pevInflictor, pevAttacker, flDamage, bitsDamageType );'
            new = old + '\n\tif ( FPDown_OnDamage( this, pevInflictor, pevAttacker, flDamage, bitsDamageType ) )\n\t\treturn 0;\t// fpbody: down, not dead'
        assert old in s, p
        i = s.index(old)
        j = s.index('\n', i)
        s = s[:i] + new + s[j:]
    wr(p, s, nl)

    for f in ('player.cpp', 'UserMessages.cpp'):
        p = d + '/dlls/' + f
        if not os.path.exists(p):
            continue
        s, nl = rd(p)
        if 'FPDown_LinkMessages' in s:
            break
        m = re.search(r'\n([ \t]*)gmsgFade\s*=\s*REG_USER_MSG\(\s*"ScreenFade"[^\n]*\n', s)
        if not m:
            continue
        s = s[:m.end()] + m.group(1) + 'extern void FPDown_LinkMessages( void ); FPDown_LinkMessages();\t// fpbody: downed / revived (fpbody_buddy.inl)\n' + s[m.end():]
        wr(p, s, nl)
        break
    else:
        sys.exit('LinkUserMessages not found in ' + d)
    print('ok', d)
