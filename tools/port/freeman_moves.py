"""Freeman moves (prone, slide, vault / mantle / pull-up, wall climb, kick,
holster all) for a Half-Life SDK: player movement, server and prediction hooks.

  python3 freeman_moves.py <sdk folder> [<hlsdk folder with the shared files>]

Copies pm_shared/fpbody_pm.h, pm_shared/fpbody_pm_move.h and
dlls/fpbody_moves.inl from this repository and patches:
  pm_shared/pm_shared.c(pp)  include them; FPM_PreDuck / FPM_PostDuck around
                             PM_Duck in PM_PlayerMove; slide friction
  dlls/client.cpp            send fuser1 / fuser4 (the move state) to the client
  dlls/player.cpp            include fpbody_moves.inl; impulses 211 / 212,
                             kick timing, redeploy after holster-all
  dlls/player.h              the members it needs
Idempotent: a file that already has the change is left alone.
"""
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..'))


def edit(path, fn, marker):
    s = open(path, encoding='latin-1', newline='').read()
    if marker in s:
        print('already patched', path)
        return
    nl = '\r\n' if '\r\n' in s else '\n'
    s2 = fn(s.replace('\r\n', '\n')).replace('\n', nl)
    assert s2 != s, path
    open(path, 'w', encoding='latin-1', newline='').write(s2)
    print('patched', path)


def one(s, pat, rep, flags=0):
    s2, n = re.subn(pat, rep, s, count=1, flags=flags)
    assert n == 1, pat
    return s2


def pm_shared(s):
    s = one(s, r'(#include "pm_shared\.h"[^\n]*\n)', r'\1#include "fpbody_pm.h"\t// fpbody: Freeman moves\n')
    s = one(s, r'(\n[ \t]*friction \*= pmove->friction;[^\n]*\n)',
            r'\1\t\tfriction *= FPM_FRICTION_SCALE( pmove );\t// fpbody: sliding\n')
    i = s.index('void PM_PlayerMove')
    # before the comment block above the function, if there is one
    j = s.rfind('/*', 0, i)
    if j < 0 or s.find('*/', j, i) < 0 or s[s.find('*/', j, i):i].strip('*/ \t\n'):
        j = s.rfind('\n', 0, i) + 1
    s = s[:j] + '#include "fpbody_pm_move.h"\t// fpbody: Freeman moves\n\n' + s[j:]
    i = s.index('void PM_PlayerMove')
    k = s.index('PM_UpdateStepSound();', i)
    m = re.compile(r'\n([ \t]*)PM_Duck\(\s*\);[^\n]*\n').search(s, k)
    ind = m.group(1)
    s = s[:m.start()] + ('\n%s// fpbody: prone, slide, vault and wall climb (a vault moves the player itself)\n'
                         '%sif ( FPM_PreDuck( pLadder != NULL ) )\n%s\treturn;\n\n%sPM_Duck();\n%sFPM_PostDuck();\n'
                         % (ind, ind, ind, ind, ind)) + s[m.end():]
    return s


def client_cpp(s):
    # UpdateClientData: the move state, next to the other per-player values
    return one(s, r'(\n([ \t]*)cd->health\s*=\s*pev->health;[^\n]*\n)',
               r'\1\2cd->fuser1 = pev->fuser1;\t// fpbody: Freeman move timer\n'
               r'\2cd->fuser4 = pev->fuser4;\t// fpbody: Freeman move state\n')


def player_h(s):
    return one(s, r'(\n([ \t]*)int[ \t]+m_iFOV;[^\n]*\n)',
               r'\1\2// fpbody: Freeman moves (dlls/fpbody_moves.inl)\n'
               r'\2float m_flFPKickTime;\t\t// when the kick lands (0 = none)\n'
               r'\2float m_flFPNextKick;\n'
               r'\2int m_iFPKickAir;\n'
               r'\2EHANDLE m_hFPHolstered;\t\t// the gun put away with pm_holster\n'
               r'\2void FPMoves_Impulse( int iImpulse );\n'
               r'\2void FPMoves_Think( void );\n'
               r'\2void FPMoves_DoKick( void );\n'
               r'\2void FPMoves_Redeploy( void );\n')


def player_h_epa(s):
    return one(s, r'(\n([ \t]*)void FPMoves_Redeploy\( void \);[^\n]*\n)',
               r'\1\2void FPMoves_Scan( void );\t\t// ExtendedER: fights and hostiles around us\n'
               r'\2float m_flFPScanTime;\n'
               r'\2float m_flFPPanicUntil;\n'
               r'\2float m_flFPHostileUntil;\n')


