"""Gargantua reactions (dlls/fpbody_react.inl, player.cpp).

  python3 garg_react.py <sdk dir> [...]          (idempotent)

  - its flames (DMG_BURN) throw you back as an explosion does (fm_blast), not
    a knockdown on every flame tick
  - its stomp (the garg_stomp energy stream) knocks you down (fm_knockdown)
The damage type now reaches FPReact_OnDamage.
"""
import re
import sys


def rd(p):
    s = open(p, encoding='latin-1', newline='').read()
    return s.replace('\r\n', '\n'), ('\r\n' if '\r\n' in s else '\n')


def wr(p, s, nl):
    open(p, 'w', encoding='latin-1', newline='').write(s.replace('\n', nl))


DECL_OLD = 'void FPReact_OnDamage( CBasePlayer *pl, entvars_t *pevInflictor, entvars_t *pevAttacker, float flDamage );'
DECL_NEW = 'void FPReact_OnDamage( CBasePlayer *pl, entvars_t *pevInflictor, entvars_t *pevAttacker, float flDamage, int bitsDamageType );'

for d in sys.argv[1:]:
    p = d + '/dlls/fpbody_react.inl'
    s, nl = rd(p)
    if 'garg_stomp' not in s:
        old = 'void FPReact_OnDamage( CBasePlayer *pl, entvars_t *pevInflictor, entvars_t *pevAttacker, float flDamage )\n'
        assert old in s, p
        s = s.replace(old, old.replace('float flDamage )', 'float flDamage, int bitsDamageType )'), 1)
        old = '\tint kind = FPReact_Kind( pAttacker, pInflictor );\n'
        assert old in s, p
        s = s.replace(old, old +
            '\t// a gargantua: its flames throw us back as an explosion does (not a\n'
            '\t// knockdown on every flame tick); its stomp\'s energy stream knocks us down\n'
            '\tbool stomp = pInflictor && FStrEq( STRING( pInflictor->pev->classname ), "garg_stomp" );\n'
            '\tif ( kind == 2 && ( bitsDamageType & DMG_BURN ) && pAttacker && strstr( STRING( pAttacker->pev->classname ), "garg" ) )\n'
            '\t\tkind = 1;\n'
            '\tif ( stomp )\n'
            '\t\tkind = 2;\n', 1)
        old = '\t\tbool can = pAttacker == pInflictor && s_fpKnockEnd <= 0.0f'
        assert old in s, p
        s = s.replace(old, '\t\tbool can = ( pAttacker == pInflictor || stomp ) && s_fpKnockEnd <= 0.0f', 1)
        s = s.replace('*	Big enemies (every zombie,', '*	A gargantua\'s stomp knocks the player down too, its flames throw him back.\n*\n*	Big enemies (every zombie,', 1)
    wr(p, s, nl)

    p = d + '/dlls/player.cpp'
    s, nl = rd(p)
    if DECL_NEW not in s:
        assert DECL_OLD in s, p
        s = s.replace(DECL_OLD, DECL_NEW, 1)
        if 'damageInfo.damage );' in s and 'FPReact_OnDamage( this, pevInflictor, pevAttacker, damageInfo.damage );' in s:
            s = s.replace('FPReact_OnDamage( this, pevInflictor, pevAttacker, damageInfo.damage );',
                          'FPReact_OnDamage( this, pevInflictor, pevAttacker, damageInfo.damage, damageInfo.type );', 1)
        else:
            old = 'FPReact_OnDamage( this, pevInflictor, pevAttacker, flDamage );'
            assert old in s, p
            s = s.replace(old, 'FPReact_OnDamage( this, pevInflictor, pevAttacker, flDamage, bitsDamageType );', 1)
    wr(p, s, nl)
    print('ok', d)
