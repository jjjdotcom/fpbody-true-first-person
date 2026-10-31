"""Adds buddha mode to a Half-Life server DLL (original or Updated SDK).

  python3 buddha.py <sdk folder>

'buddha' in the console toggles it ('buddha 1' / 'buddha 0' to set it).
While it is on the player still takes damage, pain and knockback, but
health never drops below 1. Stored in the sv_buddha cvar, so it carries
across level changes. Allowed in single player, or with sv_cheats 1.
"""
import os
import sys


def patch(path, edits):
    s = open(path, encoding='latin-1', newline='').read()
    if 'sv_buddha' in s:
        print('already patched', path)
        return
    nl = '\r\n' if '\r\n' in s else '\n'
    for old, new in edits:
        old = old.replace('\n', nl)
        new = new.replace('\n', nl)
        assert s.count(old) >= 1, (path, old)
        s = s.replace(old, new, 1)
    open(path, 'w', encoding='latin-1', newline='').write(s)
    print('patched', path)


def first_of(path, options):
    s = open(path, encoding='latin-1').read()
    for o in options:
        if o in s:
            return o
    raise SystemExit('anchor not found in ' + path)


def main(sdk):
    d = os.path.join(sdk, 'dlls')

    reg = first_of(os.path.join(d, 'game.cpp'), ['CVAR_REGISTER( &allow_spectators );', 'CVAR_REGISTER(&allow_spectators);'])
    decl = first_of(os.path.join(d, 'game.cpp'), ['cvar_t  allow_spectators', 'cvar_t allow_spectators'])
    patch(os.path.join(d, 'game.cpp'), [
        (decl, 'cvar_t sv_buddha = { "sv_buddha", "0", 0 };	// fpbody: buddha mode\n' + decl),
        (reg, reg + '\n\tCVAR_REGISTER( &sv_buddha );'),
    ])

    gh = first_of(os.path.join(d, 'game.h'), ['extern cvar_t allow_spectators;', '#endif'])
    patch(os.path.join(d, 'game.h'), [
        (gh, 'extern cvar_t sv_buddha;	// fpbody: buddha mode\n' + gh),
    ])

    patch(os.path.join(d, 'player.cpp'), [
        ('\tfTookDamage = CBaseMonster::TakeDamage(pevInflictor, pevAttacker, (int)flDamage, bitsDamageType);',
         '\t// fpbody: buddha mode - take the hit, but never drop below 1 health\n'
         '\tif ( sv_buddha.value != 0 && pev->health - (int)flDamage < 1 )\n'
         '\t{\n'
         '\t\tflDamage = (int)pev->health - 1;\n'
         '\t\tif ( flDamage < 0 )\n'
         '\t\t\tflDamage = 0;\n'
         '\t}\n\n'
         '\tfTookDamage = CBaseMonster::TakeDamage(pevInflictor, pevAttacker, (int)flDamage, bitsDamageType);'),
    ])

    cl = os.path.join(d, 'client.cpp')
    anchor = first_of(cl, ['\telse if ( FStrEq(pcmd, "fullupdate" ) )', '\telse if (FStrEq(pcmd, "fullupdate"))'])
    patch(cl, [
        (anchor,
         '\telse if ( FStrEq( pcmd, "buddha" ) )	// fpbody: buddha mode\n'
         '\t{\n'
         '\t\tif ( gpGlobals->maxClients == 1 || CVAR_GET_FLOAT( "sv_cheats" ) != 0 )\n'
         '\t\t{\n'
         '\t\t\tconst bool on = CMD_ARGC() > 1 ? atoi( CMD_ARGV( 1 ) ) != 0 : sv_buddha.value == 0;\n'
         '\t\t\tCVAR_SET_FLOAT( "sv_buddha", on ? 1 : 0 );\n'
         '\t\t\tClientPrint( pev, HUD_PRINTCONSOLE, on ? "buddha ON\\n" : "buddha OFF\\n" );\n'
         '\t\t}\n'
         '\t\telse\n'
         '\t\t\tClientPrint( pev, HUD_PRINTCONSOLE, "buddha needs sv_cheats 1 in multiplayer\\n" );\n'
         '\t}\n' + anchor),
    ])


if __name__ == '__main__':
    main(sys.argv[1])