def player_h_ctx(s):
    return one(s, r'(\n([ \t]*)float m_flFPHostileUntil;[^\n]*\n)',
               r'\1\2void FPMoves_OnUse( CBaseEntity *pObject );\t// Contextual Player Animations\n'
               r'\2float m_flFPUseUntil;\n'
               r'\2float m_flFPNextUse;\n'
               r'\2int m_iFPUseKind;\n')


def player_cpp_ctx(s):
    # PlayerUse: tell the client what is being used, just before the Use
    return one(s, r'\n([ \t]*)(pObject->Use\(\s*this,\s*this,\s*USE_SET,\s*1\s*\);)',
               '\n\\1FPMoves_OnUse( pObject );\t// fpbody: Contextual Player Animations\n\\1\\2')


def player_cpp(s):
    # the implementation lives in its own file, compiled as part of player.cpp
    s = s.rstrip('\n') + '\n\n#include "fpbody_moves.inl"\t// fpbody: Freeman moves (kick, holster all)\n'
    # no gun in the hands (start of the game, holster all): the empty-hands hold
    s = one(s, r'\n([ \t]*)return ent->LookupSequence\( name \);\n\}',
            '\n\\1int seq = ent->LookupSequence( name );\n'
            '\\1size_t n = strlen( name );\n'
            '\\1if ( seq < 0 && n > 0 && name[ n - 1 ] == \'_\' )\t// fpbody: no weapon\n'
            '\\1{\n\\1\tchar alt[ 80 ];\n\\1\tsnprintf( alt, sizeof( alt ), "%sunarmed", name );\n'
            '\\1\tseq = ent->LookupSequence( alt );\n\\1}\n\\1return seq;\n}')
    # impulses: before Half-Life's own handling
    s = one(s, r'(void\s+CBasePlayer\s*::\s*ImpulseCommands\s*\(\s*(?:void)?\s*\)\s*\{[^\n]*\n(?:[^\n]*\n)*?[ \t]*int[ \t]+iImpulse\s*=\s*\(int\)\s*pev->impulse;[^\n]*\n)',
            r'\1\tFPMoves_Impulse( iImpulse );\t// fpbody: kick, holster all\n')
    # every frame, after the weapons ran
    s = one(s, r'(void\s+CBasePlayer\s*::\s*PostThink\s*\(\s*(?:void)?\s*\)\s*\{[^\n]*\n)',
            r'\1\tFPMoves_Think();\t// fpbody: kick, redeploy after holster-all\n')
    return s


def entity_cpp(s):
    return s     # nothing: fuser1 / fuser4 come from the server


def main(sdk, src=REPO):
    for rel in ('pm_shared/fpbody_pm.h', 'pm_shared/fpbody_pm_move.h', 'dlls/fpbody_moves.inl'):
        dst = os.path.join(sdk, rel)
        if os.path.abspath(dst) != os.path.abspath(os.path.join(src, rel)):
            shutil.copyfile(os.path.join(src, rel), dst)
            print('copied', dst)
    pm = os.path.join(sdk, 'pm_shared', 'pm_shared.cpp')
    if not os.path.exists(pm):
        pm = os.path.join(sdk, 'pm_shared', 'pm_shared.c')
    edit(pm, pm_shared, 'fpbody_pm.h')
    edit(os.path.join(sdk, 'dlls', 'client.cpp'), client_cpp, 'Freeman move state')
    edit(os.path.join(sdk, 'dlls', 'player.h'), player_h, 'm_flFPKickTime')
    edit(os.path.join(sdk, 'dlls', 'player.h'), player_h_epa, 'm_flFPPanicUntil')
    edit(os.path.join(sdk, 'dlls', 'player.cpp'), player_cpp, 'fpbody_moves.inl')
    edit(os.path.join(sdk, 'dlls', 'player.h'), player_h_ctx, 'm_flFPUseUntil')
    edit(os.path.join(sdk, 'dlls', 'player.cpp'), player_cpp_ctx, 'FPMoves_OnUse')
    # ExtendedER: the additive gesture layer and the damage types, in the client
    import epa_hooks
    epa_hooks.main(sdk)


if __name__ == '__main__':
    main(*sys.argv[1:3])
